# FUNC-006: Cross-Encoder 기반 재정렬 모듈

from src.models.schemas import RetrievedChunk, RerankingResult
from src.models.state import GraphState
from src.utils.config import RERANK_THRESHOLD
from src.utils.exception import AccountingRAGError, RerankFailureError, ScoreThresholdError
from src.utils.logger import get_logger

logger = get_logger(__name__)


def rerank_chunks(state: GraphState) -> dict:
    """
    워크플로우 노드: retrieved_chunks를 재정렬하고 임계치 필터링을 수행한다.

    동작:
        - rerank() 헬퍼 호출 → 내림차순 정렬된 RerankingResult 리스트 수신
        - 결과가 비었거나 최고 점수가 RERANK_THRESHOLD 미만이면 ScoreThresholdError
        - AccountingRAGError 계열(ScoreThresholdError, RerankFailureError 등)은
          error_logs에 누적 기록 후 reranked_chunks 갱신 없이 반환
          → 후속 evaluate/generate 노드가 빈 컨텍스트 폴백 경로로 처리
    """
    logger.info(
        f"재정렬 수행: {len(state.retrieved_chunks)}개 청크, "
        f"질의: {state.original_query[:50]}..."
    )

    # TODO: search 노드 구현 후 search-rerank 간 관계 재정의 후에 처리 방식을 명확하게 결정해야 함
    # 현재는 retrieved_chunks가 비어있을 때 조기 반환하여 ScoreThresholdError를 발생시키지 않는다.
    # 이는 search 노드 실패(빈 결과)와 리랭킹 자체 실패를 구분하기 위함이다.
    # search 노드가 구현되면 빈 retrieved_chunks의 원인(정상적 검색 결과 없음 vs 노드 오류)에 따라
    # rerank_chunks의 대응 방식(조기 반환 vs ScoreThresholdError)을 결정해야 한다.
    if not state.retrieved_chunks:
        return {"reranked_chunks": []}

    try:
        results = rerank(state.original_query, state.retrieved_chunks)

        if not results:
            logger.warning("재정렬 후 유효한 청크가 없습니다.")
            raise ScoreThresholdError("재정렬 후 유효한 청크가 없습니다.")

        # rerank()가 내림차순 정렬을 보장하므로 0번째가 최고 점수
        max_score = results[0].rerank_score
        if max_score < RERANK_THRESHOLD:
            logger.warning(
                f"재정렬 점수 임계값 미달: 최고점={max_score}, "
                f"임계값={RERANK_THRESHOLD}"
            )
            raise ScoreThresholdError(
                f"최고 관련도({max_score})가 임계값({RERANK_THRESHOLD})에 미달합니다."
            )

        logger.info(f"재정렬 완료: {len(results)}개 청크 반환")
        return {"reranked_chunks": results, "needs_reretrieval": False}

    except AccountingRAGError as e:
        new_logs = state.error_logs + [e.to_error_log()]
        if isinstance(e, RerankFailureError):
            # 모델 실패 → 1차 검색 결과 순서 유지하여 fallback 반환, 재검색 신호 없음
            fallback = [
                RerankingResult(chunk=c, rerank_score=c.score)
                for c in state.retrieved_chunks
            ]
            return {
                "reranked_chunks": fallback,
                "needs_reretrieval": False,
                "error_logs": new_logs,
            }
        # ScoreThresholdError 등: 점수 임계치 미달 → 재검색 신호
        return {
            "reranked_chunks": [],
            "needs_reretrieval": True,
            "error_logs": new_logs,
        }
    except Exception as e:
        # 시스템 예외는 AccountingRAGError로 래핑하지 않고 원본 타입 그대로 전파한다.
        # rerank_chunks() 노드의 except Exception 블록에서 logger.critical 기록 후 파이프라인 중단
        logger.critical(f"[{type(e).__name__}] rerank_chunks 노드 치명적 오류: {e}", exc_info=True)
        raise


def rerank(original_query: str, chunks: list[RetrievedChunk]) -> list[RerankingResult]:
    """
    Cross-Encoder로 질의-문서 쌍의 관련도를 재산출하여 정렬한다.
    유틸리티 수준에서는 threshold 기반 필터링을 수행하지 않는다.
    
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
        # TODO: 단일 청크인 경우에도 리랭커 모델을 호출하여 실제 score를 할당하도록 변경 필요
        # 현재는 비교 대상이 없으므로 최상위 점수(1.0)를 부여하여 반환함
        return [RerankingResult(chunk=chunks[0], rerank_score=1.0)]

    try:
        # TODO: 실제 Reranker 알고리즘 도입하여 점수 계산
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
    # 모델마다 로짓의 분포가 다릅니다. 어떤 모델은 관련이 없어도 0.3을 내뱉고, 어떤 모델은 0.01을 내뱉음
    # 따라서 회계 기준서와 전혀 상관없는 질문을 테스트하며, RERANK_THRESHOLD의 적정값을 튜닝하는 과정이 반드시 필요
    # Pseudo:
    # input_pair = f"[CLS] {query} [SEP] {content} [SEP]"
    # logit      = cross_encoder_model.predict(input_pair)   # 단일 스칼라
    # return sigmoid(logit)   # [0, 1] 범위로 변환
    
    # TODO: 실제 Reranker 통합 전까지는 Retriever의 초기 성능 테스트를 위해 모든 청크에 1.0 반환
    return 1.0