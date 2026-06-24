import json
import logging
import pytest
from unittest.mock import MagicMock, patch

from src.agent.nodes.rewrite import (
    apply_decompose,
    apply_hyde,
    apply_stepback,
    classify_and_select,
    rewrite_query,
)
from src.models.state import GraphState


def _last_user_content(mock_client) -> str:
    """가장 최근 client.chat.completions.create 호출의 사용자 메시지 본문을 반환"""
    call = mock_client.chat.completions.create.call_args
    return call.kwargs["messages"][0]["content"]


def _mock_resp(content: dict) -> MagicMock:
    # OpenAI 응답 객체를 흉내 낸 가짜 객체 생성
    # content 딕셔너리를 JSON 문자열로 변환해 resp.choices[0].message.content에 실제로 저장
    # rewrite.py의 json.loads(resp.choices[0].message.content)가 그대로 읽을 수 있도록 맞춤
    resp = MagicMock()
    resp.choices[0].message.content = json.dumps(content)
    return resp


def _mock_raw_resp(raw: str) -> MagicMock:
    # _mock_resp와 달리 json.dumps 변환 없이 raw 문자열을 content에 그대로 심는다
    # LLM이 JSON을 마크다운 코드 블록(```json ... ```)으로 감싸 반환하는 경우를 재현할 때 사용
    # _strip_markdown이 래퍼를 올바르게 제거하고 파싱하는지 검증하는 테스트에서만 사용됨
    resp = MagicMock()
    resp.choices[0].message.content = raw
    return resp


# ── GraphState 기본값 ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_state_default_fields():
    state = GraphState(original_query="영업권 손상차손 인식 기준은?")
    assert state.is_accounting_query is True
    assert state.rewrite_count == 0
    assert state.rewritten_query is None


# ── classify_and_select ────────────────────────────────────────────────────────

@pytest.mark.unit
class TestClassifyAndSelect:
    # [단위 테스트 범위]
    # LLM이 반환한 JSON을 올바르게 파싱·처리하는지만 검증
    # LLM이 실제로 올바른 전략을 선택하는지(응답 품질)는 범위 밖 → 통합 테스트 또는 수동 테스트로 검증
    PATCH = "src.agent.nodes.rewrite.client"

    def test_accounting_hyde(self):
        with patch(self.PATCH) as mock_client:
            # patch는 client만 가짜로 교체 — classify_and_select 함수 자체는 실제로 실행됨
            # client.chat.completions.create() 호출 코드도 실행되지만 HTTP 요청은 발생하지 않음
            # 실제 환경에서는 LLM이 이 JSON을 생성하지만, 여기서는 우리가 직접 지정
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"is_accounting": True, "strategy": "hyde"}
            )
            is_acc, strategy, confidence = classify_and_select("영업권 손상차손 인식 기준은?")
        assert is_acc is True
        assert strategy == "hyde"

    def test_accounting_decompose(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"is_accounting": True, "strategy": "decompose"}
            )
            is_acc, strategy, confidence = classify_and_select("유형자산과 무형자산의 감가상각 방법 차이는?")
        assert is_acc is True
        assert strategy == "decompose"

    def test_accounting_stepback(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"is_accounting": True, "strategy": "stepback"}
            )
            is_acc, strategy, confidence = classify_and_select("삼성전자 2023년 영업권 500억 손상 처리 기준은?")
        assert is_acc is True
        assert strategy == "stepback"

    def test_non_accounting(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"is_accounting": False, "strategy": "bypass"}
            )
            is_acc, strategy, confidence = classify_and_select("오늘 날씨 어때?")
        assert is_acc is False
        assert strategy == "bypass"

    def test_llm_failure_fallback(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("timeout")
            is_acc, strategy, confidence = classify_and_select("영업권 손상차손 인식 기준은?")
        assert is_acc is True
        assert strategy == "hyde"
        assert confidence == 0.0   # 폴백 시 신뢰도 0.0

    def test_confidence_parsed_from_response(self):
        # LLM이 반환한 confidence 값이 그대로 파싱되어야 함
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"is_accounting": False, "strategy": "bypass", "confidence": 0.12}
            )
            is_acc, strategy, confidence = classify_and_select("오늘 날씨 어때?")
        assert is_acc is False
        assert confidence == 0.12

    def test_confidence_missing_defaults_to_zero(self):
        # confidence 키가 없으면 0.0으로 폴백
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"is_accounting": True, "strategy": "hyde"}
            )
            _, _, confidence = classify_and_select("영업권 손상차손 인식 기준은?")
        assert confidence == 0.0

    def test_confidence_clamped_to_unit_range(self):
        # 범위를 벗어난 값은 [0.0, 1.0]으로 클램프
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"is_accounting": True, "strategy": "hyde", "confidence": 1.7}
            )
            _, _, confidence = classify_and_select("영업권 손상차손 인식 기준은?")
        assert confidence == 1.0

    def test_confidence_non_numeric_defaults_to_zero(self):
        # 숫자로 변환 불가한 값은 0.0으로 폴백
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"is_accounting": True, "strategy": "hyde", "confidence": "high"}
            )
            _, _, confidence = classify_and_select("영업권 손상차손 인식 기준은?")
        assert confidence == 0.0

    def test_missing_keys_use_defaults(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp({})
            is_acc, strategy, confidence = classify_and_select("영업권 손상차손 인식 기준은?")
        assert is_acc is True
        assert strategy == "hyde"

    def test_markdown_wrapper_stripped_and_parsed(self):
        # LLM이 JSON을 마크다운 코드 블록으로 감싸 반환해도 올바르게 파싱되어야 함
        wrapped = "```json\n{\"is_accounting\": false, \"strategy\": \"bypass\"}\n```"
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_raw_resp(wrapped)
            is_acc, strategy, confidence = classify_and_select("오늘 날씨 어때?")
        assert is_acc is False
        assert strategy == "bypass"

    def test_string_false_treated_as_false(self):
        # LLM이 boolean 대신 문자열 "False" 반환 → 비어있지 않은 문자열은 True로 평가되므로 타입 변환 필요
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"is_accounting": "False", "strategy": "bypass"}
            )
            is_acc, strategy, confidence = classify_and_select("오늘 날씨 어때?")
        assert is_acc is False

    def test_string_true_treated_as_true(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"is_accounting": "True", "strategy": "hyde"}
            )
            is_acc, strategy, confidence = classify_and_select("영업권 손상차손 인식 기준은?")
        assert is_acc is True


