# 회계 기준서 RAG MCP 서버 (FastMCP) — API 계층과 동일한 변환(to_api_response)을 재사용해
# /query·/resume에 대응하는 도구 2종을 노출한다. 실행: `uv run python -m src.mcp.server` (stdio).
from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from src.agent.workflow import resume_workflow, run_workflow, thread_exists
from src.api.schemas import to_api_response

mcp = FastMCP("accounting-rag")


@mcp.tool
def query_standards(
    query: str,
    standard_filter: Literal["GAAP", "KIFRS", "ALL"] = "ALL",
) -> dict:
    """회계 기준서 질의. status=done이면 답변+인용, interrupted면 resume_query로 재개."""
    if not query.strip():
        raise ToolError("query must not be blank")
    return to_api_response(run_workflow(query, standard_filter=standard_filter)).model_dump()


@mcp.tool
def resume_query(thread_id: str, action: str, feedback: str | None = None) -> dict:
    """HIL 중단 재개 — interrupted 응답의 options에서 고른 action으로 호출."""
    if not thread_exists(thread_id):
        raise ToolError(f"unknown thread_id: {thread_id}")
    decision: dict = {"action": action}
    if feedback is not None:
        decision["feedback"] = feedback
    return to_api_response(resume_workflow(thread_id, decision)).model_dump()


if __name__ == "__main__":
    mcp.run()
