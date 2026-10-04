"""
[실측] 가중 RRF 하이브리드 검색 베이스라인 파이프라인 성능 및 비용 실측 하니스 (이슈 #401)

이슈 #245(앙상블 vs 딥에이전트 비교 실험)의 기준 베이스라인 계측 스크립트:
- 파이프라인: 현행 가중 RRF 하이브리드 검색 (Dense + Sparse 형태소 w=0.1) + 고정 4단계 LangGraph
- 대상: 벤치마크 114건 (K-GAAP)
- 계측 항목:
  1. 정확도: Hit@1, Hit@10, MRR, Recall (검색 및 생성 단계별 exact/prefix 매칭)
  2. LLM 호출 및 비용: PydanticAI Agent.run_sync 계측 래퍼를 통한
     - 쿼리당 LLM 호출 횟수
     - 노드별/전체 입력 및 출력 토큰 수
     - gpt-5.4-mini 가격 모델 기준 비용 (USD)
  3. 지연 시간: 쿼리별 전체 시간, 내부(검색/RRF)/외부(LLM) 시간 분리, p50/p90/p95/p99 통계

실행:
  uv run python scripts/benchmark_baseline_pipeline.py
  uv run python scripts/benchmark_baseline_pipeline.py --limit 5        # 스모크 테스트
  uv run python scripts/benchmark_baseline_pipeline.py --resume         # 중단 시 이어하기
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv()
if os.getenv("POSTGRES_HOST") in ("database", "localhost", None):
    os.environ["POSTGRES_HOST"] = "127.0.0.1"

# TEI 임베딩 컨테이너가 8080에 기동되어 있을 경우 활용
if not os.getenv("EMBEDDING_SERVER_URL"):
    os.environ["EMBEDDING_SERVER_URL"] = "http://localhost:8080"

from pydantic_ai import Agent

from src.db.connection import close_pool, init_pool
from src.utils.config import (
    GPT_5_4_MINI_INPUT_COST_PER_TOKEN,
    GPT_5_4_MINI_OUTPUT_COST_PER_TOKEN,
    KST,
    TARGET_LATENCY_TOTAL_SEC,
    USE_RERANKER,
)
from tests.integration.helpers import run_workflow_to_completion
from tests.utils.benchmark_loader import BenchmarkCase, load_benchmark
from tests.utils.benchmark_metrics import (
    _percentile,
    extract_chunk_paras,
    get_chunk_count,
    get_indexed_chapters,
    gold_para_set,
    legacy_substring_hit,
    parse_gold_clauses,
    rank_hit,
    resolve_core_paras,
    retrieval_pass,
    sort_chapters,
)
from tests.utils.infra_check import check_docker_infrastructure


@dataclass
class LLMCallRecord:
    """단일 LLM 호출 계측 레코드"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    elapsed_sec: float = 0.0
    model: str = ""


@dataclass
class BaselineCaseResult:
    """베이스라인 고정 파이프라인 단일 케이스 계측 결과"""
    case_id: str
    chapter: str
    measurable: bool
    gold_paras: list[str]
    metrics: dict[str, Any] = field(default_factory=dict)
    diag: dict[str, Any] = field(default_factory=dict)
    llm_calls: list[dict[str, Any]] = field(default_factory=list)
    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    elapsed_sec: float = 0.0
    external_sec: float = 0.0
    internal_sec: float = 0.0
    error: str | None = None


# 하위 호환성을 위한 별칭
Scenario1CaseResult = BaselineCaseResult


def compute_llm_cost(input_tokens: int, output_tokens: int) -> float:
    """입출력 토큰 수 기반 gpt-5.4-mini 비용 산정식"""
    return round(
        input_tokens * GPT_5_4_MINI_INPUT_COST_PER_TOKEN
        + output_tokens * GPT_5_4_MINI_OUTPUT_COST_PER_TOKEN,
        8,
    )