# ── apply_hyde ─────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestApplyHyde:
    PATCH = "src.agent.nodes.rewrite.client"
    QUERY = "리스부채 최초 인식 방법은?"

    def test_returns_original_and_hypothetical(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"hypothetical_answer": "리스부채는 리스료의 현재가치로 측정합니다."}
            )
            result = apply_hyde(self.QUERY, "ALL")
        assert result[0] == self.QUERY
        assert result[1] == "리스부채는 리스료의 현재가치로 측정합니다."
        assert len(result) == 2

    def test_llm_failure_returns_original_only(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("timeout")
            result = apply_hyde(self.QUERY, "ALL")
        assert result == [self.QUERY]

    def test_empty_hypothetical_returns_original_only(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"hypothetical_answer": ""}
            )
            result = apply_hyde(self.QUERY, "ALL")
        assert result == [self.QUERY]

    def test_markdown_wrapper_stripped_and_parsed(self):
        wrapped = "```json\n{\"hypothetical_answer\": \"리스부채는 현재가치로 측정합니다.\"}\n```"
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_raw_resp(wrapped)
            result = apply_hyde(self.QUERY, "ALL")
        assert result == [self.QUERY, "리스부채는 현재가치로 측정합니다."]


# ── apply_decompose ────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestApplyDecompose:
    PATCH = "src.agent.nodes.rewrite.client"
    QUERY = "유형자산과 무형자산의 감가상각 방법 차이는?"

    def test_returns_original_and_subqueries(self):
        subs = ["유형자산 감가상각 방법은?", "무형자산 상각 방법은?"]
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"sub_queries": subs}
            )
            result = apply_decompose(self.QUERY, "ALL")
        assert result[0] == self.QUERY
        assert result[1:] == subs
        assert len(result) == 3

    def test_llm_failure_returns_original_only(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("timeout")
            result = apply_decompose(self.QUERY, "ALL")
        assert result == [self.QUERY]

    def test_empty_subqueries_returns_original_only(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"sub_queries": []}
            )
            result = apply_decompose(self.QUERY, "ALL")
        assert result == [self.QUERY]

    def test_markdown_wrapper_stripped_and_parsed(self):
        wrapped = "```json\n{\"sub_queries\": [\"유형자산 감가상각 방법은?\", \"무형자산 상각 방법은?\"]}\n```"
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_raw_resp(wrapped)
            result = apply_decompose(self.QUERY, "ALL")
        assert result[0] == self.QUERY
        assert len(result) == 3


