# 회계 기준서 RAG MCP 서버 (FastMCP) — API 계층과 동일한 변환(to_api_response)을 재사용해
# /query·/resume에 대응하는 도구 2종을 노출한다. 실행: `uv run python -m src.mcp_server.server` (stdio).
from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from src.agent.workflow import resume_workflow, run_workflow, thread_exists
from src.api.schemas import to_api_response
from src.utils.input_limits import check_feedback_length, check_query_length

mcp = FastMCP("accounting-rag")


@mcp.tool
def query_standards(
    query: str,
    standard_filter: Literal["GAAP", "KIFRS", "ALL"] = "ALL",
) -> dict:
    """회계 기준서 질의. status=done이면 답변+인용, interrupted면 resume_query로 재개."""
    if not query.strip():
        raise ToolError("query must not be blank")
    try:
        check_query_length(query.strip())
    except ValueError as e:
        raise ToolError(str(e)) from e
    return to_api_response(run_workflow(query, standard_filter=standard_filter)).model_dump()


@mcp.tool
def resume_query(thread_id: str, action: str, feedback: str | None = None) -> dict:
    """HIL 중단 재개 — interrupted 응답의 options에서 고른 action으로 호출."""
    if feedback is not None:
        try:
            check_feedback_length(feedback)
        except ValueError as e:
            raise ToolError(str(e)) from e
    if not thread_exists(thread_id):
        raise ToolError(f"unknown thread_id: {thread_id}")
    decision: dict = {"action": action}
    if feedback is not None:
        decision["feedback"] = feedback
    return to_api_response(resume_workflow(thread_id, decision)).model_dump()


def main() -> None:
    """콘솔 스크립트 진입점. stdio 전송으로 MCP 서버를 실행한다."""
    mcp.run()


if __name__ == "__main__":
    main()
