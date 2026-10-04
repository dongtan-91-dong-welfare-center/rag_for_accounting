# FUNC-010: 단일 검색 도구 기반 자율 ReAct 딥에이전트 프로토타입 (시나리오 2, 이슈 #402)
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.usage import UsageLimits

from src.models.schemas import Citation, FinalResponse, RetrievedChunk
from src.retrieval.searcher import dense_search, embed_query
from src.utils.config import OPENAI_MODEL
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEEP_AGENT_SYSTEM_PROMPT = """당신은 한국 일반기업회계기준(K-GAAP) 및 회계기준서를 정밀하게 탐색하고 답변하는 자율 회계 전문 AI 에이전트입니다.

사용자의 회계 질의에 답변하기 위해 `search_accounting_standards` 도구를 자율적으로 호출할 수 있습니다.

[도구 사용 및 탐색 지침]
1. 질문의 핵심 회계 개념이나 키워드로 `search_accounting_standards` 도구를 호출하세요.
2. 검색 결과가 불충분하거나 관련성이 낮다고 판단되면, 질의를 구체화하거나 동의어/상위개념으로 재검색할 수 있습니다.
3. 충분한 조항과 근거가 확보되면 추가 검색을 멈추고 최종 답변을 작성하세요.

[답변 작성 및 인용 규칙]
1. 반드시 도구를 통해 검색된 회계기준 문서만을 근거로 정확하게 답변을 작성하세요.
2. 답변의 논리적 근거가 되는 문장 끝에 반드시 해당 맥락 청크의 인덱스 번호를 [n] 형태로 표시하세요. (예: ...로 인식합니다 [1].)
3. 여러 청크를 참고한 경우 [1][2] 와 같이 표시하세요.
4. 검색된 문서 내에서 질의에 대한 충분한 근거를 찾지 못했거나 답변할 수 없는 경우, `is_answerable=false`로 설정하고 답변에 근거 부족 사유를 명시하세요.
"""


class DeepAgentInternalResponse(BaseModel):
    """딥에이전트 LLM 최종 구조화 응답 모델"""

    answer: str = Field(description="답변 본문 ([n] 인용 표기 포함)")
    is_answerable: bool = Field(description="검색된 맥락을 근거로 명확히 답변 가능하면 true, 부족하면 false")
    llm_self_score: float = Field(default=1.0, description="스스로 평가한 답변의 정확도 및 근거 충실도 (0.0 ~ 1.0)")


@dataclass
class DeepAgentDeps:
    """딥에이전트 실행 컨텍스트 의존성 객체"""

    collected_chunks: list[RetrievedChunk] = field(default_factory=list)
    standard_filter: str | None = None
    top_k: int = 10
    search_queries: list[str] = field(default_factory=list)
    call_count: int = 0


def create_deep_agent(model_name: str | None = None) -> Agent[DeepAgentDeps, DeepAgentInternalResponse]:
    """단일 검색 도구를 장착한 pydantic-ai 기반 딥에이전트 인스턴스를 생성합니다."""
    resolved_model = model_name or f"openai-chat:{OPENAI_MODEL}"
    agent = Agent(
        resolved_model,
        deps_type=DeepAgentDeps,
        output_type=DeepAgentInternalResponse,
        system_prompt=DEEP_AGENT_SYSTEM_PROMPT,
    )

    @agent.tool
    def search_accounting_standards(ctx: RunContext[DeepAgentDeps], query: str) -> str:
        """회계기준서 문서를 Dense 벡터 유사도 검색으로 조회합니다.

        Args:
            query: 검색할 회계 주제, 용어 또는 질의문
        Returns:
            검색된 조항 청크 목록 텍스트 ([n] 번호 포함)
        """
        ctx.deps.call_count += 1
        ctx.deps.search_queries.append(query)
        logger.info(f"[DeepAgent Tool Call #{ctx.deps.call_count}] search_accounting_standards: '{query}'")

        query_vec = embed_query(query)
        metadata_filter = None
        if ctx.deps.standard_filter and ctx.deps.standard_filter != "ALL":
            metadata_filter = {"standard_type": ctx.deps.standard_filter}

        chunks = dense_search(
            query_embedding=query_vec,
            top_k=ctx.deps.top_k,
            metadata_filter=metadata_filter,
        )

        if not chunks:
            return "검색 결과가 없습니다. 다른 검색어로 재시도해 보세요."

        formatted_lines = []
        start_idx = len(ctx.deps.collected_chunks) + 1
        for i, chunk in enumerate(chunks, start=start_idx):
            ctx.deps.collected_chunks.append(chunk)
            chapter_info = f" (제{chunk.metadata.chapter}장)" if chunk.metadata.chapter else ""
            formatted_lines.append(f"[{i}] {chunk.chunk_id}{chapter_info}\n{chunk.content}")

        return "\n\n".join(formatted_lines)

    return agent


