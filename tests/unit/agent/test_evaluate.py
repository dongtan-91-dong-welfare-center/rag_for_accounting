"""
[FUNC-007] 맥락 평가 단위 테스트 Stub

대상 모듈: src/agent/nodes/evaluate.py
검증 범위:
    - evaluate_context(): reranked_chunks → EvaluationResult 변환
    - check_relevance(): 단일 청크 관련성 판단
    - check_external_reference(): 외부 기준서 참조 필요 여부 판단

TODO: evaluate.py 구현 완료 후 @pytest.mark.skip을 제거
"""
import pytest
from src.models.schemas import (
    RetrievedChunk,
    RerankingResult,
    EvaluationResult,
)
from src.utils.config import RERANK_THRESHOLD


@pytest.mark.unit
class TestCheckRelevance:
    """check_relevance() 함수 인터페이스 검증"""

    @pytest.mark.skip(reason="FUNC-007 evaluate 노드 구현 후 활성화 예정")
    def test_relevant_chunk_above_threshold(self):
        """rerank_score >= RERANK_THRESHOLD이고 content가 비어있지 않으면 True"""
        from src.agent.nodes.evaluate import check_relevance

        chunk = RerankingResult(
            chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="영업권 정의", score=0.8, metadata={}),
            rerank_score=RERANK_THRESHOLD + 0.1,
        )
        assert check_relevance(chunk, "영업권 손상차손") is True

    @pytest.mark.skip(reason="FUNC-007 evaluate 노드 구현 후 활성화 예정")
    def test_irrelevant_chunk_below_threshold(self):
        """rerank_score < RERANK_THRESHOLD이면 False"""
        from src.agent.nodes.evaluate import check_relevance

        chunk = RerankingResult(
            chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="내용", score=0.3, metadata={}),
            rerank_score=RERANK_THRESHOLD - 0.1,
        )
        assert check_relevance(chunk, "영업권 손상차손") is False

    @pytest.mark.skip(reason="FUNC-007 evaluate 노드 구현 후 활성화 예정")
    def test_empty_content_returns_false(self):
        """content가 비어있으면 False"""
        from src.agent.nodes.evaluate import check_relevance

        chunk = RerankingResult(
            chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="", score=0.9, metadata={}),
            rerank_score=0.9,
        )
        assert check_relevance(chunk, "영업권 손상차손") is False


@pytest.mark.unit
class TestCheckExternalReference:
    """check_external_reference() 함수 인터페이스 검증"""

    @pytest.mark.skip(reason="FUNC-007 evaluate 노드 구현 후 활성화 예정")
    def test_external_keyword_detected(self):
        """reasoning에 외부 참조 키워드가 포함되면 True"""
        from src.agent.nodes.evaluate import check_external_reference

        evaluation = EvaluationResult(
            is_relevant=True, needs_external=False, confidence=0.7,
            reasoning="IFRS 16호에 대한 추가 외부 기준서 참조가 필요합니다."
        )
        assert check_external_reference(evaluation) is True

    @pytest.mark.skip(reason="FUNC-007 evaluate 노드 구현 후 활성화 예정")
    def test_no_external_keyword(self):
        """reasoning에 외부 참조 키워드가 없으면 False"""
        from src.agent.nodes.evaluate import check_external_reference

        evaluation = EvaluationResult(
            is_relevant=True, needs_external=False, confidence=0.9,
            reasoning="검색된 문서에서 충분한 근거를 확인할 수 있습니다."
        )
        assert check_external_reference(evaluation) is False


@pytest.mark.unit
class TestEvaluateContext:
    """evaluate_context() 노드 함수 인터페이스 검증"""

    @pytest.mark.skip(reason="FUNC-007 evaluate 노드 구현 후 활성화 예정 — LLM 연동 필요")
    def test_evaluate_returns_evaluation_result(self):
        """
        입력: GraphState (reranked_chunks 포함)
        출력: GraphState (evaluation: EvaluationResult 필드 설정)
        """
        from src.agent.nodes.evaluate import evaluate_context
        from src.models.state import GraphState

        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="영업권 정의", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        result = evaluate_context(state)
        assert result.evaluation is not None
        assert isinstance(result.evaluation, EvaluationResult)
