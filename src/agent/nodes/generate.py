# FUNC-008: 답변 생성 노드

from src.models.state import GraphState
from src.models.schemas import RerankingResult, Citation, FinalResponse

def generate_response(state: GraphState) -> GraphState:
    """
    reranked_chunks와 GENERATION_PROMPT를 이용해 최종 답변을 생성한다.
    - 인용 근거를 포함한 FinalResponse를 state.final_response에 저장
    """
    # Pseudo:
    # try:
    #   [답변 가능 여부 판단]
    #   if not state.evaluation.is_relevant or len(state.reranked_chunks) == 0:
    #       state.final_response = build_unanswerable_response(state.query)
    #       return state
    #
    #   [LLM 답변 생성]
    #   citations = extract_citations(state.reranked_chunks)
    #   prompt    = GENERATION_PROMPT.format(
    #                   query=state.query,
    #                   context=[c.chunk.content for c in state.reranked_chunks],
    #                   citations=citations)
    #   response  = llm.invoke(prompt)   # JSON: {answer, is_answerable}
    #
    #   [confidence_score: 사용된 청크의 rerank_score 평균]
    #   # LLM이 느낀 확신도를 반영하는 방법도 있을 수 있음
    #   confidence = sum(r.rerank_score for r in state.reranked_chunks) \
    #                / len(state.reranked_chunks)
    #
    #   state.final_response = FinalResponse(
    #       answer=response["answer"],
    #       citations=citations,
    #       is_answerable=response["is_answerable"],
    #       confidence_score=confidence,
    #   )
    #
    # except Exception as e:
    #   state.error_logs.append({...})
    #
    # return state
    raise NotImplementedError

def extract_citations(chunks: list[RerankingResult]) -> list[Citation]:
    """답변 생성에 사용된 청크에서 Citation 리스트를 추출한다."""
    # page_number나 section_title 같은 메타데이터를 인용구에 포함하는 로직을 추가 고려
    # Pseudo:
    # return [
    #     Citation(
    #         document_id=r.chunk.document_id,
    #         chunk_id=r.chunk.chunk_id,
    #         content=r.chunk.content,
    #         relevance_score=r.rerank_score,   # [0, 1] 범위
    #     )
    #     for r in chunks
    #     if r.rerank_score >= RERANK_THRESHOLD
    # ]
    raise NotImplementedError

def build_unanswerable_response(query: str) -> FinalResponse:
    """맥락 부족으로 답변 불가 시 is_answerable=False인 응답을 반환 편집."""
    # Pseudo:
    # return FinalResponse(
    #     answer="제공된 회계기준 문서에서 해당 질의에 대한 충분한 근거를 찾지 못했습니다.",
    #     citations=[],
    #     is_answerable=False,
    #     confidence_score=0.0,
    # )
    raise NotImplementedError