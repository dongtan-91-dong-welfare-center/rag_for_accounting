"""
단일 검색 및 앙상블 검색 딥에이전트 벤치마크 공통 계측 및 집계 유틸리티 (DRY)

상위 이슈 #245, #402, #403의 딥에이전트 벤치마크 하니스에서 공통으로 사용되는
데이터 클래스, 비용 계산식, 단일 케이스 계측, 집계 및 체크포인트 영속화 로직을 제공합니다.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from pydantic_ai import Agent

from src.agent.deep_agent import run_deep_agent
from src.utils.config import (
    GPT_5_4_MINI_INPUT_COST_PER_TOKEN,
    GPT_5_4_MINI_OUTPUT_COST_PER_TOKEN,
    KST,
    TARGET_LATENCY_TOTAL_SEC,
)
from tests.utils.benchmark_loader import BenchmarkCase
from tests.utils.benchmark_metrics import (
    _percentile,
    extract_chunk_paras,
    gold_para_set,
    legacy_substring_hit,
    parse_gold_clauses,
    rank_hit,
    resolve_core_paras,
    retrieval_pass,
)


@dataclass
class DeepAgentCaseResult:
    """딥에이전트 단일 케이스 계측 결과 (단일 검색 및 앙상블 검색 공통)"""

    case_id: str
    chapter: str
    measurable: bool
    gold_paras: list[str]
    max_turns: int
    metrics: dict[str, Any] = field(default_factory=dict)
    diag: dict[str, Any] = field(default_factory=dict)
    total_llm_turns: int = 0
    total_tool_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    elapsed_sec: float = 0.0
    external_sec: float = 0.0
    internal_sec: float = 0.0
    error: str | None = None


# 하위 호환성을 위한 별칭
DeepAgentEnsembleCaseResult = DeepAgentCaseResult


def compute_llm_cost(input_tokens: int, output_tokens: int) -> float:
    """입출력 토큰 수 기반 gpt-5.4-mini 비용 산정식"""
    return round(
        input_tokens * GPT_5_4_MINI_INPUT_COST_PER_TOKEN + output_tokens * GPT_5_4_MINI_OUTPUT_COST_PER_TOKEN,
        8,
    )


def measure_deep_agent_case(
    case: BenchmarkCase,
    max_turns: int = 3,
    k: int = 10,
    agent: Agent | None = None,
    tool_type: str = "single",
) -> DeepAgentCaseResult:
    """단일 벤치마크 케이스에 대해 딥에이전트를 실행하고 정확도/비용/지연시간을 계측합니다."""
    clauses = parse_gold_clauses(case.references)
    gold_paras = gold_para_set(clauses)
    chapter = clauses[0].chapter if clauses else "?"

    res = DeepAgentCaseResult(
        case_id=case.id,
        chapter=chapter,
        measurable=True,
        gold_paras=sorted(gold_paras),
        max_turns=max_turns,
    )

    t0 = time.perf_counter()
    try:
        final_resp, chunks, meta = run_deep_agent(
            query=case.query,
            standard_filter=case.standard,
            max_turns=max_turns,
            top_k=k,
            agent=agent,
            tool_type=tool_type,
        )
    except Exception as e:
        dt = time.perf_counter() - t0
        res.elapsed_sec = round(dt, 2)
        res.error = f"{type(e).__name__}: {e}"
        res.diag["error"] = res.error
        return res

    dt = time.perf_counter() - t0
    res.elapsed_sec = round(dt, 2)

    res.total_llm_turns = meta.get("turns_executed", 0)
    res.total_tool_calls = meta.get("tool_calls", meta.get("search_calls", 0))
    res.total_input_tokens = meta.get("input_tokens", 0)
    res.total_output_tokens = meta.get("output_tokens", 0)
    res.total_tokens = meta.get("total_tokens", res.total_input_tokens + res.total_output_tokens)
    res.total_cost_usd = compute_llm_cost(res.total_input_tokens, res.total_output_tokens)

    # 지연 시간 추정 (외부 LLM 비율 대략 계측: 전체 시간 중 도구 실행 외 시간)
    res.external_sec = round(max(0.0, dt * 0.8), 2)
    res.internal_sec = round(max(0.0, dt - res.external_sec), 2)

    search_items = [(c.content, c.chunk_id) for c in chunks]
    citations = list(final_resp.citations) if final_resp else []
    cite_items = [(c.content, c.chunk_id) for c in citations]

    metrics: dict[str, Any] = {}
    for stage, contents in (("retrieval", search_items), ("generation", cite_items)):
        for mode in ("exact", "prefix"):
            fh, cov = rank_hit(contents, gold_paras, mode)
            metrics[f"{stage}_{mode}_hit@1"] = fh == 1
            metrics[f"{stage}_{mode}_hit@{k}"] = fh is not None and fh <= k
            metrics[f"{stage}_{mode}_mrr"] = round(1.0 / fh, 4) if fh else 0.0
            metrics[f"{stage}_{mode}_recall"] = round(len(cov) / len(gold_paras), 4) if gold_paras else 0.0

    metrics["legacy_substring"] = legacy_substring_hit(case.references, citations)
    metrics["is_answerable"] = bool(final_resp.is_answerable) if final_resp else False
    metrics["retrieval_pass"] = retrieval_pass(search_items, resolve_core_paras(case, gold_paras))
    res.metrics = metrics

    res.diag = {
        "max_turns": max_turns,
        "turns_executed": meta.get("turns_executed"),
        "search_calls": meta.get("search_calls"),
        "search_queries": meta.get("search_queries"),
        "fallback_triggered": meta.get("fallback_triggered"),
        "fallback_reason": meta.get("fallback_reason"),
        "n_retrieved": len(chunks),
        "n_citations": len(citations),
        "retrieval_chapters": [c.metadata.chapter for c in chunks][:10],
        "citation_paras": sorted({p for c in citations for p in extract_chunk_paras(c.content, c.chunk_id)}),
        "query": case.query,
        "answer": (final_resp.answer if final_resp else ""),
    }

    return res


def aggregate_deep_agent_results(rows: list[DeepAgentCaseResult], k: int = 10) -> dict[str, Any]:
    """딥에이전트 실측 결과 통계 집계"""
    n_total = len(rows)
    valid_rows = [r for r in rows if r.error is None and r.metrics]
    n_valid = len(valid_rows)

    summary: dict[str, Any] = {
        "n_total": n_total,
        "n_measured": n_valid,
        "n_error": n_total - n_valid,
        "max_turns": rows[0].max_turns if rows else 0,
    }

    if n_valid == 0:
        return summary

    for stage in ("retrieval", "generation"):
        for mode in ("exact", "prefix"):
            for metric in ("hit@1", f"hit@{k}"):
                key = f"{stage}_{mode}_{metric}"
                hits = sum(1 for r in valid_rows if r.metrics.get(key) is True)
                summary[key] = {
                    "hits": hits,
                    "rate": round(hits / n_valid, 4),
                }

            for metric in ("mrr", "recall"):
                key = f"{stage}_{mode}_{metric}"
                vals = [float(r.metrics.get(key, 0.0)) for r in valid_rows]
                summary[f"{key}_avg"] = round(sum(vals) / n_valid, 4)

    retrieval_pass_hits = sum(1 for r in valid_rows if r.metrics.get("retrieval_pass") is True)
    summary["retrieval_pass"] = {
        "hits": retrieval_pass_hits,
        "rate": round(retrieval_pass_hits / n_valid, 4),
    }

    answerable_hits = sum(1 for r in valid_rows if r.metrics.get("is_answerable") is True)
    summary["is_answerable"] = {
        "hits": answerable_hits,
        "rate": round(answerable_hits / n_valid, 4),
    }

    fallback_hits = sum(1 for r in valid_rows if r.diag.get("fallback_triggered") is True)
    summary["fallback_rate"] = {
        "hits": fallback_hits,
        "rate": round(fallback_hits / n_valid, 4),
    }

    # 토큰 및 비용 통계
    n = n_valid
    llm_turns_list = [r.total_llm_turns for r in valid_rows]
    tool_calls_list = [r.total_tool_calls for r in valid_rows]
    cost_list = [r.total_cost_usd for r in valid_rows]
    input_tokens_list = [r.total_input_tokens for r in valid_rows]
    output_tokens_list = [r.total_output_tokens for r in valid_rows]
    total_tokens_list = [r.total_tokens for r in valid_rows]

    summary["cost_and_tokens"] = {
        "total_cost_usd": round(sum(cost_list), 6),
        "avg_cost_usd": round(sum(cost_list) / n, 6),
        "avg_llm_turns": round(sum(llm_turns_list) / n, 2),
        "avg_tool_calls": round(sum(tool_calls_list) / n, 2),
        "total_input_tokens": sum(input_tokens_list),
        "total_output_tokens": sum(output_tokens_list),
        "total_tokens": sum(total_tokens_list),
        "avg_input_tokens": round(sum(input_tokens_list) / n, 1),
        "avg_output_tokens": round(sum(output_tokens_list) / n, 1),
        "avg_total_tokens": round(sum(total_tokens_list) / n, 1),
    }

    # 지연 시간 통계
    def _compute_stats(series: list[float]) -> dict[str, float]:
        s = sorted(series)
        return {
            "p50": round(_percentile(s, 50.0), 2),
            "p90": round(_percentile(s, 90.0), 2),
            "p95": round(_percentile(s, 95.0), 2),
            "p99": round(_percentile(s, 99.0), 2),
            "avg": round(sum(s) / len(s), 2),
            "min": round(min(s), 2),
            "max": round(max(s), 2),
        }

    summary["latency"] = {
        "total": _compute_stats([r.elapsed_sec for r in valid_rows]),
        "external_llm": _compute_stats([r.external_sec for r in valid_rows]),
        "internal_search": _compute_stats([r.internal_sec for r in valid_rows]),
        "target_sec": TARGET_LATENCY_TOTAL_SEC,
    }

    return summary


# 하위 호환성을 위한 별칭
aggregate_deep_agent_ensemble_results = aggregate_deep_agent_results


def _save_checkpoint(path: Path, results: list[DeepAgentCaseResult], max_turns: int, k: int) -> None:
    """원자적 교체 방식으로 체크포인트 저장"""
    tmp_path = path.with_suffix(".tmp")
    payload = {
        "updated_at": datetime.now(KST).isoformat(),
        "max_turns": max_turns,
        "k": k,
        "cases": [asdict(r) for r in results],
    }
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _load_checkpoint(path: Path, expected_turns: int, expected_k: int) -> list[DeepAgentCaseResult]:
    """체크포인트 파일 로드"""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    saved_turns = data.get("max_turns")
    saved_k = data.get("k")
    if saved_turns is not None and saved_turns != expected_turns:
        raise ValueError(f"체크포인트 max_turns({saved_turns}) != 지정된 max_turns({expected_turns})")
    if saved_k is not None and saved_k != expected_k:
        raise ValueError(f"체크포인트 k({saved_k}) != 지정된 k({expected_k})")
    return [DeepAgentCaseResult(**c) for c in data.get("cases", [])]


def execute_benchmark_loop(
    cases: list[BenchmarkCase],
    completed_ids: set[str],
    checkpoint_path: Path,
    results: list[DeepAgentCaseResult],
    max_turns: int,
    k: int,
    agent: Agent | None,
    tool_type: str = "single",
    measure_fn: Callable[..., DeepAgentCaseResult] | None = None,
) -> None:
    """케이스 반복 실행 및 계측 로그 출력"""
    fn = measure_fn or measure_deep_agent_case
    for i, case in enumerate(cases, 1):
        if case.id in completed_ids:
            continue

        print(f"[{i}/{len(cases)}] {case.id} 실측 중…", flush=True)
        if measure_fn is not None:
            res = fn(case, max_turns=max_turns, k=k, agent=agent)
        else:
            res = fn(case, max_turns=max_turns, k=k, agent=agent, tool_type=tool_type)
        sec_str = f"{res.elapsed_sec:.2f}s"
        if res.error:
            print(f"    ✗ 에러: {res.error} ({sec_str})")
        else:
            m = res.metrics
            print(
                f"    소요={sec_str} | "
                f"LLM턴={res.total_llm_turns}회 | "
                f"도구호출={res.total_tool_calls}회 | "
                f"토큰={res.total_tokens} (비용=${res.total_cost_usd:.6f}) | "
                f"검색 exact@{k}={m[f'retrieval_exact_hit@{k}']} | "
                f"생성 exact@1={m['generation_exact_hit@1']}"
            )
        results.append(res)
        _save_checkpoint(checkpoint_path, results, max_turns, k)
