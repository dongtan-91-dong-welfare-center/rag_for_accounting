import pytest
from src.agent.workflow import build_workflow
from src.models.state import GraphState

@pytest.fixture
def initial_state():
    """기본 GraphState 객체 생성 피처"""
    return GraphState(query="영업권 손상차손 인식 기준은?")

@pytest.fixture
def workflow_app():
    """컴파일된 LangGraph 워크플로우 앱 피처"""
    return build_workflow()
