# FUNC-008: 답변 생성 노드

import re
from pydantic_ai import Agent
from src.models.state import GraphState
from src.models.schemas import RerankingResult, Citation, FinalResponse, LLMInternalResponse
from src.agent.prompts import GENERATION_PROMPT
from src.utils.config import RERANK_THRESHOLD

# PydanticAI 에이전트 초기화
# 프로젝트 설정에 따라 모델을 변경할 수 있습니다.
generator_agent = Agent("openai:gpt-4o-mini", result_type=LLMInternalResponse)

def generate_response(state: GraphState) -> dict:
    """
    reranked_chunks와 GENERATION_PROMPT를 이용해 최종 답변을 생성한다.
    - 인용 근거를 포함한 FinalResponse를 state.final_response에 저장
    """
    # 검색 결과가 없으면 답변 불가능 처리
    if not state.reranked_chunks:
        return {"final_response": build_unanswerable_response(state.original_query)}

    # 컨텍스트 조립 (인덱스 부여)
    context_chunks = []
    chunk_map = {}
    for idx, r_chunk in enumerate(state.reranked_chunks, start=1):
        if r_chunk.rerank_score >= RERANK_THRESHOLD:
            context_chunks.append(f"[{idx}] {r_chunk.chunk.content}")   # [1] 문서 내용, [2] 문서 내용
            chunk_map[idx] = r_chunk

    # 임계치를 초과하는 문서 청크가 없으면 답변 불가능 처리
    if not context_chunks:
        return {"final_response": build_unanswerable_response(state.original_query)}

    context_str = "\n\n".join(context_chunks)
    prompt = GENERATION_PROMPT.format(query=state.original_query, context=context_str)

    try:
        # PydanticAI 실행
        result = generator_agent.run_sync(prompt)
        llm_response: LLMInternalResponse = result.data

        # 인용구 추출 및 citations 리스트 구성
        extracted_citations, final_answer = extract_citations_from_text(llm_response.answer, chunk_map)

        # 검색 점수 계산 (사용된 청크의 rerank_score 평균)
        if chunk_map:
            retrieval_score = sum(r.rerank_score for r in chunk_map.values()) / len(chunk_map)
        else:
            retrieval_score = 0.0

        # 생성 점수 계산 (LLM 자체 평가 점수 사용)
        generation_score = llm_response.llm_self_score
        
        # 최종 신뢰도 (검색 0.4 + 생성 0.6)
        final_confidence = (retrieval_score * 0.4) + (generation_score * 0.6)

        final_response = FinalResponse(
            answer=final_answer,
            citations=extracted_citations,
            is_answerable=llm_response.is_answerable,
            confidence_score=final_confidence
        )

        return {
            "final_response": final_response,
            "retrieval_score": retrieval_score,
            "generation_score": generation_score
        }

    except Exception as e:
        # 오류 발생 시 error_logs는 workflow의 데코레이터에서 처리됨을 가정
        raise e

def extract_citations_from_text(text: str, chunk_map: dict[int, RerankingResult]) -> tuple[list[Citation], str]:
    """
    답변 본문에서 [n] 마크업을 찾아 Citation 리스트를 추출한다.

    Args:
        text: 답변 텍스트
        chunk_map: 인덱스-청크 매핑 정보

    Returns:
        tuple[list[Citation], str]: 인용구 리스트와 답변 텍스트
    """
    citations = []
    used_indices = set()
    
    # 정규식을 통한 인덱스 추출
    matches = re.finditer(r'\[(\d+)\]', text)   # \d+ : 0~9 숫자가 1번 이상 반복되는 패턴
    for match in matches:
        idx = int(match.group(1))   # 괄호 안의 숫자를 추출
        # 인덱스가 chunk_map에 존재하고, 사용하지 않았는지 확인
        if idx in chunk_map and idx not in used_indices:
            r = chunk_map[idx]
            citations.append(
                Citation(
                    document_id=r.chunk.document_id,
                    chunk_id=r.chunk.chunk_id,
                    content=r.chunk.content,
                    relevance_score=r.rerank_score
                )
            )
            used_indices.add(idx)
            
    return citations, text

def build_unanswerable_response(query: str) -> FinalResponse:
    """맥락 부족으로 답변 불가 시 is_answerable=False인 응답 반환."""
    return FinalResponse(
        answer="제공된 회계기준 문서에서 해당 질의에 대한 충분한 근거를 찾지 못했습니다.",
        citations=[],
        is_answerable=False,
        confidence_score=0.0
    )