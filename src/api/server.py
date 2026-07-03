"""FastAPI 서버 — 회계 기준서 RAG 워크플로의 HTTP 진입점 (#195).

CLI(src/main.py)·Streamlit(app.py)과 동일한 워크플로(run_workflow → resume_workflow)를
React 프론트엔드가 소비할 수 있게 노출한다. 응답 조립은 src/api/schemas.to_api_response가
전담하므로 이 모듈은 HTTP 관심사(검증·상태코드·CORS·lifespan)만 다룬다.

실행 (단일 워커 전제 — HIL 체크포인터가 프로세스-로컬 MemorySaver):
    uv run uvicorn src.api.server:app --host 0.0.0.0 --port 8000

엔드포인트는 async def가 아닌 일반 def로 선언한다
run_workflow는 동기·블로킹(매 호출 그래프 재컴파일 + LLM 수 초)이므로 Starlette 스레드풀에서 실행해 단일 워커의 이벤트 루프가 막히지 않게 한다.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from src.agent.workflow import resume_workflow, run_workflow, thread_exists
from src.api.schemas import WorkflowResponse, to_api_response
from src.db.connection import close_pool, init_pool
from src.utils.config import API_CORS_ORIGINS
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _warmup_embedding() -> None:
    """
    임베딩 모델을 기동 시 preload해 KURE-v1 콜드 로드(~50s)를 step_timeout(노드 30s) 밖으로 분리
    실패해도 서버를 막지 않는다 — 첫 질의가 기존 lazy 로드로 폴백한다(main.py·app.py 선례).
    """
    from src.utils.embedding import warmup_model

    try:
        warmup_model()
    except Exception as e:  # noqa: BLE001 — preload 실패는 비치명적(lazy 폴백 존재)
        logger.warning(f"임베딩 preload 실패 — 첫 질의에서 lazy 로드로 폴백: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    _warmup_embedding()
    yield
    close_pool()


app = FastAPI(title="회계 기준서 RAG API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=API_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/query", response_model=WorkflowResponse)
def query(req: QueryRequest) -> WorkflowResponse:
    """질의 실행 — 완료(done) 또는 HIL 중단(interrupted) 유니언 응답."""
    result = run_workflow(req.query, standard_filter=req.standard_filter)
    return to_api_response(result)


@app.post("/resume", response_model=WorkflowResponse)
def resume(req: ResumeRequest) -> WorkflowResponse:
    """HIL 중단 재개 — 재중단 가능(MAX_HIL_COUNT까지), 미존재 thread_id는 404."""
    if not thread_exists(req.thread_id):
        raise HTTPException(status_code=404, detail=f"unknown thread_id: {req.thread_id}")
    decision: dict = {"action": req.action}
    if req.feedback is not None:
        decision["feedback"] = req.feedback
    result = resume_workflow(req.thread_id, decision)
    return to_api_response(result)
