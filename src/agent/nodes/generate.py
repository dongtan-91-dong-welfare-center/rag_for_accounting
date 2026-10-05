# generate: 답변 생성 노드

import re
from datetime import datetime

import httpx
import pydantic
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior

from src.models.state import GraphState
from src.models.schemas import RerankingResult, Citation, FinalResponse, LLMInternalResponse
from src.agent.prompts import GENERATION_PROMPT
from src.utils import config
from src.utils.config import KST, MAX_CONTEXT_TOKENS, OPENAI_MODEL
from src.utils.exception import (
    AccountingRAGError,
    LLMResponseFormatError,
    LLMAPIConnectionError,
    ContextLengthExceededError,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _assemble_context(
    reranked_chunks: list[RerankingResult],
) -> tuple[str, dict[int, RerankingResult]]:
    """rerank_score 임계값을 만족하는 청크들을 모아 토큰 한도 내에서 프롬프트 컨텍스트와 매핑을 조립한다."""
    context_chunks = []
    chunk_map = {}
    for idx, r_chunk in enumerate(reranked_chunks, start=1):
        if r_chunk.rerank_score >= config.RERANK_THRESHOLD:
            chunk_text = f"[{idx}] {r_chunk.chunk.content}"
            candidate_str = "\n\n".join(context_chunks + [chunk_text])
            estimated_tokens = len(candidate_str) // 2

            if estimated_tokens > MAX_CONTEXT_TOKENS:
                if not context_chunks:
                    raise ContextLengthExceededError(
                        f"첫 번째 청크만으로도 컨텍스트 길이 한도({MAX_CONTEXT_TOKENS} 토큰)를 초과했습니다."
                    )
                break

            context_chunks.append(chunk_text)
            chunk_map[idx] = r_chunk

    return "\n\n".join(context_chunks), chunk_map


def _execute_generator_llm(prompt: str) -> LLMInternalResponse:
    """PydanticAI LLM을 실행하고 파싱 및 네트워크 오류를 도메인 예외로 래핑한다."""
    generator_agent = Agent(f"openai-chat:{OPENAI_MODEL}", output_type=LLMInternalResponse)
    try:
        result = generator_agent.run_sync(prompt)
        return result.output
    except (pydantic.ValidationError, UnexpectedModelBehavior) as e:
        raise LLMResponseFormatError(f"LLM 응답 파싱 실패: {e}")
    except httpx.RequestError as e:
        raise LLMAPIConnectionError(f"LLM API 연결 오류: {e}", node="generate")


def _build_final_response(
    llm_response: LLMInternalResponse,
    chunk_map: dict[int, RerankingResult],
) -> dict:
    """답변에서 인용구를 추출하고 신뢰도 스코어를 계산하여 FinalResponse dict를 생성한다."""
    extracted_citations, final_answer = extract_citations_from_text(llm_response.answer, chunk_map)

    if not extracted_citations and llm_response.is_answerable:
        raise LLMResponseFormatError("답변 가능 상태임에도 인용 근거가 없습니다.")

    retrieval_score = (
        sum(r.rerank_score for r in chunk_map.values()) / len(chunk_map)
        if chunk_map else 0.0
    )
    generation_score = max(0.0, min(1.0, llm_response.llm_self_score))
    final_confidence = (retrieval_score * 0.4) + (generation_score * 0.6)

    return {
        "final_response": FinalResponse(
            answer=final_answer,
            citations=extracted_citations,
            is_answerable=llm_response.is_answerable,
            confidence_score=final_confidence,
        ),
        "retrieval_score": retrieval_score,
        "generation_score": generation_score,
    }


def generate_response(state: GraphState) -> dict:
    """
    reranked_chunks와 GENERATION_PROMPT를 이용해 최종 답변을 생성한다.
    - 인용 근거를 포함한 FinalResponse를 만들어 state.final_response에 저장하고, 신뢰도 계산에 쓴 retrieval_score·generation_score도 함께 반환한다
    """
    if not state.reranked_chunks:
        return {"final_response": build_unanswerable_response(state.original_query)}

    try:
        context_str, chunk_map = _assemble_context(state.reranked_chunks)
        if not context_str:
            return {"final_response": build_unanswerable_response(state.original_query)}

        prompt = GENERATION_PROMPT.format(query=state.original_query, context=context_str)
        llm_response = _execute_generator_llm(prompt)
        return _build_final_response(llm_response, chunk_map)

    except AccountingRAGError as e:
        new_logs = state.error_logs + [e.to_error_log()]
        return {
            "final_response": build_unanswerable_response(state.original_query),
            "error_logs": new_logs,
        }
    except Exception as e:
        logger.error(f"[{type(e).__name__}] generate_response 노드 시스템 에러: {e}", exc_info=True)
        error_log = {
            "timestamp": datetime.now(KST).isoformat(),
            "node": "generate",
            "error_type": "UNKNOWN",
            "message": f"[{type(e).__name__}] {str(e)}",
        }
        new_logs = state.error_logs + [error_log]
        return {
            "final_response": build_unanswerable_response(state.original_query),
            "error_logs": new_logs,
        }


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
                    relevance_score=r.rerank_score,
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
        confidence_score=0.0,
    )
