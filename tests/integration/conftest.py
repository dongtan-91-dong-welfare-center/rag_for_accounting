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


def _read_chunks_state() -> tuple[bool, int] | None:
    """운영 chunks 상태를 (테이블_존재, 행수)로 반환한다. DB에 접근할 수 없으면 None.

    to_regclass로 '테이블 없음(DROP됨)'과 '일시적 DB 불가'를 구분한다 
    전자만 가드가 실패로 다뤄야 하고, 후자(teardown 중 커넥션 일시 장애 등)는 판단 불가이므로 거짓 양성을 피하려 None으로 보고한다.
    세션 종료 시 일부 모듈 픽스처가 close_pool()했을 수 있어 멱등 init_pool()로 필요 시 재연결하며, 
    DB 미가동 환경에서 오래 매달리지 않도록 짧은 타임아웃으로 커넥션을 얻는다.
    """
    try:
        from src.db.connection import get_pool, init_pool

        init_pool()
        with get_pool().connection(timeout=5) as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('chunks')")
            if cur.fetchone()[0] is None:
                return (False, 0)  # 테이블이 존재하지 않음
            cur.execute("SELECT COUNT(*) FROM chunks")
            return (True, int(cur.fetchone()[0]))
    except Exception:
        return None  # DB 접근 불가 — 존재 여부 판단 불가


@pytest.fixture(scope="session", autouse=True)
def protect_production_chunks(check_integration_env):
    """통합 테스트 세션이 운영 chunks 테이블을 소실/축소시키지 않았는지 검증한다.

    과거 한 통합 테스트의 tear-down이 운영 chunks를 DROP해, 1회 실행으로 전체 코퍼스가 소실되고 서비스가 즉시 다운된 사고가 있었다. 
    검색·적재는 collection 파라미터로 전용 테스트 컬렉션에 격리되므로 정상 테스트는 운영 chunks를 건드리지 않는다.
    이 가드는 향후 회귀(DROP/TRUNCATE/DELETE)를 세션 종료 시 실패로 드러내는 탐지형 안전망이다(예방이 아닌 탐지).

    세션 시작 시 운영 chunks 상태(존재·행수)를 스냅샷하고 종료 시 비교한다. 
    시작 시점에 chunks가 없거나(미적재) DB에 접근할 수 없으면 보호 대상이 없으므로 무동작한다.
    teardown 시점에 상태를 읽지 못하면(일시적 DB 불가) DROP과 구분할 수 없어 판단을 보류한다(거짓 양성 회피).
    check_integration_env에 의존해 POSTGRES_HOST(localhost) 보정 이후에 스냅샷한다.
    라이브 인프라가 없는 ingestion 트랙은 자식 conftest에서 이 픽스처를 무력화한다.

    주의: 행수 '감소'는 외부 재적재(ingest --reset)가 세션과 겹쳐도 트리거될 수 있다.
    """
    before = _read_chunks_state()
    try:
        yield
    finally:
        try:
            # 시작 시 보호 대상(존재하며 적재된 chunks)이 없었으면 검증 생략
            if before is not None and before[0]:
                after = _read_chunks_state()
                # after가 None이면 teardown 중 DB 접근 불가 — DROP과 구분 불가하므로 판단 보류
                if after is not None:
                    if not after[0]:
                        pytest.fail(
                            f"운영 chunks 테이블이 세션 중 DROP되었습니다 "
                            f"(시작 {before[1]}행 → 테이블 없음). 통합 테스트가 운영 chunks를 직접 건드렸습니다. "
                            f"테스트는 전용 collection을 쓰고 delete_collection으로 정리하십시오."
                        )
                    if after[1] < before[1]:
                        pytest.fail(
                            f"운영 chunks 행수가 {before[1]} → {after[1]}로 감소했습니다. "
                            f"통합 테스트가 운영 데이터를 삭제했거나, 외부 재적재(ingest --reset)가 세션과 겹쳤습니다. "
                            f"전자라면 전용 collection을 사용하십시오."
                        )
        finally:
            # 가드가 teardown에서 (재)연 풀을 누수 없이 닫는다(미반환 커넥션·ResourceWarning 방지)
            from src.db.connection import close_pool

            close_pool()
