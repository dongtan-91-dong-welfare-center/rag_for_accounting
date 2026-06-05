# psycopg3의 ConnectionPool을 싱글톤으로 제공한다.
# 환경변수에서 접속 정보를 읽어 Docker 및 로컬 환경 모두 대응한다.

import os
import threading

from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo
from psycopg_pool import ConnectionPool

from src.utils.exception import ConfigNotFoundError
from src.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

_pool: ConnectionPool | None = None # 전역 커넥션 풀
_lock = threading.Lock()    # init_pool() 이중 호출 방지용


def init_pool() -> None:
    """
    커넥션 풀을 명시적으로 초기화한다. 앱 시작 시 단 1회 호출한다.

    환경변수(POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER,
    POSTGRES_PASSWORD)에서 접속 정보를 읽어 풀을 생성한다.

    - POSTGRES_PASSWORD 미설정 시 ConfigNotFoundError로 조기 실패한다.
      기본값으로 접속을 시도하다 "인증 실패"로 둔갑하는 것을 방지한다.
    - make_conninfo()로 conninfo를 구성해 값에 포함된 공백·특수문자(`=`, `'`,
      `\\` 등)를 자동 이스케이프한다.
    - _lock으로 보호해 멀티스레드 환경에서 풀이 두 번 생성되지 않도록 하며,
      이중 호출 시에는 아무 동작도 하지 않는다(idempotent).
    """
    global _pool
    with _lock:
        if _pool is not None:
            return

        password = os.getenv("POSTGRES_PASSWORD")
        if not password:
            raise ConfigNotFoundError(
                "POSTGRES_PASSWORD 환경변수가 설정되지 않았습니다.", node="search"
            )

        # make_conninfo: postgresql 접속을 위한 connection string을 만드는 함수
        conninfo = make_conninfo(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DB", "accounting_db"),
            user=os.getenv("POSTGRES_USER", "accounting_user"),
            password=password,
        )
        _pool = ConnectionPool(conninfo, min_size=2, max_size=10, open=True)
        logger.info("PostgreSQL 커넥션 풀 초기화 완료")


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
            logger.info("PostgreSQL 커넥션 풀 종료 완료")
