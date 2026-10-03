"""scripts/content_judge_stability.py 순수부 테스트: 판정 반복 결과의 안정성 집계."""
import pytest

from scripts.content_judge_stability import summarize_stability

pytestmark = pytest.mark.unit


class TestSummarizeStability:
    def test_all_same_is_stable(self):
        s = summarize_stability({"A": ["pass", "pass", "pass"], "B": ["fail", "fail", "fail"]})
        assert s["n_cases"] == 2
        assert s["n_unstable"] == 0
        assert s["unstable_ids"] == []
        assert s["agreement_rate"] == 1.0

    def test_flip_detected_and_listed(self):
        s = summarize_stability({"A": ["pass", "partial", "pass"], "B": ["pass", "pass", "pass"]})
        assert s["n_unstable"] == 1
        assert s["unstable_ids"] == ["A"]
        assert s["agreement_rate"] == 0.5

    def test_pass_flip_counts_only_pass_boundary(self):
        # partial<->fail 변동은 content_pass(pass만 통과)에 영향이 없으므로 경계 뒤집힘이 아니다
        s = summarize_stability({"A": ["partial", "fail", "partial"], "B": ["pass", "fail", "pass"]})
        assert s["n_unstable"] == 2
        assert s["n_pass_boundary_flips"] == 1
        assert s["pass_boundary_ids"] == ["B"]

    def test_empty_input(self):
        s = summarize_stability({})
        assert s["n_cases"] == 0
        assert s["agreement_rate"] == 0.0
