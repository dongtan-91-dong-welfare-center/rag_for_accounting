"""
[CRAG 루프 및 예외 복구 시나리오]

평가 노드에서 검색 결과가 불충분하다고 판단하거나, 노드 처리 중 예외가 발생했을 때
CRAG 루프의 라우팅과 상태 진화가 올바르게 동작하고, 무한 루프 없이 안전하게 복구/중단되는지 검증합니다.

설계 원칙:
    - rewrite_count의 증가 이력, error_logs의 순차 적재를 추적합니다.
    - 기대하는 라우팅 경로(방문 노드 수)를 검증합니다.
    - evaluate 노드의 반환값만 시나리오별로 교체하여 실제 라우팅 로직이 올바르게 분기하는지 확인합니다.
"""
import pytest
from unittest.mock import patch, call
from src.models.state import GraphState
from src.utils.exception import EvaluationParsingError, SearchTimeoutError, ScoreThresholdError
from src.utils.config import MAX_REWRITE_COUNT
from tests.integration.inference.helpers import make_retrieved_chunks, make_reranked_results, make_eval_result

# ── CRAG 루프 라우팅 검증 ──

@pytest.mark.system
class TestScenarioHallucinationRisk:
    """CRAG 루프, 에러 복구 및 예외 처리 라우팅의 상태 진화 검증"""

    @pytest.mark.parametrize(
        "eval_sequence, expected_rewrite_count, expected_answerable",
        [
            # 케이스 1: 첫 평가에서 바로 충분 → 루프 없이 답변 생성
            (
                [make_eval_result(needs_external=False)],
                1,  # 초기 진입 1회
                True,
            ),
            # 케이스 2: 1회 부족 판단 → rewrite 루프 1회 → 2차 평가에서 충분 → 답변
            (
                [
                    make_eval_result(needs_external=True, confidence=0.3),
                    make_eval_result(needs_external=False, confidence=0.9),
                ],
                2,  # 초기 1 + 루프 1
                True,
            ),
            # 케이스 3: 2회 연속 부족 → rewrite 2회 → 3차 평가에서 충분 → 답변
            (
                [
                    make_eval_result(needs_external=True, confidence=0.2),
                    make_eval_result(needs_external=True, confidence=0.4),
                    make_eval_result(needs_external=False, confidence=0.85),
                ],
                3,  # 초기 1 + 루프 2
                True,
            ),
        ],
        ids=["no_loop", "single_retry", "double_retry"]
    )
    def test_crag_loop_rewrite_count_evolution(
        self, mocked_app, eval_sequence, expected_rewrite_count, expected_answerable
    ):
        """evaluate 노드의 needs_external 판단에 따라 CRAG 루프가 정확한 횟수만큼 rewrite를 반복하고, rewrite_count가 올바르게 누적되는지 검증"""

        chunks = make_retrieved_chunks()
        reranked = make_reranked_results(chunks)

        # Mock 데이터 생성
        with (
            patch("src.agent.workflow.hybrid_search", return_value={"retrieved_chunks": chunks}),
            patch("src.agent.workflow.rerank_chunks", return_value={"reranked_chunks": reranked}),
            patch("src.agent.workflow.evaluate_context", side_effect=eval_sequence),
        ):
            state = GraphState(original_query="영업권 손상차손 인식 기준은?", standard_filter="ALL")
            final_state = mocked_app.invoke(state)

        # ── State Evolution 검증 ──
        assert final_state["rewrite_count"] == expected_rewrite_count, \
            f"rewrite_count: expected={expected_rewrite_count}, actual={final_state['rewrite_count']}"
        assert final_state["final_response"].is_answerable is expected_answerable
        assert len(final_state["error_logs"]) == 0


    def test_max_rewrite_count_forces_generate(self, mocked_app):
        """MAX_REWRITE_COUNT에 도달하면 needs_external=True여도 무한 루프 없이 generate로 강제 진행되는지 검증"""

        chunks = make_retrieved_chunks()
        reranked = make_reranked_results(chunks)

        # evaluate가 항상 "추가 검색 필요"를 반환 → 무한 루프 위험
        eval_always_retry = make_eval_result(needs_external=True, confidence=0.1)

        with (
            patch("src.agent.workflow.hybrid_search", return_value={"retrieved_chunks": chunks}),
            patch("src.agent.workflow.rerank_chunks", return_value={"reranked_chunks": reranked}),
            patch("src.agent.workflow.evaluate_context", return_value=eval_always_retry),
        ):
            state = GraphState(original_query="무한 루프 테스트", standard_filter="ALL")
            final_state = mocked_app.invoke(state)

        # 최대 재시도 횟수에서 멈춤 (초기 1 + 루프 MAX_REWRITE_COUNT - 1 ≤ MAX_REWRITE_COUNT)
        assert final_state["rewrite_count"] <= MAX_REWRITE_COUNT, \
            f"rewrite_count({final_state['rewrite_count']})가 MAX({MAX_REWRITE_COUNT})를 초과했습니다."
        # 답변이 생성되었는지 확인 (무한 루프가 아닌 정상 종료)
        assert final_state["final_response"] is not None


    @pytest.mark.parametrize(
        "error_node, exception_class, expected_error_type, expected_rewrite_count",
        [
            # 케이스 1: evaluate 노드 에러 → generate로 탈출, 루프 진입하지 않음
            ("evaluate", EvaluationParsingError, "EV-301", 1),
            # 케이스 2: search 노드 에러 → 후속 노드가 빈 상태로 진행, 답변 불가
            ("search", SearchTimeoutError, "SE-101", 1),
        ],
        ids=["evaluate_error_fallback", "search_error_fallback"]
    )
    def test_node_error_fallback_routing(
        self, mocked_app, error_node, exception_class, expected_error_type, expected_rewrite_count
    ):
        """특정 노드에서 예외 발생 시 CRAG 루프에 진입하지 않고
        안전하게 generate로 직행하는 Fallback 경로를 검증"""

        from src.agent.workflow import handle_node_errors

        def raise_error(state):
            raise exception_class(message=f"{error_node} 테스트 에러")

        decorated = handle_node_errors(error_node)(raise_error)

        patch_target = {
            "evaluate": "src.agent.workflow.evaluate_context",
            "search": "src.agent.workflow.hybrid_search",
        }[error_node]

        with patch(patch_target, side_effect=decorated):
            state = GraphState(original_query="에러 복구 테스트", standard_filter="ALL")
            final_state = mocked_app.invoke(state)

        # ── State Evolution 검증 ──
        # 에러 로그에 정확한 노드명과 에러 코드 기록
        assert any(
            log["node"] == error_node and log["error_type"] == expected_error_type
            for log in final_state["error_logs"]
        ), f"error_logs에 {error_node}/{expected_error_type}가 기록되지 않았습니다."

        # rewrite 루프에 재진입하지 않음
        assert final_state["rewrite_count"] == expected_rewrite_count, \
            f"Fallback 경로에서 rewrite_count가 {expected_rewrite_count}이어야 합니다."

        # 에러에도 불구하고 최종 답변이 생성
        assert final_state["final_response"] is not None

    def test_needs_reretrieval_priority_over_evaluate_error(self, mocked_app):
        """
        needs_reretrieval=True가 evaluate 에러보다 우선하여
        rewrite 루프를 MAX_REWRITE_COUNT까지 반복한 후 build_unanswerable_response를 반환하는지 검증

        시나리오:
          - rerank: ScoreThresholdError 동작 모사 → needs_reretrieval=True, reranked_chunks=[]
          - evaluate: 빈 컨텍스트 전달로 EvaluationParsingError 발생

        needs_reretrieval이 적절하지 않은 경우: 첫 번째 evaluate 에러에서 즉시 generate → rewrite_count=1
        needs_reretrieval이 적절한 경우: MAX_REWRITE_COUNT까지 rewrite 반복 → rewrite_count=MAX
        """
        from src.agent.workflow import handle_node_errors

        chunks = make_retrieved_chunks()

        def mock_rerank_score_error(state):
            e = ScoreThresholdError("리랭킹 임계값 미달")
            new_logs = state.error_logs + [e.to_error_log()]
            return {"reranked_chunks": [], "needs_reretrieval": True, "error_logs": new_logs}

        def raise_eval_error(state):
            raise EvaluationParsingError("빈 컨텍스트로 평가 불가")

        decorated_evaluate = handle_node_errors("evaluate")(raise_eval_error)

        with (
            patch("src.agent.workflow.hybrid_search", return_value={"retrieved_chunks": chunks}),
            patch("src.agent.workflow.rerank_chunks", side_effect=mock_rerank_score_error),
            patch("src.agent.workflow.evaluate_context", side_effect=decorated_evaluate),
        ):
            state = GraphState(original_query="needs_reretrieval 우선순위 통합 검증", standard_filter="ALL")
            final_state = mocked_app.invoke(state)

        # needs_reretrieval이 evaluate 에러보다 우선하므로 MAX까지 rewrite 반복
        assert final_state["rewrite_count"] == MAX_REWRITE_COUNT, (
            f"needs_reretrieval이 evaluate 에러보다 우선되어 "
            f"rewrite_count={MAX_REWRITE_COUNT}에 도달해야 합니다. "
            f"실제={final_state['rewrite_count']}"
        )

        # MAX 도달 후 빈 reranked_chunks로 generate 진입 → build_unanswerable_response 호출
        assert final_state["final_response"] is not None
        assert final_state["final_response"].is_answerable is False
        assert "제공된 회계기준 문서에서" in final_state["final_response"].answer   # generate.py에 정의된 fallback 메시지

        # evaluate 에러(EV-301)가 error_logs에 기록됨
        assert any(
            log["node"] == "evaluate" and log["error_type"] == "EV-301"
            for log in final_state["error_logs"]
        )
