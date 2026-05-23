# FUNC-009: LangGraph StateGraph 파이프라인 정의

from datetime import datetime
from functools import wraps
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from src.agent.nodes.generate import generate_response
from src.agent.nodes.evaluate import evaluate_context
from src.retrieval.reranker import rerank
from src.utils import config
from src.utils.config import MAX_REWRITE_COUNT, KST, RERANK_THRESHOLD
from src.utils.exception import AccountingRAGError, RerankFailureError, ScoreThresholdError
from src.utils.logger import get_logger
from src.models.state import GraphState
from src.models.schemas import (
    RetrievedChunk, FinalResponse, EvaluationResult,
    Citation, RerankingResult
)

logger = get_logger(__name__)


def handle_node_errors(node_name: str):
    """
    각 노드에서 발생하는 예외를 캐치하여 state.error_logs에 기록하고,
    워크플로우가 중단되지 않도록 상태를 반환하는 데코레이터입니다.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(state: GraphState) -> dict:
            try:
                return func(state)
            except AccountingRAGError as e:
                # 커스텀 예외 처리(Exception.py에서 정의)
                new_logs = state.error_logs + [e.to_error_log()]
                return {"error_logs": new_logs}
            except Exception as e:
                # 예상치 못한 예외 처리
                error_log = {
                    # src.utils.config에 정의된 KST(+09:00) 타임존을 사용하여 ISO 8601 형식으로 변환
                    "timestamp": datetime.now(KST).isoformat(),
                    "node": node_name,
                    "error_type": "UNKNOWN",
                    "message": str(e)
                }
                new_logs = state.error_logs + [error_log]
                return {"error_logs": new_logs}
        return wrapper
    return decorator

@handle_node_errors("rewrite")
def rewrite_query(state: GraphState) -> dict:
    """
    TODO: FUNC-004 (질의 재작성 노드) - Mock 구현
    실제 구현 대기 (src/agent/nodes/rewrite.py)

    [반환 패턴 설명]
    LangGraph는 노드가 반환한 dict의 키를 State의 필드명과 매칭하여 해당 필드만 증분 업데이트합니다.
    따라서 GraphState 전체를 반환할 필요 없이, 이 노드가 업데이트할 필드(여기서는 rewrite_count)만 반환하면 됩니다.
    """
    return {"rewrite_count": state.rewrite_count + 1}

@handle_node_errors("search")
def hybrid_search(state: GraphState) -> dict:
    """
    TODO: FUNC-005 (하이브리드 검색 노드) - Mock 구현
    실제 구현 대기 (src/retrieval/searcher.py)
    """
    return {
        "retrieved_chunks": [
            RetrievedChunk(
                chunk_id="1",
                document_id="DOC-001",
                content="유형자산의 감가상각은...",
                score=0.9,
                metadata={}
            ),
            RetrievedChunk(
                chunk_id="2",
                document_id="DOC-002",
                content="전환사채를 투자목적으로...",
                score=0.8,
                metadata={}
            ),
        ]
    }


def rerank_chunks(state: GraphState) -> dict:
    """
    워크플로우 노드: USE_RERANKER 활성화 여부에 따라 재정렬 모델 호출 여부를 결정한다.

    동작:
        - USE_RERANKER=false: 모델 호출 없이 retrieved_chunks를 score=1.0으로 래핑하여 반환
        - USE_RERANKER=true: rerank() 유틸리티 호출 → 임계값 필터링 → 예외 처리
          - ScoreThresholdError: needs_reretrieval=True + reranked_chunks=[]
          - RerankFailureError: needs_reretrieval=False + fallback(1차 검색 결과 순서 유지)
    """
    # 활성화 여부 확인 (조기 반환 - 모델 호출 없음)
    if not config.USE_RERANKER:
        logger.info("USE_RERANKER=false: 모델 호출 스킵, 1차 검색 결과 반환")
        fallback = [RerankingResult(chunk=c, rerank_score=1.0)
                    for c in state.retrieved_chunks]
        return {
            "reranked_chunks": fallback,
            "needs_reretrieval": False,
            "error_logs": state.error_logs,
        }

    logger.info(
        f"재정렬 수행: {len(state.retrieved_chunks)}개 청크, "
        f"질의: {state.original_query[:50]}..."
    )

    # TODO: search 노드 구현 후 search-rerank 간 관계 재정의 후에 처리 방식을 명확하게 결정해야 함
    # 현재는 retrieved_chunks가 비어있을 때 조기 반환하여 ScoreThresholdError를 발생시키지 않는다.
    # 이는 search 노드 실패(빈 결과)와 리랭킹 자체 실패를 구분하기 위함이다.
    if not state.retrieved_chunks:
        return {"reranked_chunks": []}

    # rerank() 유틸리티 함수 호출 (실제 모델 추론)
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
        logger.critical(f"[{type(e).__name__}] rerank_chunks 노드 치명적 오류: {e}", exc_info=True)
        raise


def route_after_evaluate(state: GraphState) -> str:
    """
    TODO: FUNC-009 (평가 후 라우팅 결정)
    평가 결과 또는 에러 상태에 따라 다음 노드를 결정한다.

    [IF문 우선순위]
    1순위: needs_reretrieval (어느 노드에서든 재검색이 확정된 상태)
    2순위: evaluate 노드 자체 에러 안전장치 (무한 루프 방지)
    3순위: evaluation.needs_external 기반 CRAG 루프

    needs_reretrieval을 최상단에 두는 이유:
    rerank가 reranked_chunks=[]를 evaluate에 넘기면 evaluate가 자체 실패할 가능성이 높아
    error_logs[-1]["node"] == "evaluate" 조건이 먼저 트리거되고, 결과적으로 needs_reretrieval=True 신호가
    무시된 채 잘못된 답변 생성으로 직행하는 버그가 발생한다.
    """
    # 1순위: 어느 노드에서든 재검색이 확정된 상태라면, 다른 안전장치보다 먼저 rewrite를 고려한다.
    if state.needs_reretrieval and state.rewrite_count < MAX_REWRITE_COUNT:
        return "rewrite"

    # 2순위: evaluate 노드 자체에서 에러가 발생했다면, 무한 루프 방지를 위해 강제로 generate로 우회한다.
    if state.error_logs and state.error_logs[-1]["node"] == "evaluate":
        return "generate"

    # 3순위: CRAG (Corrective RAG) 루프 진입 조건 판단
    # 아래 3가지 조건이 모두 만족될 때만 rewrite 노드로 돌아가서 쿼리 재작성 및 검색을 다시 시도합니다.
    #   (1) state.evaluation 존재: 정상적으로 평가 결과 객체가 반환되었는가?
    #   (2) needs_external == True: LLM이 기존 컨텍스트만으로는 부족하여 외부 정보가 더 필요하다고 판단했는가?
    #   (3) rewrite_count < MAX_REWRITE_COUNT: 무한 루프를 막기 위한 최대 재시도 횟수 제한(예: 3회)을 넘지 않았는가?
    if (state.evaluation and
        state.evaluation.needs_external and
        state.rewrite_count < MAX_REWRITE_COUNT):
        return "rewrite"

    # 답변 생성 단계로 진행
    # 검색된 컨텍스트가 충분히 유효하거나(needs_external=False), 이미 최대 재시도 횟수를 소진했다면 답변을 생성합니다.
    return "generate"

def build_workflow() -> CompiledStateGraph:
    """
    LangGraph StateGraph를 구성하고 컴파일하여 반환합니다.

    노드 등록 및 조건부 엣지를 정의하여 StateGraph를 반환한다.
    실행 순서: rewrite_query → hybrid_search → rerank → evaluate_context → generate_response
    evaluate_context 이후 route_after_evaluate로 분기 처리.

    return CompiledStateGraph : LangGraph로 빌드된 상태 그래프
    왜 CompiledGraph를 사용하는가? -> StateGraph보다 성능이 좋다. (동작 방식은 동일하지만 내부적으로 최적화됨)
    동작 방식이 어떠한데? -> LangGraph의 build_workflow를 통해 StateGraph를 컴파일하면 CompiledStateGraph 객체가 반환된다.
    이 객체는 내부적으로 최적화되어 StateGraph보다 빠른 실행 속도를 제공한다. 
    """
    workflow = StateGraph(GraphState)

    # 노드 추가
    workflow.add_node("rewrite", rewrite_query)
    workflow.add_node("search", hybrid_search)
    workflow.add_node("rerank", rerank_chunks)
    workflow.add_node("evaluate", evaluate_context)
    workflow.add_node("generate", generate_response)

    # 엣지 연결 (고정 흐름)
    workflow.add_edge(START, "rewrite")
    workflow.add_edge("rewrite", "search")
    workflow.add_edge("search", "rerank")
    workflow.add_edge("rerank", "evaluate")

    # 조건부 엣지 연결 (평가 결과에 따른 분기)
    workflow.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {
            "rewrite": "rewrite",
            "generate": "generate"
        }
    )

    workflow.add_edge("generate", END)

    # 그래프 컴파일
    return workflow.compile()
