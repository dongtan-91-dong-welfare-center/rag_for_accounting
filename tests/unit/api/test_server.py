"""src/api/server.py — FastAPI 계약 테스트.

워크플로·DB 풀·임베딩 워밍업은 모킹하고 HTTP 계약(상태코드·유니언 스키마)만 검증한다:
done/interrupted 스키마 · resume 왕복(재중단 포함) · 타임아웃 폴백 error_code ·
미존재 thread_id 404 · 빈 질의 422 · 비회계 조기종료.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from langgraph.types import Interrupt

from src.models.schemas import FinalResponse

DONE_KEYS = {
    "status",
    "thread_id",
    "answer",
    "is_answerable",
    "confidence",
    "error_code",
    "clauses",
    "citations",
}

INTERRUPT_PAYLOAD = {
    "type": "human_review",
    "strategy": "decompose",
    "original_query": "리스 회계처리",
    "search_queries": ["리스 인식", "리스 측정"],
    "hil_count": 0,
    "max_hil_count": 5,
    "options": [
        {"action": "approve", "label": "이대로 검색을 진행합니다"},
        {"action": "rewrite", "label": "재작성을 요청합니다 (피드백 입력)"},
    ],
}

TIMEOUT_LOG = {
    "timestamp": "2026-07-04T21:00:00+09:00",
    "node": "workflow",
    "error_type": "TIMEOUT",
    "message": "노드 실행이 step_timeout을 초과했습니다.",
}


def _done_result(thread_id="t1", **overrides) -> dict:
    """run_workflow/resume_workflow 완료 반환 dict의 최소 형태."""
    result = {
        "thread_id": thread_id,
        "final_response": FinalResponse(
            answer="재고자산은 취득원가로 측정한다.",
            citations=[],
            is_answerable=True,
            confidence_score=0.9,
        ),
        "reranked_chunks": [],
        "error_logs": [],
    }
    result.update(overrides)
    return result


def _interrupted_result(thread_id="t9") -> dict:
    return {"thread_id": thread_id, "__interrupt__": [Interrupt(value=INTERRUPT_PAYLOAD)]}


@pytest.fixture
def client(monkeypatch):
    """lifespan의 DB 풀 초기화·임베딩 워밍업을 무력화한 TestClient."""
    monkeypatch.setattr("src.api.server.init_pool", lambda: None)
    monkeypatch.setattr("src.api.server.close_pool", lambda: None)
    monkeypatch.setattr("src.api.server._warmup_embedding", lambda: None)
    from src.api.server import app

    with TestClient(app) as c:
        yield c


class TestQuery:
    def test_done_schema_and_workflow_args(self, client, monkeypatch):
        """완료 응답은 done 유니언 스키마이며, 질의·기준 필터가 워크플로에 그대로 전달된다."""
        captured = {}

        def fake_run(query, standard_filter="ALL"):
            captured["args"] = (query, standard_filter)
            return _done_result()

        monkeypatch.setattr("src.api.server.run_workflow", fake_run)
        r = client.post("/query", json={"query": "재고자산 측정", "standard_filter": "GAAP"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "done"
        assert set(body) == DONE_KEYS
        assert body["error_code"] is None
        assert captured["args"] == ("재고자산 측정", "GAAP")

    def test_interrupted_schema(self, client, monkeypatch):
        """HIL 중단 시 interrupted 유니언 스키마 — interrupt 노출 필드는 계약 4종."""
        monkeypatch.setattr("src.api.server.run_workflow", lambda q, standard_filter="ALL": _interrupted_result())
        r = client.post("/query", json={"query": "리스 회계처리"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "interrupted"
        assert body["thread_id"] == "t9"
        assert set(body["interrupt"]) == {"strategy", "original_query", "search_queries", "options"}

    def test_empty_query_is_422(self, client):
        """빈 질의(공백만 포함)는 워크플로 진입 전에 422로 거절한다."""
        assert client.post("/query", json={"query": ""}).status_code == 422
        assert client.post("/query", json={"query": "   "}).status_code == 422

    def test_timeout_fallback_returns_200_with_error_code(self, client, monkeypatch):
        """#131 타임아웃 폴백은 5xx가 아니라 200 done + error_code="TIMEOUT"이다."""
        fallback = _done_result(
            final_response=FinalResponse(
                answer="처리 시간이 초과되어 답변을 생성하지 못했습니다. 잠시 후 다시 시도해주세요.",
                citations=[],
                is_answerable=False,
                confidence_score=0.0,
            ),
            error_logs=[TIMEOUT_LOG],
        )
        monkeypatch.setattr("src.api.server.run_workflow", lambda q, standard_filter="ALL": fallback)
        r = client.post("/query", json={"query": "아주 오래 걸리는 질의"})
        assert r.status_code == 200
        body = r.json()
        assert body["error_code"] == "TIMEOUT"
        assert body["is_answerable"] is False

    def test_non_accounting_early_exit(self, client, monkeypatch):
        """비회계 질의 조기종료도 정상 done 응답이다(error_code 없음, 안내 answer)."""
        early = _done_result(
            final_response=FinalResponse(
                answer="죄송합니다. 회계 관련 질문을 해 주세요.",
                citations=[],
                is_answerable=False,
                confidence_score=0.97,
            ),
        )
        monkeypatch.setattr("src.api.server.run_workflow", lambda q, standard_filter="ALL": early)
        body = client.post("/query", json={"query": "오늘 점심 메뉴 추천"}).json()
        assert body["status"] == "done"
        assert body["is_answerable"] is False
        assert body["error_code"] is None


