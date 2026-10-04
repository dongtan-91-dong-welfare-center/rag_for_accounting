"""
scripts/benchmark_baseline_pipeline.py 단위 테스트

비용 산정식, LLMTracker 계측, 집계(aggregate_baseline_results), 마크다운 리포트 생성 및
체크포인트 저장/복구 로직을 검증합니다.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from scripts.benchmark_baseline_pipeline import (
    BaselineCaseResult,
    LLMCallRecord,
    LLMTracker,
    Scenario1CaseResult,
    _load_checkpoint,
    _save_checkpoint,
    aggregate_baseline_results,
    aggregate_scenario1,
    compute_llm_cost,
    write_baseline_markdown_report,
    write_scenario1_markdown_report,
)
from src.utils.config import (
    GPT_5_4_MINI_INPUT_COST_PER_TOKEN,
    GPT_5_4_MINI_OUTPUT_COST_PER_TOKEN,
)

pytestmark = pytest.mark.unit


def test_compute_llm_cost():
    """입력/출력 토큰 수에 따른 gpt-5.4-mini 비용 산정식이 config SSoT 단가와 일치하는지 검증합니다."""
    # 1,000,000 in + 1,000,000 out 계산
    expected_cost = 1_000_000 * GPT_5_4_MINI_INPUT_COST_PER_TOKEN + 1_000_000 * GPT_5_4_MINI_OUTPUT_COST_PER_TOKEN
    cost = compute_llm_cost(1_000_000, 1_000_000)
    assert abs(cost - expected_cost) < 1e-6

    # 1,000 in + 500 out 계산
    expected_cost2 = 1000 * GPT_5_4_MINI_INPUT_COST_PER_TOKEN + 500 * GPT_5_4_MINI_OUTPUT_COST_PER_TOKEN
    cost2 = compute_llm_cost(1000, 500)
    assert abs(cost2 - expected_cost2) < 1e-6


def test_llm_tracker_captures_run_sync():
    """LLMTracker 컨텍스트 매니저가 Agent.run_sync 실행 시 토큰 사용량과 지연 시간을 정상 가로채는지 검증합니다."""
    tracker = LLMTracker()
    with tracker:
        from pydantic_ai import Agent
        agent = Agent("test")
        res = agent.run_sync("test prompt")

    assert len(tracker.calls) == 1
    call = tracker.calls[0]
    assert call.input_tokens > 0
    assert call.output_tokens > 0
    assert call.total_tokens == call.input_tokens + call.output_tokens
    assert call.cost_usd > 0.0
    assert call.elapsed_sec >= 0.0


def test_aggregate_scenario1_statistics():
    """복수 케이스 결과로부터 Hit rate, MRR, 평균 비용 및 지연 시간 집계 통계가 올바르게 계산되는지 검증합니다."""
    r1 = Scenario1CaseResult(
        case_id="TEST-1",
        chapter="2",
        measurable=True,
        gold_paras=["2.1"],
        metrics={
            "retrieval_exact_hit@10": True,
            "retrieval_exact_hit@1": True,
            "retrieval_exact_mrr": 1.0,
            "retrieval_exact_recall": 1.0,
            "generation_exact_hit@1": True,
            "generation_exact_hit@10": True,
            "generation_exact_mrr": 1.0,
            "generation_exact_recall": 1.0,
            "retrieval_pass": True,
            "is_answerable": True,
        },
        total_llm_calls=4,
        total_input_tokens=2000,
        total_output_tokens=400,
        total_tokens=2400,
        total_cost_usd=0.00054,
        elapsed_sec=4.0,
        external_sec=3.5,
        internal_sec=0.5,
    )
    r2 = Scenario1CaseResult(
        case_id="TEST-2",
        chapter="2",
        measurable=True,
        gold_paras=["2.5"],
        metrics={
            "retrieval_exact_hit@10": True,
            "retrieval_exact_hit@1": False,
            "retrieval_exact_mrr": 0.5,
            "retrieval_exact_recall": 1.0,
            "generation_exact_hit@1": False,
            "generation_exact_hit@10": True,
            "generation_exact_mrr": 0.5,
            "generation_exact_recall": 1.0,
            "retrieval_pass": True,
            "is_answerable": True,
        },
        total_llm_calls=4,
        total_input_tokens=1500,
        total_output_tokens=300,
        total_tokens=1800,
        total_cost_usd=0.000405,
        elapsed_sec=6.0,
        external_sec=5.0,
        internal_sec=1.0,
    )

    summary = aggregate_scenario1([r1, r2], k=10)

    assert summary["n_measured"] == 2
    assert summary["retrieval_exact_hit@10"]["hits"] == 2
    assert summary["retrieval_exact_hit@10"]["rate"] == 1.0
    assert summary["retrieval_exact_hit@1"]["hits"] == 1
    assert summary["retrieval_exact_hit@1"]["rate"] == 0.5
    assert summary["retrieval_exact_mrr_avg"] == 0.75

    c = summary["cost_and_tokens"]
    assert c["avg_llm_calls"] == 4.0
    assert c["total_tokens"] == 4200
    assert c["avg_total_tokens"] == 2100.0

    lat = summary["latency"]["total"]
    assert lat["min"] == 4.0
    assert lat["max"] == 6.0
    assert lat["p50"] == 5.0


def test_checkpoint_save_and_load(tmp_path: Path):
    """체크포인트 JSON 파일로의 원자적 저장 및 k값 검증을 포함한 역직렬화 복구를 검증합니다."""
    chk_path = tmp_path / "chk.json"
    r = Scenario1CaseResult(
        case_id="TEST-1",
        chapter="10",
        measurable=True,
        gold_paras=["10.1"],
        total_llm_calls=4,
    )
    _save_checkpoint(chk_path, [r], k=10)

    loaded = _load_checkpoint(chk_path, expected_k=10)
    assert len(loaded) == 1
    assert loaded[0].case_id == "TEST-1"
    assert loaded[0].chapter == "10"
    assert loaded[0].total_llm_calls == 4

    # k 불일치 시 예외 검증
    with pytest.raises(ValueError, match="체크포인트 k"):
        _load_checkpoint(chk_path, expected_k=5)


def test_write_scenario1_markdown_report(tmp_path: Path):
    """집계 통계 결과를 바탕으로 마크다운 보고서 파일이 필수 섹션을 포함하여 생성되는지 검증합니다."""
    r = Scenario1CaseResult(
        case_id="TEST-1",
        chapter="2",
        measurable=True,
        gold_paras=["2.1"],
        metrics={
            "retrieval_exact_hit@10": True,
            "retrieval_exact_hit@1": True,
            "generation_exact_hit@1": True,
            "generation_exact_hit@10": True,
            "retrieval_pass": True,
            "is_answerable": True,
        },
        total_llm_calls=4,
        total_tokens=2000,
        total_cost_usd=0.0005,
        elapsed_sec=4.2,
        external_sec=3.8,
        internal_sec=0.4,
    )
    summary = aggregate_scenario1([r], k=10)
    out_file = tmp_path / "report.md"
    write_scenario1_markdown_report(summary, [r], out_file, k=10)

    content = out_file.read_text(encoding="utf-8")
    assert "# [실측 리포트] 가중 RRF 하이브리드 검색 베이스라인 성능 및 비용" in content
    assert "한 줄 요약 (BLUF)" in content
    assert "100.0%" in content
    assert "지연 시간" in content
