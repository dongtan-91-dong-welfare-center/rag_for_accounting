"""
[FUNC-007] 맥락 평가 단위 테스트

대상 모듈: src/agent/nodes/evaluate.py
검증 범위:
    - evaluate_context(): reranked_chunks → EvaluationResult 변환 (dict 반환)
    - check_relevance(): 단일 청크 관련성 판단
    - check_external_reference(): 외부 기준서 참조 필요 여부 판단
    - validate_verdict(): EvaluationResult 내부 일관성 검증 (EV-302)
    - detect_hallucination(): 컨텍스트에 없는 조항 인용 감지 (EV-303)
    - EV-301: LLM 응답 파싱 실패 시 보수적 폴백
    - CM-002: API 연결 오류 시 rewrite_count 기반 판단
"""
import pytest
from unittest.mock import MagicMock, patch
from src.models.schemas import (
    RetrievedChunk,
    RerankingResult,
    EvaluationResult,
)
from src.models.state import GraphState
from src.utils.config import RERANK_THRESHOLD, MAX_REWRITE_COUNT
from src.utils.exception import (
    EvaluationParsingError,
    LLMAPIConnectionError,
    InconsistentVerdictError,
    HallucinationDetectedError,
)
from src.agent.nodes.evaluate import (
    evaluate_context,
    check_relevance,
    check_external_reference,
    validate_verdict,
    detect_hallucination,
)


def _mock_evaluator_agent(evaluation: EvaluationResult | None = None, error: Exception | None = None):
    """
    src.agent.nodes.evaluate.Agent를 패치하여 run_sync가 지정한 결과(또는 예외)를 반환하도록 한다.
    conftest의 autouse mock_llm_agent는 generate.Agent만 패치하므로 evaluate에는 별도 패치가 필요하다.
    """
    mock_instance = MagicMock()
    # error가 있으면 side_effect로 설정, 없으면 반환값으로 설정
    if error is not None:
        mock_instance.run_sync.side_effect = error
    else:
        mock_result = MagicMock()
        mock_result.output = evaluation
        mock_instance.run_sync.return_value = mock_result
    return patch("src.agent.nodes.evaluate.Agent", return_value=mock_instance)


@pytest.mark.unit
class TestCheckRelevance:
    """check_relevance() 함수 단위 테스트"""

    def test_relevant_chunk_above_threshold(self):
        """rerank_score >= RERANK_THRESHOLD이고 content가 비어있지 않으면 True"""
        chunk = RerankingResult(
            chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="영업권 정의", score=0.8, metadata={}),
            rerank_score=RERANK_THRESHOLD + 0.1,
        )
        assert check_relevance(chunk, "영업권 손상차손") is True   # rerank_score >= RERANK_THRESHOLD

    def test_irrelevant_chunk_below_threshold(self):
        """rerank_score < RERANK_THRESHOLD이면 False"""
        chunk = RerankingResult(
            chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="내용", score=0.3, metadata={}),
            rerank_score=RERANK_THRESHOLD - 0.1,
        )
        assert check_relevance(chunk, "영업권 손상차손") is False   # rerank_score < RERANK_THRESHOLD

    def test_empty_content_returns_false(self):
        """content가 공백만 포함하면 False"""
        chunk = RerankingResult(
            chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="   ", score=0.9, metadata={}),
            rerank_score=0.9,
        )
        assert check_relevance(chunk, "영업권 손상차손") is False   # content가 공백만 포함


