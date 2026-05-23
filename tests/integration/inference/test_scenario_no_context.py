"""
[검색 결과 부재 시나리오]

검색 결과가 없거나 리랭킹 점수가 기준 미달일 경우,
파이프라인이 Fail-Fast 전략을 올바르게 수행하여 "답변 불가" 처리에 도달하는지,
그리고 GraphState의 상태 변화가 의도된 대로 기록되는지 검증합니다.

설계 원칙:
    - 검색 점수, 청크 개수, 에러 종류를 parametrize로 다양하게 주입하여
      전체 파이프라인의 경계값(Boundary) 처리와 예외 대응을 검증합니다.
    - 노드 간 데이터 전달이 끊어지는 지점에서 후속 노드가 어떻게 반응하는지를 추적합니다.
"""
import pytest
from unittest.mock import patch
from src.models.state import GraphState
from src.models.schemas import (
    RetrievedChunk, RerankingResult, EvaluationResult,
    FinalResponse
)
from src.utils.exception import ScoreThresholdError, SearchTimeoutError

# ── Mock 데이터 팩토리 ──

def make_retrieved_chunks(scores: list[float]) -> list[RetrievedChunk]:
    """주어진 점수 목록으로 검색 결과 청크를 생성"""
    return [
        RetrievedChunk(
            chunk_id=f"chunk-{i}",
            document_id=f"DOC-{i:03d}",
            content=f"검색 결과 내용 {i}",
            score=score,
            metadata={}
        )
        for i, score in enumerate(scores)
    ]


# ── 검색 결과 부재/미달 시 Fail-Fast 검증 ──

@pytest.mark.system
class TestScenarioNoContext:
    """검색 결과 부재/점수 미달 상황에서 파이프라인의 Fail-Fast 전략과 상태 진화 검증"""

    @pytest.mark.parametrize(
        "search_scores, reranked_chunks, expected_answerable, expected_answer_contains",
        [
            # 케이스 1: DB 검색 결과 0건 → 빈 리랭킹 → 답변 불가
            (
                [],
                [],
                False,
                "제공된 회계기준 문서에서 해당 질의에 대한 충분한 근거를 찾지 못했습니다.",
            ),
            # 케이스 2: 검색은 됐지만 리랭킹 후 전부 필터링 → 답변 불가
            (
                [0.4, 0.3, 0.2],
                [],  # 리랭커가 임계치 미달로 모두 걸러냄
                False,
                "제공된 회계기준 문서에서 해당 질의에 대한 충분한 근거를 찾지 못했습니다.",
            ),
            # 케이스 3: 검색 결과 1건, 리랭킹 통과 1건 → 정상 답변
            (
                [0.85],
                "PASS_THROUGH",  # 리랭커가 통과시킴 (테스트 내부에서 처리)
                True,
                None,
            ),
        ],
        ids=["empty_search", "all_filtered", "single_pass"]
    )
    def test_pipeline_with_varying_search_results(
        self, mocked_app, search_scores, reranked_chunks,
        expected_answerable, expected_answer_contains
    ):
        """검색 결과의 양과 점수에 따라 파이프라인이 Fail-Fast 또는 정상 경로를 올바르게 선택하는지 검증"""

        chunks = make_retrieved_chunks(search_scores)

        # 리랭킹 결과 구성
        if reranked_chunks == "PASS_THROUGH":
            mock_reranked = [RerankingResult(chunk=c, rerank_score=0.9) for c in chunks]
        else:
            mock_reranked = reranked_chunks

        with (
            patch("src.agent.workflow.hybrid_search", return_value={"retrieved_chunks": chunks}),
            patch("src.agent.workflow.rerank_chunks", return_value={"reranked_chunks": mock_reranked}),
            patch("src.agent.workflow.evaluate_context", return_value={
                "evaluation": EvaluationResult(
                    is_relevant=bool(mock_reranked), needs_external=False,
                    confidence=0.9 if mock_reranked else 0.0,
                    reasoning="충분" if mock_reranked else "관련 청크 없음"
                )
            }),
        ):
            state = GraphState(original_query="영업권 손상차손 인식 기준은?", standard_filter="ALL")
            final_state = mocked_app.invoke(state)

        # ── State Evolution 검증 ──
        response = final_state["final_response"]
        assert response is not None
        assert response.is_answerable is expected_answerable

        if expected_answer_contains:
            assert expected_answer_contains in response.answer

        # 검색 결과가 State에 올바르게 반영
        assert len(final_state["retrieved_chunks"]) == len(search_scores)

        # 리랭킹 결과가 State에 올바르게 반영
        assert len(final_state["reranked_chunks"]) == len(mock_reranked)


    @pytest.mark.parametrize(
        "exception_class, expected_error_type, expected_node",
        [
            # 케이스 1: 리랭킹 임계치 미달 에러 → RR-202 기록, 답변 불가
            (ScoreThresholdError, "RR-202", "rerank"),
            # 케이스 2: 검색 타임아웃 에러 → SE-101 기록, 답변 불가
            (SearchTimeoutError, "SE-101", "search"),
        ],
        ids=["rerank_threshold_error", "search_timeout_error"]
    )
    def test_pipeline_node_exception_graceful_degradation(
        self, mocked_app, exception_class, expected_error_type, expected_node
    ):
        """특정 노드에서 예외 발생 시 파이프라인이 중단되지 않고,
        error_logs에 정확한 에러 정보를 기록한 뒤 안전하게 답변 불가로 종료되는지 검증"""

        from src.agent.workflow import handle_node_errors

        # 예외를 발생시키는 노드 함수 생성
        def raise_exception(state):
            raise exception_class(message=f"{expected_node} 노드 테스트 에러")

        decorated = handle_node_errors(expected_node)(raise_exception)

        # 해당 노드만 에러 버전으로 교체
        patch_target = {
            "search": "src.agent.workflow.hybrid_search",
            "rerank": "src.agent.workflow.rerank_chunks",
        }[expected_node]

        with patch(patch_target, side_effect=decorated):
            state = GraphState(original_query="영업권 손상차손 인식 기준은?", standard_filter="ALL")
            final_state = mocked_app.invoke(state)

        # ── State Evolution 검증 ──
        # 에러 로그에 정확한 노드명과 에러 코드가 기록
        assert len(final_state["error_logs"]) > 0
        last_error = final_state["error_logs"][-1]
        assert last_error["node"] == expected_node
        assert last_error["error_type"] == expected_error_type

        # 에러에도 불구하고 최종 답변이 생성 (답변 불가 메시지)
        response = final_state["final_response"]
        assert response is not None
        assert response.is_answerable is False
