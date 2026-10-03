"""Runtime Guard 및 타임아웃 SSoT 계층 구조 검증 테스트"""

from unittest.mock import MagicMock, patch
import pytest
from psycopg_pool import ConnectionPool, PoolTimeout

from src.clients.llm import client as openai_client
from src.db import connection
from src.utils.config import (
    DB_POOL_TIMEOUT_SECONDS,
    EMBEDDING_BATCH_TIMEOUT_SECONDS,
    EMBEDDING_QUERY_TIMEOUT_SECONDS,
    GRAPH_STEP_TIMEOUT_SECONDS,
    LLM_MAX_RETRIES,
    LLM_TIMEOUT_SECONDS,
    SEARCH_TIMEOUT_SECONDS,
)


def test_timeout_hierarchy_invariants():
    """
    Inside-Out 타임아웃 계층 불변식을 검증한다.
    개별 I/O 타임아웃 (DB 검색 10s, DB 풀 10s, LLM 45s, 쿼리 임베딩 10s)은 반드시
    상위 LangGraph 노드 타임아웃(120s)보다 작아야 한다.
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
    assert EMBEDDING_QUERY_TIMEOUT_SECONDS < GRAPH_STEP_TIMEOUT_SECONDS, (
        f"EMBEDDING_QUERY_TIMEOUT_SECONDS({EMBEDDING_QUERY_TIMEOUT_SECONDS}) >= GRAPH_STEP_TIMEOUT_SECONDS({GRAPH_STEP_TIMEOUT_SECONDS})"
    )
    assert EMBEDDING_BATCH_TIMEOUT_SECONDS >= GRAPH_STEP_TIMEOUT_SECONDS, (
        f"EMBEDDING_BATCH_TIMEOUT_SECONDS({EMBEDDING_BATCH_TIMEOUT_SECONDS}) < GRAPH_STEP_TIMEOUT_SECONDS({GRAPH_STEP_TIMEOUT_SECONDS})"
    )


def test_embedding_client_contextual_timeout_routing(monkeypatch):
    """
    embed_texts()가 node='search'일 때는 쿼리 타임아웃(10s),
    node='index'일 때는 배치 타임아웃(120s)을 원격 클라이언트에 전달하는지 검증한다.
    """
    from src.clients import embedding, embedding_remote
    from src.utils import config

    monkeypatch.setattr(config, "EMBEDDING_SERVER_URL", "http://fake-tei:8080")

    recorded_timeouts = []

    def fake_remote_embed(texts, timeout=None):
        recorded_timeouts.append(timeout)
        return [[0.1] * 1024 for _ in texts]

    monkeypatch.setattr(embedding_remote, "embed_texts", fake_remote_embed)

    # 1. search 노드 (런타임 질의)
    embedding.embed_texts(["회계 질문"], node="search")
    assert recorded_timeouts[-1] == config.EMBEDDING_QUERY_TIMEOUT_SECONDS

    # 2. index 노드 (오프라인 배치)
    embedding.embed_texts(["청크 데이터"], node="index")
    assert recorded_timeouts[-1] == config.EMBEDDING_BATCH_TIMEOUT_SECONDS

    # 3. 명시적 timeout 전달
    embedding.embed_texts(["임의 데이터"], node="search", timeout=25.0)
    assert recorded_timeouts[-1] == 25.0


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


def test_graph_state_error_logs_capacity_and_rotation(monkeypatch):
    """GraphState error_logs가 MAX_ERROR_LOGS를 초과할 경우 FIFO 방식으로 회전하여 상한을 유지하는지 검증한다."""
    from src.models.state import GraphState, ErrorLog
    import src.utils.config as cfg
    import src.models.state as state_mod

    # 임의의 작은 상한으로 monkeypatch
    monkeypatch.setattr(cfg, "MAX_ERROR_LOGS", 3)
    monkeypatch.setattr(state_mod, "MAX_ERROR_LOGS", 3)

    logs: list[ErrorLog] = [
        {"timestamp": "2026-10-03T12:00:00+09:00", "node": "search", "error_type": "SE-101", "message": f"err {i}"}
        for i in range(5)
    ]

    state = GraphState(original_query="테스트 질의", error_logs=logs)
    assert len(state.error_logs) == 3
    # 가장 오래된 err 0, err 1은 잘리고 최신 err 2, err 3, err 4만 남아야 함
    assert [log["message"] for log in state.error_logs] == ["err 2", "err 3", "err 4"]
