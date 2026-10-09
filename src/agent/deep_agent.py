"""자율 ReAct 딥에이전트 프로토타입 구현 모듈 (이슈 #245, #402, #403).

pydantic-ai Agent 기반으로 회계기준서 검색 도구를 자율 호출하여 최종 답변을 생성합니다.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.usage import UsageLimits

from src.agent.prompts import DEEP_AGENT_SYSTEM_PROMPT
from src.models.schemas import (
    Citation,
    DeepAgentDeps,
    DeepAgentInternalResponse,
    FinalResponse,
    RetrievedChunk,
)
from src.retrieval.searcher import search_chunks
from src.utils.config import OPENAI_MODEL
from src.utils.exception import NoContextFoundError
from src.utils.logger import get_logger, log_kv

logger = get_logger(__name__)


def _format_and_append_chunks(deps: DeepAgentDeps, chunks: list[RetrievedChunk]) -> str:
    """검색된 청크 목록을 컨텍스트에 축적하고 [n] 인덱스 포맷 텍스트로 변환합니다."""
    if not chunks:
        return "검색 결과가 없습니다. 다른 검색어로 재시도해 보세요."

    formatted_lines = []
    start_idx = len(deps.collected_chunks) + 1
    for i, chunk in enumerate(chunks, start=start_idx):
        deps.collected_chunks.append(chunk)
        chapter_info = f" (제{chunk.metadata.chapter}장)" if chunk.metadata.chapter else ""
        formatted_lines.append(f"[{i}] {chunk.chunk_id}{chapter_info}\n{chunk.content}")

    return "\n\n".join(formatted_lines)


def _execute_search(query: str, deps: DeepAgentDeps, include_sparse: bool = True) -> list[RetrievedChunk]:
    """검증된 하이브리드/단일 검색기(`src.retrieval.searcher.search_chunks`)를 재사용하여 검색을 수행합니다.

    0건 검색 시 재탐색 메커니즘 및 부분 장애 격리가 search_chunks 내부에 구현되어 있습니다.
    """
    metadata_filter = None
    if deps.standard_filter and deps.standard_filter != "ALL":
        metadata_filter = {"standard_type": deps.standard_filter}

    try:
        return search_chunks(
            query=query,
            top_k=deps.top_k,
            metadata_filter=metadata_filter,
            include_sparse=include_sparse,
        )
    except NoContextFoundError:
        return []
    except Exception as e:
        log_kv(logger, logging.ERROR, "deep_agent", "search_accounting_standards 도구 시스템 에러", 함수="search_accounting_standards", 오류=type(e).__name__, 상세=e, exc_info=True)
        return []


def create_deep_agent(
    model_name: str | None = None,
    tool_type: str = "ensemble",
) -> Agent[DeepAgentDeps, DeepAgentInternalResponse]:
    """앙상블(hybrid, 기본) 또는 단일(dense) 검색 도구를 장착한 pydantic-ai 기반 딥에이전트 인스턴스를 생성합니다.

    Args:
        model_name: 사용할 LLM 모델 식별자 (미지정 시 config.OPENAI_MODEL)
        tool_type: 검색 도구 유형 ('ensemble' 기본 또는 'single')
    """
    resolved_model = model_name or f"openai-chat:{OPENAI_MODEL}"
    agent = Agent(
        resolved_model,
        deps_type=DeepAgentDeps,
        output_type=DeepAgentInternalResponse,
        system_prompt=DEEP_AGENT_SYSTEM_PROMPT,
    )

    include_sparse = (tool_type != "single")

    @agent.tool
    def search_accounting_standards(ctx: RunContext[DeepAgentDeps], query: str) -> str:
        """회계기준서 문서를 검색으로 조회합니다.

        Args:
            query: 검색할 회계 주제, 용어 또는 질의문
        Returns:
            검색된 조항 청크 목록 텍스트 ([n] 번호 포함)
        """
        ctx.deps.call_count += 1
        ctx.deps.search_queries.append(query)
        mode_label = "ensemble" if include_sparse else "single"
        log_kv(logger, logging.INFO, "deep_agent", "딥에이전트 도구 호출", 건수=ctx.deps.call_count, 모드=mode_label, 질의길이=len(query))
        log_kv(logger, logging.DEBUG, "deep_agent", "딥에이전트 도구 호출 질의", 상세=query)

        chunks = _execute_search(query, ctx.deps, include_sparse=include_sparse)
        return _format_and_append_chunks(ctx.deps, chunks)

    return agent


def _parse_citation_part_indices(part_str: str) -> list[int]:
    """쉼표로 구분된 개별 인용 문자열(예: '1', '1-3')로부터 1-based 인덱스 목록을 추출합니다."""
    if "-" in part_str:
        sub = part_str.split("-")
        if len(sub) == 2 and sub[0].strip().isdigit() and sub[1].strip().isdigit():
            start_i, end_i = int(sub[0].strip()), int(sub[1].strip())
            if start_i <= end_i:
                return list(range(start_i, end_i + 1))
    elif part_str.isdigit():
        return [int(part_str)]
    return []


def extract_citations_from_collected_chunks(
    answer: str,
    collected_chunks: list[RetrievedChunk],
) -> list[Citation]:
    """답변 본문의 [n] 인용 표기를 파싱하여 1-based 인덱스에 해당하는 Citation 목록을 생성합니다.

    `[1]`, `[1][2]` 표준 표기뿐만 아니라 `[1, 2]`, `[1-3]` 등의 복수 인용 엣지 케이스도 파싱합니다.
    """
    citations: list[Citation] = []
    used_indices: set[int] = set()

    # 대괄호 내 숫자, 쉼표, 하이픈이 포함된 인용 블록 검색 (예: "[1]", "[1, 2]", "[1-3]")
    for block in re.finditer(r"\[([\d\s,\-]+)\]", answer):
        raw_content = block.group(1)
        # 쉼표 구분 복수 인용 처리 (예: "1, 2" -> ["1", "2"])
        for part in raw_content.split(","):
            part_str = part.strip()
            if not part_str:
                continue

            for idx in _parse_citation_part_indices(part_str):
                # 수집된 청크 인덱스 범위 유효성 검증 및 중복 인용 방지
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
    tool_type: str = "ensemble",
    agent: Agent[DeepAgentDeps, DeepAgentInternalResponse] | None = None,
) -> tuple[FinalResponse, list[RetrievedChunk], dict[str, Any]]:
    """자율 딥에이전트를 실행하고 결과 및 계측 메타데이터를 반환합니다.

    Args:
        query: 사용자 질의
        standard_filter: 적용 기준서 범위 (기본: "GAAP")
        max_turns: LLM 추론/도구 호출 최대 상한 턴 수 (1, 3, 5 등)
        top_k: 도구 1회 검색당 반환할 청크 수 (기본: 10)
        model_name: 사용할 모델 명 (미지정 시 config.OPENAI_MODEL)
        tool_type: 사용할 검색 도구 유형 ('ensemble' 기본 또는 'single')
        agent: 주입할 Agent 인스턴스 (테스트 시 모의 객체 주입 가능)

    Returns:
        tuple[FinalResponse, list[RetrievedChunk], dict[str, Any]]:
            - FinalResponse: 최종 응답 (답변, 인용구, 신뢰도 등)
            - list[RetrievedChunk]: 에이전트가 탐색 과정에서 수집한 누적 청크 목록
            - dict[str, Any]: 실행 통계 및 메타데이터 (턴 수, 토큰, 도구 호출 수 등)
    """
    if agent is None:
        agent = create_deep_agent(model_name=model_name, tool_type=tool_type)

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
        log_kv(logger, logging.WARNING, "deep_agent", "턴 상한선 초과 폴백", 상한=max_turns, 대체동작="폴백 응답", 상세=e)
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
        log_kv(logger, logging.ERROR, "deep_agent", "실행 중 예외 발생", 오류=type(e).__name__, 상세=e, exc_info=True)
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
