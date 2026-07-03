"""scripts/rerank_replay.py 순수부 테스트 — 오프라인 병합·채택기준 판정기.

DB·모델 의존부(dump/replay 실행)는 스크립트 내 self-check와 실측 리포트로 검증하고, 여기서는 순수 함수만 고정한다.
"""
import pytest

from src.models.schemas import RetrievedChunk
from src.retrieval.searcher import reciprocal_rank_fusion
from scripts.rerank_replay import EXCLUDED_CASE_IDS, fuse_top_n, judge_adoption

pytestmark = pytest.mark.unit


def _chunk(cid: str) -> RetrievedChunk:
    return RetrievedChunk(chunk_id=cid, document_id="doc", content=f"내용 {cid}", score=0.0, metadata={})


def _ids(chunks: list[RetrievedChunk]) -> list[str]:
    return [c.chunk_id for c in chunks]


class TestFuseTopN:
    """fuse_top_n() — 덤프된 사이드별 리스트의 오프라인 병합이 라이브 RRF와 동일해야 한다"""

    def test_delegates_to_reciprocal_rank_fusion(self):
        """fuse_top_n(dense, sparse, k)[:n] == reciprocal_rank_fusion([dense, sparse], k)[:n]"""
        dense = [_chunk(f"d{i}") for i in range(12)]
        sparse = [_chunk("d3"), _chunk("s1"), _chunk("d7"), _chunk("s2")]

        got = fuse_top_n(dense, sparse, k=60, n=10)
        expected = reciprocal_rank_fusion([dense, sparse], k=60)[:10]

        assert _ids(got) == _ids(expected)
        assert len(got) == 10

    def test_k_changes_ranking(self):
        """k에 따라 병합 순위가 실제로 바뀐다 — X(랭크 1·10) vs Y(랭크 3·3)는 k=1이면 X, k=60이면 Y가 앞선다"""
        fillers_d = [_chunk(f"fd{i}") for i in range(8)]
        fillers_s = [_chunk(f"fs{i}") for i in range(8)]
        # dense: X=1위, Y=3위 / sparse: Y=3위, X=10위
        dense = [_chunk("X"), fillers_d[0], _chunk("Y")] + fillers_d[1:]
        sparse = [fillers_s[0], fillers_s[1], _chunk("Y")] + fillers_s[2:] + [_chunk("X")]

        order_k1 = _ids(fuse_top_n(dense, sparse, k=1, n=10))
        order_k60 = _ids(fuse_top_n(dense, sparse, k=60, n=10))

        assert order_k1.index("X") < order_k1.index("Y")    # 1/2+1/11 > 1/4+1/4
        assert order_k60.index("Y") < order_k60.index("X")  # 2/63 > 1/61+1/70


class TestJudgeAdoption:
    """judge_adoption() — 사전 확정 기준(Hit@1 순증 ≥+2 · 회귀 0 · MRR 순증 >0 · p50 ≤1s)"""

    def test_adopts_when_all_criteria_met(self):
        """순증 2건·회귀 0·MRR 상승·지연 통과 → 채택"""
        base = {"A": 2, "B": None, "C": 5, "D": 1}
        cand = {"A": 1, "B": 1, "C": 2, "D": 1}

        verdict = judge_adoption(base, cand, p50_latency_s=0.4, excluded_ids=frozenset())

        assert verdict["adopt"] is True
        assert sorted(verdict["gains"]) == ["A", "B"]
        assert verdict["regressions"] == []
        assert verdict["mrr_delta"] > 0

    def test_single_regression_rejects(self):
        """순증이 충분해도 기존 hit@1 케이스가 1건이라도 밀리면 롤백"""
        base = {"A": 2, "B": None, "C": None, "D": 1}
        cand = {"A": 1, "B": 1, "C": 1, "D": 3}

        verdict = judge_adoption(base, cand, p50_latency_s=0.4, excluded_ids=frozenset())

        assert verdict["adopt"] is False
        assert verdict["regressions"] == ["D"]

    def test_insufficient_gains_rejects(self):
        """순증 +1건은 기준(≥+2) 미달"""
        base = {"A": None, "B": 3, "C": 2}
        cand = {"A": 1, "B": 2, "C": 2}

        verdict = judge_adoption(base, cand, p50_latency_s=0.4, excluded_ids=frozenset())

        assert verdict["adopt"] is False
        assert verdict["gains"] == ["A"]

    def test_latency_over_budget_rejects(self):
        """정확도 기준을 다 채워도 p50 > 1s면 롤백"""
        base = {"A": None, "B": None, "C": 1}
        cand = {"A": 1, "B": 1, "C": 1}

        verdict = judge_adoption(base, cand, p50_latency_s=1.5, excluded_ids=frozenset())

        assert verdict["adopt"] is False

    def test_mrr_must_strictly_increase(self):
        """순위 변동이 전혀 없으면 MRR 순증 >0 미충족"""
        base = {"A": 1, "B": 2, "C": None}
        cand = {"A": 1, "B": 2, "C": None}

        verdict = judge_adoption(base, cand, p50_latency_s=0.4, excluded_ids=frozenset())

        assert verdict["adopt"] is False
        assert verdict["mrr_delta"] == 0

    def test_excluded_cases_do_not_count(self):
        """#183 대기 케이스의 순증은 판정 모집단에서 제외된다 (기본 제외 = 003·005·012)"""
        base = {"TEST-K-GAAP-003": None, "TEST-K-GAAP-005": None, "A": 1, "B": None, "C": None}
        cand = {"TEST-K-GAAP-003": 1, "TEST-K-GAAP-005": 1, "A": 1, "B": 1, "C": 1}

        verdict = judge_adoption(base, cand, p50_latency_s=0.4)

        assert sorted(verdict["gains"]) == ["B", "C"]
        assert "TEST-K-GAAP-003" not in verdict["population"]
        assert EXCLUDED_CASE_IDS >= {"TEST-K-GAAP-003", "TEST-K-GAAP-005", "TEST-K-GAAP-012"}
