import pytest
from unittest.mock import patch
from src.agent.workflow import build_workflow
from src.models.state import GraphState
from src.utils.config import MAX_REWRITE_COUNT
from src.models.schemas import EvaluationResult

@pytest.fixture
def initial_state():
    """기본 GraphState 객체 생성 피처"""
    return GraphState(query="영업권 손상차손 인식 기준은?")

class TestWorkflowIntegration:
    """LangGraph 워크플로우 통합 테스트. 노드 간의 상태 전이 및 조건부 루프 동작 검증"""

    def test_crag_loop_with_needs_external_true(self, initial_state):
        """needs_external=True일 때 rewrite 노드로 다시 분기되는지 검증"""
        # evaluate_context가 첫 번째 호출에서는 needs_external=True를, 
        # 두 번째 호출에서는 False를 반환하도록 모킹
        with patch("src.agent.workflow.evaluate_context") as mock_eval:
            mock_eval.side_effect = [
                {
                    "evaluation": EvaluationResult(
                        is_relevant=True, needs_external=True, confidence=0.8, reasoning="추가 검색 필요"
                    )
                },
                {
                    "evaluation": EvaluationResult(
                        is_relevant=True, needs_external=False, confidence=0.9, reasoning="검색 완료"
                    )
                }
            ]
            
            # 패치된 함수를 사용하도록 워크플로우 재빌드
            app = build_workflow()
            final_state = app.invoke(initial_state)
            
            # 초기 1번 + 루프 1번 = 총 2번의 rewrite_count 증가 기대
            assert final_state["rewrite_count"] == 2
            assert final_state["evaluation"].needs_external is False

    def test_crag_loop_stops_at_max_count(self, initial_state):
        """MAX_REWRITE_COUNT에 도달하면 needs_external=True라도 루프를 중단하고 generate로 진행하는지 검증"""
        with patch("src.agent.workflow.evaluate_context") as mock_eval:
            # need_external이 True이므로 evaluate_context -> rewrite 노드로 계속 분기되니 결국 MAX_REWRITE_COUNT(현재 3)까지 카운트가 증가
            mock_eval.return_value = {
                "evaluation": EvaluationResult(
                    is_relevant=True, needs_external=True, confidence=0.5, reasoning="계속 검색 필요"
                )
            }
            
            # 패치된 함수를 사용하도록 워크플로우 재빌드
            app = build_workflow()
            final_state = app.invoke(initial_state)
            
            # MAX_REWRITE_COUNT(현재 3)까지 카운트가 증가하고 루프가 멈춰야 함
            assert final_state["rewrite_count"] == MAX_REWRITE_COUNT
            assert final_state["final_response"] is not None