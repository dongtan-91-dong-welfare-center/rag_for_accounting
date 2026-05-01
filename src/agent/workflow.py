# FUNC-009: LangGraph StateGraph 파이프라인 정의

from datetime import datetime, timezone
from functools import wraps
from langgraph.graph import StateGraph, START, END
from src.utils.config import MAX_REWRITE_COUNT
from src.utils.exception import AccountingRAGError
from src.models.state import GraphState
from src.models.schemas import RetrievedChunk, FinalResponse, EvaluationResult, RerankingResult

def handle_node_errors(node_name: str):
    """
    각 노드에서 발생하는 예외를 캐치하여 state.error_logs에 기록하고,
    워크플로우가 중단되지 않도록 상태를 반환하는 데코레이터입니다.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(state: GraphState) -> GraphState:
            try:
                return func(state)
            except AccountingRAGError as e:
                # 커스텀 예외 처리(Exception.py에서 정의)
                state.error_logs.append(e.to_error_log())
                return state
            except Exception as e:
                # 예상치 못한 예외 처리
                error_log = {
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "node": node_name,
                    "error_type": "UNKNOWN",
                    "message": str(e)
                }
                state.error_logs.append(error_log)
                return state
        return wrapper
    return decorator

@handle_node_errors("rewrite")
def rewrite_query(state: GraphState) -> GraphState:
    """
    TODO: FUNC-004 (질의 재작성 노드) - Mock 구현
    실제 구현 대기 (src/agent/nodes/rewrite.py)
    """
    state.rewrite_count += 1
    return state

@handle_node_errors("search")
def hybrid_search(state: GraphState) -> GraphState:
    """
    TODO: FUNC-005 (하이브리드 검색 노드) - Mock 구현
    실제 구현 대기 (src/retrieval/searcher.py)
    """
    state.retrieved_chunks = [
        RetrievedChunk(document_id="DOC-001", chunk_id="1", content="유형자산의 감가상각은..."),
        RetrievedChunk(document_id="DOC-002", chunk_id="2", content="전환사채를 투자목적으로..."),
    ]
    return state

@handle_node_errors("rerank")
def rerank(state: GraphState) -> GraphState:
    """
    TODO: FUNC-006 (재정렬 노드) - Mock 구현
    실제 구현 대기 (src/retrieval/reranker.py)
    """
    # 더미 구현: 검색된 청크를 그대로 재정렬 결과로 매핑
    state.reranked_chunks = [
        RerankingResult(
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            content=chunk.content,
            score=0.9
        ) for chunk in state.retrieved_chunks
    ]
    return state

@handle_node_errors("evaluate")
def evaluate_context(state: GraphState) -> GraphState:
    """
    TODO: FUNC-007 (컨텍스트 평가 노드) - Mock 구현
    실제 구현 대기 (src/agent/nodes/evaluate.py)
    """
    # 더미 구현: 항상 추가 검색이 필요 없는 것으로 평가
    state.evaluation = EvaluationResult(
        is_relevant=True,
        needs_external=False,
        reasoning="더미 평가: 검색된 컨텍스트가 충분히 관련성 있음"
    )
    return state

@handle_node_errors("generate")
def generate_response(state: GraphState) -> GraphState:
    """
    TODO: FUNC-008 (답변 생성 노드) - Mock 구현
    실제 구현 대기 (src/agent/nodes/generate.py)
    """
    # Fail-Fast 회피: 청크가 없더라도 이곳에서 기본 메시지 처리
    if not state.reranked_chunks:
        state.final_response = FinalResponse(
            answer="죄송합니다. 제공된 자료에서 관련 정보를 찾지 못했습니다.",
            citations=[],
            is_answerable=False,
            confidence_score=0.0
        )
        return state

    state.final_response = FinalResponse(
        answer="채권형 매도가능증권은 유효이자율법에 따라...",
        citations=["DOC-001", "DOC-002"],
        is_answerable=True,
        confidence_score=0.95
    )
    return state

def route_after_evaluate(state: GraphState) -> str:
    """
    TODO: FUNC-009 (평가 후 라우팅 결정)
    평가 결과에 따라 다음 노드를 결정한다.
    - needs_external=True → 'rewrite' (재검색)
    - 그 외 → 'generate'
    """
    if state.evaluation and state.evaluation.needs_external and state.rewrite_count < MAX_REWRITE_COUNT:
        return "rewrite"
    return "generate"

def build_workflow() -> StateGraph:
    """
    LangGraph StateGraph를 구성하고 컴파일하여 반환합니다.

    노드 등록 및 조건부 엣지를 정의하여 StateGraph를 반환한다.
    실행 순서: rewrite_query → hybrid_search → rerank → evaluate_context → generate_response
    evaluate_context 이후 route_after_evaluate로 분기 처리.
    """
    workflow = StateGraph(GraphState)

    # 노드 추가
    workflow.add_node("rewrite", rewrite_query)
    workflow.add_node("search", hybrid_search)
    workflow.add_node("rerank", rerank)
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