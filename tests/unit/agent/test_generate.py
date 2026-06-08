"""
[FUNC-008] 답변 생성 단위 테스트

대상 모듈: src/agent/nodes/generate.py
검증 범위:
    - generate_response(): PydanticAI 연동 및 최종 응답 생성
    - extract_citations_from_text(): 정규식을 통한 인용 마크업 파싱 및 Citation 조립
    - build_unanswerable_response(): 안전 응답 생성
"""
import pytest
import pydantic
import httpx
from pydantic import BaseModel
from pydantic_ai.exceptions import UnexpectedModelBehavior
from unittest.mock import MagicMock, patch
from src.models.schemas import (
    RetrievedChunk,
    RerankingResult,
    EvaluationResult,
    Citation,
    FinalResponse,
    LLMInternalResponse
)
from src.models.state import GraphState
from src.utils.config import MAX_CONTEXT_TOKENS
from src.utils.exception import LLMResponseFormatError, LLMAPIConnectionError
from src.agent.nodes.generate import extract_citations_from_text, build_unanswerable_response, generate_response


def _mock_generator_agent(response: LLMInternalResponse | None = None, error: Exception | None = None):
    """
    src.agent.nodes.generate.Agent를 패치하여 run_sync가 지정한 결과(또는 예외)를 반환하도록 한다.
    conftest의 autouse mock_llm_agent는 generate.Agent를 전역 패치하므로 특정 동작(에러 유발 등)이 필요한 테스트에서는 이 헬퍼로 재패치한다.
    """
    mock_instance = MagicMock()
    if error is not None:
        mock_instance.run_sync.side_effect = error
    else:
        mock_result = MagicMock()
        mock_result.output = response
        mock_instance.run_sync.return_value = mock_result
    return patch("src.agent.nodes.generate.Agent", return_value=mock_instance)


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

    def test_generate_returns_final_response(self):
        """정상 경로: GraphState(evaluation + reranked_chunks)로 FinalResponse가 반환되는지 검증

        conftest의 mock_llm_agent가 전역으로 generate.Agent를 패치하므로 별도 패치 불필요.
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
        assert isinstance(result["final_response"], FinalResponse)  # 최종 결과물이 FinalResponse인지?
        assert result["final_response"].is_answerable is True       # 답변이 가능한지?
        assert "retrieval_score" in result                          # 검색 점수를 반환했는지?
        assert "generation_score" in result                         # 생성 점수를 반환했는지?

    def test_llm_response_format_error_records_error_log(self):
        """LLMResponseFormatError 발생 시 error_logs에 기록되고 폴백 응답이 반환되는지 검증

        [GN-401] LLMResponseFormatError는 AccountingRAGError 계열이므로 to_error_log()를 통해 구조화된 로그로 변환되어 error_logs에 누적된다.
        터미널 노드이므로 예외를 상위로 전파하지 않고 build_unanswerable_response 폴백을 반환한다.
        """
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="영업권 정의", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_generator_agent(error=LLMResponseFormatError("응답 포맷 오류")):
            result = generate_response(state)

        assert "error_logs" in result   # error_logs가 존재하는지 확인
        assert result["error_logs"][0]["error_type"] == "GN-401"    # 에러 타입이 GN-401인지 확인
        assert result["final_response"].is_answerable is False       # 폴백 응답이 반환되는지 확인

    def test_llm_api_connection_error_records_error_log(self):
        """LLMAPIConnectionError 발생 시 error_logs에 기록되고 폴백 응답이 반환되는지 검증

        [CM-002] LLMAPIConnectionError는 AccountingRAGError 계열이므로 to_error_log()를 통해 구조화된 로그로 변환되어 error_logs에 누적된다.
        터미널 노드이므로 예외를 상위로 전파하지 않고 build_unanswerable_response 폴백을 반환한다.
        """
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="영업권 정의", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_generator_agent(error=LLMAPIConnectionError("API 연결 실패", node="generate")):
            result = generate_response(state)

        assert "error_logs" in result   # error_logs가 존재하는지 확인
        assert result["error_logs"][0]["error_type"] == "CM-002"    # 에러 타입이 CM-002인지 확인
        assert result["final_response"].is_answerable is False       # 폴백 응답이 반환되는지 확인

    def test_context_truncation_drops_excess_chunks(self):
        """MAX_CONTEXT_TOKENS 초과 시 후순위 청크가 조립에서 제외되는지 검증 (GN-402 트런케이션)"""
        small_content = "청크내용" * 10
        # [2] + large_content를 추가하면 estimated_tokens > MAX_CONTEXT_TOKENS가 되도록 설정
        large_content = "가" * (MAX_CONTEXT_TOKENS * 2 + 1)

        state = GraphState(
            original_query="영업권 손상차손의 인식 기준은?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content=small_content, score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c2", document_id="D1", content=large_content, score=0.8, metadata={}),
                    rerank_score=0.85,
                ),
            ],
        )
        mock_response = LLMInternalResponse(answer="영업권의 장부금액이 배분된 현금창출단위(CGU)의 회수가능액에 미달할 때...[1]", is_answerable=True, llm_self_score=0.9)
        with _mock_generator_agent(response=mock_response):
            result = generate_response(state)

        assert "final_response" in result   # 정상적으로 최종 응답이 반환되었는지
        assert len(result["final_response"].citations) == 1 # 두 번째 청크는 토큰 한도 초과로 인해 제외 → citations는 c1 하나만 포함
        assert result["final_response"].citations[0].chunk_id == "c1"  # 첫 번째 청크의 ID가 올바르게 저장되었는지

    def test_context_length_exceeded_raises_gn402(self):
        """첫 번째 청크만으로 토큰 한도 초과 시 GN-402 에러 로그가 기록되는지 검증"""
        huge_content = "가" * (MAX_CONTEXT_TOKENS * 2 + 1)

        state = GraphState(
            original_query="영업권 손상차손의 인식 기준은?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content=huge_content, score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        result = generate_response(state)

        assert "error_logs" in result   # 에러 로그가 기록되었는지
        assert result["error_logs"][0]["error_type"] == "GN-402"   # GN-402 타입이 올바르게 기록되었는지
        assert result["final_response"].is_answerable is False  # 답변 불가능한 경우의 안전 응답이 반환되었는지

    def test_pydantic_validation_error_wrapped_as_gn401(self):
        """pydantic.ValidationError 발생 시 GN-401 에러 로그로 기록되는지 검증"""
        class _M(BaseModel):
            x: int

        try:
            _M(x="잘못된 값")  # type: ignore[arg-type]
        except pydantic.ValidationError as ve:
            validation_error = ve

        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="내용", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_generator_agent(error=validation_error):
            result = generate_response(state)

        assert result["error_logs"][0]["error_type"] == "GN-401" # pydantic.ValidationError 발생 시 GN-401 에러 로그로 기록되는지 검증
        assert result["final_response"].is_answerable is False  # 답변 불가능한 경우의 안전 응답이 반환되었는지

    def test_unexpected_model_behavior_wrapped_as_gn401(self):
        """pydantic_ai.UnexpectedModelBehavior 발생 시 GN-401 에러 로그로 기록되는지 검증"""
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="내용", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_generator_agent(error=UnexpectedModelBehavior("예상치 못한 모델 출력")):
            result = generate_response(state)

        assert result["error_logs"][0]["error_type"] == "GN-401" # pydantic_ai.UnexpectedModelBehavior 발생 시 GN-401 에러 로그로 기록되는지 검증
        assert result["final_response"].is_answerable is False  # 답변 불가능한 경우의 안전 응답이 반환되었는지

    def test_httpx_request_error_wrapped_as_cm002(self):
        """httpx.RequestError 발생 시 CM-002 에러 로그로 기록되는지 검증"""
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="내용", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_generator_agent(error=httpx.RequestError("connection failed")):
            result = generate_response(state)

        assert result["error_logs"][0]["error_type"] == "CM-002"    # httpx.RequestError 발생 시 CM-002 에러 로그로 기록되는지 검증
        assert result["final_response"].is_answerable is False  # 답변 불가능한 경우의 안전 응답이 반환되었는지

    def test_generation_score_clamped_below_zero(self):
        """llm_self_score < 0.0 이면 generation_score가 0.0으로 클램핑되는지 검증"""
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="내용", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        mock_response = LLMInternalResponse(answer="영업권의 장부금액이 배분된 현금창출단위(CGU)의 회수가능액에 미달할 때...[1]", is_answerable=True, llm_self_score=-0.5)
        with _mock_generator_agent(response=mock_response):
            result = generate_response(state)

        assert result["generation_score"] == 0.0    # llm_self_score < 0.0 이면 generation_score가 0.0으로 클램핑되는지 검증

    def test_generation_score_clamped_above_one(self):
        """llm_self_score > 1.0 이면 generation_score가 1.0으로 클램핑되는지 검증"""
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="내용", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        mock_response = LLMInternalResponse(answer="영업권의 장부금액이 배분된 현금창출단위(CGU)의 회수가능액에 미달할 때...[1]", is_answerable=True, llm_self_score=1.5)
        with _mock_generator_agent(response=mock_response):
            result = generate_response(state)

        assert result["generation_score"] == 1.0    # llm_self_score > 1.0 이면 generation_score가 1.0으로 클램핑되는지 검증

    def test_empty_citations_with_answerable_raises_gn401(self):
        """is_answerable=True이고 citations가 없으면 GN-401 에러 로그가 기록되는지 검증"""
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="내용", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        mock_response = LLMInternalResponse(answer="영업권의 장부금액이 배분된 현금창출단위(CGU)의 회수가능액에 미달할 때...", is_answerable=True, llm_self_score=0.9)
        with _mock_generator_agent(response=mock_response):
            result = generate_response(state)

        assert result["error_logs"][0]["error_type"] == "GN-401"    # is_answerable=True이고 citations가 없으면 GN-401 에러 로그가 기록되는지 검증
        assert result["final_response"].is_answerable is False  # 답변 불가능한 경우의 안전 응답이 반환되었는지
