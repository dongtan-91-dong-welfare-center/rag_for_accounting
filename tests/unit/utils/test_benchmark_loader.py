"""
benchmark.jsonl 로더 스키마 단위 테스트

대상: tests/utils/benchmark_loader.py
  - BenchmarkCase.core_paras: 멀티조항 gold의 핵심(core) 문단번호.
    비어 있으면 references 전체를 핵심으로 간주한다(검색 통과 판정용).
"""
import pytest

from tests.utils.benchmark_loader import BenchmarkCase, load_benchmark


@pytest.mark.unit
class TestBenchmarkCaseSchema:
    """BenchmarkCase 스키마 — core_paras 필드"""

    def test_core_paras_defaults_empty(self):
        """core_paras 미지정 시 빈 리스트(=references 전체가 핵심)"""
        c = BenchmarkCase(
            id="X", category="c", standard="GAAP",
            query="q", expected_answer="a",
            references=["일반기업회계기준 제1장 1.1조"],
        )
        assert c.core_paras == []

    def test_core_paras_explicit(self):
        c = BenchmarkCase(
            id="X", category="c", standard="GAAP",
            query="q", expected_answer="a",
            references=["일반기업회계기준 제21장 21.8조, 21.9조"],
            core_paras=["21.8"],
        )
        assert c.core_paras == ["21.8"]


@pytest.mark.unit
class TestFixtureCoreParas:
    """실제 fixture(benchmark.jsonl)의 핵심/보조 1차 라벨 (#163)"""

    def setup_method(self):
        self.cases = {c.id: c for c in load_benchmark()}

    def test_multi_clause_core_marked(self):
        """핵심⊊전체 케이스만 core_paras 지정(003·004)"""
        assert self.cases["TEST-K-GAAP-003"].core_paras == ["21.8"]
        assert self.cases["TEST-K-GAAP-004"].core_paras == ["15.18"]

    def test_full_core_cases_unmarked(self):
        """단일조항·전부핵심 케이스는 core_paras 미지정(기본 빈 리스트)"""
        assert self.cases["TEST-K-GAAP-001"].core_paras == []   # 단일 2.65
        assert self.cases["TEST-K-GAAP-007"].core_paras == []   # 6.29·6.31 둘 다 핵심
        assert self.cases["TEST-K-GAAP-012"].core_paras == []   # 21.8·21.10 둘 다 핵심

    def test_all_cases_loaded(self):
        assert len(self.cases) == 14
