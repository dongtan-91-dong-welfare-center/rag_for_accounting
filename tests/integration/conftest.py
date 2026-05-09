import os
import pytest
from dotenv import load_dotenv
from src.agent.workflow import build_workflow

load_dotenv()

@pytest.fixture(scope="session", autouse=True)
def check_integration_env():
    """통합/품질 테스트 진입 전 필수 환경 변수 검증 (Fast-Fail)"""
    required_vars = [
        "OPENAI_API_KEY",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "POSTGRES_HOST"
    ]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        pytest.fail(f"통합 테스트 환경 변수가 누락되었습니다: {', '.join(missing)}")

@pytest.fixture(scope="session")
def workflow_app():
    """실제 노드가 연결된 LangGraph 애플리케이션 (세션당 1회 생성)"""
    return build_workflow()