def extract_citations_from_collected_chunks(
    answer: str,
    collected_chunks: list[RetrievedChunk],
) -> list[Citation]:
    """답변 본문의 [n] 인용 표기를 파싱하여 1-based 인덱스에 해당하는 Citation 목록을 생성합니다."""
    citations: list[Citation] = []
    used_indices: set[int] = set()

    for match in re.finditer(r"\[(\d+)\]", answer):
        idx = int(match.group(1))
        # 1-based 인덱스 검증
        if 1 <= idx <= len(collected_chunks) and idx not in used_indices:
            chunk = collected_chunks[idx - 1]
            citations.append(
                Citation(
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    relevance_score=float(chunk.score),
                )
            )
            used_indices.add(idx)

    return citations


def run_deep_agent(
    query: str,
    standard_filter: str | None = "GAAP",
    max_turns: int = 3,
    top_k: int = 10,
    model_name: str | None = None,
    agent: Agent[DeepAgentDeps, DeepAgentInternalResponse] | None = None,
) -> tuple[FinalResponse, list[RetrievedChunk], dict[str, Any]]:
    """단일 검색기 기반 자율 딥에이전트를 실행하고 결과 및 계측 메타데이터를 반환합니다.

    Args:
        query: 사용자 질의
        standard_filter: 적용 기준서 범위 (기본: "GAAP")
        max_turns: LLM 추론/도구 호출 최대 상한 턴 수 (1, 3, 5 등)
        top_k: 도구 1회 검색당 반환할 청크 수 (기본: 10)
        model_name: 사용할 모델 명 (미지정 시 config.OPENAI_MODEL)
        agent: 주입할 Agent 인스턴스 (테스트 시 모의 객체 주입 가능)

    Returns:
        tuple[FinalResponse, list[RetrievedChunk], dict[str, Any]]:
            - FinalResponse: 최종 응답 (답변, 인용구, 신뢰도 등)
            - list[RetrievedChunk]: 에이전트가 탐색 과정에서 수집한 누적 청크 목록
            - dict[str, Any]: 실행 통계 및 메타데이터 (턴 수, 토큰, 도구 호출 수 등)
    """
    if agent is None:
        agent = create_deep_agent(model_name=model_name)

    deps = DeepAgentDeps(
        standard_filter=standard_filter,
        top_k=top_k,
    )

    limits = UsageLimits(request_limit=max_turns)
    meta: dict[str, Any] = {
        "max_turns": max_turns,
        "turns_executed": 0,
        "search_calls": 0,
        "search_queries": [],
        "fallback_triggered": False,
        "fallback_reason": None,
    }

    try:
        run_res = agent.run_sync(query, deps=deps, usage_limits=limits)
        output = run_res.output
        usage = run_res.usage
        meta["turns_executed"] = getattr(usage, "requests", 1)
        meta["tool_calls"] = getattr(usage, "tool_calls", deps.call_count)
        meta["input_tokens"] = getattr(usage, "input_tokens", 0)
        meta["output_tokens"] = getattr(usage, "output_tokens", 0)
        meta["total_tokens"] = getattr(usage, "total_tokens", 0)
        meta["search_calls"] = deps.call_count
        meta["search_queries"] = list(deps.search_queries)

        citations = extract_citations_from_collected_chunks(output.answer, deps.collected_chunks)
        confidence = max(0.0, min(1.0, float(output.llm_self_score)))

        final_response = FinalResponse(
            answer=output.answer,
            citations=citations,
            is_answerable=output.is_answerable,
            confidence_score=confidence,
        )
        return final_response, deps.collected_chunks, meta

    except UsageLimitExceeded as e:
        logger.warning(f"[DeepAgent] 턴 상한선({max_turns}턴) 초과 폴백: {e}")
        meta["turns_executed"] = max_turns
        meta["search_calls"] = deps.call_count
        meta["search_queries"] = list(deps.search_queries)
        meta["fallback_triggered"] = True
        meta["fallback_reason"] = "MAX_TURNS_EXCEEDED"

        # 수집된 청크가 있다면 상위 청크를 기반으로 안전한 인용구 구성
        citations: list[Citation] = []
        if deps.collected_chunks:
            top_chunk = deps.collected_chunks[0]
            citations.append(
                Citation(
                    document_id=top_chunk.document_id,
                    chunk_id=top_chunk.chunk_id,
                    content=top_chunk.content,
                    relevance_score=float(top_chunk.score),
                )
            )

        fallback_resp = FinalResponse(
            answer=f"최대 탐색 턴 수({max_turns}턴)를 초과하여 충분한 확신을 가진 답변을 도출하지 못했습니다.",
            citations=citations,
            is_answerable=False,
            confidence_score=0.0,
        )
        return fallback_resp, deps.collected_chunks, meta

    except Exception as e:
        logger.error(f"[DeepAgent] 실행 중 예외 발생: {e}", exc_info=True)
        meta["search_calls"] = deps.call_count
        meta["search_queries"] = list(deps.search_queries)
        meta["fallback_triggered"] = True
        meta["fallback_reason"] = f"{type(e).__name__}: {e}"

        error_resp = FinalResponse(
            answer="에이전트 실행 중 오류가 발생하여 답변을 생성하지 못했습니다.",
            citations=[],
            is_answerable=False,
            confidence_score=0.0,
        )
        return error_resp, deps.collected_chunks, meta
