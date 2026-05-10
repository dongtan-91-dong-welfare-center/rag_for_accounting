"""
[FUNC-008] 답변 생성 단위 테스트

대상 모듈: src/agent/nodes/generate.py
검증 범위:
    - generate_response(): PydanticAI 연동 및 최종 응답 생성
    - extract_citations_from_text(): 정규식을 통한 인용 마크업 파싱 및 Citation 조립
    - build_unanswerable_response(): 안전 응답 생성

TODO: generate_response()의 PydanticAI Mocking 테스트 보완
"""
import pytest
from src.models.schemas import (
    RetrievedChunk,
    RerankingResult,
    EvaluationResult,
    Citation,
    FinalResponse,
    LLMInternalResponse
)
from src.models.state import GraphState
from src.utils.config import RERANK_THRESHOLD
from src.agent.nodes.generate import extract_citations_from_text, build_unanswerable_response, generate_response


@pytest.mark.unit
class TestExtractCitationsFromText:
    """extract_citations_from_text() 함수 단위 테스트"""

    def test_extract_citations_success(self):
        """[n] 마크업에서 정상적으로 Citation을 추출하는지 검증"""
        text = "영업권 손상차손은 매년 검사합니다 [1]. 또한 징후가 있을 때도 합니다 [2]."
        chunk_map = {
            1: RerankingResult(
                chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="매년 검사", score=0.9, metadata={}),
                rerank_score=0.95
            ),
            2: RerankingResult(
                chunk=RetrievedChunk(chunk_id="c2", document_id="D1", content="징후 시 검사", score=0.8, metadata={}),
                rerank_score=0.90
            )
        }
        
        citations, result_text = extract_citations_from_text(text, chunk_map)
        
        assert len(citations) == 2  # 응답 문서 근거 개수 검증
        assert citations[0].chunk_id == "c1"    # 응답 문서 근거 ID 검증
        assert citations[1].chunk_id == "c2"    # 응답 문서 근거 ID 검증
        assert "[1]" in result_text             # 원본 텍스트는 보존되어야 함

    def test_extract_citations_missing_index(self):
        """chunk_map에 없는 인덱스는 무시되는지 검증"""
        text = "존재하지 않는 문헌 [99] 참조."
        chunk_map = {
            1: RerankingResult(
                chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="정상", score=0.9, metadata={}),
                rerank_score=0.95
            )
        }
        
        citations, _ = extract_citations_from_text(text, chunk_map)
        assert len(citations) == 0

    def test_extract_citations_duplicate_index(self):
        """동일한 인덱스를 여러 번 참조할 경우 중복 제거 여부 검증"""
        text = "이것은 중요합니다 [1]. 다시 말해 매우 중요하죠 [1]."
        chunk_map = {
            1: RerankingResult(
                chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="중요", score=0.9, metadata={}),
                rerank_score=0.95
            )
        }
        
        citations, _ = extract_citations_from_text(text, chunk_map)
        assert len(citations) == 1


@pytest.mark.unit
class TestBuildUnanswerableResponse:
    """build_unanswerable_response() 함수 단위 테스트"""

    def test_unanswerable_response_structure(self):
        """답변 불가능한 경우의 안전 응답 구조를 검증"""
        response = build_unanswerable_response("영업권 손상차손 인식 기준은?")
        assert isinstance(response, FinalResponse)                        # 최종 응답 구조체를 반환하는지?
        assert response.is_answerable is False                        # 답변 불가능 플래그가 설정되었는지?
        assert response.citations == []                               # 인용 근거가 비어있는지?
        assert response.confidence_score == 0.0                         # 신뢰도 점수가 0인지?
        assert "충분한 근거를 찾지 못했습니다" in response.answer       # 안전 응답 메시지를 포함하는지?


@pytest.mark.unit
class TestGenerateResponse:
    """generate_response() 노드 함수 인터페이스 검증"""

    @pytest.mark.skip(reason="FUNC-008 PydanticAI Mocking 추가 후 활성화 예정")
    def test_generate_returns_final_response(self):
        """
        입력: GraphState (evaluation + reranked_chunks 포함)
        출력: dict (final_response, retrieval_score, generation_score)
        """
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
        
        assert "final_response" in result                           # 최종 결과물을 반환했는지?
        assert isinstance(result["final_response"], FinalResponse)   # 최종 결과물이 FinalResponse인지?
        assert result["final_response"].is_answerable is True         # 답변이 가능한지?
        assert "retrieval_score" in result                        # 검색 점수를 반환했는지?
        assert "generation_score" in result                         # 생성 점수를 반환했는지?
