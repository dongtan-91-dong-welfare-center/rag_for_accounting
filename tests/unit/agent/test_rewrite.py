import json
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

    def test_non_accounting_sets_bypass(self):
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"is_accounting": False, "strategy": "bypass", "confidence": 0.95}
            )
            state = rewrite_query(self._make_state("오늘 날씨 어때?"))
        assert state.is_accounting_query is False
        assert state.rewritten_query.strategy == "bypass"
        assert state.rewritten_query.search_queries == ["오늘 날씨 어때?"]
        # 비회계 조기 종료 시 early_exit가 사용할 분류 신뢰도가 state에 기록되어야 함
        assert state.classification_confidence == 0.95

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
        # _STRATEGY_FN["unknown_strategy"] → KeyError 발생 → rewrite_query outer except에서 잡힘
        # 예외가 rewrite_query까지 전파되므로 error_logs에 기록됨
        # cf. test_all_llm_failure: 각 함수가 예외를 내부에서 삼키므로 outer except 미발동
        with patch("src.agent.nodes.rewrite.classify_and_select") as mock_classify:
            mock_classify.return_value = (True, "unknown_strategy", 0.8)
            state = rewrite_query(self._make_state("영업권 손상차손 인식 기준은?"))
        assert state.rewritten_query.strategy == "bypass"
        assert state.rewritten_query.search_queries == ["영업권 손상차손 인식 기준은?"]
        assert len(state.error_logs) == 1
        assert state.error_logs[0]["node"] == "rewrite"
        assert state.error_logs[0]["error_type"] == "KeyError"

    def test_all_llm_failure_falls_back_to_hyde_with_original(self):
        # classify_and_select 내부 except → (True, "hyde") 반환, apply_hyde 내부 except → [query] 반환
        # 예외가 각 함수 안에서 삼켜져 rewrite_query까지 전파되지 않으므로 outer except 미발동
        # cf. test_unknown_strategy: KeyError는 rewrite_query 내부에서 직접 발생해 outer except에 잡힘
        with patch(self.PATCH) as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("network error")
            state = rewrite_query(self._make_state("영업권 손상차손 인식 기준은?"))
        assert state.rewritten_query.strategy == "hyde"
        assert state.rewritten_query.search_queries == ["영업권 손상차손 인식 기준은?"]
        assert state.error_logs == []

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
