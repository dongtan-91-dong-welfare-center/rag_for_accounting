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
    """references 문자열에서 장 번호만 추출하는지 검증한다.

    "제 21 장"처럼 공백이 섞인 표기도 인식하고, 장 표기가 없는 문자열("기타")은 무시해야 한다.
    """
    refs = ["일반기업회계기준 제2장 2.65조", "일반기업회계기준 제 21 장 21.3", "기타"]
    assert extract_gold_chapters(refs) == {"2", "21"}


def test_exclude_chapters_drops_gold_and_unknown():
    """음성 묶음 생성 시 정답 장 청크와 chapter 미상 청크를 제거하고, 검색 순위를 유지한 채 n개로 자르는지 검증한다.

    chapter가 None인 청크는 정답 장 여부를 판정할 수 없으므로 음성에 섞이면 안 된다.
    """
    chunks = [{"chapter": "2"}, {"chapter": None}, {"chapter": "6"}, {"chapter": "21"}, {"chapter": "7"}]
    assert exclude_chapters(chunks, {"2"}, n=2) == [{"chapter": "6"}, {"chapter": "21"}]


def test_auc_perfect_and_tie():
    """AUC가 완전 분리일 때 1.0, 양성·음성 점수가 같을 때 0.5(동점 절반 처리)인지 검증한다."""
    assert auc([0.9, 0.8], [0.1, 0.2]) == 1.0
    assert auc([0.5], [0.5]) == 0.5


def test_rates_at():
    """임계값 "미만"을 차단으로 보는 규칙에 따라 차단율과 오차단율을 올바르게 계산하는지 검증한다.

    임계값 0.5에서 음성 [0.1, 0.6] 중 0.1만, 양성 [0.4, 0.9] 중 0.4만 차단되어 둘 다 50%이다.
    """
    assert rates_at(0.5, [0.4, 0.9], [0.1, 0.6]) == (0.5, 0.5)


def test_select_threshold_respects_false_block_cap():
    """임계값 선정이 오차단율 상한(10%)을 지키면서 음성 차단율을 최대화하는지 검증한다.

    0.9 이상으로 올리면 양성 9건(0.9)이 모두 차단되어 상한을 넘으므로,
    양성 1건(0.3)만 희생하는 지점에서 음성 2/3(0.1, 0.2)을 차단하는 것이 최적이다.
    """
    pos = [0.3] + [0.9] * 9
    neg = [0.1, 0.2, 0.95]
    best = select_threshold(pos, neg, max_false_block=0.1)
    assert best["false_block_rate"] <= 0.1
    assert best["block_rate"] == pytest.approx(2 / 3)


def test_select_bands_shares_sum_to_one():
    """3구간 경계가 양성 최저점(low)으로 잡히고, 즉시 차단·위임·즉시 통과 비율의 합이 1인지 검증한다.

    세 구간은 모든 점수를 빠짐없이, 겹침 없이 나눠야 LLM 호출 절감 추정치가 왜곡되지 않는다.
    """
    bands = select_bands([0.4, 0.9], [0.1, 0.6])
    assert bands["low"] == 0.4
    assert bands["block_share"] + bands["delegate_share"] + bands["pass_share"] == pytest.approx(1.0)


def test_h1_verdict():
    """H1 판정이 경계값(차단율 70%, 오차단율 10%)을 포함하고, 어느 한 조건만 어겨도 기각하는지 검증한다."""
    assert h1_verdict(0.7, 0.1)
    assert not h1_verdict(0.69, 0.05)
    assert not h1_verdict(0.9, 0.11)
