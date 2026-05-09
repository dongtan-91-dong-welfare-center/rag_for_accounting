"""
[FUNC-008] 답변 생성 단위 테스트 Stub

대상 모듈: src/agent/nodes/generate.py
검증 범위:
    - generate_response(): reranked_chunks → FinalResponse 생성
    - extract_citations(): 청크 → Citation 리스트 추출
    - build_unanswerable_response(): 답변 불가 시 안전 응답 생성

TODO: generate.py 구현 완료 후 @pytest.mark.skip을 제거
"""
import pytest
from src.models.schemas import (
    RetrievedChunk,
    RerankingResult,
    EvaluationResult,
    Citation,
    FinalResponse,
)
from src.utils.config import RERANK_THRESHOLD


@pytest.mark.unit
class TestExtractCitations:
    """extract_citations() 함수 인터페이스 검증"""

    @pytest.mark.skip(reason="FUNC-008 generate 노드 구현 후 활성화 예정")
    def test_extract_citations_from_chunks(self):
        """
        입력: chunks (list[RerankingResult])
        출력: list[Citation] — RERANK_THRESHOLD 이상인 청크만 포함
        """
        from src.agent.nodes.generate import extract_citations

        chunks = [
            RerankingResult(
                chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="영업권 정의", score=0.9, metadata={}),
                rerank_score=0.95,
            ),
            RerankingResult(
                chunk=RetrievedChunk(chunk_id="c2", document_id="D1", content="관계없는 내용", score=0.2, metadata={}),
                rerank_score=RERANK_THRESHOLD - 0.1,
            ),
        ]
        citations = extract_citations(chunks)
        assert isinstance(citations, list)
        assert all(isinstance(c, Citation) for c in citations)
        # threshold 미만 청크는 제외
        assert len(citations) == 1
        assert citations[0].chunk_id == "c1"

    @pytest.mark.skip(reason="FUNC-008 generate 노드 구현 후 활성화 예정")
    def test_extract_citations_empty_chunks(self):
        """빈 청크 리스트 → 빈 Citation 리스트"""
        from src.agent.nodes.generate import extract_citations

        citations = extract_citations([])
        assert citations == []


@pytest.mark.unit
class TestBuildUnanswerableResponse:
    """build_unanswerable_response() 함수 인터페이스 검증"""

    @pytest.mark.skip(reason="FUNC-008 generate 노드 구현 후 활성화 예정")
    def test_unanswerable_response_structure(self):
        """
        입력: query (str)
        출력: FinalResponse (is_answerable=False, citations=[], confidence_score=0.0)
        """
        from src.agent.nodes.generate import build_unanswerable_response

        response = build_unanswerable_response("영업권 손상차손 인식 기준은?")
        assert isinstance(response, FinalResponse)
        assert response.is_answerable is False
        assert response.citations == []
        assert response.confidence_score == 0.0
        assert len(response.answer) > 0


@pytest.mark.unit
class TestGenerateResponse:
    """generate_response() 노드 함수 인터페이스 검증"""

    @pytest.mark.skip(reason="FUNC-008 generate 노드 구현 후 활성화 예정 — LLM 연동 필요")
    def test_generate_returns_final_response(self):
        """
        입력: GraphState (evaluation + reranked_chunks 포함)
        출력: GraphState (final_response: FinalResponse 필드 설정)
        """
        from src.agent.nodes.generate import generate_response
        from src.models.state import GraphState

        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            evaluation=EvaluationResult(
                is_relevant=True, needs_external=False, confidence=0.9, reasoning="충분"
            ),
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="영업권 정의", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        result = generate_response(state)
        assert result.final_response is not None
        assert isinstance(result.final_response, FinalResponse)
        assert result.final_response.is_answerable is True
