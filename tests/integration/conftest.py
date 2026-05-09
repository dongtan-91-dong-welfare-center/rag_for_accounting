import os
import pytest
from dotenv import load_dotenv
from src.agent.workflow import build_workflow
from src.models.state import GraphState

load_dotenv()

@pytest.fixture(scope="session", autouse=True)
def check_env_vars():
    """통합 테스트 실행 전 필수 환경 변수 존재 여부 확인"""
    required_vars = [
        "OPENAI_API_KEY",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "POSTGRES_HOST"
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        pytest.skip(f"필수 환경 변수 누락으로 통합 테스트 건너뜀: {', '.join(missing_vars)}")

@pytest.fixture
def workflow_app():
    """컴파일된 LangGraph StateGraph 객체 반환"""
    return build_workflow()

@pytest.fixture
def initial_state():
    """기본 GraphState 초기화 객체 생성"""
    return GraphState(
        original_query="영업권 손상차손 인식 기준은?",
        standard_filter="ALL"
    )