# ── apply_stepback ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestApplyStepback:
    PATCH = "src.agent.nodes.rewrite.client"
    QUERY = "삼성전자 2023년 영업권 500억 손상 처리 기준은?"

    def test_returns_original_and_abstract(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"abstract_query": "영업권 손상차손 인식 및 측정 기준은?"}
            )
            result = apply_stepback(self.QUERY, "ALL")
        assert result[0] == self.QUERY
        assert result[1] == "영업권 손상차손 인식 및 측정 기준은?"
        assert len(result) == 2

    def test_llm_failure_returns_original_only(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("timeout")
            result = apply_stepback(self.QUERY, "ALL")
        assert result == [self.QUERY]

    def test_empty_abstract_returns_original_only(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"abstract_query": ""}
            )
            result = apply_stepback(self.QUERY, "ALL")
        assert result == [self.QUERY]

    def test_markdown_wrapper_stripped_and_parsed(self):
        wrapped = "```json\n{\"abstract_query\": \"영업권 손상차손 인식 기준은?\"}\n```"
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_raw_resp(wrapped)
            result = apply_stepback(self.QUERY, "ALL")
        assert result == [self.QUERY, "영업권 손상차손 인식 기준은?"]


# ── rewrite_query ──────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestRewriteQuery:
    PATCH = "src.agent.nodes.rewrite.client"

    def _make_state(self, query: str) -> GraphState:
        return GraphState(original_query=query)

    # 장문("오늘 날씨 어때?")과 단일 단어("날씨") 모두 비회계 분류 시 동일하게 bypass 처리되어야 함
    # 단위 테스트에서 LLM이 모킹되므로 입력 길이와 무관하게 mock 분류 결과가 경로를 결정
    @pytest.mark.parametrize("query", ["오늘 날씨 어때?", "날씨"])
    def test_non_accounting_sets_bypass(self, query):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"is_accounting": False, "strategy": "bypass", "confidence": 0.95}
            )
            state = rewrite_query(self._make_state(query))
        assert state.is_accounting_query is False
        assert state.rewritten_query.strategy == "bypass"
        assert state.rewritten_query.search_queries == [query]
        # 비회계 조기 종료 시 early_exit가 사용할 분류 신뢰도가 state에 기록되어야 함
        assert state.classification_confidence == 0.95

    @pytest.mark.parametrize("query", ["", "  "])
    def test_rewrite_empty_string_raises_valueerror(self, query):
        # 빈 문자열·공백 문자열 입력은 rewrite_query 진입부 가드에서 ValueError로 차단됨
        # outer try보다 앞에서 raise하므로 error_logs로 흡수되지 않고 그대로 전파
        with pytest.raises(ValueError):
            rewrite_query(self._make_state(query))

    def test_accounting_hyde_strategy(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = [
                _mock_resp({"is_accounting": True, "strategy": "hyde"}),
                _mock_resp({"hypothetical_answer": "리스부채는 현재가치로 측정합니다."}),
            ]
            state = rewrite_query(self._make_state("리스부채 최초 인식 방법은?"))
        assert state.is_accounting_query is True
        assert state.rewritten_query.strategy == "hyde"
        assert len(state.rewritten_query.search_queries) == 2
        assert state.rewritten_query.search_queries[0] == "리스부채 최초 인식 방법은?"

    def test_accounting_decompose_strategy(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = [
                _mock_resp({"is_accounting": True, "strategy": "decompose"}),
                _mock_resp({"sub_queries": ["유형자산 감가상각 방법은?", "무형자산 상각 방법은?"]}),
            ]
            state = rewrite_query(self._make_state("유형자산과 무형자산의 감가상각 방법 차이는?"))
        assert state.rewritten_query.strategy == "decompose"
        assert len(state.rewritten_query.search_queries) == 3

    def test_accounting_stepback_strategy(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = [
                _mock_resp({"is_accounting": True, "strategy": "stepback"}),
                _mock_resp({"abstract_query": "영업권 손상차손 인식 기준은?"}),
            ]
            state = rewrite_query(self._make_state("삼성전자 2023년 영업권 500억 손상 처리는?"))
        assert state.rewritten_query.strategy == "stepback"
        assert len(state.rewritten_query.search_queries) == 2

    def test_unknown_strategy_fallback_to_bypass_with_error_log(self):
        # 미정의 전략 → 명시 검증에서 ValueError 발생 → rewrite_query outer except에서 잡힘
        # 예외가 rewrite_query까지 전파되므로 error_logs에 기록됨 (메시지에 전략명 포함)
        # cf. test_all_llm_failure: 각 함수가 예외를 내부에서 삼키므로 outer except 미발동
        with patch("src.agent.nodes.rewrite.classify_and_select") as mock_classify:
            mock_classify.return_value = (True, "unknown_strategy", 0.8)
            state = rewrite_query(self._make_state("영업권 손상차손 인식 기준은?"))
        assert state.rewritten_query.strategy == "bypass"
        assert state.rewritten_query.search_queries == ["영업권 손상차손 인식 기준은?"]
        assert len(state.error_logs) == 1
        assert state.error_logs[0]["node"] == "rewrite"
        assert state.error_logs[0]["error_type"] == "ValueError"
        assert "unknown_strategy" in state.error_logs[0]["message"]

    def test_all_llm_failure_falls_back_to_hyde_with_original(self):
        # classify_and_select 내부 except → (True, "hyde") 반환, apply_hyde 내부 except → [query] 반환
        # 예외가 각 함수 안에서 삼켜져 rewrite_query까지 전파되지 않으므로 outer except 미발동
        # cf. test_unknown_strategy: 미정의 전략은 rewrite_query 내부 명시 검증의 ValueError로 outer except에 잡힘
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("network error")
            state = rewrite_query(self._make_state("영업권 손상차손 인식 기준은?"))
        assert state.rewritten_query.strategy == "hyde"
        assert state.rewritten_query.search_queries == ["영업권 손상차손 인식 기준은?"]
        # 폴백은 유지하되, classify_and_select·apply_hyde 두 헬퍼의 LLM 실패가 더 이상 silent하지 않고 각각 CM-002로 state.error_logs에 누적된다.
        assert len(state.error_logs) == 2  # classify_and_select + apply_hyde
        assert [e["error_type"] for e in state.error_logs] == ["CM-002", "CM-002"]
        assert all(e["node"] == "rewrite" for e in state.error_logs)

    def test_original_query_always_first_in_search_queries(self):
        query = "리스부채 최초 인식 방법은?"
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = [
                _mock_resp({"is_accounting": True, "strategy": "hyde"}),
                _mock_resp({"hypothetical_answer": "리스부채는 현재가치로 측정합니다."}),
            ]
            state = rewrite_query(GraphState(original_query=query))
        assert state.rewritten_query.search_queries[0] == query

    def test_rewritten_query_original_matches_state_query(self):
        query = "수익인식 5단계 모형이란?"
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = [
                _mock_resp({"is_accounting": True, "strategy": "hyde"}),
                _mock_resp({"hypothetical_answer": "수익은 5단계로 인식합니다."}),
            ]
            state = rewrite_query(GraphState(original_query=query))
        assert state.rewritten_query.original_query == query

    def test_classify_fail_but_strategy_succeeds(self):
        # 첫 호출(분류)은 예외 → classify_and_select 내부 폴백 (True, "hyde", 0.0)
        # 두 번째 호출(전략-HyDE)은 성공 → [원문, 가상답변]
        # 분류 실패가 함수 안에서 삼켜지므로 outer except 미발동 → error_logs 비어 있음
        original_query = "리스부채 최초 인식 방법은?"
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = [
                Exception("timeout"),
                _mock_resp({"hypothetical_answer": "fallback_ans"}),
            ]
            state = rewrite_query(self._make_state(original_query))
        rq = state.rewritten_query
        assert rq.strategy == "hyde"
        assert rq.search_queries[1] == "fallback_ans"
        assert rq.search_queries[0] == original_query     # 원문이 첫 번째 쿼리로 유지
        assert rq.original_query == original_query         # 원문 필드 보존
        # 분류 실패가 함수 안에서 삼켜져 outer except는 미발동하나, 분류 실패 1건이 CM-002로 기록된다(전략 성공분은 기록 없음).
        assert len(state.error_logs) == 1
        assert state.error_logs[0]["error_type"] == "CM-002"
        assert state.error_logs[0]["node"] == "rewrite"

    def test_classify_succeeds_but_strategy_fails(self):
        # 첫 호출(분류)은 성공하여 "decompose" 할당
        # 두 번째 호출(전략)은 예외 → apply_decompose 내부 폴백 [원문]
        # 전략 실패가 함수 안에서 삼켜지므로 outer except 미발동 → error_logs 비어 있음
        original_query = "유형자산과 무형자산의 감가상각 방법 차이는?"
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = [
                _mock_resp({"is_accounting": True, "strategy": "decompose"}),
                Exception("timeout"),
            ]
            state = rewrite_query(self._make_state(original_query))
        rq = state.rewritten_query
        assert rq.strategy == "decompose"                  # 분류 성공 결과 유지
        assert rq.search_queries == [original_query]       # 원문 보존
        assert rq.original_query == original_query         # 원문 필드 보존
        # 전략(apply_decompose) 실패가 함수 안에서 삼켜져 outer except는 미발동하나, 전략 실패 1건이 CM-002로 기록된다(분류 성공분은 기록 없음).
        assert len(state.error_logs) == 1
        assert state.error_logs[0]["error_type"] == "CM-002"
        assert state.error_logs[0]["node"] == "rewrite"

    def test_llm_failure_emits_warning_log(self, caplog):
        # AC "LLM 실패 시 경고 로그가 남는다"를 직접 검증한다.
        # classify_and_select·apply_hyde 두 호출이 모두 실패하므로 WARNING 2건 이상 남고, 각 메시지에 실패한 헬퍼명이 포함된다.
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("network error")
            with caplog.at_level(logging.WARNING, logger="src.agent.nodes.rewrite"):
                rewrite_query(self._make_state("영업권 손상차손 인식 기준은?"))
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) >= 2
        assert any("classify_and_select" in r.getMessage() for r in warnings)
        assert any("apply_hyde" in r.getMessage() for r in warnings)


# ── HIL 피드백 주입 (apply_* / rewrite_query) ───────────────────────────────────

@pytest.mark.unit
class TestFeedbackInjection:
    PATCH = "src.agent.nodes.rewrite.client"
    FEEDBACK = "리스 회계처리를 강조해줘"

    def test_apply_hyde_injects_feedback_into_prompt(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"hypothetical_answer": "..."}
            )
            apply_hyde("리스부채 최초 인식 방법은?", "ALL", feedback=self.FEEDBACK)
        content = _last_user_content(mock_client)
        assert self.FEEDBACK in content        # 피드백이 프롬프트에 포함
        assert "[사용자 추가 요청]" in content   # 제약 문구 헤더 포함

    def test_apply_hyde_without_feedback_omits_clause(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"hypothetical_answer": "..."}
            )
            apply_hyde("리스부채 최초 인식 방법은?", "ALL")
        content = _last_user_content(mock_client)
        assert "[사용자 추가 요청]" not in content   # 피드백 없으면 절 미포함

    def test_apply_decompose_injects_feedback(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"sub_queries": ["a", "b"]}
            )
            apply_decompose("유형자산과 무형자산 차이는?", "ALL", feedback=self.FEEDBACK)
        assert self.FEEDBACK in _last_user_content(mock_client)

    def test_apply_stepback_injects_feedback(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"abstract_query": "..."}
            )
            apply_stepback("삼성전자 2023년 영업권 손상은?", "ALL", feedback=self.FEEDBACK)
        assert self.FEEDBACK in _last_user_content(mock_client) 

    def test_rewrite_query_passes_feedback_and_clears_it(self):
        # state.human_feedback이 전략 프롬프트에 주입되고, 사용 후 None으로 초기화되어야 함
        state = GraphState(original_query="리스부채 최초 인식 방법은?", human_feedback=self.FEEDBACK)
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = [
                _mock_resp({"is_accounting": True, "strategy": "hyde", "confidence": 0.9}),
                _mock_resp({"hypothetical_answer": "리스부채는 현재가치로 측정합니다."}),
            ]
            result = rewrite_query(state)

        strategy_call = mock_client.chat.completions.create.call_args_list[1] 
        assert self.FEEDBACK in strategy_call.kwargs["messages"][0]["content"]  # 두 번째 호출(전략 프롬프트)에 피드백이 포함되었는지 검증
        assert result.human_feedback is None    # 사용 후 초기화 (다음 루프 대비)
