"""
content_pass(답변 내용 적절성 LLM 판정) 인프라 단위 테스트

대상: tests/utils/benchmark_metrics.py
  - ContentVerdict / content_pass() : 판정('pass'/'partial'/'fail') → 통과(bool) 매핑
  - judge_content()                 : PydanticAI Agent로 판정(오프라인 TestModel 주입)
  - aggregate()                     : content_pass 별도 축 집계(판정된 케이스만, 자체 분모)

LLM 판정은 TestModel로 강제해 키·네트워크 없이 결정적으로 검증한다.
"""
import pytest
from pydantic_ai.models.test import TestModel

from tests.utils.benchmark_metrics import (
    CaseResult,
    ContentVerdict,
    aggregate,
    content_pass,
    judge_content,
)


@pytest.mark.unit
class TestContentPassMapping:
    """content_pass() — 'pass'만 통과, partial/fail은 불통과"""

    def test_pass_is_true(self):
        assert content_pass(ContentVerdict(verdict="pass", reasoning="기대정답과 일치")) is True

    def test_partial_is_false(self):
        assert content_pass(ContentVerdict(verdict="partial", reasoning="일부만 부합")) is False

    def test_fail_is_false(self):
        assert content_pass(ContentVerdict(verdict="fail", reasoning="불일치")) is False


@pytest.mark.unit
class TestJudgeContent:
    """judge_content() — 주입 모델 출력을 ContentVerdict로 파싱"""

    def test_judge_parses_injected_verdict(self):
        model = TestModel(custom_output_args={"verdict": "pass", "reasoning": "expected와 일치"})
        v = judge_content(query="q", expected_answer="e", answer="a", model=model)
        assert isinstance(v, ContentVerdict)
        assert v.verdict == "pass"

    def test_judge_fail_verdict(self):
        model = TestModel(custom_output_args={"verdict": "fail", "reasoning": "근거 없음"})
        v = judge_content(query="q", expected_answer="e", answer="a", model=model)
        assert content_pass(v) is False


@pytest.mark.unit
class TestAggregateContentPass:
    """aggregate() — content_pass는 판정된 케이스만 자체 분모로 집계"""

    def _case(self, cp):
        return CaseResult(
            case_id="C", chapter="2", measurable=True, gold_paras=["2.65"],
            metrics={"content_pass": cp},
        )

    def test_aggregated_with_own_denominator(self):
        rows = [self._case(True), self._case(False), self._case(True)]
        summary = aggregate(rows, 10)
        assert summary["content_pass"] == {"hits": 2, "rate": round(2 / 3, 4), "n": 3}

    def test_absent_when_not_judged(self):
        """content_pass 미판정이면 summary에 키 없음 — 기본 측정 동작 불변"""
        row = CaseResult(
            case_id="C", chapter="2", measurable=True, gold_paras=["2.65"],
            metrics={"retrieval_pass": True},
        )
        summary = aggregate([row], 10)
        assert "content_pass" not in summary
