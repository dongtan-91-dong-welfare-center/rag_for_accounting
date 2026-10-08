"""scripts/rerank_gate_eval.py 순수부 테스트 — 정답 장 추출·제외, AUC, 임계값·구간 선정.

DB·모델이 필요한 dump/score 실행부는 실측 리포트로 검증하고, 여기서는 순수 함수만 고정한다.
"""
import pytest

from scripts.rerank_gate_eval import (
    auc,
    exclude_chapters,
    extract_gold_chapters,
    h1_verdict,
    rates_at,
    select_bands,
    select_threshold,
)

pytestmark = pytest.mark.unit


def test_extract_gold_chapters():
    refs = ["일반기업회계기준 제2장 2.65조", "일반기업회계기준 제 21 장 21.3", "기타"]
    assert extract_gold_chapters(refs) == {"2", "21"}


def test_exclude_chapters_drops_gold_and_unknown():
    chunks = [{"chapter": "2"}, {"chapter": None}, {"chapter": "6"}, {"chapter": "21"}, {"chapter": "7"}]
    assert exclude_chapters(chunks, {"2"}, n=2) == [{"chapter": "6"}, {"chapter": "21"}]


def test_auc_perfect_and_tie():
    assert auc([0.9, 0.8], [0.1, 0.2]) == 1.0
    assert auc([0.5], [0.5]) == 0.5


def test_rates_at():
    assert rates_at(0.5, [0.4, 0.9], [0.1, 0.6]) == (0.5, 0.5)


def test_select_threshold_respects_false_block_cap():
    pos = [0.3] + [0.9] * 9
    neg = [0.1, 0.2, 0.95]
    best = select_threshold(pos, neg, max_false_block=0.1)
    # 0.9에서 끊으면 양성 1/10(0.3)만 차단되고 음성 2/3이 차단된다.
    assert best["false_block_rate"] <= 0.1
    assert best["block_rate"] == pytest.approx(2 / 3)


def test_select_bands_shares_sum_to_one():
    bands = select_bands([0.4, 0.9], [0.1, 0.6])
    assert bands["low"] == 0.4
    assert bands["block_share"] + bands["delegate_share"] + bands["pass_share"] == pytest.approx(1.0)


def test_h1_verdict():
    assert h1_verdict(0.7, 0.1)
    assert not h1_verdict(0.69, 0.05)
    assert not h1_verdict(0.9, 0.11)