@pytest.mark.unit
class TestCheckExternalReference:
    """check_external_reference() 함수 단위 테스트"""

    def test_explicit_external_phrase_detected(self):
        """reasoning에 명시적 외부 참조 문구가 포함되면 standard_filter 무관하게 True"""
        evaluation = EvaluationResult(
            is_relevant=False, needs_external=False, confidence=0.5,
            reasoning="해당 항목은 타 기준서 준용이 필요합니다."
        )
        assert check_external_reference(evaluation, "ALL") is True # 외부 참조 문구
        assert check_external_reference(evaluation, "GAAP") is True # 외부 참조 문구
        assert check_external_reference(evaluation, "KIFRS") is True # 외부 참조 문구

    def test_no_external_keyword(self):
        """reasoning에 외부 참조 키워드가 없으면 False"""
        evaluation = EvaluationResult(
            is_relevant=True, needs_external=False, confidence=0.9,
            reasoning="검색된 문서에서 충분한 근거를 확인할 수 있습니다."
        )
        assert check_external_reference(evaluation, "ALL") is False # 외부 참조 키워드 없음
        assert check_external_reference(evaluation, "GAAP") is False # 외부 참조 키워드 없음
        assert check_external_reference(evaluation, "KIFRS") is False # 외부 참조 키워드 없음

    def test_all_filter_ifrs_keyword_alone_returns_false(self):
        """standard_filter=ALL에서 K-IFRS·K-GAAP 키워드 단독 등장은 외부 참조로 판단하지 않음"""
        evaluation = EvaluationResult(
            is_relevant=True, needs_external=False, confidence=0.8,
            reasoning="K-IFRS 제1116호와 K-GAAP의 비교 내용이 청크 내에 포함되어 있습니다."
        )
        assert check_external_reference(evaluation, "ALL") is False # ALL 필터에 의해 외부 참조로 판단하지 않음

    def test_single_filter_opposite_standard_returns_true(self):
        """standard_filter=GAAP에서 K-IFRS 키워드가 reasoning에 등장하면 True"""
        evaluation = EvaluationResult(
            is_relevant=False, needs_external=False, confidence=0.4,
            reasoning="해당 사안은 K-IFRS 제1109호에서 다루고 있습니다."
        )
        assert check_external_reference(evaluation, "GAAP") is True # 기준서 필터로 인해 외부 참조로 판단

    def test_negated_external_phrase_returns_false(self):
        """외부 참조 문구가 부정 문맥("… 필요하지 않습니다")이면 외부 참조로 보지 않는다"""
        evaluation = EvaluationResult(
            is_relevant=True, needs_external=False, confidence=0.96,
            reasoning="검색된 청크로 충분하며 외부 기준서 추가 검색이 필요하지 않습니다."
        )
        assert check_external_reference(evaluation, "ALL") is False
        assert check_external_reference(evaluation, "GAAP") is False
        assert check_external_reference(evaluation, "KIFRS") is False

    def test_negated_sentence_does_not_suppress_positive_sentence(self):
        """부정 문장이 있어도, 다른 문장의 (부정 아닌) 외부 참조 지시는 살아남아 True"""
        evaluation = EvaluationResult(
            is_relevant=False, needs_external=False, confidence=0.5,
            reasoning="청크 본문만으로는 부족하지 않습니다. 다만 해당 항목은 타 기준서 준용이 필요합니다."
        )
        assert check_external_reference(evaluation, "ALL") is True


