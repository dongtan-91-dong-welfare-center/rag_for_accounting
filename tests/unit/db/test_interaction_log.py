"""
interaction_log 단위 테스트 — 운영 질의/응답 로깅

대상 모듈: src/db/interaction_log.py
검증 범위:
    - ensure_interaction_log_table(): DDL 실행, 실패 시에도 예외를 올리지 않음
    - log_interaction(): INSERT 파라미터 구성, 실패 시에도 예외를 올리지 않음(요청 경로 비차단)

DB는 vector_store 단위 테스트와 동일하게 mock으로 차단한다.
"""
from unittest.mock import MagicMock, patch

import pytest

from src.db.interaction_log import ensure_interaction_log_table, log_interaction
from src.models.schemas import Citation, EvaluationResult


@pytest.fixture
def mock_db_pool():
    with patch("src.db.interaction_log.get_pool") as mock_get_pool:
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_pool.return_value = mock_pool
        yield mock_cursor


class TestEnsureInteractionLogTable:
    def test_executes_ddl(self, mock_db_pool):
        ensure_interaction_log_table()
        sqls = " ".join(str(call.args[0]) for call in mock_db_pool.execute.call_args_list)
        assert "CREATE TABLE IF NOT EXISTS" in sqls
        assert "CREATE INDEX IF NOT EXISTS" in sqls

    def test_does_not_raise_when_ddl_fails(self):
        """DB 순단 등으로 테이블 준비가 실패해도 서버 기동을 막지 않는다."""
        with patch("src.db.interaction_log.get_pool", side_effect=RuntimeError("no pool")):
            ensure_interaction_log_table()  # 예외 없이 반환되어야 함


class TestLogInteraction:
    def test_inserts_done_interaction(self, mock_db_pool):
        log_interaction(
            thread_id="t1",
            endpoint="query",
            query="재고자산 측정",
            standard_filter="GAAP",
            status="done",
            answer="취득원가로 측정한다.",
            is_answerable=True,
            confidence=0.9,
            error_code=None,
            evaluation=EvaluationResult(
                is_relevant=True, needs_external=False, confidence=0.8, reasoning="충분함",
            ),
            citations=[
                Citation(document_id="d1", chunk_id="c1", content="본문", relevance_score=0.7),
            ],
            elapsed_ms=1234,
        )
        assert mock_db_pool.execute.call_count == 1
        args = mock_db_pool.execute.call_args.args
        assert "INSERT INTO" in str(args[0])
        params = args[1]
        assert params[0] == "t1"
        assert params[4] == "done"
        # eval_is_relevant, eval_needs_external, eval_confidence, eval_reasoning 순서로 컬럼화되어 있어야 한다
        assert params[9:13] == (True, False, 0.8, "충분함")
        assert params[13].obj == [
            {"document_id": "d1", "chunk_id": "c1", "content": "본문", "relevance_score": 0.7},
        ]

    def test_inserts_none_when_evaluation_absent(self, mock_db_pool):
        """평가가 아직 없는 경우(HIL 중단 등)에도 eval_* 컬럼은 NULL로 안전하게 들어간다."""
        log_interaction(
            thread_id="t9",
            endpoint="query",
            query="리스 회계처리",
            standard_filter=None,
            status="interrupted",
        )
        params = mock_db_pool.execute.call_args.args[1]
        assert params[9:13] == (None, None, None, None)
        assert params[13] is None

    def test_does_not_raise_when_insert_fails(self):
        """적재 실패는 예외를 올리지 않는다 — 로깅이 사용자 응답 경로를 막으면 안 된다."""
        with patch("src.db.interaction_log.get_pool", side_effect=RuntimeError("no pool")):
            log_interaction(
                thread_id="t1",
                endpoint="query",
                query="q",
                standard_filter=None,
                status="done",
            )  # 예외 없이 반환되어야 함
