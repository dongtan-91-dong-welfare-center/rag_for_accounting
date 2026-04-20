# FUNC-004: 질의 재작성 노드

from src.models.state import GraphState

def rewrite_query(state: GraphState) -> GraphState:
    """
    GraphState.query를 REWRITE_PROMPT + GPT-4o-mini로 재작성한다.
    - rewrite_count가 MAX_REWRITE_COUNT 초과 시 원본 질의 그대로 반환
    - 결과를 state.rewritten_query에 저장
    """
    # Pseudo:
    # try:
    #   [상한 초과 시 조기 반환]
    #   if state.rewrite_count >= MAX_REWRITE_COUNT:
    #       # evaluation 노드에서 "검색 결과가 부적절했던 이유"를 피드백으로 받아 rewrite_query에 전달하는 방식을 고려 가능
    #       return state  # 원본 query 그대로 유지, 이후 workflow가 generate로 라우팅
    #
    #   [LLM 호출]
    #   prompt = REWRITE_PROMPT.format(query=state.query)
    #   response = llm.invoke(prompt)          # JSON 형식: {rewritten, reasoning}
    #   parsed   = RewrittenQuery(**response)
    #
    #   [상태 갱신]
    #   state.rewritten_query  = parsed
    #   state.rewrite_count   += 1
    #   state.retrieved_chunks = []            # 이전 검색 결과 초기화
    #   state.reranked_chunks  = []
    #   state.evaluation       = None
    #
    # except Exception as e:
    #   state.error_logs.append({
    #       "timestamp": datetime.utcnow().isoformat(),
    #       "node":       "rewrite",
    #       "error_type": type(e).__name__,
    #       "message":    str(e),
    #   })
    #
    # return state
    raise NotImplementedError

def is_complex_query(query: str) -> bool:
    """복합 조항 참조 여부를 판단하여 재작성 필요성을 반환한다."""
    # Pseudo — 복합 조항 참조 신호어 기반 휴리스틱:
    # signals = ["및", "또는", "경우에는", "불구하고", "다만", "제N조"]
    # return any(signal in query for signal in signals)
    #   → True: 여러 조항을 동시에 참조할 가능성 높음 → 재작성 필요
    #   → False: 단일 조항 질의 → 재작성 생략 가능 (workflow 판단에 위임)
    raise NotImplementedError