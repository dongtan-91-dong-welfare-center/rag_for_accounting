"""API 응답 스키마와 워크플로 결과 변환 계층.

run_workflow/resume_workflow의 반환 dict를 status(done|interrupted)로 구분되는 유니언 스키마로 변환한다.
FastAPI 서버(src/api/server.py)가 두 엔드포인트(/query·/resume)모두 이 변환을 거쳐 응답하므로, 
여기가 API 노출 필드의 단일 정의 지점이다.

계약:
- GraphState 통째 직렬화 금지 — retrieved_chunks·error_logs 등 내부 상태 비노출.
- clauses[]는 build_clause_rows(src/ui/clauses.py) 재사용 — Streamlit과 동일한 조항 표현.
- error_code는 서버가 error_logs에서 파생하는 폴백 구분자 — 클라이언트가 타임아웃(일시적, 재시도 유도)을 일반 답변불가(영구적)와 구분하는 유일한 통로다.
- interrupt 노출 필드는 strategy·original_query·search_queries·options 4종(7/4 결정 — hil_count·max_hil_count는 페이로드에 있어도 비노출).
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel

from src.agent.interrupts import extract_interrupt_payload, is_interrupt
from src.ui.clauses import build_clause_rows


class ClauseOut(BaseModel):
    """검색 조항 1건 — ClauseRow(src/ui/clauses.py)와 동일 구조의 API 표현."""

    rank: int
    chapter: str
    node_id: str
    score: float
    content: str
    document_id: str = ""          # 뷰어가 GET /documents/{document_id}/pdf를 여는 데 사용(#196)
    page_start: int | None = None  # 원본 PDF 페이지 범위(#196) — 미백필/미매칭이면 None(뷰어 버튼 미표시)
    page_end: int | None = None


class CitationOut(BaseModel):
    """답변 인용 1건 — src/models/schemas.py Citation의 API 표현."""

    document_id: str
    chunk_id: str
    content: str
    relevance_score: float
    page_start: int | None = None  # chunk_id로 reranked_chunks metadata를 조회해 결합(#196)
    page_end: int | None = None


class InterruptOption(BaseModel):
    """HIL 결정 선택지 — /resume의 action으로 되돌아온다."""

    action: str
    label: str


class InterruptInfo(BaseModel):
    """human_review interrupt 페이로드의 API 노출 필드."""

    strategy: str
    original_query: str
    search_queries: list[str]
    options: list[InterruptOption]


class QueryDoneResponse(BaseModel):
    """워크플로 완료 응답. 폴백(타임아웃·recursion)도 이 형태다(200, is_answerable=false)."""

    status: Literal["done"] = "done"
    thread_id: str
    answer: str
    is_answerable: bool
    confidence: float
    error_code: Literal["TIMEOUT"] | None = None
    clauses: list[ClauseOut]
    citations: list[CitationOut]


class QueryInterruptedResponse(BaseModel):
    """HIL 중단 응답 — 클라이언트는 thread_id로 /resume을 호출해 재개한다."""

    status: Literal["interrupted"] = "interrupted"
    thread_id: str
    interrupt: InterruptInfo


WorkflowResponse = QueryDoneResponse | QueryInterruptedResponse


def _derive_error_code(error_logs: list[dict]) -> Literal["TIMEOUT"] | None:
    """
    폴백이 기록한 워크플로 레벨 TIMEOUT을 응답 구분자로 파생한다.

    GraphRecursionError 폴백은 error_logs를 기록하지 않으므로 None이다
    TODO! #210에서 v1.1에서 대칭화 예정 — 그 전까지 클라이언트는 일반 답변불가와 구분 불가.
    """
    if any(log.get("error_type") == "TIMEOUT" for log in error_logs):
        return "TIMEOUT"
    return None


def to_api_response(result: dict) -> WorkflowResponse:
    """run_workflow/resume_workflow 반환 dict를 API 유니언 스키마로 변환한다."""
    thread_id = result["thread_id"]

    if is_interrupt(result):
        payload = extract_interrupt_payload(result)
        return QueryInterruptedResponse(
            thread_id=thread_id,
            interrupt=InterruptInfo(
                strategy=payload.get("strategy", "?"),
                original_query=payload.get("original_query", ""),
                search_queries=payload.get("search_queries", []),
                options=payload.get("options", []),
            ),
        )

    response = result["final_response"]
    # 인용의 페이지는 Citation 스키마 불변 원칙(#196)에 따라 chunk_id로 검색 청크 metadata를 조회해 결합한다.
    pages_by_chunk: dict[str, tuple[int | None, int | None]] = {}
    for item in result.get("reranked_chunks") or []:
        extra = item.chunk.metadata.model_extra or {}
        pages_by_chunk[item.chunk.chunk_id] = (extra.get("page_start"), extra.get("page_end"))

    return QueryDoneResponse(
        thread_id=thread_id,
        answer=response.answer,
        is_answerable=response.is_answerable,
        confidence=response.confidence_score,
        error_code=_derive_error_code(result.get("error_logs", [])),
        clauses=[ClauseOut(**asdict(row)) for row in build_clause_rows(result.get("reranked_chunks"))],
        citations=[
            CitationOut(
                document_id=c.document_id,
                chunk_id=c.chunk_id,
                content=c.content,
                relevance_score=c.relevance_score,
                page_start=pages_by_chunk.get(c.chunk_id, (None, None))[0],
                page_end=pages_by_chunk.get(c.chunk_id, (None, None))[1],
            )
            for c in response.citations
        ],
    )
