# FUNC-009: LangGraph StateGraph 파이프라인 정의

from datetime import datetime
from functools import wraps
from langgraph.graph import StateGraph, START, END
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
                    "timestamp": datetime.now(KST).isoformat(), # datetime 객체를 ISO 8601 국제 표준 형식의 문자열로 변환
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

@handle_node_errors("evaluate")
def evaluate_context(state: GraphState) -> dict:
    """
    TODO: FUNC-007 (컨텍스트 평가 노드) - Mock 구현
    실제 구현 대기 (src/agent/nodes/evaluate.py)
    """
    # 더미 구현: 항상 추가 검색이 필요 없는 것으로 평가
    return {
        "evaluation": EvaluationResult(
            is_relevant=True,
            needs_external=False,
            confidence=0.9,
            reasoning="더미 평가: 검색된 컨텍스트가 충분히 관련성 있음"
        )
    }

@handle_node_errors("generate")
def generate_response(state: GraphState) -> dict:
    """
    TODO: FUNC-008 (답변 생성 노드) - Mock 구현
    실제 구현 대기 (src/agent/nodes/generate.py)
    """
    # Fail-Fast 회피: 청크가 없더라도 이곳에서 기본 메시지 처리
    if not state.reranked_chunks:
        return {
            "final_response": FinalResponse(
                answer="죄송합니다. 제공된 자료에서 관련 정보를 찾지 못했습니다.",
                citations=[],
                is_answerable=False,
                confidence_score=0.0
            )
        }

    # Citation 객체 생성
    citations = [
        Citation(
            document_id=r.chunk.document_id,
            chunk_id=r.chunk.chunk_id,
            content=r.chunk.content,
            relevance_score=r.rerank_score
        ) for r in state.reranked_chunks
    ]

    return {
        "final_response": FinalResponse(
            answer="채권형 매도가능증권은 유효이자율법에 따라...",
            citations=citations,
            is_answerable=True,
            confidence_score=0.95
        )
    }

def route_after_evaluate(state: GraphState) -> str:
    """
    TODO: FUNC-009 (평가 후 라우팅 결정)
    평가 결과 또는 에러 상태에 따라 다음 노드를 결정한다.
    """
    # evaluate 노드에서 에러 발생 여부 확인 (명시적 에러 감지)
    if state.error_logs and state.error_logs[-1]["node"] == "evaluate":
        # 평가 단계 실패 시, 재작성 루프를 타지 않고 바로 generate로 진행
        return "generate"

    # 정상적인 CRAG 루프 분기
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