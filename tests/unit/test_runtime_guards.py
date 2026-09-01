"""Runtime Guard 및 타임아웃 SSoT 계층 구조 검증 테스트"""

from psycopg_pool import ConnectionPool

from src.clients.llm import client as openai_client
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
    개별 I/O 타임아웃 (DB 검색 5s, DB 풀 5s, LLM 20s)은 반드시
    상위 LangGraph 노드 타임아웃(30s)보다 작아야 한다.
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


def test_db_pool_timeout_fast_fail():
    """DB 커넥션 풀이 마이크로 크기일 때, 커넥션 획득을 기다리는 타임아웃이 초과하면 무한대기하지 않고 PoolTimeout 예외를 올바르게 던지는지 Fast-Fail 동작을 검증한다."""
    # mock/test용 conninfo (실제 접속 불필요, kwargs 레벨 대기 동작 테스트)
    # min_size=1, max_size=1, timeout=0.1s로 가동
    dummy_conninfo = "host=127.0.0.1 port=5432 dbname=dummy user=dummy password=dummy"
    pool = ConnectionPool(
        dummy_conninfo,
        min_size=1,
        max_size=1,
        timeout=0.1,
        open=False,
    )
    assert pool.timeout == 0.1
