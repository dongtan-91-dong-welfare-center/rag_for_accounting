"""
API 경로 HIL 왕복 라이브 스모크

test_hil_live_resume.py와 동일한 라이브 경로(실 LLM 분류 → interrupt → approve → 완료)를 HTTP 계층에서 검증한다:
FastAPI TestClient가 실제 lifespan(풀 초기화·임베딩 워밍업)을 실행하고, /query의 interrupted 유니언 응답 → /resume(approve) → done 응답(조항·답변)을 단언한다.

@pytest.mark.benchmark 게이트(라이브 LLM+Docker
 — tests/integration/conftest.py의 check_integration_env가 키/인프라 부재 시 세션 skip 한다.
워크플로 로직 자체의 검증은 test_hil_live_resume.py 책임이고, 본 스모크의 책임은 API 계약(유니언 스키마·상태코드)과 서버 lifespan 경로다.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.db.connection import close_pool, init_pool
from tests.utils.benchmark_metrics import get_indexed_chapters

# test_hil_live_resume.py의 HIL-DECOMPOSE-001과 동일 설계 — 두 독립 회계 주제로 decompose 유도
DECOMPOSE_QUERY = (
    "K-GAAP에서 유형자산 재평가잉여금을 처분할 때의 회계처리와, "
    "매도가능증권 중 지분상품을 처분할 때 평가손익 처리 방법을 각각 알려주세요."
)


@pytest.fixture(scope="module")
def api_client():
    """chunks 적재를 확인한 뒤 실제 lifespan(init_pool·임베딩 워밍업)으로 TestClient를 연다.

    검색이 chunks 테이블을 읽으므로 미적재면 UndefinedTable로 죽는다 — 확인 후 skip.
    확인용 풀은 닫는다(lifespan이 멱등 init_pool로 다시 연다).
    """
    try:
        init_pool()
    except Exception as e:
        pytest.skip(f"커넥션 풀 초기화 불가 — 라이브 스모크 skip ({e})")
    try:
        if not get_indexed_chapters():
            pytest.skip("chunks 미적재 — 수동 ingest 선행 필요")
    finally:
        close_pool()

    from src.api.server import app

    with TestClient(app) as client:
        yield client


@pytest.mark.benchmark
def test_api_hil_roundtrip_live(api_client):
    """/query interrupted → /resume(approve) → done — HIL 왕복 1건(API 경로)."""
    # 1) 질의: decompose 분류 → interrupted 유니언 응답
    r = api_client.post("/query", json={"query": DECOMPOSE_QUERY, "standard_filter": "GAAP"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "interrupted", (
        f"interrupt 미발생 — 전략 유도 실패(라이브 분류 변동 가능). body={body}"
    )
    interrupt = body["interrupt"]
    assert interrupt["strategy"] == "decompose"
    assert {o["action"] for o in interrupt["options"]} == {"approve", "rewrite"}
    thread_id = body["thread_id"]
    assert thread_id

    # 2) approve 재개: done 응답 + 조항·답변 (React UI 표시 항목의 API 근거)
    r = api_client.post("/resume", json={"thread_id": thread_id, "action": "approve"})
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["status"] == "done", f"resume 후에도 done이 아님: {done.get('status')}"
    assert done["thread_id"] == thread_id
    assert done["answer"].strip(), "answer가 비어 있음"
    assert done["clauses"], "검색 조항이 비어 있음 — chunks 적재 상태에서 top-k는 비지 않아야 한다"
    assert done["error_code"] is None
