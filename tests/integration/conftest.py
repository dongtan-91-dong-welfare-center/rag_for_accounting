import os
import pytest
from dotenv import load_dotenv
from src.agent.workflow import build_workflow

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
