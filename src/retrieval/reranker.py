# rerank: Cross-Encoder 기반 재정렬 모듈
import math

from src.models.schemas import RetrievedChunk, RerankingResult
from src.utils.config import RERANK_MAX_LENGTH, RERANK_MODEL
from src.utils.exception import RerankFailureError
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 모델 로드 실패 시에도 모듈 임포트가 NameError 없이 진행되도록 기본값을 선언한다.
# (선언이 없으면 로드 실패 시 compute_relevance_scores의 None 체크가 NameError로 터진다)
#
# [지연 로딩] 모델은 import 시점이 아니라 compute_relevance_scores 최초 호출 시 1회만 로드한다.
# USE_RERANKER=false(기본값)이면 rerank 노드가 compute_relevance_scores를 호출하지 않으므로
# 모델(~수백 MB)을 받지 않는다 → 앱/워크플로 import 시 불필요한 다운로드·메모리·로드 로그를 제거한다.
_cross_encoder = None
_load_error = None
_load_attempted = False


def _ensure_model_loaded() -> None:
    """Cross-Encoder 모델을 지연 로딩한다(프로세스당 1회 시도).

    _cross_encoder 또는 _load_error 중 하나라도 이미 설정돼 있으면(성공/실패 확정,
    또는 테스트가 직접 주입한 경우) 재시도하지 않고 즉시 반환한다.
    """
    global _cross_encoder, _load_error, _load_attempted
    if _cross_encoder is not None or _load_error is not None or _load_attempted:
        return
    _load_attempted = True
    try:
        from sentence_transformers import CrossEncoder
        _cross_encoder = CrossEncoder(RERANK_MODEL, max_length=RERANK_MAX_LENGTH)
        logger.info(f"Cross-Encoder 모델 로드 완료: {RERANK_MODEL}")
    except Exception as e:
        _load_error = e
        logger.warning(f"Cross-Encoder 모델 로드 실패 — compute_relevance_scores 호출 시 RerankFailureError 발생: {e}")


def warmup_reranker() -> None:
    """
    리랭커 모델을 기동 시 미리 로드해, 첫 질의의 콜드 로드를 요청 처리 경로 밖으로 분리한다.

    rerank 노드는 그래프 러너의 step_timeout(노드당 30초) 안에서 돈다.
    bge-reranker-v2-m3(~2.2GB)를 첫 질의 때 지연 로딩하면 최초 다운로드가 30초를 넘겨 타임아웃에 걸리고, 사용자는 답변 대신 폴백을 받는다.
    기동 시 미리 데우면 이 콜드 로드가 요청 밖에서 끝난다.

    USE_RERANKER가 꺼져 있으면 아무 것도 하지 않는다 — 리랭커를 안 쓰므로 로드도 불필요하다.
    로드가 실패해도 _ensure_model_loaded가 예외를 흡수하므로 이 함수는 조용히 끝나고, 첫 질의가 lazy 로드로 폴백한다.
    """
    from src.utils import config
    if not config.USE_RERANKER:
        return
    _ensure_model_loaded()


def rerank_chunks(original_query: str, chunks: list[RetrievedChunk]) -> list[RerankingResult]:
    """
    Cross-Encoder로 질의-문서 쌍의 관련도를 재산출하여 정렬한다.
    유틸리티 수준에서는 threshold 기반 필터링을 수행하지 않는다.
    rerank 노드에서 USE_RERANKER를 사전 확인한 뒤 호출한다.

    Args:
        original_query: 사용자 원문 또는 재작성된 쿼리
        chunks: 검색 엔진에서 반환된 후보 청크 리스트

    Returns:
        재정렬된 RerankingResult 리스트
    """
    # 빈 리스트 입력 시
    if not chunks:
        return []

    # 단일 청크 입력 시
    if len(chunks) == 1:
        # 현재는 비교 대상이 없으므로 최상위 점수(1.0)를 부여하여 반환함
        return [RerankingResult(chunk=chunks[0], rerank_score=1.0)]

    try:
        # 청크별 개별 호출 대신 쌍 리스트를 한 번에 추론하여 forward pass를 1회로 줄인다.
        scores = compute_relevance_scores(original_query, [chunk.content for chunk in chunks])
        scored_results = [
            RerankingResult(chunk=chunk, rerank_score=score)
            for chunk, score in zip(chunks, scores)
        ]

        # 점수 내림차순 정렬
        # Threshold 기반 필터링은 이 유틸리티가 아닌 호출자(rerank 노드)의 책임이다(바로 위 독스트링 참고).
        scored_results.sort(key=lambda x: x.rerank_score, reverse=True)
        
        # RerankingResult 반환
        return scored_results

    except RerankFailureError:
        # 상위 노드(rerank())는 이 예외를 잡아 1차 검색 결과로 조용히 폴백하고, error_logs에 오류 내역을 기록한다.
        # 재검색을 유발하지는 않는다.
        raise
    except Exception as e:
        # 만약 재시도 후에도 실패하여 Fallback 처리가 필요하다면 호출부에서 담당한다.
        # 시스템 예외는 AccountingRAGError로 래핑하지 않고 원본 타입 그대로 전파한다.
        # 이 함수는 error 레벨로만 기록하고 그대로 재전파한다.
        # 상위 rerank() 노드가 이 예외를 다시 잡아 critical로 기록하고 파이프라인을 중단한다.
        logger.error(f"[{type(e).__name__}] 리랭킹 모델 호출 중 시스템 에러: {e}", exc_info=True)
        raise


def compute_relevance_scores(query: str, contents: list[str]) -> list[float]:
    """질의-문서 쌍 리스트의 Cross-Encoder 관련도 점수를 배치로 반환한다.

    CrossEncoder.predict()는 쌍 리스트를 한 번의 forward pass로 처리하므로
    청크 수와 무관하게 모델 추론을 1회만 수행한다.
    """
    _ensure_model_loaded()
    if _cross_encoder is None:
        raise RerankFailureError(f"Cross-Encoder 모델 로드 실패: {_load_error}")
    pairs = [(query, content) for content in contents]
    raw_scores = _cross_encoder.predict(pairs)  # type: ignore  # forward pass 1회, numpy.ndarray 반환
    return [1 / (1 + math.exp(-float(score))) for score in raw_scores]    # 로지스틱 함수로 변환
