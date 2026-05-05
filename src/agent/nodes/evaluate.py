# FUNC-007: 검색 맥락 평가 노드 (CRAG 패턴)

from src.models.state import GraphState
from src.models.schemas import RerankingResult, EvaluationResult

def evaluate_context(state: GraphState) -> GraphState:
    """
    reranked_chunks를 EVALUATION_PROMPT + GPT-4o-mini로 평가한다.
    - 결과를 state.evaluation에 저장
    - needs_external=True이면 workflow가 외부 검색 경로로 라우팅
    """
    # Pseudo:
    # try:
    #   [각 청크 관련도 판단]
    #   relevant_chunks = [r for r in state.reranked_chunks
    #                       if check_relevance(r, state.original_query)]
    #
    #   [LLM 기반 종합 평가]
    #   prompt   = EVALUATION_PROMPT.format(
    #                  query=state.original_query,
    #                  chunks=[r.chunk.content for r in relevant_chunks])
    #   response = llm.invoke(prompt)   # JSON: {is_relevant, needs_external, confidence, reasoning}
    #   eval_result = EvaluationResult(**response)
    #
    #   [외부 참조 필요 여부 별도 확인]
    #   if check_external_reference(eval_result):
    #       eval_result.needs_external = True
    #
    #   state.evaluation = eval_result
    #
    # except Exception as e:
    #   state.error_logs.append({...})  # TASK-02와 동일 구조
    #
    # return state
    #   → route_after_evaluate가 state.evaluation을 읽어 다음 노드 결정
    raise NotImplementedError

def check_relevance(chunk: RerankingResult, query: str) -> bool:
    """단일 청크가 질의에 관련성이 있는지 판단한다."""
    # Pseudo:
    # return chunk.rerank_score >= RERANK_THRESHOLD
    #   and len(chunk.chunk.content.strip()) > 0
    raise NotImplementedError

def check_external_reference(evaluation: EvaluationResult) -> bool:
    """평가 결과에서 외부 기준서 참조 필요 여부를 반환한다."""
    # Pseudo:
    # 신호 키워드가 reasoning에 포함되면 외부 참조 필요로 판단
    # keywords = ["외부", "타 기준서", "IFRS", "공표 전", "개정"]
    # return any(kw in evaluation.reasoning for kw in keywords)
    raise NotImplementedError