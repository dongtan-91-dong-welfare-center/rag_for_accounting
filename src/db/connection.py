# psycopg3의 ConnectionPool을 싱글톤으로 제공한다.
# 환경변수에서 접속 정보를 읽어 Docker 및 로컬 환경 모두 대응한다.

import logging
import os
import threading

from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo
from psycopg_pool import ConnectionPool

from src.utils.config import DB_CONNECT_TIMEOUT_SECONDS, DB_POOL_TIMEOUT_SECONDS
from src.utils.exception import ConfigNotFoundError
from src.utils.logger import get_logger, log_kv

load_dotenv()
logger = get_logger(__name__)

_pool: ConnectionPool | None = None # 전역 커넥션 풀
_lock = threading.Lock()    # init_pool()·close_pool()이 전역 _pool을 동시에 건드리지 않도록 보호

_checkpointer_pool: ConnectionPool | None = None # HIL 체크포인터(PostgresSaver) 전용 커넥션 풀(#209)
_checkpointer_pool_lock = threading.Lock()


def _build_conninfo() -> str:
    """환경변수(POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)에서
    접속 정보를 읽어 conninfo 문자열을 만든다. init_pool()과 get_checkpointer_pool()이 공유한다.

    POSTGRES_PASSWORD 미설정 시 ConfigNotFoundError로 조기 실패한다. 기본값으로 접속을
    시도하다 "인증 실패"로 둔갑하는 것을 방지한다. make_conninfo()가 값에 포함된
    공백·특수문자(`=`, `'`, `\\` 등)를 자동 이스케이프한다.
    """
    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise ConfigNotFoundError(
            "POSTGRES_PASSWORD 환경변수가 설정되지 않았습니다.", node="search"
        )
    return make_conninfo(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "accounting_db"),
        user=os.getenv("POSTGRES_USER", "accounting_user"),
        password=password,
        connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
    )


def init_pool() -> None:
    """
    커넥션 풀을 명시적으로 초기화한다. 앱 시작 시 단 1회 호출한다.

    - _lock으로 보호해 멀티스레드 환경에서 풀이 두 번 생성되지 않도록 하며,
      이중 호출 시에는 아무 동작도 하지 않는다(idempotent).
    - timeout=DB_POOL_TIMEOUT_SECONDS 가드로 풀 고갈 시 무한 대기를 막고 Fast-Fail한다.
    """
    global _pool
    with _lock:
        if _pool is not None:
            return

        _pool = ConnectionPool(
            _build_conninfo(),
            min_size=2,
            max_size=10,
            timeout=DB_POOL_TIMEOUT_SECONDS,
            open=True,
        )
        log_kv(logger, logging.INFO, "db", "PostgreSQL 커넥션 풀 초기화 완료")


def get_checkpointer_pool() -> ConnectionPool:
    """HIL 체크포인터(PostgresSaver) 전용 커넥션 풀을 지연 초기화하여 반환한다(#209).

    PostgresSaver.setup()은 내부적으로 CREATE INDEX CONCURRENTLY를 실행하는데, 이는
    트랜잭션 블록 안에서는 실행할 수 없다. get_pool()의 메인 풀은 쿼리마다 트랜잭션을
    열고 커밋하므로 공유할 수 없어, autocommit=True로 별도 풀을 둔다. 접속 정보는
    메인 풀과 동일하게 환경변수에서 읽되, 체크포인터 트래픽에 맞춰 풀 규모는 작게 유지한다.
    """
    global _checkpointer_pool
    if _checkpointer_pool is None:
        with _checkpointer_pool_lock:
            if _checkpointer_pool is None:
                _checkpointer_pool = ConnectionPool(
                    _build_conninfo(),
                    min_size=1,
                    max_size=5,
                    timeout=DB_POOL_TIMEOUT_SECONDS,
                    kwargs={"autocommit": True},
                    open=True,
                )
                log_kv(logger, logging.INFO, "db", "체크포인터 전용 PostgreSQL 커넥션 풀 초기화 완료")
    return _checkpointer_pool


def close_checkpointer_pool() -> None:
    """체크포인터 전용 커넥션 풀을 명시적으로 종료한다. 애플리케이션 종료 시 호출."""
    global _checkpointer_pool
    with _checkpointer_pool_lock:
        if _checkpointer_pool is not None:
            _checkpointer_pool.close()
            _checkpointer_pool = None
            log_kv(logger, logging.INFO, "db", "체크포인터 전용 PostgreSQL 커넥션 풀 종료 완료")


def get_pool() -> ConnectionPool:
    """
    비즈니스 로직에서 커넥션 풀을 획득한다.

    init_pool()이 선행되지 않았다면 RuntimeError를 발생시킨다.
    테스트 시에는 이 함수를 mock하여 DB 의존성을 차단할 수 있다.
    """
    if _pool is None:
        raise RuntimeError(
            "DB 커넥션 풀이 초기화되지 않았습니다. 앱 시작 시 init_pool()을 호출하세요."
        )
    return _pool


def close_pool() -> None:
    """커넥션 풀을 명시적으로 종료한다. 애플리케이션 종료 시 호출."""
    global _pool
    with _lock:
        if _pool is not None:
            _pool.close()
            _pool = None
            log_kv(logger, logging.INFO, "db", "PostgreSQL 커넥션 풀 종료 완료")
