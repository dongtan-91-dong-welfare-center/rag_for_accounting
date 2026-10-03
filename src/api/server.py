"""
FastAPI 서버 — 회계 기준서 RAG 워크플로의 HTTP 진입점

CLI와 동일한 워크플로(run_workflow → resume_workflow)를
React 프론트엔드가 소비할 수 있게 노출한다. 응답 조립은 src/api/schemas.to_api_response가
전담하므로 이 모듈은 HTTP 관심사(검증·상태코드·CORS·lifespan)만 다룬다.

실행:
    uv run uvicorn src.api.server:app --host 0.0.0.0 --port 8000

HIL 체크포인터는 PostgreSQL 기반(PostgresSaver, #209)이라 서버 재시작이나 다중 워커에도
진행 중인 HIL 세션이 유지된다.

엔드포인트는 async def가 아닌 일반 def로 선언한다
run_workflow는 동기·블로킹(매 호출 그래프 재컴파일 + LLM 수 초)이므로 Starlette 스레드풀에서 실행해 이벤트 루프가 막히지 않게 한다.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
import time
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi import Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
import psycopg
from pydantic import BaseModel, Field, field_validator

from src.agent.workflow import resume_workflow, run_workflow, thread_exists
from src.api.schemas import FeedbackResponse, QueryDoneResponse, WorkflowResponse, to_api_response
from src.db.answer_feedback import ensure_answer_feedback_table, save_feedback
from src.db.connection import close_checkpointer_pool, close_pool, get_pool, init_pool
from src.db.interaction_log import ensure_interaction_log_table, log_interaction
from src.ingest.parse.page_map import resolve_pdf_path
from src.utils.config import API_CORS_ORIGINS, EMBEDDING_SERVER_URL, PDF_DIR, READINESS_PROBE_TIMEOUT_SECONDS
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _warmup_embedding() -> None:
    """
    임베딩·리랭커 모델을 기동 시 preload해 콜드 로드를 step_timeout(노드 30s) 밖으로 분리한다.

    KURE-v1(~50s)·bge-reranker-v2-m3(~2.2GB) 콜드 로드가 첫 질의 노드 안에서 일어나면 step_timeout을
    넘겨 첫 질의가 타임아웃 폴백으로 실패할 수 있다. 기동 때 미리 데워 이를 막는다.
    리랭커는 USE_RERANKER가 켜져 있을 때만 로드한다(warmup_reranker 내부 가드).
    어느 preload가 실패해도 서버를 막지 않는다 — 첫 질의가 기존 lazy 로드로 폴백한다.
    """
    from src.clients.embedding import warmup_model
    from src.retrieval.reranker import warmup_reranker

    try:
        warmup_model()
    except Exception as e:  # noqa: BLE001 — preload 실패는 비치명적(lazy 폴백 존재)
        logger.warning(f"임베딩 preload 실패 — 첫 질의에서 lazy 로드로 폴백: {e}")

    try:
        warmup_reranker()
    except Exception as e:  # noqa: BLE001 — preload 실패는 비치명적(lazy 폴백 존재)
        logger.warning(f"리랭커 preload 실패 — 첫 질의에서 lazy 로드로 폴백: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    ensure_interaction_log_table()
    ensure_answer_feedback_table()
    _warmup_embedding()
    yield
    close_pool()
    close_checkpointer_pool()


def _record_interaction(
    *,
    endpoint: str,
    query_text: str,
    standard_filter: str | None,
    response: WorkflowResponse,
    result: dict,
    elapsed_ms: int,
) -> None:
    """/query·/resume 응답 1건을 interaction_log에 남긴다.

    이 함수의 실패는 log_interaction 내부에서 이미 흡수되므로, 
    호출자(엔드포인트)는 로깅 실패를 신경 쓸 필요 없이 항상 정상 응답을 반환한다.
    """
    if isinstance(response, QueryDoneResponse):
        evaluation = result.get("evaluation")
        log_interaction(
            thread_id=response.thread_id,
            endpoint=endpoint,
            query=query_text,
            standard_filter=standard_filter,
            status="done",
            answer=response.answer,
            is_answerable=response.is_answerable,
            confidence=response.confidence,
            error_code=response.error_code,
            evaluation=evaluation,
            citations=response.citations,
            elapsed_ms=elapsed_ms,
        )
    else:
        log_interaction(
            thread_id=response.thread_id,
            endpoint=endpoint,
            query=query_text,
            standard_filter=standard_filter,
            status="interrupted",
            elapsed_ms=elapsed_ms,
        )


app = FastAPI(title="회계 기준서 RAG API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=API_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIST_DIR = Path(os.getenv("FRONTEND_DIST_DIR", "frontend/dist"))
FRONTEND_INDEX = FRONTEND_DIST_DIR / "index.html"

if (FRONTEND_DIST_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="assets")


class QueryRequest(BaseModel):
    """질의 요청. 빈 질의(공백만 포함)는 워크플로 진입 전에 422로 거절한다."""

    query: str = Field(min_length=1)
    standard_filter: Literal["GAAP", "KIFRS", "ALL"] = "ALL"

    @field_validator("query", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


class ResumeRequest(BaseModel):
    """HIL 재개 요청 — action은 interrupt 응답 options의 action과 대응한다."""

    thread_id: str
    action: Literal["approve", "rewrite"]
    feedback: str | None = None


class FeedbackRequest(BaseModel):
    """답변 평가 요청(#300) — thread_id는 /query 응답의 것을 그대로 돌려보낸다."""

    thread_id: str = Field(min_length=1)
    rating: Literal["up", "down"]
    reason: str | None = Field(default=None, max_length=2000)

    @field_validator("reason", mode="before")
    @classmethod
    def _strip_reason(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


@app.get("/health")
def health() -> dict[str, str]:
    """라이브니스: 프로세스가 응답하는지만 확인한다. 외부 의존성은 점검하지 않는다."""
    return {"status": "ok"}


def _check_database() -> None:
    """DB에 실제로 질의를 보낼 수 있는지 확인한다. 실패하면 예외를 던진다."""
    with get_pool().connection(timeout=READINESS_PROBE_TIMEOUT_SECONDS) as conn:
        conn.execute("SELECT 1")


def _check_embedding() -> str:
    """원격 임베딩 서버(TEI)의 /health 도달성을 확인한다. 로컬 임베딩 구성이면 점검 대상이 아니다."""
    if not EMBEDDING_SERVER_URL:
        return "skipped"
    httpx.get(f"{EMBEDDING_SERVER_URL}/health", timeout=READINESS_PROBE_TIMEOUT_SECONDS).raise_for_status()
    return "ok"


def _run_check(check) -> str:
    try:
        return check() or "ok"
    except Exception as e:  # noqa: BLE001 — 점검 실패는 상태 문자열로 보고하며 서버를 죽이지 않는다
        return f"fail: {type(e).__name__}"


@app.get("/ready")
def ready() -> JSONResponse:
    """
    준비성: 지금 질의를 받아도 되는지 확인한다. DB 또는 임베딩 서버에 닿지 않으면 503을 돌려준다.

    /health(라이브니스)와 분리한 이유: DB 장애로 컨테이너를 재시작해도 해결되지 않으므로,
    라이브니스까지 실패시키면 불필요한 재시작 루프가 생긴다.
    """
    checks = {"database": _run_check(_check_database), "embedding": _run_check(_check_embedding)}
    ok = not any(v.startswith("fail") for v in checks.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ready" if ok else "not_ready", "checks": checks},
    )


@app.post("/query", response_model=WorkflowResponse)
def query(req: QueryRequest) -> WorkflowResponse:
    """질의 실행 — 완료(done) 또는 HIL 중단(interrupted) 유니언 응답."""
    start = time.perf_counter()
    result = run_workflow(req.query, standard_filter=req.standard_filter)
    response = to_api_response(result)
    _record_interaction(
        endpoint="query",
        query_text=req.query,
        standard_filter=req.standard_filter,
        response=response,
        result=result,
        elapsed_ms=round((time.perf_counter() - start) * 1000),
    )
    return response


@app.post("/resume", response_model=WorkflowResponse)
def resume(req: ResumeRequest) -> WorkflowResponse:
    """HIL 중단 재개 — 재중단 가능(MAX_HIL_COUNT까지), 미존재 thread_id는 404, DB 장애 시 503."""
    try:
        exists = thread_exists(req.thread_id)
    except psycopg.Error as e:
        logger.error(f"HIL 세션 확인 중 DB 오류 발생: thread_id={req.thread_id}, {e}")
        raise HTTPException(
            status_code=503,
            detail="데이터베이스 연결 장애로 세션을 조회할 수 없습니다.",
        ) from e

    if not exists:
        raise HTTPException(status_code=404, detail=f"unknown thread_id: {req.thread_id}")

    decision: dict = {"action": req.action}
    if req.feedback is not None:
        decision["feedback"] = req.feedback
    start = time.perf_counter()
    try:
        result = resume_workflow(req.thread_id, decision)
    except psycopg.Error as e:
        logger.error(f"HIL 세션 재개 중 DB 오류 발생: thread_id={req.thread_id}, {e}")
        raise HTTPException(
            status_code=503,
            detail="데이터베이스 연결 장애로 세션을 재개할 수 없습니다.",
        ) from e

    response = to_api_response(result)
    _record_interaction(
        endpoint="resume",
        query_text=req.feedback or f"[resume:{req.action}]",
        standard_filter=None,
        response=response,
        result=result,
        elapsed_ms=round((time.perf_counter() - start) * 1000),
    )
    return response


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(req: FeedbackRequest) -> FeedbackResponse:
    """답변 평가 저장 — 저장 실패는 사용자가 알 수 있도록 503으로 알린다."""
    try:
        save_feedback(thread_id=req.thread_id, rating=req.rating, reason=req.reason)
    except Exception as e:  # noqa: BLE001 — DB 오류 종류와 무관하게 503으로 변환
        logger.error(f"answer_feedback 저장 실패: thread_id={req.thread_id}, {e}")
        raise HTTPException(status_code=503, detail="feedback not saved") from e
    return FeedbackResponse()


@app.get("/documents/{document_id}/pdf")
@app.head("/documents/{document_id}/pdf")  # 뷰어(checkPdfAvailable)의 제공 여부 확인 — Starlette 1.x는 HEAD 자동 등록이 없다
def document_pdf(
    document_id: str = PathParam(pattern=r"^[a-z0-9-]+$"),  # 경로 탈출(..%2F 등) 라우팅 단계 차단
) -> FileResponse:
    """
    원문 PDF 서빙 — 파일 경로는 resolve_pdf_path(document_id, PDF_DIR)로 찾는다.
    이 프로젝트는 저작권 문제로 원문 PDF를 리포지토리에 넣지 않고 사용자가 직접 준비해 PDF_DIR에 두는 방식을 쓰므로, 파일이 이 규칙대로 놓여 있어야 조회에 성공한다.

    파일이 없거나 매핑이 모호하면 404를 반환한다 — 이 경우 React 뷰어는 PDF 보기 버튼 대신 안내 메시지를 보여주는 것으로 처리를 끝낸다.
    """
    pdf_path = resolve_pdf_path(document_id, PDF_DIR)
    if pdf_path is None:
        raise HTTPException(status_code=404, detail=f"no pdf for document_id: {document_id}")
    # filename을 넘기면 Starlette이 표지를 attachment로 기본 설정해 뷰어 iframe이 PDF를 표시하지 못한다
    # inline으로 명시해 화면 표시를 되살린다
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
        content_disposition_type="inline",
    )


@app.get("/favicon.svg")
def favicon() -> FileResponse:
    favicon_path = FRONTEND_DIST_DIR / "favicon.svg"
    if not favicon_path.exists():
        raise HTTPException(status_code=404, detail="favicon not found")
    return FileResponse(favicon_path, media_type="image/svg+xml")


@app.get("/")
@app.get("/{full_path:path}")
def frontend_app(full_path: str = "") -> FileResponse:
    """React SPA fallback for the integrated app image."""
    if not FRONTEND_INDEX.exists():
        raise HTTPException(status_code=404, detail="frontend build not found")
    return FileResponse(FRONTEND_INDEX)
