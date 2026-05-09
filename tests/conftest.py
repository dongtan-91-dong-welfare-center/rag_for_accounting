import sys
from pathlib import Path
import pytest
from src.models.state import GraphState

# 프로젝트 루트 경로를 sys.path에 추가 (모든 디렉토리에서 pytest 실행 시 모듈 경로 인식)
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture(scope="session")
def initial_state():
    """모든 단계에서 활용 가능한 기본 GraphState 객체 정의"""
    return GraphState(
        original_query="영업권 손상차손 인식 기준은?",
        standard_filter="ALL",
        rewrite_count=0,
        error_logs=[]
    )
