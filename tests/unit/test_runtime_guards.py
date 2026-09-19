"""Runtime Guard 및 타임아웃 SSoT 계층 구조 검증 테스트"""

from unittest.mock import MagicMock, patch
import pytest
from psycopg_pool import ConnectionPool, PoolTimeout

from src.clients.llm import client as openai_client
from src.db import connection
from src.utils.config import (
    DB_POOL_TIMEOUT_SECONDS,
    GRAPH_STEP_TIMEOUT_SECONDS,
    LLM_MAX_RETRIES,
    LLM_TIMEOUT_SECONDS,
    SEARCH_TIMEOUT_SECONDS,
)


def test_timeout_hierarchy_invariants():
    """
    Inside-Out 타임아웃 계층 불변식을 검증한다.
    개별 I/O 타임아웃 (DB 검색 10s, DB 풀 10s, LLM 45s)은 반드시
    상위 LangGraph 노드 타임아웃(60s)보다 작아야 한다.
    """
    assert SEARCH_TIMEOUT_SECONDS < GRAPH_STEP_TIMEOUT_SECONDS, (
        f"SEARCH_TIMEOUT_SECONDS({SEARCH_TIMEOUT_SECONDS}) >= GRAPH_STEP_TIMEOUT_SECONDS({GRAPH_STEP_TIMEOUT_SECONDS})"
    )
    assert DB_POOL_TIMEOUT_SECONDS < GRAPH_STEP_TIMEOUT_SECONDS, (
        f"DB_POOL_TIMEOUT_SECONDS({DB_POOL_TIMEOUT_SECONDS}) >= GRAPH_STEP_TIMEOUT_SECONDS({GRAPH_STEP_TIMEOUT_SECONDS})"
    )
    assert LLM_TIMEOUT_SECONDS < GRAPH_STEP_TIMEOUT_SECONDS, (
        f"LLM_TIMEOUT_SECONDS({LLM_TIMEOUT_SECONDS}) >= GRAPH_STEP_TIMEOUT_SECONDS({GRAPH_STEP_TIMEOUT_SECONDS})"
    )


def test_openai_client_timeout_and_retries_configured():
    """OpenAI 싱글톤 클라이언트에 타임아웃과 재시도 설정이 적용되었는지 검증한다."""
    assert openai_client.timeout == LLM_TIMEOUT_SECONDS
    assert openai_client.max_retries == LLM_MAX_RETRIES


def test_init_pool_passes_timeout_guard(monkeypatch):
    """init_pool() 호출 시 ConnectionPool에 DB_POOL_TIMEOUT_SECONDS가 올바르게 주입되는지 검증한다."""
    monkeypatch.setenv("POSTGRES_PASSWORD", "dummy_pass")
    with patch("src.db.connection.ConnectionPool") as mock_pool_cls:
        connection._pool = None
        try:
            connection.init_pool()
            # assert_called_once: ConnectionPool이 한 번만 호출되었는지 확인
            mock_pool_cls.assert_called_once()  
            # DB_POOL_TIMEOUT_SECONDS가 ConnectionPool에 올바르게 주입되었는지 확인
            assert mock_pool_cls.call_args.kwargs.get("timeout") == DB_POOL_TIMEOUT_SECONDS 
        finally:
            connection._pool = None


def test_db_pool_timeout_fast_fail():
    """DB 커넥션 풀이 고갈되었을 때, 커넥션 획득 대기가 타임아웃을 초과하면 무한대기하지 않고 PoolTimeout 예외를 던지는 Fast-Fail 동작을 검증한다."""
    class MockConn:
        @classmethod
        def connect(cls, conninfo, **kwargs):
            conn = MagicMock()
            conn.closed = False
            return conn

    pool = ConnectionPool(
        "dbname=dummy",
        min_size=1,
        max_size=1,
        timeout=0.05,  # timeout: 커넥션 획득 대기 제한 시간 (초)
        connection_class=MockConn,  # ConnectionPool이 사용할 커넥션 클래스
        open=True,  # 즉시 풀을 엽니다. 
    )
    try:
        conn1 = pool.getconn()
        assert conn1 is not None    # 정상적으로 커넥션을 획득했는지 확인

        # 풀이 고갈된 상태에서 추가 커넥션 요청 시 PoolTimeout 발생 검증
        # pytest.raises: PoolTimeout 예외가 발생할 것임을 명시
        with pytest.raises(PoolTimeout):
            pool.getconn() # Pool이 고갈된 상태에서 추가 커넥션 요청 시 PoolTimeout 예외를 던짐
    finally:
        pool.close() # 테스트 후 풀을 닫는다.
