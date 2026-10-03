"""
HIL 세션 지속성 및 다중 워커 교차 재개 검증 (#299)

HIL 체크포인터가 PostgresSaver(#209)로 이관됨에 따라:
1. 다중 워커 환경에서 세션 공유 및 교차 승인 정상 동작
2. 서버 재시작(인스턴스 재생성) 시 기존 HIL 세션 복원 및 지속성 유지
3. 외부 저장소(PostgreSQL) 일시적 연결 장애 시의 예외 처리(503 Fast-Fail)
를 검증한다.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import psycopg
import pytest
from langgraph.checkpoint.postgres import PostgresSaver

import src.agent.workflow as workflow_module
from src.agent.workflow import (
    build_workflow,
    resume_workflow,
    run_workflow,
    thread_exists,
)
from src.db.connection import (
    close_checkpointer_pool,
    get_checkpointer_pool,
    init_pool,
    close_pool,
)
from src.models.schemas import EvaluationResult, LLMInternalResponse, RetrievedChunk
from src.models.state import GraphState


@pytest.fixture(scope="module")
def hil_db_setup():
    """테스트 실행 전 DB 풀 및 PostgresSaver 테이블을 준비하고 종료 시 정리한다."""
    try:
        init_pool()
        saver = PostgresSaver(get_checkpointer_pool())
        saver.setup()
    except Exception as e:
        pytest.skip(f"PostgreSQL 연결 불가 — HIL 지속성 통합 테스트 skip: {e}")
    yield
    close_checkpointer_pool()
    close_pool()


@pytest.fixture
def clean_thread_id(hil_db_setup):
    """각 테스트마다 고유 thread_id를 발급하고 종료 시 DB 체크포인트를 정리한다."""
    tid = f"test-hil-{uuid.uuid4()}"
    yield tid
    try:
        pool = get_checkpointer_pool()
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s;", (tid,))
            cur.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s;", (tid,))
            cur.execute("DELETE FROM checkpoints WHERE thread_id = %s;", (tid,))
    except Exception:
        pass


@pytest.fixture
def mock_external_nodes():
    """HIL 세션 영속성 검증에 집중할 수 있도록 외부 LLM/Search 노드를 격리한다."""
    mock_chunk = RetrievedChunk(
        chunk_id="chunk-test-1",
        document_id="DOC-HIL-001",
        content="재평가잉여금은 기타포괄손익누계액으로 처리한다.",
        score=0.95,
        metadata={},
    )
    with (
        patch("src.agent.nodes.rewrite.classify_and_select") as mock_classify,
        patch("src.agent.nodes.rewrite.client") as mock_client,
        patch("src.agent.workflow._search_impl") as mock_search,
        patch("src.agent.nodes.evaluate._execute_evaluator_llm") as mock_eval_llm,
        patch("src.agent.nodes.generate._execute_generator_llm") as mock_gen_llm,
    ):
        # 1. rewrite: decompose 전략으로 분류하여 human_review에서 interrupt 발생 유도
        mock_classify.return_value = (True, "decompose", 0.9, "accounting")
        decompose_resp = MagicMock()
        decompose_resp.choices[0].message.content = '{"sub_queries": ["재평가잉여금 회계처리는?", "매도가능증권 처분손익은?"]}'
        mock_client.chat.completions.create.return_value = decompose_resp

        # 2. search: 모의 검색 청크 반환
        mock_search.return_value = [mock_chunk]

        # 3. evaluate: pass 판정
        mock_eval_llm.return_value = (
            EvaluationResult(
                is_relevant=True,
                needs_external=False,
                confidence=0.95,
                reasoning="검색된 청크가 질의에 충분히 부합함",
            ),
            [],
        )

        # 4. generate: 최종 답변
        mock_gen_llm.return_value = LLMInternalResponse(
            answer="재평가잉여금은 기타포괄손익누계액으로 표시합니다 [1].",
            is_answerable=True,
            llm_self_score=0.95,
        )

        yield


@pytest.mark.system
class TestHILSessionPersistence:
    """PostgreSQL 기반 HIL 체크포인트 지속성 및 다중 워커 동작 검증."""

    def test_cross_worker_hil_resume(self, clean_thread_id, mock_external_nodes):
        """
        [DoD 1] 다중 워커 교차 재개:
        워커 1에서 생성되어 interrupt된 HIL 세션을 워커 2가 전달받아 정상 재개 및 완료한다.
        """
        thread_id = clean_thread_id

        # Worker 1 인스턴스 생성 및 실행 -> human_review interrupt 진입
        pool1 = get_checkpointer_pool()
        saver1 = PostgresSaver(pool1)
        worker1_app = build_workflow(checkpointer=saver1)

        result_w1 = worker1_app.invoke(
            GraphState(original_query="재평가잉여금과 매도가능증권 처분손익 회계처리"),
            config=workflow_module._run_config(thread_id),
        )

        assert "__interrupt__" in result_w1, "Worker 1 실행 결과에 interrupt가 발생해야 합니다."
        interrupt_val = result_w1["__interrupt__"][0].value
        assert interrupt_val["strategy"] == "decompose"

        # Worker 2: 독립된 앱 및 체크포인터 인스턴스
        pool2 = get_checkpointer_pool()
        saver2 = PostgresSaver(pool2)
        worker2_app = build_workflow(checkpointer=saver2)

        # Worker 2에서 동일 thread_id의 존재 여부 확인
        assert saver2.get(workflow_module._run_config(thread_id)) is not None

        # Worker 2에서 승인(approve)으로 워크플로 재개
        from langgraph.types import Command
        result_w2 = worker2_app.invoke(
            Command(resume={"action": "approve"}),
            config=workflow_module._run_config(thread_id),
        )

        assert "__interrupt__" not in result_w2, "Worker 2 재개 후에는 interrupt가 해소되어야 합니다."
        assert result_w2.get("final_response") is not None, "Worker 2 재개 후 최종 답변이 생성되어야 합니다."
        assert "재평가잉여금" in result_w2["final_response"].answer

    def test_server_restart_hil_persistence(self, clean_thread_id, mock_external_nodes):
        """
        [DoD 2] 서버 재시작 세션 유지:
        HIL interrupt 발생 후 애플리케이션 싱글턴/커넥션 풀을 리셋(서버 재시작 모사)해도
        동일한 thread_id로 세션을 복원하고 정상 재개할 수 있다.
        """
        thread_id = clean_thread_id

        # 1. 서버 실행 중 첫 질의 요청 -> interrupt 발생
        run_res = run_workflow(
            query="재평가잉여금과 매도가능증권 처분손익 회계처리",
            thread_id=thread_id,
        )
        assert "__interrupt__" in run_res
        assert thread_exists(thread_id) is True

        # 2. 서버 재시작 모사: 전역 체크포인터 싱글턴 해제 및 커넥션 풀 재시작
        close_checkpointer_pool()
        workflow_module._checkpointer = None

        # 3. 재시작된 새 서버 환경에서 세션 존재 확인
        assert thread_exists(thread_id) is True

        # 4. 재시작된 새 서버 환경에서 resume_workflow 호출 -> 완료 확인
        resume_res = resume_workflow(
            thread_id=thread_id,
            resume_value={"action": "approve"},
        )
        assert "__interrupt__" not in resume_res
        assert resume_res.get("final_response") is not None
        assert "재평가잉여금" in resume_res["final_response"].answer


@pytest.mark.system
class TestHILDatabaseFailureHandling:
    """[DoD 3] PostgreSQL 장애 시 예외 발생 및 Fast-Fail 검증."""

    def test_thread_exists_raises_on_db_disconnect(self, monkeypatch):
        """DB 연결 단절 시 thread_exists는 psycopg.OperationalError 등을 상위로 전달(Fast-Fail)한다."""
        fake_saver = MagicMock()
        fake_saver.get.side_effect = psycopg.OperationalError("PostgreSQL connection lost")
        monkeypatch.setattr(workflow_module, "_get_checkpointer", lambda: fake_saver)

        with pytest.raises(psycopg.OperationalError, match="PostgreSQL connection lost"):
            thread_exists("any-thread-id")

    def test_resume_endpoint_returns_503_on_db_error(self, monkeypatch):
        """API /resume 엔드포인트는 DB 장애 시 상태 왜곡 없이 503(Service Unavailable)을 반환한다."""
        from fastapi.testclient import TestClient
        from src.api.server import app

        monkeypatch.setattr(
            "src.api.server.thread_exists",
            MagicMock(side_effect=psycopg.OperationalError("DB down")),
        )

        client = TestClient(app)
        response = client.post("/resume", json={"thread_id": "test-t1", "action": "approve"})
        assert response.status_code == 503
        assert response.json()["detail"] == "데이터베이스 연결 장애로 세션을 조회할 수 없습니다."
