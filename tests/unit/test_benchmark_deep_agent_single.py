"""
scripts/benchmark_deep_agent_single.py 단위 테스트 (이슈 #402)

비용 산정식, measure_deep_agent_case, aggregate_deep_agent_results 통계 집계,
체크포인트 원자적 저장/로드 및 마크다운 리포트 생성을 검증합니다.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.models.test import TestModel

from scripts.benchmark_deep_agent_single import (
    DeepAgentCaseResult,
    _load_checkpoint,
    _save_checkpoint,
    aggregate_deep_agent_results,
    compute_llm_cost,
    measure_deep_agent_case,
    write_deep_agent_markdown_report,
)
from src.agent.deep_agent import create_deep_agent
from tests.utils.benchmark_loader import BenchmarkCase

pytestmark = pytest.mark.unit


def test_compute_llm_cost():
    # gpt-5.4-mini: $0.15/1M in, $0.60/1M out
    # 1,000,000 in + 1,000,000 out = $0.75
    cost = compute_llm_cost(1_000_000, 1_000_000)
    assert abs(cost - 0.75) < 1e-6

    # 2,000 in + 500 out = 2000 * 1.5e-7 + 500 * 6.0e-7 = 0.00030 + 0.00030 = 0.00060
    cost2 = compute_llm_cost(2000, 500)
    assert abs(cost2 - 0.00060) < 1e-6


def test_measure_deep_agent_case_mock():
    mock_model = TestModel(
        call_tools=["search_accounting_standards"],
        custom_output_args={
            "answer": "정상 답변 [1].",
            "is_answerable": True,
            "llm_self_score": 0.9,
        },
    )
    agent = create_deep_agent()
    agent.model = mock_model

    case = BenchmarkCase(
        id="TEST-001",
        category="유형자산",
        standard="GAAP",
        query="유형자산 감가상각 방법",
        expected_answer="감가상각방법 내용",
        references=["일반기업회계기준 제10장 문단 10.38"],
    )

    with (
        patch("src.agent.deep_agent.embed_query", return_value=[0.1] * 768),
        patch("src.agent.deep_agent.dense_search") as mock_dense,
    ):
        from src.models.schemas import ChunkMetadata, RetrievedChunk

        mock_dense.return_value = [
            RetrievedChunk(
                chunk_id="gaap-ch10-10.38",
                document_id="doc1",
                content="#### 10.38\n\n감가상각방법 내용",
                score=0.95,
                metadata=ChunkMetadata(chapter="10", standard_type="GAAP"),
            )
        ]

        res = measure_deep_agent_case(case, max_turns=3, k=10, agent=agent)

    assert res.error is None
    assert res.case_id == "TEST-001"
    assert res.total_llm_turns >= 1
    assert res.metrics["retrieval_exact_hit@10"] is True
    assert res.metrics["generation_exact_hit@1"] is True
    assert res.metrics["is_answerable"] is True
    assert res.total_cost_usd > 0.0


def test_aggregate_deep_agent_results():
    r1 = DeepAgentCaseResult(
        case_id="TEST-1",
        chapter="10",
        measurable=True,
        gold_paras=["10.38"],
        max_turns=3,
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
        diag={"fallback_triggered": False},
        total_llm_turns=2,
        total_tool_calls=1,
        total_input_tokens=1500,
        total_output_tokens=300,
        total_tokens=1800,
        total_cost_usd=0.000405,
        elapsed_sec=3.0,
        external_sec=2.4,
        internal_sec=0.6,
    )
    r2 = DeepAgentCaseResult(
        case_id="TEST-2",
        chapter="10",
        measurable=True,
        gold_paras=["10.40"],
        max_turns=3,
        metrics={
            "retrieval_exact_hit@10": False,
            "retrieval_exact_hit@1": False,
            "retrieval_exact_mrr": 0.0,
            "retrieval_exact_recall": 0.0,
            "generation_exact_hit@1": False,
            "generation_exact_hit@10": False,
            "generation_exact_mrr": 0.0,
            "generation_exact_recall": 0.0,
            "retrieval_pass": False,
            "is_answerable": False,
        },
        diag={"fallback_triggered": True},
        total_llm_turns=3,
        total_tool_calls=2,
        total_input_tokens=2500,
        total_output_tokens=500,
        total_tokens=3000,
        total_cost_usd=0.000675,
        elapsed_sec=5.0,
        external_sec=4.0,
        internal_sec=1.0,
    )

    summary = aggregate_deep_agent_results([r1, r2], k=10)

    assert summary["n_total"] == 2
    assert summary["n_measured"] == 2
    assert summary["n_error"] == 0
    assert summary["retrieval_exact_hit@10"]["rate"] == 0.5
    assert summary["generation_exact_hit@1"]["rate"] == 0.5
    assert summary["fallback_rate"]["rate"] == 0.5
    assert summary["cost_and_tokens"]["avg_llm_turns"] == 2.5
    assert summary["cost_and_tokens"]["avg_tool_calls"] == 1.5
    assert summary["latency"]["total"]["avg"] == 4.0


def test_checkpoint_save_and_load(tmp_path: Path):
    ckpt_file = tmp_path / "checkpoint_test.json"
    r = DeepAgentCaseResult(
        case_id="TEST-CKPT",
        chapter="10",
        measurable=True,
        gold_paras=["10.1"],
        max_turns=3,
        total_tokens=500,
    )

    _save_checkpoint(ckpt_file, [r], max_turns=3, k=10)
    assert ckpt_file.exists()

    loaded = _load_checkpoint(ckpt_file, expected_turns=3, expected_k=10)
    assert len(loaded) == 1
    assert loaded[0].case_id == "TEST-CKPT"
    assert loaded[0].total_tokens == 500

    # max_turns 불일치 시 ValueError 검증
    with pytest.raises(ValueError, match="체크포인트 max_turns"):
        _load_checkpoint(ckpt_file, expected_turns=5, expected_k=10)


def test_write_deep_agent_markdown_report(tmp_path: Path):
    report_file = tmp_path / "test_report.md"
    summary = {
        "n_total": 1,
        "n_measured": 1,
        "n_error": 0,
        "max_turns": 3,
        "retrieval_exact_hit@10": {"hits": 1, "rate": 1.0},
        "generation_exact_hit@1": {"hits": 1, "rate": 1.0},
        "cost_and_tokens": {
            "avg_llm_turns": 2.0,
            "avg_tool_calls": 1.0,
            "avg_cost_usd": 0.0005,
            "total_cost_usd": 0.0005,
            "total_tokens": 1000,
            "avg_total_tokens": 1000.0,
            "total_input_tokens": 800,
            "total_output_tokens": 200,
        },
        "latency": {
            "total": {"p50": 3.0, "p90": 3.0, "p95": 3.0, "p99": 3.0, "avg": 3.0},
        },
    }
    write_deep_agent_markdown_report(summary, [], report_file, k=10)
    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "시나리오 2: 단일 검색 도구 기반 딥에이전트" in content
    assert "시나리오 1 베이스라인과의 대조 요약" in content
