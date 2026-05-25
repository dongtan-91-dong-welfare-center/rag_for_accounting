# psycopg3의 ConnectionPool을 싱글톤으로 제공한다.
# 환경변수에서 접속 정보를 읽어 Docker 및 로컬 환경 모두 대응한다.

import os

from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

from src.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """
    싱글톤 커넥션 풀을 반환한다.

    최초 호출 시 환경변수(POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
    POSTGRES_USER, POSTGRES_PASSWORD)에서 접속 정보를 읽어 풀을 생성한다.
    이후 호출에서는 이미 생성된 풀을 재사용한다.

    테스트 시에는 이 함수를 mock하여 DB 의존성을 차단할 수 있다.
    """
    global _pool
    if _pool is None:
        conninfo = (
            f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
            f"port={os.getenv('POSTGRES_PORT', '5432')} "
            f"dbname={os.getenv('POSTGRES_DB', 'accounting_db')} "
            f"user={os.getenv('POSTGRES_USER', 'accounting_user')} "
            f"password={os.getenv('POSTGRES_PASSWORD', '')}"
        )
        _pool = ConnectionPool(conninfo, min_size=2, max_size=10)
        logger.info("PostgreSQL 커넥션 풀 생성 완료")
    return _pool


def close_pool() -> None:
    """커넥션 풀을 명시적으로 종료한다. 애플리케이션 종료 시 호출."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
        logger.info("PostgreSQL 커넥션 풀 종료 완료")
