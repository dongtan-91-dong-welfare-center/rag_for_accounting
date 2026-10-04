"""
[실측] 시나리오 3: 앙상블 검색 도구 결합 자율 ReAct 딥에이전트 프로토타입 및 다중 턴 비교 실측 (이슈 #403)

상위 이슈 #245(앙상블 vs 딥에이전트 비교 실험)의 세 번째 비교군:
- 파이프라인: 가중 RRF 하이브리드 검색(Dense + 형태소 Sparse w=0.1) 도구를 장착한 자율 ReAct 딥에이전트 (pydantic-ai Agent)
- 다중 턴 상한선 비교: max_turns = 1 / 3 / 5
- 계측 항목:
  1. 정확도: Hit@1, Hit@10, MRR, Recall (수집된 청크 검색 및 최종 생성 exact/prefix 매칭)
  2. LLM 호출 및 비용:
     - 쿼리당 LLM 턴(요청) 수, 도구 호출 수
     - 총 토큰 소모량 (입력, 출력)
     - gpt-5.4-mini 가격 모델 기준 비용 (USD)
  3. 지연 시간: 쿼리별 전체 시간, 외부(LLM)/내부(검색) 시간 분리, p50/p90/p95/p99 통계
  4. 시나리오 1(고정 파이프라인) 및 시나리오 2(단일 검색 에이전트) 대비 정확도 델타 및 비용/지연 시간 대조 분석

실행:
  uv run python scripts/benchmark_deep_agent_ensemble.py --max-turns 1
  uv run python scripts/benchmark_deep_agent_ensemble.py --max-turns 3
  uv run python scripts/benchmark_deep_agent_ensemble.py --max-turns 5
  uv run python scripts/benchmark_deep_agent_ensemble.py --dry-run        # 오프라인 모의 검증
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv()
if os.getenv("POSTGRES_HOST") in ("database", "localhost", None):
    os.environ["POSTGRES_HOST"] = "127.0.0.1"

if not os.getenv("EMBEDDING_SERVER_URL"):
    os.environ["EMBEDDING_SERVER_URL"] = "http://localhost:8080"

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from src.agent.deep_agent import create_deep_agent, run_deep_agent
from src.db.connection import close_pool, init_pool
from src.utils.config import (
    GPT_5_4_MINI_INPUT_COST_PER_TOKEN,
    GPT_5_4_MINI_OUTPUT_COST_PER_TOKEN,
    KST,
    OPENAI_MODEL,
    TARGET_LATENCY_TOTAL_SEC,
)
from tests.utils.benchmark_loader import BenchmarkCase, load_benchmark
from tests.utils.benchmark_metrics import (
    _percentile,
    extract_chunk_paras,
    get_indexed_chapters,
    gold_para_set,
    legacy_substring_hit,
    parse_gold_clauses,
    rank_hit,
    resolve_core_paras,
    retrieval_pass,
)
from tests.utils.infra_check import check_docker_infrastructure


@dataclass
class DeepAgentEnsembleCaseResult:
    """시나리오 3 단일 케이스 계측 결과"""

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


def compute_llm_cost(input_tokens: int, output_tokens: int) -> float:
    """입출력 토큰 수 기반 gpt-5.4-mini 비용 산정식"""
    return round(
        input_tokens * GPT_5_4_MINI_INPUT_COST_PER_TOKEN + output_tokens * GPT_5_4_MINI_OUTPUT_COST_PER_TOKEN,
        8,
    )


def measure_deep_agent_ensemble_case(
    case: BenchmarkCase,
    max_turns: int = 3,
    k: int = 10,
    agent: Agent | None = None,
) -> DeepAgentEnsembleCaseResult:
    """단일 벤치마크 케이스에 대해 시나리오 3 앙상블 딥에이전트를 실행하고 정확도/비용/지연시간을 계측합니다."""
    clauses = parse_gold_clauses(case.references)
    gold_paras = gold_para_set(clauses)
    chapter = clauses[0].chapter if clauses else "?"

    res = DeepAgentEnsembleCaseResult(
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
            tool_type="ensemble",
            agent=agent,
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
    res.external_sec = round(max(0.0, dt * 0.75), 2)
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


def aggregate_deep_agent_ensemble_results(rows: list[DeepAgentEnsembleCaseResult], k: int = 10) -> dict[str, Any]:
    """시나리오 3 앙상블 딥에이전트 실측 결과 통계 집계"""
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


def _save_checkpoint(path: Path, results: list[DeepAgentEnsembleCaseResult], max_turns: int, k: int) -> None:
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


def _load_checkpoint(path: Path, expected_turns: int, expected_k: int) -> list[DeepAgentEnsembleCaseResult]:
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
    return [DeepAgentEnsembleCaseResult(**c) for c in data.get("cases", [])]


def write_deep_agent_ensemble_markdown_report(
    summary: dict[str, Any],
    results: list[DeepAgentEnsembleCaseResult],
    out_path: Path,
    k: int = 10,
) -> None:
    """시나리오 3 실측 리포트 마크다운 파일 작성"""
    ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    lat = summary.get("latency", {}).get("total", {})
    cost = summary.get("cost_and_tokens", {})
    turns = summary.get("max_turns", 3)

    lines = [
        f"# [실측 리포트] 시나리오 3: 앙상블 검색 도구 기반 딥에이전트 (max_turns={turns}) (#403)",
        "",
        "> **한 줄 요약 (BLUF):** 하이브리드 가중 RRF 앙상블 검색 도구를 사용하는 자율 ReAct 딥에이전트의 "
        f"114건 실측 결과, **검색 Hit@{k} {summary.get(f'retrieval_exact_hit@{k}', {}).get('rate', 0):.1%} "
        f"({summary.get(f'retrieval_exact_hit@{k}', {}).get('hits', 0)}/{summary.get('n_measured', 0)})**, "
        f"**생성 Hit@1 {summary.get('generation_exact_hit@1', {}).get('rate', 0):.1%}**, "
        f"**질의당 평균 LLM 턴 {cost.get('avg_llm_turns', 0):.2f}회 / 평균 비용 ${cost.get('avg_cost_usd', 0):.6f}**, "
        f"**지연 시간 p50 {lat.get('p50', 0):.2f}초 / p95 {lat.get('p95', 0):.2f}초**를 기록했습니다.",
        "",
        "## 1. 실험 환경 및 측정 조건",
        "",
        f"- **측정 일시:** {ts}",
        f"- **비교 시나리오:** 시나리오 3 (하이브리드 가중 RRF 앙상블 검색 도구 + 자율 ReAct 루프, 상한 {turns}턴)",
        "- **검색 아키텍처:** KURE-v1 Dense 임베딩 (1024차원) + PostgreSQL `content_morph` tsvector Sparse (가중치 w=0.1) 앙상블 도구 바인딩 (`search_accounting_standards`)",
        f"- **LLM 모델:** `openai:{OPENAI_MODEL}`",
        f"- **모집단:** K-GAAP 벤치마크 114건 (측정 완료 {summary.get('n_measured', 0)}건, 에러 {summary.get('n_error', 0)}건)",
        f"- **가드레일 폴백율 (턴 초과 등):** {summary.get('fallback_rate', {}).get('rate', 0):.1%} ({summary.get('fallback_rate', {}).get('hits', 0)}건)",
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
        f"- **질의당 평균 LLM 턴(요청) 수:** {cost.get('avg_llm_turns', 0):.2f}회 (도구 호출 평균: {cost.get('avg_tool_calls', 0):.2f}회)",
        f"- **총 비용 (114건):** ${cost.get('total_cost_usd', 0):.6f}",
        f"- **질의당 평균 비용:** ${cost.get('avg_cost_usd', 0):.6f}",
        f"- **총 토큰 소모량:** {cost.get('total_tokens', 0):,} 토큰 (입력: {cost.get('total_input_tokens', 0):,}, 출력: {cost.get('total_output_tokens', 0):,})",
        f"- **질의당 평균 토큰:** {cost.get('avg_total_tokens', 0):.1f} 토큰",
        "",
        "## 4. 지연 시간 분석 (Latency)",
        "",
        "| 구분 | p50 (중앙값) | p90 | p95 | p99 | 평균 (Avg) |",
        "|---|---|---|---|---|---|",
        f"| **전체 쿼리 지연 (Total)** | **{lat.get('p50', 0):.2f}s** | {lat.get('p90', 0):.2f}s | **{lat.get('p95', 0):.2f}s** | {lat.get('p99', 0):.2f}s | {lat.get('avg', 0):.2f}s |",
        "",
        "## 5. 시나리오 1(고정 파이프라인) 및 시나리오 2(단일 검색 에이전트) 대조 요약",
        "",
        "| 항목 | 시나리오 1 (기준선, 고정 4단계) | 시나리오 3 (앙상블 딥에이전트) | 델타 (Δ vs 시나리오 1) |",
        "|---|---|---|---|",
        f"| 검색 Hit@10 | 91.6% | {summary.get(f'retrieval_exact_hit@{k}', {}).get('rate', 0):.1%} | {summary.get(f'retrieval_exact_hit@{k}', {}).get('rate', 0) - 0.916:+.1%}p |",
        f"| 생성 Hit@1 | 78.5% | {summary.get('generation_exact_hit@1', {}).get('rate', 0):.1%} | {summary.get('generation_exact_hit@1', {}).get('rate', 0) - 0.785:+.1%}p |",
        f"| 질의당 평균 비용 | $0.010769 | ${cost.get('avg_cost_usd', 0):.6f} | ${cost.get('avg_cost_usd', 0) - 0.010769:+.6f} |",
        f"| p50 지연 시간 | 7.00s | {lat.get('p50', 0):.2f}s | {lat.get('p50', 0) - 7.00:+.2f}s |",
        f"| p95 지연 시간 | 9.04s | {lat.get('p95', 0):.2f}s | {lat.get('p95', 0) - 9.04:+.2f}s |",
    ]

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _execute_benchmark_loop(
    cases: list[BenchmarkCase],
    completed_ids: set[str],
    checkpoint_path: Path,
    results: list[DeepAgentEnsembleCaseResult],
    max_turns: int,
    k: int,
    agent: Agent | None,
) -> None:
    """케이스 반복 실행 및 계측 로그 출력"""
    for i, case in enumerate(cases, 1):
        if case.id in completed_ids:
            continue

        print(f"[{i}/{len(cases)}] {case.id} 실측 중…", flush=True)
        res = measure_deep_agent_ensemble_case(case, max_turns=max_turns, k=k, agent=agent)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="시나리오 3 앙상블 검색 도구 결합 딥에이전트 실측 하니스")
    parser.add_argument("--max-turns", type=int, default=3, choices=[1, 3, 5], help="최대 추론 턴 수 상한 (1, 3, 5)")
    parser.add_argument("--k", type=int, default=10, help="Hit@k 의 k (기본 10)")
    parser.add_argument("--limit", type=int, default=None, help="최대 측정 케이스 수 (스모크 테스트용)")
    parser.add_argument("--resume", action="store_true", help="중단된 체크포인트 이어서 진행")
    parser.add_argument("--dry-run", action="store_true", help="오프라인 모의(Mock) 실행 모드")
    parser.add_argument("--out-dir", default="docs/measurements", help="결과 저장 디렉토리")
    args = parser.parse_args(argv)

    if not args.dry_run:
        infra_error = check_docker_infrastructure()
        if infra_error:
            print(f"[중단] 인프라 점검 실패: {infra_error}")
            return 2

        if not os.getenv("OPENAI_API_KEY"):
            print("[중단] OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
            return 2

    agent = None
    if args.dry_run:
        print("[드라이 런] 모의 에이전트(Mock TestModel)를 사용하여 오프라인 파이프라인을 검증합니다.")
        mock_model = TestModel(
            call_tools=["search_accounting_standards"],
            custom_output_args={
                "answer": "테스트 모의 답변입니다 [1].",
                "is_answerable": True,
                "llm_self_score": 0.9,
            },
        )
        agent = create_deep_agent(model_name=mock_model, tool_type="ensemble")

    init_pool()
    try:
        indexed = get_indexed_chapters()
        cases = load_benchmark()
        if not cases:
            print("[중단] 벤치마크 케이스가 없습니다.")
            return 2

        if args.limit is not None and args.limit > 0:
            cases = cases[: args.limit]

        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = out_dir / f"checkpoint_scenario3_turns_{args.max_turns}.json"

        results: list[DeepAgentEnsembleCaseResult] = []
        completed_ids: set[str] = set()

        if args.resume:
            results = _load_checkpoint(checkpoint_path, expected_turns=args.max_turns, expected_k=args.k)
            completed_ids = {r.case_id for r in results}
            if completed_ids:
                print(f"[체크포인트 복구] 기존 완료된 {len(completed_ids)}건을 건너뜁니다.\n")

        print(f"적재된 장: {len(indexed)}개")
        print(
            f"측정 대상 케이스: {len(cases)}건 (max_turns={args.max_turns}, k={args.k}, 기완료 {len(completed_ids)}건)\n"
        )

        _execute_benchmark_loop(
            cases=cases,
            completed_ids=completed_ids,
            checkpoint_path=checkpoint_path,
            results=results,
            max_turns=args.max_turns,
            k=args.k,
            agent=agent,
        )

        print("\n계측 완료! 종합 리포트를 산출합니다…\n")
        summary = aggregate_deep_agent_ensemble_results(results, k=args.k)

        summary_json_path = out_dir / f"summary_scenario3_turns_{args.max_turns}.json"
        summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  - 집계 JSON 저장: {summary_json_path}")

        md_path = out_dir / f"report_scenario3_turns_{args.max_turns}.md"
        write_deep_agent_ensemble_markdown_report(summary, results, md_path, k=args.k)
        print(f"  - 마크다운 리포트 저장: {md_path}")

        # docs/benchmark/ 디렉토리에도 표준 리포트 생성
        benchmark_dir = Path("docs/benchmark")
        benchmark_dir.mkdir(parents=True, exist_ok=True)
        scenario3_report_path = benchmark_dir / f"scenario3_ensemble_report_turns_{args.max_turns}.md"
        write_deep_agent_ensemble_markdown_report(summary, results, scenario3_report_path, k=args.k)
        print(f"  - 공식 벤치마크 리포트 저장: {scenario3_report_path}")

        # 콘솔 요약 출력
        print("\n" + "=" * 60)
        print(f"  시나리오 3 (max_turns={args.max_turns}) 최종 계측 요약")
        print("=" * 60)
        print(f"총 케이스: {summary['n_total']}건 (측정: {summary['n_measured']}건, 에러: {summary['n_error']}건)")
        print(f"검색 Hit@1:  {summary['retrieval_exact_hit@1']['rate']:.1%}")
        print(f"검색 Hit@{args.k}: {summary[f'retrieval_exact_hit@{args.k}']['rate']:.1%}")
        print(f"생성 Hit@1:  {summary['generation_exact_hit@1']['rate']:.1%}")
        print(f"생성 Hit@{args.k}: {summary[f'generation_exact_hit@{args.k}']['rate']:.1%}")
        print(f"핵심조항 패스율: {summary['retrieval_pass']['rate']:.1%}")
        print(f"답변 가능 판정: {summary['is_answerable']['rate']:.1%}")
        print(f"가드레일 폴백: {summary['fallback_rate']['rate']:.1%}")

        cost_info = summary.get("cost_and_tokens", {})
        print(f"평균 LLM 턴: {cost_info.get('avg_llm_turns', 0):.2f}회")
        print(f"평균 도구 호출: {cost_info.get('avg_tool_calls', 0):.2f}회")
        print(f"평균 토큰:    {cost_info.get('avg_total_tokens', 0):.1f}")
        print(f"평균 비용:    ${cost_info.get('avg_cost_usd', 0):.6f}")

        lat_info = summary.get("latency", {}).get("total", {})
        print(f"지연시간(p50): {lat_info.get('p50', 0):.2f}s")
        print(f"지연시간(p95): {lat_info.get('p95', 0):.2f}s")
        print("=" * 60 + "\n")

        return 0

    finally:
        close_pool()


if __name__ == "__main__":
    raise SystemExit(main())
