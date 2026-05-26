# FUNC-006: Cross-Encoder 기반 재정렬 모듈
import math

from src.models.schemas import RetrievedChunk, RerankingResult
from src.utils.config import RERANK_MODEL
from src.utils.exception import RerankFailureError
from src.utils.logger import get_logger

logger = get_logger(__name__)

try:
    from sentence_transformers import CrossEncoder as _CrossEncoder
    _cross_encoder = _CrossEncoder(RERANK_MODEL)
    logger.info(f"Cross-Encoder 모델 로드 완료: {RERANK_MODEL}")
except Exception as e:
    _load_error = e
    logger.warning(f"Cross-Encoder 모델 로드 실패 — compute_relevance_score 호출 시 RerankFailureError 발생: {e}")


def rerank(original_query: str, chunks: list[RetrievedChunk]) -> list[RerankingResult]:
    """
    Cross-Encoder로 질의-문서 쌍의 관련도를 재산출하여 정렬한다.
    유틸리티 수준에서는 threshold 기반 필터링을 수행하지 않는다.
    rerank_chunks 노드애서 USE_RERANKER를 사전 확인한 뒤 호출한다.

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
        scored_results = []
        for chunk in chunks:
            score = compute_relevance_score(original_query, chunk.content)
            scored_results.append(RerankingResult(chunk=chunk, rerank_score=score))

        # 점수 내림차순 정렬
        # TODO: Threshold 기반 필터링 추가 필요
        scored_results.sort(key=lambda x: x.rerank_score, reverse=True)
        
        # RerankingResult 반환
        return scored_results

    except RerankFailureError:
        # 상위 노드에서는 RerankFailureError: 리랭킹 과정 중 예상치 못한 오류 발생 : {오류 내용}으로 표시
        raise
    except Exception as e:
        # 만약 재시도 후에도 실패하여 Fallback 처리가 필요하다면 호출부에서 담당한다.
        # 시스템 예외는 AccountingRAGError로 래핑하지 않고 원본 타입 그대로 전파한다.
        # rerank_chunks() 노드의 except Exception 블록에서 logger.critical 기록 후 파이프라인 중단
        logger.error(f"[{type(e).__name__}] 리랭킹 모델 호출 중 시스템 에러: {e}", exc_info=True)
        raise


def compute_relevance_score(query: str, content: str) -> float:
    """단일 질의-문서 쌍의 Cross-Encoder 관련도 점수를 반환한다."""
    if _cross_encoder is None:
        raise RerankFailureError(f"Cross-Encoder 모델 로드 실패: {_load_error}")
    score = _cross_encoder.predict([(query, content)])[0]
    return 1 / (1 + math.exp(-score))    # 로지스틱 함수로 변환
