# FUNC-009: LangGraph StateGraph 파이프라인 정의

from datetime import datetime
from functools import wraps
from langgraph.graph import StateGraph, START, END
from src.agent.nodes.generate import generate_response
from src.agent.nodes.evaluate import evaluate_context
from src.utils.config import MAX_REWRITE_COUNT, KST
from src.utils.exception import AccountingRAGError
from src.models.state import GraphState
from src.models.schemas import (
    RetrievedChunk, FinalResponse, EvaluationResult,
    RerankingResult, Citation
)

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

@handle_node_errors("rerank")
def rerank(state: GraphState) -> dict:
    """
    TODO: FUNC-006 (재정렬 노드) - Mock 구현
    실제 구현 대기 (src/retrieval/reranker.py)
    """
    # 더미 구현: 검색된 청크 수만큼 재정렬 결과 생성
    reranked = [
        RerankingResult(
            chunk=chunk,
            rerank_score=0.95
        ) for chunk in state.retrieved_chunks
    ]
    return {"reranked_chunks": reranked}

def route_after_evaluate(state: GraphState) -> str:
    """
    TODO: FUNC-009 (평가 후 라우팅 결정)
    평가 결과 또는 에러 상태에 따라 다음 노드를 결정한다.
    """
    # 예외 발생 시의 안전 장치
    # evaluate 노드 자체에서 에러가 발생했다면, 무한 루프를 방지하기 위해 강제로 generate 단계로 우회합니다.
    # 다만, EV-301 발생 시 우리의 폴백(needs_external=True)이 의도한 CRAG 루프 재진입은 실제로는 발동되지 않습니다.
    # 만약, route_after_evaluate의 안전 장치가 너무 공격적이며, FUNC-007 의도(파싱 실패 시 한 번 더 시도)와 충돌한다면
    # TODO: route_after_evaluate를 손봐야 함 (예: rewrite_count 체크와 결합)
    if state.error_logs and state.error_logs[-1]["node"] == "evaluate":
        return "generate"

    # CRAG (Corrective RAG) 루프 진입 조건 판단
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