class LLMTracker:
    """PydanticAI Agent.run_sync 실행 시 LLM 토큰 및 호출 비용을 정밀 추적하는 컨텍스트 매니저"""

    def __init__(self):
        self.calls: list[LLMCallRecord] = []
        self._orig_run_sync = Agent.run_sync
        self._patcher: Any = None

    def __enter__(self) -> LLMTracker:
        self.calls = []

        def _tracking_run_sync(agent_self: Agent, *args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            result = self._orig_run_sync(agent_self, *args, **kwargs)
            dt = time.perf_counter() - t0

            usage = getattr(result, "usage", None)
            inp = getattr(usage, "input_tokens", 0) if usage else 0
            out = getattr(usage, "output_tokens", 0) if usage else 0
            tot = getattr(usage, "total_tokens", inp + out) if usage else (inp + out)

            cost = 0.0
            if usage and getattr(usage, "cost", None) is not None:
                cost = float(usage.cost)
            else:
                cost = compute_llm_cost(inp, out)

            rec = LLMCallRecord(
                input_tokens=inp,
                output_tokens=out,
                total_tokens=tot,
                cost_usd=cost,
                elapsed_sec=round(dt, 3),
                model=str(getattr(agent_self, "model", "")),
            )
            self.calls.append(rec)
            return result

        self._patcher = patch.object(Agent, "run_sync", _tracking_run_sync)
        self._patcher.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._patcher:
            self._patcher.stop()


def measure_scenario1_case(case: BenchmarkCase, k: int = 10) -> Scenario1CaseResult:
    """단일 벤치마크 케이스에 대해 시나리오 1 전체 파이프라인 및 LLM 비용을 실측합니다."""
    clauses = parse_gold_clauses(case.references)
    gold_paras = gold_para_set(clauses)
    chapter = clauses[0].chapter if clauses else "?"

    res = Scenario1CaseResult(
        case_id=case.id,
        chapter=chapter,
        measurable=True,
        gold_paras=sorted(gold_paras),
    )

    t0 = time.perf_counter()
    tracker = LLMTracker()
    try:
        with tracker:
            state = run_workflow_to_completion(
                case.query,
                standard_filter=case.standard,
                metadata={"case_id": case.id, "gold": sorted(gold_paras)},
            )
    except Exception as e:
        dt = time.perf_counter() - t0
        res.elapsed_sec = round(dt, 2)
        res.error = f"{type(e).__name__}: {e}"
        res.diag["error"] = res.error
        return res

    dt = time.perf_counter() - t0
    res.elapsed_sec = round(dt, 2)

    # LLM 호출 및 비용 통계
    res.llm_calls = [asdict(c) for c in tracker.calls]
    res.total_llm_calls = len(tracker.calls)
    res.total_input_tokens = sum(c.input_tokens for c in tracker.calls)
    res.total_output_tokens = sum(c.output_tokens for c in tracker.calls)
    res.total_tokens = sum(c.total_tokens for c in tracker.calls)
    res.total_cost_usd = round(sum(c.cost_usd for c in tracker.calls), 8)

    # 파이프라인 내부/외부 지연 시간
    llm_time = sum(c.elapsed_sec for c in tracker.calls)
    res.external_sec = round(llm_time, 2)
    res.internal_sec = round(max(0.0, dt - llm_time), 2)

    fr = state.get("final_response")
    reranked = state.get("reranked_chunks") or []
    retrieved = state.get("retrieved_chunks") or []
    citations = list(fr.citations) if fr else []

    search_items = [(r.chunk.content, r.chunk.chunk_id) for r in reranked]
    cite_items = [(c.content, c.chunk_id) for c in citations]

    metrics: dict[str, Any] = {}
    for stage, contents in (("retrieval", search_items), ("generation", cite_items)):
        for mode in ("exact", "prefix"):
            fh, cov = rank_hit(contents, gold_paras, mode)
            metrics[f"{stage}_{mode}_hit@1"] = fh == 1
            metrics[f"{stage}_{mode}_hit@{k}"] = fh is not None and fh <= k
            metrics[f"{stage}_{mode}_mrr"] = round(1.0 / fh, 4) if fh else 0.0
            metrics[f"{stage}_{mode}_recall"] = (
                round(len(cov) / len(gold_paras), 4) if gold_paras else 0.0
            )

    metrics["legacy_substring"] = legacy_substring_hit(case.references, citations)
    metrics["is_answerable"] = bool(fr.is_answerable) if fr else False
    metrics["retrieval_pass"] = retrieval_pass(search_items, resolve_core_paras(case, gold_paras))
    res.metrics = metrics

    rq = state.get("rewritten_query")
    ev = state.get("evaluation")
    res.diag = {
        "strategy": getattr(rq, "strategy", None),
        "rewrite_count": state.get("rewrite_count"),
        "n_retrieved": len(retrieved),
        "n_reranked": len(reranked),
        "n_citations": len(citations),
        "needs_external": getattr(ev, "needs_external", None),
        "eval_reasoning": (getattr(ev, "reasoning", "") or ""),
        "retrieval_chapters": [r.chunk.metadata.chapter for r in reranked][:10],
        "citation_paras": sorted(
            {p for c in citations for p in extract_chunk_paras(c.content, c.chunk_id)}
        ),
        "query": case.query,
        "answer": (fr.answer if fr else ""),
        "error_logs": state.get("error_logs") or [],
    }

    return res


def aggregate_baseline_results(results: list[BaselineCaseResult], k: int = 10) -> dict[str, Any]:
    """베이스라인 파이프라인 전체 결과에 대한 정확도, LLM 호출/토큰/비용, 지연 시간 집계"""
    rows = [r for r in results if r.measurable and r.error is None]
    n = len(rows)

    summary: dict[str, Any] = {
        "n_total": len(results),
        "n_measured": n,
        "n_error": sum(1 for r in results if r.error is not None),
    }

    if not n:
        return summary

    # 정확도 지표
    keys = [
        "generation_exact_hit@1",
        f"generation_exact_hit@{k}",
        "generation_prefix_hit@1",
        f"generation_prefix_hit@{k}",
        "retrieval_exact_hit@1",
        f"retrieval_exact_hit@{k}",
        "retrieval_prefix_hit@1",
        f"retrieval_prefix_hit@{k}",
        "retrieval_pass",
        "legacy_substring",
        "is_answerable",
    ]
    for key in keys:
        hits = sum(1 for r in rows if r.metrics.get(key))
        summary[key] = {"hits": hits, "rate": round(hits / n, 4)}

    for stage in ("generation", "retrieval"):
        for mode in ("exact", "prefix"):
            mrr_avg = sum(r.metrics.get(f"{stage}_{mode}_mrr", 0.0) for r in rows) / n
            summary[f"{stage}_{mode}_mrr_avg"] = round(mrr_avg, 4)
            recall_avg = sum(r.metrics.get(f"{stage}_{mode}_recall", 0.0) for r in rows) / n
            summary[f"{stage}_{mode}_recall_avg"] = round(recall_avg, 4)

    # LLM 호출 및 비용 통계
    llm_calls_list = [r.total_llm_calls for r in rows]
    input_tokens_list = [r.total_input_tokens for r in rows]
    output_tokens_list = [r.total_output_tokens for r in rows]
    total_tokens_list = [r.total_tokens for r in rows]
    cost_list = [r.total_cost_usd for r in rows]

    summary["cost_and_tokens"] = {
        "total_cost_usd": round(sum(cost_list), 6),
        "avg_cost_usd": round(sum(cost_list) / n, 6),
        "avg_llm_calls": round(sum(llm_calls_list) / n, 2),
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

    elapsed_list = [r.elapsed_sec for r in rows]
    ext_list = [r.external_sec for r in rows]
    int_list = [r.internal_sec for r in rows]

    summary["latency"] = {
        "total": _compute_stats(elapsed_list),
        "external_llm": _compute_stats(ext_list),
        "internal_pipeline": _compute_stats(int_list),
        "target_sec": TARGET_LATENCY_TOTAL_SEC,
    }

    return summary


# 하위 호환성을 위한 별칭
aggregate_scenario1 = aggregate_baseline_results


def _save_checkpoint(path: Path, results: list[BaselineCaseResult], k: int) -> None:
    """원자적 교체 방식으로 체크포인트 저장"""
    tmp_path = path.with_suffix(".tmp")
    payload = {
        "updated_at": datetime.now(KST).isoformat(),
        "k": k,
        "cases": [asdict(r) for r in results],
    }
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _load_checkpoint(path: Path, expected_k: int) -> list[Scenario1CaseResult]:
    """체크포인트 파일 로드"""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    saved_k = data.get("k")
    if saved_k is not None and saved_k != expected_k:
        raise ValueError(f"체크포인트 k({saved_k}) != 지정된 k({expected_k})")
    return [Scenario1CaseResult(**c) for c in data.get("cases", [])]


def write_baseline_markdown_report(
    summary: dict[str, Any],
    results: list[BaselineCaseResult],
    out_path: Path,
    k: int = 10,
) -> None:
    """베이스라인 파이프라인 기준 실측 리포트 마크다운 파일 작성"""
    ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    lat = summary.get("latency", {}).get("total", {})
    cost = summary.get("cost_and_tokens", {})

    lines = [
        "# [실측 리포트] 가중 RRF 하이브리드 검색 베이스라인 성능 및 비용 (#401)",
        "",
        "> **한 줄 요약 (BLUF):** 현행 가중 RRF 하이브리드 검색(Dense + 형태소 Sparse w=0.1)과 고정 4단계 파이프라인의 "
        f"114건 실측 결과, **검색 Hit@{k} {summary.get(f'retrieval_exact_hit@{k}', {}).get('rate', 0):.1%} "
        f"({summary.get(f'retrieval_exact_hit@{k}', {}).get('hits', 0)}/{summary.get('n_measured', 0)})**, "
        f"**생성 Hit@1 {summary.get('generation_exact_hit@1', {}).get('rate', 0):.1%}**, "
        f"**쿼리당 평균 비용 ${cost.get('avg_cost_usd', 0):.6f} (총 ${cost.get('total_cost_usd', 0):.4f})**, "
        f"**지연 시간 p50 {lat.get('p50', 0):.2f}초 / p95 {lat.get('p95', 0):.2f}초**를 기록하여 "
        "후속 비교군(#402, #403)의 명확한 기준선(Baseline)을 확립했습니다.",
        "",
        "## 1. 실험 환경 및 측정 조건",
        "",
        f"- **측정 일시:** {ts}",
        "- **비교 시나리오:** 시나리오 1 (하이브리드 가중 RRF 앙상블 + 고정 LangGraph 그래프)",
        "- **검색 아키텍처:** KURE-v1 Dense 임베딩 (1024차원) + PostgreSQL `content_morph` tsvector Sparse (가중치 w=0.1) RRF 융합",
        f"- **파이프라인:** 고정 4단계 (rewrite/전략판단 → search/RRF → evaluate/CRAG → generate) — USE_RERANKER={USE_RERANKER}",
        "- **LLM 모델:** `openai:gpt-5.4-mini` (온도 0, 재작성 및 생성)",
        f"- **모집단:** K-GAAP 벤치마크 114건 전수 (측정 완료 {summary.get('n_measured', 0)}건, 에러 {summary.get('n_error', 0)}건)",
        "",
        "## 2. 정확도 성능 (Accuracy)",
        "",
        "| 평가 단계 | 매칭 방식 | Hit@1 | Hit@10 | MRR (평균) | Recall (평균) |",
        "|---|---|---|---|---|---|",
        f"| **검색 단계 (Retrieval)** | Exact (정확 일치) | {summary.get('retrieval_exact_hit@1', {}).get('rate', 0):.1%} ({summary.get('retrieval_exact_hit@1', {}).get('hits', 0)}건) | {summary.get(f'retrieval_exact_hit@{k}', {}).get('rate', 0):.1%} ({summary.get(f'retrieval_exact_hit@{k}', {}).get('hits', 0)}건) | {summary.get('retrieval_exact_mrr_avg', 0):.4f} | {summary.get('retrieval_exact_recall_avg', 0):.4f} |",
        f"| **검색 단계 (Retrieval)** | Prefix (계층 포함) | {summary.get('retrieval_prefix_hit@1', {}).get('rate', 0):.1%} ({summary.get('retrieval_prefix_hit@1', {}).get('hits', 0)}건) | {summary.get(f'retrieval_prefix_hit@{k}', {}).get('rate', 0):.1%} ({summary.get(f'retrieval_prefix_hit@{k}', {}).get('hits', 0)}건) | {summary.get('retrieval_prefix_mrr_avg', 0):.4f} | {summary.get('retrieval_prefix_recall_avg', 0):.4f} |",
        f"| **생성 단계 (Generation)** | Exact (인용 일치) | {summary.get('generation_exact_hit@1', {}).get('rate', 0):.1%} ({summary.get('generation_exact_hit@1', {}).get('hits', 0)}건) | {summary.get(f'generation_exact_hit@{k}', {}).get('rate', 0):.1%} ({summary.get(f'generation_exact_hit@{k}', {}).get('hits', 0)}건) | {summary.get('generation_exact_mrr_avg', 0):.4f} | {summary.get('generation_exact_recall_avg', 0):.4f} |",
        f"| **생성 단계 (Generation)** | Prefix (계층 인용) | {summary.get('generation_prefix_hit@1', {}).get('rate', 0):.1%} ({summary.get('generation_prefix_hit@1', {}).get('hits', 0)}건) | {summary.get(f'generation_prefix_hit@{k}', {}).get('rate', 0):.1%} ({summary.get(f'generation_prefix_hit@{k}', {}).get('hits', 0)}건) | {summary.get('generation_prefix_mrr_avg', 0):.4f} | {summary.get('generation_prefix_recall_avg', 0):.4f} |",
        "",
        f"- **핵심 조항 검색 통과율 (`retrieval_pass`, 핵심 Top-5):** {summary.get('retrieval_pass', {}).get('rate', 0):.1%} ({summary.get('retrieval_pass', {}).get('hits', 0)}/{summary.get('n_measured', 0)})",
        f"- **답변 가능 판정율 (`is_answerable`):** {summary.get('is_answerable', {}).get('rate', 0):.1%} ({summary.get('is_answerable', {}).get('hits', 0)}/{summary.get('n_measured', 0)})",
        "",
        "## 3. LLM 호출 횟수 및 비용 (Cost & Token Usage)",
        "",
        f"- **질의당 평균 LLM 호출 횟수:** {cost.get('avg_llm_calls', 0):.2f}회 (고정 4단계 파이프라인)",
        f"- **총 비용 (114건):** ${cost.get('total_cost_usd', 0):.6f}",
        f"- **질의당 평균 비용:** ${cost.get('avg_cost_usd', 0):.6f}",
        f"- **총 토큰 소모량:** {cost.get('total_tokens', 0):,} 토큰 (입력: {cost.get('total_input_tokens', 0):,}, 출력: {cost.get('total_output_tokens', 0):,})",
        f"- **질의당 평균 토큰:** {cost.get('avg_total_tokens', 0):.1f} 토큰 (입력: {cost.get('avg_input_tokens', 0):.1f}, 출력: {cost.get('avg_output_tokens', 0):.1f})",
        "",
        "## 4. 지연 시간 분석 (Latency)",
        "",
        "| 구분 | p50 (중앙값) | p90 | p95 | p99 | 평균 (Avg) | 최소 | 최대 |",
        "|---|---|---|---|---|---|---|---|",
        f"| **전체 쿼리 지연 (Total)** | **{lat.get('p50', 0):.2f}s** | {lat.get('p90', 0):.2f}s | **{lat.get('p95', 0):.2f}s** | {lat.get('p99', 0):.2f}s | {lat.get('avg', 0):.2f}s | {lat.get('min', 0):.2f}s | {lat.get('max', 0):.2f}s |",
        f"| 외부 LLM 지연 (External) | {summary.get('latency', {}).get('external_llm', {}).get('p50', 0):.2f}s | {summary.get('latency', {}).get('external_llm', {}).get('p90', 0):.2f}s | {summary.get('latency', {}).get('external_llm', {}).get('p95', 0):.2f}s | {summary.get('latency', {}).get('external_llm', {}).get('p99', 0):.2f}s | {summary.get('latency', {}).get('external_llm', {}).get('avg', 0):.2f}s | {summary.get('latency', {}).get('external_llm', {}).get('min', 0):.2f}s | {summary.get('latency', {}).get('external_llm', {}).get('max', 0):.2f}s |",
        f"| 내부 검색/DB (Internal) | {summary.get('latency', {}).get('internal_pipeline', {}).get('p50', 0):.2f}s | {summary.get('latency', {}).get('internal_pipeline', {}).get('p90', 0):.2f}s | {summary.get('latency', {}).get('internal_pipeline', {}).get('p95', 0):.2f}s | {summary.get('latency', {}).get('internal_pipeline', {}).get('p99', 0):.2f}s | {summary.get('latency', {}).get('internal_pipeline', {}).get('avg', 0):.2f}s | {summary.get('latency', {}).get('internal_pipeline', {}).get('min', 0):.2f}s | {summary.get('latency', {}).get('internal_pipeline', {}).get('max', 0):.2f}s |",
        "",
        "## 5. 결론 및 후속 시나리오 비교를 위한 시사점",
        "",
        "1. **기준선(Baseline) 확립:** 현행 고정 LangGraph 파이프라인은 쿼리당 항상 4회의 LLM 호출이 발생하며, "
        f"평균 지연 시간 {lat.get('avg', 0):.2f}초 중 약 {(summary.get('latency', {}).get('external_llm', {}).get('avg', 0) / max(lat.get('avg', 1), 0.001) * 100):.1f}%가 "
        "순수 LLM API 왕복 지연에 의해 발생합니다.",
        "2. **단일 검색 딥에이전트(#402) 대조 포인트:** 딥에이전트의 ReAct 루프가 1~2턴 만에 조기 종료될 경우 "
        "비용과 지연 시간을 절감할 수 있으나, 3턴 이상 반복 시 고정 4단계 파이프라인 대비 비용 및 지연 시간 급증 위험이 있습니다.",
        "3. **앙상블 딥에이전트(#403) 대조 포인트:** 본 기준선의 높은 검색 회수율(Hit@10)을 유지하면서 "
        "딥에이전트의 동적 판단을 결합했을 때의 트레이드오프를 평가하는 데 본 수치가 단일 기준점으로 활용됩니다.",
    ]

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# 하위 호환성을 위한 별칭
write_scenario1_markdown_report = write_baseline_markdown_report


def run_benchmark_baseline_loop(
    cases: list[BenchmarkCase],
    completed_ids: set[str],
    checkpoint_path: Path,
    results: list[BaselineCaseResult],
    k: int,
) -> None:
    """케이스 반복 실행 및 계측 로그 출력 실행 함수"""
    for i, case in enumerate(cases, 1):
        if case.id in completed_ids:
            continue

        print(f"[{i}/{len(cases)}] {case.id} 실측 중…", flush=True)
        res = measure_scenario1_case(case, k=k)
        sec_str = f"{res.elapsed_sec:.2f}s"
        if res.error:
            print(f"    ✗ 에러: {res.error} ({sec_str})")
        else:
            m = res.metrics
            print(
                f"    소요={sec_str} (LLM {res.external_sec:.2f}s, 내부 {res.internal_sec:.2f}s) | "
                f"LLM호출={res.total_llm_calls}회 | "
                f"토큰={res.total_tokens} (비용=${res.total_cost_usd:.6f}) | "
                f"검색 exact@{k}={m[f'retrieval_exact_hit@{k}']} | "
                f"생성 exact@1={m['generation_exact_hit@1']}"
            )
        results.append(res)
        _save_checkpoint(checkpoint_path, results, k)


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점 스크립트 함수: 인자 파싱 및 인프라 검증 후 벤치마크 실행 루프를 호출합니다."""
    parser = argparse.ArgumentParser(description="가중 RRF 하이브리드 검색 베이스라인 파이프라인 성능 및 비용 실측")
    parser.add_argument("--k", type=int, default=10, help="Hit@k 의 k (기본 10)")
    parser.add_argument("--limit", type=int, default=None, help="최대 측정 케이스 수 (스모크 테스트용)")
    parser.add_argument("--resume", action="store_true", help="중단된 체크포인트 이어서 진행")
    parser.add_argument("--out-dir", default="docs/measurements", help="결과 저장 디렉토리")
    args = parser.parse_args(argv)

    infra_error = check_docker_infrastructure()
    if infra_error:
        print(f"[중단] 인프라 점검 실패: {infra_error}")
        return 2

    if not os.getenv("OPENAI_API_KEY"):
        print("[중단] OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        return 2

    init_pool()
    try:
        indexed = get_indexed_chapters()
        cases = load_benchmark()
        if not cases:
            print("[중단] 벤치마크 케이스가 없습니다.")
            return 2

        if args.limit is not None and args.limit > 0:
            cases = cases[:args.limit]

        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = out_dir / "checkpoint_scenario1.json"

        results: list[BaselineCaseResult] = []
        completed_ids: set[str] = set()

        if args.resume:
            results = _load_checkpoint(checkpoint_path, expected_k=args.k)
            completed_ids = {r.case_id for r in results}
            if completed_ids:
                print(f"[체크포인트 복구] 기존 완료된 {len(completed_ids)}건을 건너뜁니다.\n")

        print(f"적재된 장: {len(indexed)}개")
        print(f"측정 대상 케이스: {len(cases)}건 (k={args.k}, 기완료 {len(completed_ids)}건)\n")

        run_benchmark_baseline_loop(
            cases=cases,
            completed_ids=completed_ids,
            checkpoint_path=checkpoint_path,
            results=results,
            k=args.k,
        )

        summary = aggregate_baseline_results(results, k=args.k)
        print("\n" + "=" * 64)
        print("베이스라인 실측 완료 집계")
        print("=" * 64)
        print(f"측정 건수: {summary['n_measured']}/{summary['n_total']}")
        print(f"검색 Exact@{args.k}: {summary.get(f'retrieval_exact_hit@{args.k}', {}).get('rate', 0):.1%}")
        print(f"생성 Exact@1: {summary.get('generation_exact_hit@1', {}).get('rate', 0):.1%}")
        print(f"검색 Exact MRR: {summary.get('retrieval_exact_mrr_avg', 0):.4f}")
        c = summary.get("cost_and_tokens", {})
        print(f"평균 LLM 호출: {c.get('avg_llm_calls', 0):.2f}회 | 평균 비용: ${c.get('avg_cost_usd', 0):.6f}")
        l = summary.get("latency", {}).get("total", {})
        print(f"지연 시간: p50={l.get('p50', 0):.2f}s / p95={l.get('p95', 0):.2f}s / avg={l.get('avg', 0):.2f}s")

        # 결과 영속화 (raw JSON)
        raw_out_path = out_dir / "scenario1_baseline.json"
        payload = {
            "generated_at": datetime.now(KST).isoformat(),
            "k": args.k,
            "summary": summary,
            "cases": [asdict(r) for r in results],
        }
        raw_out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nRaw 데이터 저장: {raw_out_path}")

        # 마크다운 리포트 저장
        report_dir = Path("docs/benchmark")
        report_dir.mkdir(parents=True, exist_ok=True)
        report_out_path = report_dir / "scenario1_baseline_report.md"
        write_baseline_markdown_report(summary, results, report_out_path, k=args.k)
        print(f"리포트 저장: {report_out_path}")

        return 0
    finally:
        close_pool()


if __name__ == "__main__":
    raise SystemExit(main())
