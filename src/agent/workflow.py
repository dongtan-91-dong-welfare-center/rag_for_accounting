# FUNC-009: LangGraph StateGraph 파이프라인 정의

# from langgraph.graph import StateGraph
from src.models.state import GraphState

def build_workflow() -> "StateGraph":
    """
    노드 등록 및 조건부 엣지를 정의하여 StateGraph를 반환한다.
    실행 순서: rewrite_query → hybrid_search → rerank → evaluate_context → generate_response
    evaluate_context 이후 route_after_evaluate로 분기 처리.
    """
    # Pseudo:
    # graph = StateGraph(GraphState)
    #
    # [노드 등록]
    # graph.add_node("rewrite",  rewrite_query)
    # graph.add_node("search",   hybrid_search)
    # graph.add_node("rerank",   rerank)
    # graph.add_node("evaluate", evaluate_context)
    # graph.add_node("generate", generate_response)
    #
    # [고정 엣지 — 조건 없음]
    # graph.add_edge(START,        "rewrite")
    # graph.add_edge("rewrite",    "search")
    # graph.add_edge("search",     "rerank")
    # graph.add_edge("rerank",     "evaluate")
    #
    # [조건부 엣지 — route_after_evaluate 반환값으로 분기]
    # graph.add_conditional_edges(
    #     "evaluate",
    #     route_after_evaluate,
    #     {"rewrite": "rewrite", "generate": "generate"}
    # )
    # graph.add_edge("generate", END)
    #
    # return graph.compile()
    raise NotImplementedError

def route_after_evaluate(state: GraphState) -> str:
    """
    평가 결과에 따라 다음 노드를 결정한다.
    - needs_external=True → 'rewrite_query' (재검색)
    - rewrite_count >= MAX_REWRITE_COUNT → 'generate_response' (강제 종료)
    - 그 외 → 'generate_response'
    """
    # Pseudo (우선순위 순서):
    # 1순위: rewrite_count 상한 초과 → 무조건 generate로 탈출
    #   if state.rewrite_count >= MAX_REWRITE_COUNT:
    #       return "generate"
    #
    # 2순위: 외부 참조 필요 + 재작성 여력 있음 → rewrite로 루프백
    #   if state.evaluation.needs_external:
    #       return "rewrite"
    #
    # 3순위: 기본 경로 → generate
    #   return "generate"
    raise NotImplementedError