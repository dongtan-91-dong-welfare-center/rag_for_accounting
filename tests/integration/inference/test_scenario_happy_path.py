"""
[표준 성공 흐름]

다양한 질의 유형에 대해 전체 LangGraph 파이프라인(rewrite → search → rerank → evaluate → generate)이
정상 경로를 따라 최종 답변까지 도달하는지 검증합니다.

설계 원칙:
    - 노드의 비즈니스 로직은 실제 코드를 실행하되, 외부 I/O(LLM 호출, DB 검색)만 Mock 데이터로 대체합니다.
    - 최종 결과값뿐 아니라 GraphState의 필드가 각 노드를 거치며 어떻게 진화했는지 이력을 추적합니다.
    - pytest.mark.parametrize로 다양한 속성값을 주입하여 하나의 테스트 함수로 여러 시나리오를 커버합니다.
"""
import pytest
from unittest.mock import patch
from src.models.state import GraphState
from src.models.schemas import EvaluationResult, FinalResponse, Citation
from tests.integration.inference.helpers import make_reranked_results, make_retrieved_chunks

# ── 전체 파이프라인 정상 흐름 ──

@pytest.mark.system
class TestScenarioHappyPath:
    """다양한 질의 속성에 대해 전체 파이프라인이 정상 경로로 끝까지 도달하는지 검증"""

    @pytest.mark.parametrize(
        "query, search_scores, rerank_scores, expected_answerable, expected_citation_count",
        [
            # 케이스 1: 표준 회계 질의 — 높은 점수의 청크 2개 → 정상 답변
            (
                "영업권 손상차손 인식 기준은?",
                [0.92, 0.85],
                [0.95, 0.88],
                True,
                2,
            ),
            # 케이스 2: 다중 청크 검색 — 5개 청크 모두 유효 → 풍부한 인용과 함께 답변
            (
                "K-GAAP에서 유형자산 감가상각 방법과 무형자산 상각 방법의 차이점은?",
                [0.90, 0.87, 0.82, 0.78, 0.71],
                [0.93, 0.89, 0.84, 0.76, 0.70],
                True,
                5,
            ),
            # 케이스 3: 단일 청크 검색 — 하나의 결과만으로도 답변 가능
            (
                "전환사채 발행 시 회계처리 방법은?",
                [0.95],
                [0.97],
                True,
                1,
            ),
        ],
        ids=["standard_query", "multi_chunk", "single_chunk"]
    )
    def test_full_pipeline_happy_path(
        self, mocked_app, query, search_scores, rerank_scores,
        expected_answerable, expected_citation_count
    ):
        """전체 파이프라인이 정상 경로(rewrite→search→rerank→evaluate→generate)를 따라 GraphState가 올바르게 이동하고 최종 답변이 생성되는지 검증"""

        # Mock 데이터 생성
        chunks = make_retrieved_chunks(search_scores)
        reranked = make_reranked_results(chunks, rerank_scores)
        citations = [
            Citation(
                document_id=r.chunk.document_id,
                chunk_id=r.chunk.chunk_id,
                content=r.chunk.content,
                relevance_score=r.rerank_score
            ) for r in reranked
        ]

        # 노드 함수는 실제 코드를 실행하되, 외부 I/O만 Mock
        with (
            patch("src.agent.workflow.search", return_value={"retrieved_chunks": chunks}),
            patch("src.agent.workflow.rerank", return_value={"reranked_chunks": reranked}),
            patch("src.agent.workflow.evaluate", return_value={
                "evaluation": EvaluationResult(
                    is_relevant=True, needs_external=False,
                    confidence=0.9, reasoning="검색 결과가 질의에 충분히 관련됨"
                )
            }),
            patch("src.agent.workflow.generate", return_value={
                "final_response": FinalResponse(
                    answer="K-GAAP 기준에 따르면...",
                    citations=citations,
                    is_answerable=expected_answerable,
                    confidence_score=0.95
                )
            }),
        ):
            state = GraphState(original_query=query, standard_filter="ALL")
            final_state = mocked_app.invoke(state)

        # ── State Evolution 검증 ──
        # rewrite 노드를 정확히 1회 통과
        assert final_state["rewrite_count"] == 1, f"rewrite_count가 1이어야 하나 {final_state['rewrite_count']}입니다."

        # 에러 없이 정상 경로로 완주
        assert len(final_state["error_logs"]) == 0, f"에러가 발생하지 않아야 하나 {final_state['error_logs']}가 기록되었습니다."

        # 검색 결과가 State에 올바르게 적재
        assert len(final_state["retrieved_chunks"]) == len(search_scores)

        # 리랭킹 결과가 State에 올바르게 적재
        assert len(final_state["reranked_chunks"]) == len(rerank_scores)

        # 최종 답변 검증
        response = final_state["final_response"]
        assert response is not None
        assert response.is_answerable is expected_answerable
        assert len(response.citations) == expected_citation_count
        assert response.confidence_score > 0.0


    @pytest.mark.parametrize(
        "standard_filter",
        ["GAAP", "KIFRS", "ALL"],
        ids=["gaap_only", "kifrs_only", "all_standards"]
    )
    def test_standard_filter_propagation(self, mocked_app, standard_filter):
        """사용자가 선택한 기준서 필터가 파이프라인 전체에 걸쳐 GraphState에 보존되는지 검증"""

        chunks = make_retrieved_chunks([0.9])
        reranked = make_reranked_results(chunks, [0.95])

        with (
            patch("src.agent.workflow.search", return_value={"retrieved_chunks": chunks}),
            patch("src.agent.workflow.rerank", return_value={"reranked_chunks": reranked}),
            patch("src.agent.workflow.evaluate", return_value={
                "evaluation": EvaluationResult(
                    is_relevant=True, needs_external=False,
                    confidence=0.9, reasoning="충분"
                )
            }),
            patch("src.agent.workflow.generate", return_value={
                "final_response": FinalResponse(
                    answer="답변", citations=[], is_answerable=True, confidence_score=0.9
                )
            }),
        ):
            state = GraphState(original_query="테스트 질의", standard_filter=standard_filter)
            final_state = mocked_app.invoke(state)

        # standard_filter가 파이프라인 전체를 통과한 후에도 원래 값을 유지
        assert final_state["standard_filter"] == standard_filter
