# MCP 서버 와이어링 단위 테스트 — 워크플로/변환은 스텁, 도구의 인자 전달·가드만 검증.
import pytest
from fastmcp.exceptions import ToolError
from pydantic import BaseModel

from src.mcp import server


class _FakeResponse(BaseModel):
    status: str = "done"
    answer: str = "stub"


@pytest.fixture
def stub_pipeline(monkeypatch):
    calls = {}

    def fake_run_workflow(query, standard_filter="ALL"):
        calls["run"] = (query, standard_filter)
        return {"sentinel": True}

    def fake_resume_workflow(thread_id, decision):
        calls["resume"] = (thread_id, decision)
        return {"sentinel": True}

    monkeypatch.setattr(server, "run_workflow", fake_run_workflow)
    monkeypatch.setattr(server, "resume_workflow", fake_resume_workflow)
    monkeypatch.setattr(server, "to_api_response", lambda result: _FakeResponse())
    return calls


def test_query_standards_returns_serialized_response(stub_pipeline):
    result = server.query_standards("리스 회계처리", standard_filter="GAAP")

    assert result == {"status": "done", "answer": "stub"}
    assert stub_pipeline["run"] == ("리스 회계처리", "GAAP")


def test_query_standards_rejects_blank_query(stub_pipeline):
    with pytest.raises(ToolError):
        server.query_standards("   ")


def test_resume_query_rejects_unknown_thread(monkeypatch, stub_pipeline):
    monkeypatch.setattr(server, "thread_exists", lambda thread_id: False)

    with pytest.raises(ToolError):
        server.resume_query("t-404", action="approve")


def test_resume_query_builds_decision_with_feedback(monkeypatch, stub_pipeline):
    monkeypatch.setattr(server, "thread_exists", lambda thread_id: True)

    result = server.resume_query("t-1", action="rewrite", feedback="조항 더")

    assert result == {"status": "done", "answer": "stub"}
    assert stub_pipeline["resume"] == ("t-1", {"action": "rewrite", "feedback": "조항 더"})
