"""scripts/rerank_replay.py 순수부 테스트 — 오프라인 병합·채택기준 판정기.

DB·모델 의존부(dump/replay 실행)는 스크립트 내 self-check와 실측 리포트로 검증하고, 여기서는 순수 함수만 고정한다.
"""
import pytest

from src.models.schemas import RetrievedChunk
from src.retrieval.searcher import reciprocal_rank_fusion
from scripts.rerank_replay import EXCLUDED_CASE_IDS, fuse_top_n, judge_adoption, min_net_gain

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


class TestMinNetGain:
    """min_net_gain() — 모집단 크기에 비례하는 순증 기준선. 작은 표본에서는 하한 2건이 걸린다."""

    @pytest.mark.parametrize(
        "population_size, expected",
        [
            (11, 2),    # 14건 벤치마크 시절 모집단 — 하한 2건이 이긴다(3%면 1건)
            (34, 2),    # 3%가 1.02건 → 올림 2건, 하한과 같음
            (67, 3),    # 3%가 2.01건 → 올림 3건, 하한을 넘어선다
            (114, 4),   # 현행 114건 벤치마크 — 3%가 3.42건 → 올림 4건
        ],
    )
    def test_scales_with_population(self, population_size, expected):
        """표본이 커지면 기준선도 함께 커진다 — 고정 2건이면 114건에서 1.8%짜리 잡음도 통과한다"""
        assert min_net_gain(population_size) == expected


class TestJudgeAdoption:
    """judge_adoption() — 사전 확정 기준(Hit@1 순증−회귀 ≥ 모집단 비례 기준선 · MRR 순증 >0 · p50 ≤5s)"""

    def test_adopts_when_all_criteria_met(self):
        """순증 2건·회귀 0·MRR 상승·지연 통과 → 채택"""
        base = {"A": 2, "B": None, "C": 5, "D": 1}
        cand = {"A": 1, "B": 1, "C": 2, "D": 1}

        verdict = judge_adoption(base, cand, p50_latency_s=0.4, excluded_ids=frozenset())

        assert verdict["adopt"] is True
        assert sorted(verdict["gains"]) == ["A", "B"]
        assert verdict["regressions"] == []
        assert verdict["mrr_delta"] > 0

    def test_regressions_offset_by_gains_adopts(self):
        """
        회귀가 1건 있어도 순증이 3건이면 순증(net) 2건으로 기준을 채워 채택된다.

        구 기준("회귀 0건")은 표본이 114건으로 커진 뒤 사실상 달성 불가라 폐기했다 —
        대신 MRR 순증 조건이 "전체 순위가 나빠지는 교환"을 막는다.
        """
        base = {"A": 2, "B": None, "C": None, "D": 1}
        cand = {"A": 1, "B": 1, "C": 1, "D": 3}

        verdict = judge_adoption(base, cand, p50_latency_s=0.4, excluded_ids=frozenset())

        assert verdict["adopt"] is True
        assert verdict["regressions"] == ["D"]
        assert verdict["net_gain"] == 2

    def test_regressions_canceling_gains_rejects(self):
        """순증 2건을 회귀 2건이 상쇄하면 순증(net) 0건이라 기각된다"""
        base = {"A": 2, "B": None, "C": 1, "D": 1}
        cand = {"A": 1, "B": 1, "C": 4, "D": 3}

        verdict = judge_adoption(base, cand, p50_latency_s=0.4, excluded_ids=frozenset())

        assert verdict["adopt"] is False
        assert verdict["net_gain"] == 0

    def test_large_population_requires_proportional_gains(self):
        """114건 모집단에서는 순증 3건이 미달이고 4건이어야 채택된다 — 표본이 8배 커진 만큼 기준선도 오른다"""
        base = {f"C{i:03d}": 2 for i in range(114)}
        cand_three = {**base, "C000": 1, "C001": 1, "C002": 1}
        cand_four = {**cand_three, "C003": 1}

        rejected = judge_adoption(base, cand_three, p50_latency_s=0.4, excluded_ids=frozenset())
        adopted = judge_adoption(base, cand_four, p50_latency_s=0.4, excluded_ids=frozenset())

        assert rejected["adopt"] is False
        assert rejected["min_net_gain"] == 4
        assert adopted["adopt"] is True

    def test_insufficient_gains_rejects(self):
        """순증 +1건은 기준(순증−회귀 ≥ 2) 미달"""
        base = {"A": None, "B": 3, "C": 2}
        cand = {"A": 1, "B": 2, "C": 2}

        verdict = judge_adoption(base, cand, p50_latency_s=0.4, excluded_ids=frozenset())

        assert verdict["adopt"] is False
        assert verdict["gains"] == ["A"]

    def test_latency_over_budget_rejects(self):
        """정확도 기준을 다 채워도 p50 > 5s면 롤백"""
        base = {"A": None, "B": None, "C": 1}
        cand = {"A": 1, "B": 1, "C": 1}

        verdict = judge_adoption(base, cand, p50_latency_s=5.5, excluded_ids=frozenset())

        assert verdict["adopt"] is False

    def test_latency_within_relaxed_budget_adopts(self):
        """#228: 지연 기준을 5s로 완화 — bge 실측 p50(3.96s)은 이제 지연 게이트를 통과한다(1s 시절엔 탈락했음)."""
        base = {"A": 2, "B": None, "C": 5, "D": 1}
        cand = {"A": 1, "B": 1, "C": 2, "D": 1}

        verdict = judge_adoption(base, cand, p50_latency_s=3.96, excluded_ids=frozenset())

        assert verdict["adopt"] is True

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
