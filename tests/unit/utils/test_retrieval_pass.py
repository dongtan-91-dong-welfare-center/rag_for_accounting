"""
검색 통과 규칙 단위 테스트

대상: tests/utils/benchmark_metrics.py
  - resolve_core_paras(): case.core_paras 미지정 시 gold 전체를 핵심으로 간주
  - retrieval_pass(): 핵심 조항이 검색 Top-N 안에 있으면 통과
"""
import pytest

from tests.utils.benchmark_loader import BenchmarkCase
from tests.utils.benchmark_metrics import (
    RETRIEVAL_PASS_TOP_N,
    resolve_core_paras,
    retrieval_pass,
)


def _case(references, core_paras=None):
    return BenchmarkCase(
        id="X", category="c", standard="GAAP", query="q", expected_answer="a",
        references=references, core_paras=core_paras or [],
    )


@pytest.mark.unit
class TestResolveCoreParas:
    """resolve_core_paras() — 핵심집합 산정"""

    def test_unmarked_uses_full_gold(self):
        """core_paras 미지정 → gold 전체가 핵심"""
        case = _case(["일반기업회계기준 제6장 6.29조, 6.31조"])
        assert resolve_core_paras(case, {"6.29", "6.31"}) == {"6.29", "6.31"}

    def test_marked_uses_subset(self):
        """core_paras 지정 → 그 집합만 핵심"""
        case = _case(["일반기업회계기준 제21장 21.8조, 21.9조, 21.10조"], core_paras=["21.8"])
        assert resolve_core_paras(case, {"21.8", "21.9", "21.10"}) == {"21.8"}

    def test_core_paras_normalized(self):
        """가지번호(의N) 접미사는 정규화된다"""
        case = _case(["일반기업회계기준 제21장 21.5조"], core_paras=["21.5의2"])
        assert resolve_core_paras(case, {"21.5"}) == {"21.5"}


@pytest.mark.unit
class TestRetrievalPass:
    """retrieval_pass() — 핵심 조항 Top-N 포함 판정"""

    def test_default_top_n_is_5(self):
        assert RETRIEVAL_PASS_TOP_N == 5

    def test_core_within_top5_passes(self):
        """핵심이 정확히 5순위면 통과"""
        contents = [f"#### 9.{i}\n본문" for i in range(1, 5)] + ["#### 21.8\n본문"]  # rank 5
        assert retrieval_pass(contents, {"21.8"}) is True

    def test_core_outside_top5_fails(self):
        """핵심이 6순위면 불통과"""
        contents = [f"#### 9.{i}\n본문" for i in range(1, 6)] + ["#### 21.8\n본문"]  # rank 6
        assert retrieval_pass(contents, {"21.8"}) is False

    def test_multi_core_uses_earliest_hit(self):
        """핵심이 여럿이면 가장 앞선 hit 순위로 판정"""
        contents = ["#### 6.31\n본문", "#### 9.1\n본문"]  # 6.31 rank 1
        assert retrieval_pass(contents, {"6.29", "6.31"}) is True

    def test_no_core_hit_fails(self):
        assert retrieval_pass(["#### 9.1\n본문", "#### 9.2\n본문"], {"21.8"}) is False