@pytest.mark.unit
class TestEvaluateContext:
    """evaluate_context() 노드 함수 단위 테스트"""

    def test_empty_reranked_chunks_returns_early(self):
        """
        [Case 1] reranked_chunks가 비어 있으면 LLM 호출 없이 조기 반환.
        - is_relevant=False, needs_external=False
        - error_logs는 변동 없음
        """
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            reranked_chunks=[],
        )
        result = evaluate_context(state)

        assert "evaluation" in result   # evaluation 키 존재 확인
        eval_result = result["evaluation"]
        assert isinstance(eval_result, EvaluationResult)    # EvaluationResult 타입 반환
        assert eval_result.is_relevant is False # reranked_chunks가 없음
        assert eval_result.needs_external is False # 외부 참조 키워드 없음
        assert "error_logs" not in result   # 평가 실패 로깅 없음

    def test_no_relevant_chunks_after_filtering_returns_early(self):
        """rerank_score가 모두 임계값 미만일 때 LLM 호출 없이 조기 반환"""
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="내용", score=0.1, metadata={}),
                    rerank_score=RERANK_THRESHOLD - 0.1,
                ),
            ],
        )
        result = evaluate_context(state)
        eval_result = result["evaluation"]
        assert eval_result.is_relevant is False # 점수가 기준치 미달
        assert eval_result.needs_external is False  # 외부 참조 키워드 없음

    def test_external_reference_overrides_needs_external(self):
        """
        외부 참조 키워드 포함 reasoning, standard_filter=GAAP → needs_external=True.
        LLM이 needs_external=False로 답해도 check_external_reference()에서 True로 오버라이드한다.
        """
        llm_eval = EvaluationResult(
            is_relevant=False,
            needs_external=False,
            confidence=0.6,
            reasoning="해당 항목은 타 기준서 준용이 필요합니다."
        )
        state = GraphState(
            original_query="리스 회계처리는?",
            standard_filter="GAAP",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="리스 회계처리...", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_evaluator_agent(evaluation=llm_eval):
            result = evaluate_context(state)

        eval_result = result["evaluation"]
        assert eval_result.needs_external is True   # 추론 필요
        assert eval_result.is_relevant is False # 재정렬 점수 기반

    def test_all_filter_does_not_override_when_keyword_alone(self):
        """
        standard_filter=ALL에서 reasoning에 IFRS·GAAP 키워드만 단독 등장하는 경우,
        check_external_reference()는 False를 반환하여 LLM의 needs_external=False가 보존된다.
        """
        llm_eval = EvaluationResult(
            is_relevant=True,
            needs_external=False,
            confidence=0.9,
            reasoning="K-IFRS와 K-GAAP의 비교 내용이 청크 내에 모두 포함되어 있어 외부 참조가 불필요합니다."
        )
        state = GraphState(
            original_query="리스 회계처리는?",
            standard_filter="ALL",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="리스 비교...", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_evaluator_agent(evaluation=llm_eval):
            result = evaluate_context(state)

        eval_result = result["evaluation"]
        assert eval_result.needs_external is False  # 추론 불필요, ALL 필터 적용
        assert eval_result.is_relevant is True  # LLM 응답 유지

    def test_negated_external_reasoning_does_not_override(self):
        """LLM이 needs_external=False + 부정 문맥 reasoning을 반환하면,
        check_external_reference가 오버라이드하지 않아 needs_external=False가 보존된다.
        substring 오탐으로 CRAG 루프가 MAX_REWRITE_COUNT까지 3배 공회전하던 회귀 방지
        """
        llm_eval = EvaluationResult(
            is_relevant=True,
            needs_external=False,
            confidence=0.96,
            reasoning="청크에 충분한 근거가 있어 외부 기준서 추가 검색이 필요하지 않습니다."
        )
        state = GraphState(
            original_query="재고자산의 취득원가는 어떻게 측정하나요?",
            standard_filter="ALL",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="취득원가 측정...", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_evaluator_agent(evaluation=llm_eval):
            result = evaluate_context(state)

        eval_result = result["evaluation"]
        assert eval_result.needs_external is False  # 부정 문맥 → 오버라이드 안 함
        assert eval_result.is_relevant is True      # LLM 응답 유지
        assert "error_logs" not in result           # 일관성 위반 없음

    def test_llm_exception_propagates(self):
        """
        Unknown Exception 발생 시 원본 예외가 그대로 전파된다.
        - 시스템 에러는 AccountingRAGError로 래핑하지 않고 파이프라인을 중단시킨다.
        - needs_external 의미 정합성 유지: 네트워크 오류 ≠ 외부 참조 필요
        """
        state = GraphState(
            original_query="리스 회계처리는?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="리스 회계처리...", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_evaluator_agent(error=ValueError("올바르지 않은 JSON 응답")):
            with pytest.raises(ValueError):
                evaluate_context(state)

    def test_normal_path_returns_llm_evaluation(self):
        """정상 케이스: LLM이 반환한 EvaluationResult가 그대로 evaluation 필드로 반환된다."""
        llm_eval = EvaluationResult(
            is_relevant=True,
            needs_external=False,
            confidence=0.85,
            reasoning="질의에 대한 충분한 근거가 청크 내에 포함되어 있습니다."
        )
        state = GraphState(
            original_query="유형자산 감가상각 방법은?",
            standard_filter="ALL",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="감가상각 방법...", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_evaluator_agent(evaluation=llm_eval):
            result = evaluate_context(state)

        eval_result = result["evaluation"]
        assert eval_result.is_relevant is True  # LLM 응답 유지
        assert eval_result.needs_external is False  # 추론 불필요, ALL 필터 적용
        assert eval_result.confidence == 0.85   # LLM 응답 유지
        assert "error_logs" not in result   # 에러 없음

    def test_llm_parsing_failure_returns_conservative_fallback(self):
        """EvaluationParsingError 발생 시 보수적 폴백이 반환되고 error_logs에 기록되는지 검증

        [EV-301] EvaluationParsingError는 AccountingRAGError 계열이므로 to_error_log()를 통해 구조화된 로그로 변환되어 error_logs에 누적된다.
        폴백은 is_relevant=False, needs_external=True로 설정되어 CRAG 루프 재진입을 유도한다.
        """
        state = GraphState(
            original_query="리스 회계처리는?",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="리스 회계처리...", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_evaluator_agent(error=EvaluationParsingError("JSON 파싱 실패")):
            result = evaluate_context(state)

        assert result["evaluation"].is_relevant is False    # 보수적 폴백
        assert result["evaluation"].needs_external is True  # CRAG 루프 재진입 유도
        assert "error_logs" in result   # error_logs가 존재하는지 확인
        assert result["error_logs"][0]["error_type"] == "EV-301"    # 에러 타입이 EV-301인지 확인

    def test_llm_api_error_below_max_retries_triggers_reentry(self):
        """rewrite_count < MAX_REWRITE_COUNT → needs_external=True로 CRAG 루프 재진입

        네트워크 오류는 일시적일 수 있으므로, 재시도 여지가 있을 때는 루프로 재진입한다.
        """
        state = GraphState(
            original_query="리스 회계처리는?",
            rewrite_count=MAX_REWRITE_COUNT - 1,
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="리스 회계처리...", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_evaluator_agent(error=LLMAPIConnectionError("API 연결 오류", node="evaluate")):
            result = evaluate_context(state)

        assert result["evaluation"].is_relevant is False    # 폴백
        assert result["evaluation"].needs_external is True  # 재시도 여지 있음 → CRAG 루프 재진입
        assert result["error_logs"][-1]["error_type"] == "CM-002"   # 에러 타입이 CM-002인지 확인

    def test_llm_api_error_at_max_retries_stops_loop(self):
        """rewrite_count >= MAX_REWRITE_COUNT → needs_external=False로 루프 강제 종료

        최대 재시도에 도달한 상태에서의 네트워크 오류는 루프를 지속해도 의미가 없으므로 중단한다.
        """
        state = GraphState(
            original_query="리스 회계처리는?",
            rewrite_count=MAX_REWRITE_COUNT,
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="리스 회계처리...", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_evaluator_agent(error=LLMAPIConnectionError("API 연결 오류", node="evaluate")):
            result = evaluate_context(state)

        assert result["evaluation"].is_relevant is False    # 폴백
        assert result["evaluation"].needs_external is False # 최대 재시도 도달 → 루프 강제 종료
        assert result["error_logs"][-1]["error_type"] == "CM-002"   # 에러 타입이 CM-002인지 확인

    def test_inconsistent_verdict_returns_ev302_fallback(self):
        """LLM이 is_relevant=True, confidence=0.2를 반환하면 일관성 위반으로 보수적 폴백

        is_relevant=True이면서 confidence가 0.3 미만이면 신뢰할 수 없는 평가로 간주한다.
        EV-302 보수적 폴백은 needs_external=False로 설정되어 CRAG 루프에 재진입하지 않는다.
        """
        llm_eval = EvaluationResult(
            is_relevant=True,
            needs_external=False,
            confidence=0.2,
            reasoning="충분한 근거가 포함되어 있습니다."
        )
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            standard_filter="ALL",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="손상차손 내용", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_evaluator_agent(evaluation=llm_eval):
            result = evaluate_context(state)

        assert result["evaluation"].is_relevant is False    # 보수적 폴백
        assert result["evaluation"].needs_external is False # needs_external=False → 루프 재진입 없음
        assert result["error_logs"][-1]["error_type"] == "EV-302"   # 에러 타입이 EV-302인지 확인

    def test_hallucination_detected_returns_ev303_fallback(self):
        """reasoning에 청크에 없는 조항 번호 인용 시 환각 감지로 is_relevant=False 반환

        reasoning에 'K-IFRS 제1116호'가 인용되어 있지만 청크 내용에 해당 조항이 없으면 환각으로 판단.
        EV-303 보수적 폴백은 needs_external=False로 설정되어 CRAG 루프에 재진입하지 않는다.
        """
        llm_eval = EvaluationResult(
            is_relevant=True,
            needs_external=False,
            confidence=0.85,
            reasoning="K-IFRS 제1116호 제15조에 따르면 리스 자산을 인식해야 합니다."
        )
        state = GraphState(
            original_query="리스 회계처리는?",
            standard_filter="ALL",
            reranked_chunks=[
                RerankingResult(
                    chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content="리스 회계처리 일반론입니다.", score=0.9, metadata={}),
                    rerank_score=0.95,
                ),
            ],
        )
        with _mock_evaluator_agent(evaluation=llm_eval):
            result = evaluate_context(state)

        assert result["evaluation"].is_relevant is False    # 환각 감지 → is_relevant=False
        assert result["evaluation"].needs_external is False # needs_external=False → 루프 재진입 없음
        assert result["error_logs"][-1]["error_type"] == "EV-303"   # 에러 타입이 EV-303인지 확인


@pytest.mark.unit
class TestValidateVerdict:
    """validate_verdict() 내부 일관성 검증 단위 테스트 (EV-302)"""

    def test_consistent_verdict_no_error(self):
        """정상 평가 결과는 예외 없이 통과한다"""
        eval_result = EvaluationResult(
            is_relevant=True, needs_external=False, confidence=0.85,
            reasoning="충분한 근거가 포함되어 있습니다."
        )
        validate_verdict(eval_result)   # 예외 없이 통과해야 함

    def test_low_confidence_with_relevant_raises_error(self):
        """is_relevant=True이고 confidence < 0.3이면 InconsistentVerdictError 발생"""
        eval_result = EvaluationResult(
            is_relevant=True, needs_external=False, confidence=0.2,
            reasoning="충분한 근거가 포함되어 있습니다."
        )
        with pytest.raises(InconsistentVerdictError):
            validate_verdict(eval_result)

    def test_needs_external_without_reference_phrase_raises_error(self):
        """needs_external=True, is_relevant=True이고 외부 참조 근거 없으면 InconsistentVerdictError 발생"""
        eval_result = EvaluationResult(
            is_relevant=True, needs_external=True, confidence=0.8,
            reasoning="검색된 청크에 충분한 내용이 있습니다."   # 외부 참조 키워드 없음
        )
        with pytest.raises(InconsistentVerdictError):
            validate_verdict(eval_result)

    def test_needs_external_with_reference_phrase_no_error(self):
        """needs_external=True, is_relevant=True이고 외부 참조 근거가 있으면 통과"""
        eval_result = EvaluationResult(
            is_relevant=True, needs_external=True, confidence=0.7,
            reasoning="해당 항목은 타 기준서 준용이 필요합니다."   # 외부 참조 키워드 있음
        )
        validate_verdict(eval_result)   # 예외 없이 통과해야 함

    def test_not_relevant_low_confidence_no_error(self):
        """is_relevant=False이면 confidence 낮아도 불일치가 아님"""
        eval_result = EvaluationResult(
            is_relevant=False, needs_external=False, confidence=0.1,
            reasoning="관련 없는 내용입니다."
        )
        validate_verdict(eval_result)   # 예외 없이 통과해야 함

    def test_needs_external_with_negated_phrase_raises_error(self):
        """[#145] needs_external=True인데 외부 참조 문구가 부정 문맥이면 신호로 보지 않아 불일치"""
        eval_result = EvaluationResult(
            is_relevant=True, needs_external=True, confidence=0.8,
            reasoning="외부 기준서 추가 검색은 필요하지 않습니다."   # 부정 문맥 → 외부 참조 신호 아님
        )
        with pytest.raises(InconsistentVerdictError):
            validate_verdict(eval_result)


@pytest.mark.unit
class TestDetectHallucination:
    """detect_hallucination() 환각 감지 단위 테스트 (EV-303)"""

    def _make_chunk(self, content: str) -> RerankingResult:
        return RerankingResult(
            chunk=RetrievedChunk(chunk_id="c1", document_id="D1", content=content, score=0.9, metadata={}),
            rerank_score=0.9,
        )

    def test_no_citations_in_reasoning_no_error(self):
        """reasoning에 조항 번호 패턴이 없으면 예외 없이 통과"""
        eval_result = EvaluationResult(
            is_relevant=True, needs_external=False, confidence=0.9,
            reasoning="검색된 청크에 충분한 근거가 포함되어 있습니다."
        )
        detect_hallucination(eval_result, [self._make_chunk("리스 관련 내용")])   # 예외 없이 통과해야 함

    def test_citation_found_in_chunks_no_error(self):
        """reasoning의 조항 번호가 청크에도 존재하면 예외 없이 통과"""
        eval_result = EvaluationResult(
            is_relevant=True, needs_external=False, confidence=0.9,
            reasoning="K-IFRS 제1116호에 따라 리스 자산을 인식합니다."
        )
        chunk = self._make_chunk("K-IFRS 제1116호에 따르면 사용권 자산을 인식해야 한다.")
        detect_hallucination(eval_result, [chunk])   # 예외 없이 통과해야 함

    def test_citation_not_in_chunks_raises_error(self):
        """reasoning의 조항 번호가 청크에 없으면 HallucinationDetectedError 발생"""
        eval_result = EvaluationResult(
            is_relevant=True, needs_external=False, confidence=0.9,
            reasoning="K-IFRS 제1116호 제15조에 따르면 리스 자산을 인식해야 합니다."
        )
        chunk = self._make_chunk("리스 회계처리 일반론입니다.")   # 조항 번호 없음
        with pytest.raises(HallucinationDetectedError):
            detect_hallucination(eval_result, [chunk])

    def test_empty_chunks_no_error(self):
        """청크가 없으면 검증을 건너뛴다"""
        eval_result = EvaluationResult(
            is_relevant=True, needs_external=False, confidence=0.9,
            reasoning="K-IFRS 제1116호를 참조합니다."
        )
        detect_hallucination(eval_result, [])   # 예외 없이 통과해야 함
