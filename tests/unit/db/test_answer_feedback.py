"""
answer_feedback 단위 테스트 — 실사용 답변 평가 저장 (#300)

대상 모듈: src/db/answer_feedback.py
검증 범위:
    - ensure_answer_feedback_table(): 멱등 DDL(IF NOT EXISTS) 실행, 실패 시에도 예외를 올리지 않음
    - save_feedback(): INSERT 파라미터 구성, 실패 시 예외 전파(사용자에게 저장 실패를 알려야 하므로)
"""
from unittest.mock import MagicMock, patch

import pytest

from src.db.answer_feedback import ensure_answer_feedback_table, save_feedback

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_db_pool():
    with patch("src.db.answer_feedback.get_pool") as mock_get_pool:
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_pool.return_value = mock_pool
        yield mock_cursor


class TestEnsureTable:
    def test_executes_idempotent_ddl(self, mock_db_pool):
        ensure_answer_feedback_table()
        sqls = " ".join(str(c.args[0]) for c in mock_db_pool.execute.call_args_list)
        assert "CREATE TABLE IF NOT EXISTS" in sqls
        assert "CREATE INDEX IF NOT EXISTS" in sqls

    def test_does_not_raise_when_ddl_fails(self):
        with patch("src.db.answer_feedback.get_pool", side_effect=RuntimeError("no pool")):
            ensure_answer_feedback_table()


class TestSaveFeedback:
    def test_inserts_params(self, mock_db_pool):
        save_feedback(thread_id="t1", rating="down", reason="조항이 틀림")
        mock_db_pool.execute.assert_called_once()
        params = mock_db_pool.execute.call_args.args[1]
        assert params == ("t1", "down", "조항이 틀림")

    def test_reason_optional(self, mock_db_pool):
        save_feedback(thread_id="t1", rating="up")
        assert mock_db_pool.execute.call_args.args[1] == ("t1", "up", None)

    def test_raises_when_insert_fails(self):
        with patch("src.db.answer_feedback.get_pool", side_effect=RuntimeError("no pool")):
            with pytest.raises(RuntimeError):
                save_feedback(thread_id="t1", rating="up")
