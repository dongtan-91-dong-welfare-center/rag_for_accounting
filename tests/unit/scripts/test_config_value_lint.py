"""scripts/config_value_lint.py — 문서 설정값 드리프트 검사.

문서에 박힌 `NAME=값`이 config.py와 어긋나면 잡고, 일치하면 통과시킨다.
손-스냅샷 대신 이 검사로 CLAUDE.md SSoT 규칙을 기계 강제한다.
"""
import pytest

from scripts.config_value_lint import find_mismatches

pytestmark = pytest.mark.unit


def test_flags_stale_value():
    """어긋난 값은 보고하고, 일치하는 값은 보고하지 않는다."""
    values = {"RRF_K": 60, "MAX_REWRITE_COUNT": 3}
    text = "병합(`RRF_K=99`) · 루프(`MAX_REWRITE_COUNT=3`)"
    m = find_mismatches(text, values)
    reported = [(n, stated, actual) for _, n, stated, actual in m]
    assert ("RRF_K", "99", "60") in reported
    assert all(n != "MAX_REWRITE_COUNT" for _, n, *_ in m)


def test_correct_value_not_flagged():
    assert find_mismatches("`RRF_K=60`", {"RRF_K": 60}) == []


def test_float_is_normalized():
    # 0.50 == 0.5 → 불일치 아님
    assert find_mismatches("`RERANK_THRESHOLD=0.50`", {"RERANK_THRESHOLD": 0.5}) == []


def test_reports_line_number():
    m = find_mismatches("첫 줄\n`RRF_K=1`", {"RRF_K": 60})
    assert m and m[0][0] == 2
