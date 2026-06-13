import os
import pytest
from dotenv import load_dotenv

load_dotenv()

@pytest.fixture(scope="session", autouse=True)
def check_integration_env():
    """통합/품질 테스트 진입 전 필수 환경 변수 및 인프라 검증"""

    # 로컬 통합 테스트를 위한 DB 호스트 강제 변경
    # .env에 'database'로 되어 있어도, 호스트 머신에서 실행되는 테스트를 위해 'localhost'로 덮어씀
    if os.getenv("POSTGRES_HOST") == "database":
        os.environ["POSTGRES_HOST"] = "localhost"

    # 환경 변수 검증
    required_vars = [
        "OPENAI_API_KEY"
    ]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        pytest.skip(f"통합 테스트 환경 변수가 누락되어 LLM을 의존하는 테스트를 건너뜁니다: {', '.join(missing)}")
        
    # 인프라 동작 검증
    from tests.utils.infra_check import check_docker_infrastructure
    infra_error = check_docker_infrastructure()
    if infra_error:
        pytest.skip(f"인프라 준비 상태에 문제가 있어 테스트를 건너뜁니다: {infra_error}")


def _chunks_rowcount() -> int | None:
    """운영 chunks 테이블의 행수를 반환한다. 테이블이 없거나 DB에 접근할 수 없으면 None.

    세션 종료 시점엔 일부 모듈 픽스처가 close_pool()로 풀을 닫았을 수 있으므로,
    멱등인 init_pool()로 필요 시 풀을 다시 연 뒤 조회한다.
    """
    try:
        from src.db.connection import get_pool, init_pool

        init_pool()
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks")
            return int(cur.fetchone()[0])
    except Exception:
        return None


@pytest.fixture(scope="session", autouse=True)
def protect_production_chunks(check_integration_env):
    """통합 테스트 세션이 운영 chunks 테이블을 소실/축소시키지 않았는지 검증한다.

    과거 한 통합 테스트의 tear-down이 운영 chunks를 DROP해, 1회 실행으로 전체 코퍼스가 소실되고 서비스가 즉시 다운된 사고가 있었다.
    검색·적재는 collection 파라미터로 전용 테스트 컬렉션에 격리되므로 정상 테스트는 운영 chunks를 건드리지 않는다. 
    이 가드는 향후 회귀를 메커니즘(DROP/TRUNCATE/DELETE 등)과 무관하게 세션 종료 시 즉시 실패로 드러낸다.

    세션 시작 시 운영 chunks 행수를 스냅샷하 종료 시 비교한다. 
    시작 시점에 chunks가 없거나(미적재) DB에 접근할 수 없으면 보호 대상이 없으므로 조용히 무동작한다.
    check_integration_env에 의존해 POSTGRES_HOST(localhost) 보정 이후에 스냅샷한다.
    """
    before = _chunks_rowcount()
    yield
    if before is None:
        return  # 세션 시작 시 보호 대상(적재된 운영 chunks)이 없었음 → 검증 생략

    after = _chunks_rowcount()
    if after is None:
        pytest.fail(
            f"운영 chunks 테이블을 더 이상 읽을 수 없습니다 "
            f"(세션 시작 {before}행 → DROP되었거나 접근 불가). 통합 테스트가 운영 chunks를 "
            f"직접 건드렸을 수 있습니다. 테스트는 전용 collection을 쓰고 delete_collection으로 정리하십시오."
        )
    if after < before:
        pytest.fail(
            f"운영 chunks 행수가 {before} → {after}로 감소했습니다. "
            f"통합 테스트가 운영 데이터를 삭제했습니다. 운영 chunks 대신 전용 collection을 사용하십시오."
        )