class TestResume:
    def test_resume_approve_roundtrip(self, client, monkeypatch):
        """approve 재개 — 결정 dict가 human_review 계약({"action": "approve"})으로 전달된다."""
        captured = {}

        def fake_resume(thread_id, resume_value):
            captured["args"] = (thread_id, resume_value)
            return _done_result(thread_id=thread_id)

        monkeypatch.setattr("src.api.server.thread_exists", lambda tid: True)
        monkeypatch.setattr("src.api.server.resume_workflow", fake_resume)
        r = client.post("/resume", json={"thread_id": "t9", "action": "approve"})
        assert r.status_code == 200
        assert r.json()["status"] == "done"
        assert r.json()["thread_id"] == "t9"
        assert captured["args"] == ("t9", {"action": "approve"})

    def test_resume_rewrite_carries_feedback_and_can_reinterrupt(self, client, monkeypatch):
        """rewrite 재개는 feedback을 싣고, 재중단되면 다시 interrupted 스키마다(MAX_HIL_COUNT까지)."""
        captured = {}

        def fake_resume(thread_id, resume_value):
            captured["args"] = (thread_id, resume_value)
            return _interrupted_result(thread_id=thread_id)

        monkeypatch.setattr("src.api.server.thread_exists", lambda tid: True)
        monkeypatch.setattr("src.api.server.resume_workflow", fake_resume)
        r = client.post(
            "/resume",
            json={"thread_id": "t9", "action": "rewrite", "feedback": "리스 회계처리를 강조해줘"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "interrupted"
        assert captured["args"] == ("t9", {"action": "rewrite", "feedback": "리스 회계처리를 강조해줘"})

    def test_unknown_thread_id_is_404(self, client, monkeypatch):
        """미존재 thread_id는 재개 전에 404 — resume_workflow는 호출되지 않는다."""
        monkeypatch.setattr("src.api.server.thread_exists", lambda tid: False)
        monkeypatch.setattr(
            "src.api.server.resume_workflow",
            lambda *a, **kw: pytest.fail("resume_workflow must not be called for unknown thread"),
        )
        r = client.post("/resume", json={"thread_id": "no-such-thread", "action": "approve"})
        assert r.status_code == 404


def test_thread_exists_false_for_unknown_thread():
    """404 가드의 근거 계약 — 체크포인터에 없는 thread_id는 False다(실제 MemorySaver 조회)."""
    from src.agent.workflow import thread_exists

    assert thread_exists(str(uuid.uuid4())) is False
