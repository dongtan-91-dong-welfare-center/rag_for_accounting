"""
benchmark.jsonl 로더 스키마 단위 테스트

대상: tests/utils/benchmark_loader.py
  - BenchmarkCase.core_paras: 멀티조항 gold의 핵심(core) 문단번호.
    비어 있으면 references 전체를 핵심으로 간주한다(검색 통과 판정용).
"""
import re

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
        """핵심⊊전체 케이스는 core_paras 지정 — 대표 3건으로 회귀 감지(003·004·012)"""
        assert self.cases["TEST-K-GAAP-003"].core_paras == ["21.8"]
        assert self.cases["TEST-K-GAAP-004"].core_paras == ["15.18"]
        assert self.cases["TEST-K-GAAP-012"].core_paras == ["21.8", "21.10"]

    def test_full_core_cases_unmarked(self):
        """단일조항·전부핵심 케이스는 core_paras 미지정(기본 빈 리스트)"""
        assert self.cases["TEST-K-GAAP-001"].core_paras == []   # 단일 2.65
        assert self.cases["TEST-K-GAAP-007"].core_paras == []   # 6.29·6.30·6.31 전부 핵심

    def test_all_cases_loaded(self):
        assert len(self.cases) == 114

    def test_no_practice_prefix_references(self):
        """
        실무지침(실N.N)·결론도출근거(결N.N) 접두 문단이 references에 없어야 한다.

        현행 채점기는 문단번호를 정규식으로 뽑을 때 접두사를 버리고 읽는다(예: '실2.11조' → 2.11)
        그 번호의 본문 문단이 코퍼스에 실존하면, 무관한 문단이 정답(gold)에 주입되어 hit@k·recall이 왜곡된다.
        채점기 접두 처리가 해결되면 이 가드를 제거하고, 보류해 둔 실/결 근거를 references에 복원한다.
        """
        pat = re.compile(r"[실결]\s*\d+\.\d+")
        offenders = [
            (c.id, ref)
            for c in self.cases.values()
            for ref in c.references
            if pat.search(ref)
        ]
        assert offenders == [], f"채점기에서 실/결 접두사 정규식 처리가 해결된 후 사용해주세요."
