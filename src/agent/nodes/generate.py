# FUNC-008: 답변 생성 노드

import re
from datetime import datetime

import httpx
import pydantic
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior

from src.models.state import GraphState
from src.models.schemas import RerankingResult, Citation, FinalResponse, LLMInternalResponse
from src.agent.prompts import GENERATION_PROMPT
from src.utils.config import RERANK_THRESHOLD, KST, MAX_CONTEXT_TOKENS, OPENAI_MODEL
from src.utils.exception import (
    AccountingRAGError,
    LLMResponseFormatError,
    LLMAPIConnectionError,
    ContextLengthExceededError,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def generate_response(state: GraphState) -> dict:
    """
    reranked_chunks와 GENERATION_PROMPT를 이용해 최종 답변을 생성한다.
    - 인용 근거를 포함한 FinalResponse를 state.final_response에 저장
    """
    # PydanticAI 에이전트 초기화
    generator_agent = Agent(f"openai:{OPENAI_MODEL}", output_type=LLMInternalResponse)

    # 검색 결과가 없으면 답변 불가능 처리
    if not state.reranked_chunks:
        return {"final_response": build_unanswerable_response(state.original_query)}

    try:
        # 컨텍스트 조립: 청크를 하나씩 추가하며 토큰 한도 초과 시 트런케이션
        # 토큰 추정: len(str) * 0.5 (o200k_base 기준 한국어 1 토큰 ≈ 2~3 글자)
        context_chunks = []
        chunk_map = {}
        for idx, r_chunk in enumerate(state.reranked_chunks, start=1):
            if r_chunk.rerank_score >= RERANK_THRESHOLD:
                chunk_text = f"[{idx}] {r_chunk.chunk.content}"     # [1] 문서 내용, [2] 문서 내용
                candidate_str = "\n\n".join(context_chunks + [chunk_text])  # "[1] ...\n\n[2] ..."
                estimated_tokens = len(candidate_str) // 2  # 토큰 추정 (o200k_base 기준 한국어 1 토큰 ≈ 2~3 글자)

                if estimated_tokens > MAX_CONTEXT_TOKENS:
                    if not context_chunks:
                        # 첫 번째 청크만으로 한도 초과 — 극단적 예외
                        raise ContextLengthExceededError(
                            f"첫 번째 청크만으로도 컨텍스트 길이 한도({MAX_CONTEXT_TOKENS} 토큰)를 초과했습니다."
                        )
                    break  # 이전 청크까지만 사용 (트런케이션)

                context_chunks.append(chunk_text)
                chunk_map[idx] = r_chunk

        # 임계치를 초과하는 문서 청크가 없으면 답변 불가능 처리
        if not context_chunks:
            return {"final_response": build_unanswerable_response(state.original_query)}

        context_str = "\n\n".join(context_chunks)
        prompt = GENERATION_PROMPT.format(query=state.original_query, context=context_str)

        # PydanticAI 실행 — 파싱/네트워크 오류를 도메인 예외로 래핑
        try:
            result = generator_agent.run_sync(prompt)
            llm_response: LLMInternalResponse = result.output
        except (pydantic.ValidationError, UnexpectedModelBehavior) as e:
            raise LLMResponseFormatError(f"LLM 응답 파싱 실패: {e}")
        except httpx.RequestError as e:
            raise LLMAPIConnectionError(f"LLM API 연결 오류: {e}", node="generate")

        # 인용구 추출 및 citations 리스트 구성
        extracted_citations, final_answer = extract_citations_from_text(llm_response.answer, chunk_map)

        # 답변 가능 상태임에도 인용 근거가 없으면 프롬프트 지시 위반 (GN-401)
        if not extracted_citations and llm_response.is_answerable:
            raise LLMResponseFormatError(
                "답변 가능 상태임에도 인용 근거가 없습니다."
            )

        # 검색 점수 계산 (사용된 청크의 rerank_score 평균)
        retrieval_score = (
            sum(r.rerank_score for r in chunk_map.values()) / len(chunk_map)
            if chunk_map else 0.0
        )

        # 생성 점수: LLM 자체 평가 점수를 [0.0, 1.0] 범위로 클램핑
        generation_score = max(0.0, min(1.0, llm_response.llm_self_score))

        # 최종 신뢰도 (검색 0.4 + 생성 0.6)
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

    except AccountingRAGError as e:
        # 도메인 에러: error_logs 기록 + 폴백 반환 (터미널 노드이므로 파이프라인 유지)
        new_logs = state.error_logs + [e.to_error_log()]
        return {
            "final_response": build_unanswerable_response(state.original_query),
            "error_logs": new_logs,
        }
    except Exception as e:
        # 시스템 에러: 터미널 노드이므로 re-raise 없이 UNKNOWN 로그 적재 + 폴백 반환
        # TODO: generate -> evaluate, evaluate -> generate 노드 결정 여부에 따라서 해당 설계는 바뀔 가능성 존재
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
