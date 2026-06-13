"""
NFR-002 벤치마크 정확도 베이스라인 측정 하니스

채점 방법론이 회의 미결정 상태이므로, 단일 점수로 합치지 않고 여러 지표를 "동시에" 산출하여 회의에서 비교·결정할 수 있게 한다.

산출 지표(각 케이스별):
  - legacy_substring : 현행 test_reference_coverage 방식 재현(정답 라벨 문자열이 citation 본문에 부분일치하는가)
  - clause_exact     : 정규화 조항키 정확 매칭 (문단번호 집합 교집합)
  - clause_prefix    : 계층(prefix) 매칭 (gold "2.6.5" ↔ 청크 "2.6" 허용) — gold 라벨과 청크 문단번호의 입도 불일치를 보정
  - is_answerable    : 가드레일 지표

각 조항키 지표는 검색단계(reranked_chunks)와 생성단계(citations)에서 각각 측정하여
"검색이 못 찾은 것"과 "찾았는데 인용에서 누락된 것"을 분리한다.
함께 Hit@1 / Hit@k / MRR / Recall, CRAG 루프 횟수(rewrite_count), 재작성 전략,
needs_external 판정, 에러 로그를 기록한다.

전제: pgvector(Docker) + 라이브 LLM(gpt-5.4-mini). benchmark.jsonl은 K-GAAP 14건이고 적재 데이터도 GAAP뿐이므로,
gold references 중 "일반기업회계기준 …" 항목만 채점 대상으로 삼는다(K-IFRS 라벨은 미적재 → 채점 제외).

실행:
  uv run python scripts/benchmark_baseline.py                  # 적재된 장의 케이스만
  uv run python scripts/benchmark_baseline.py --all-cases      # 미적재 장 포함 강제
  uv run python scripts/benchmark_baseline.py --case TEST-K-GAAP-002
  uv run python scripts/benchmark_baseline.py --k 5            # Hit@k 의 k (기본 10)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

# ── 프로젝트 루트를 import 경로에 추가 (tests.*, src.* 재사용) ──
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv()
# tests/integration/conftest.py 와 동일하게, 호스트 실행 시 DB 호스트를 localhost로 보정한다.
if os.getenv("POSTGRES_HOST") == "database":
    os.environ["POSTGRES_HOST"] = "localhost"

from src.utils.config import KST  # noqa: E402
from tests.utils.benchmark_loader import load_benchmark, BenchmarkCase  # noqa: E402

# datetime은 KST 스탬프용으로만 사용 (워크플로 스크립트 제약과 무관한 일반 실행 환경)
from datetime import datetime  # noqa: E402


# ════════════════════════════════ 조항키 유틸 ════════════════════════════════
# 청크 본문의 문단 헤더:  "#### 21.8", "#### 2.6.5", "#### 6.13의2"
_CHUNK_PARA_RE = re.compile(r"####\s+(\d+\.\d+(?:\.\d+)?(?:의\d+)?)")
# gold 라벨에서 장 번호:   "일반기업회계기준 제21장 …"
_GOLD_CHAPTER_RE = re.compile(r"제\s*(\d+)\s*장")
# 문단 토큰:               "21.8", "2.6.5", "6.13의2"
_PARA_TOKEN_RE = re.compile(r"\d+\.\d+(?:\.\d+)?(?:의\d+)?")
# 범위 표기:               "15.15조~15.16조"
_RANGE_RE = re.compile(r"(\d+\.\d+(?:\.\d+)?)\s*조?\s*~\s*(\d+\.\d+(?:\.\d+)?)")


def _normalize_para(p: str) -> str:
    """가지번호 접미사(의N)를 제거해 기준 문단번호로 정규화한다. '21.5의2' → '21.5'."""
    return re.sub(r"의\d+$", "", p)


def _expand_range(a: str, b: str) -> set[str]:
    """'15.15'~'15.16' 처럼 같은 prefix의 연속 범위를 끝점 포함으로 펼친다."""
    pa, pb = a.split("."), b.split(".")
    if len(pa) == len(pb) == 2 and pa[0] == pb[0]:
        try:
            lo, hi = int(pa[1]), int(pb[1])
            if 0 <= hi - lo <= 50:
                return {f"{pa[0]}.{i}" for i in range(lo, hi + 1)}
        except ValueError:
            pass
    return {a, b}


@dataclass
class GoldClause:
    chapter: str
    paras: set[str]
    raw: str


def parse_gold_clauses(references: list[str]) -> list[GoldClause]:
    """벤치마크 references에서 K-GAAP 조항만 (chapter, 문단번호 집합)으로 파싱한다."""
    clauses: list[GoldClause] = []
    for ref in references:
        if "일반기업회계기준" not in ref:  # 적재 데이터가 GAAP뿐 → GAAP 라벨만 채점
            continue
        mch = _GOLD_CHAPTER_RE.search(ref)
        if not mch:
            continue
        chapter = mch.group(1)
        body = ref[mch.end():]
        paras: set[str] = set()
        for a, b in _RANGE_RE.findall(body):
            paras.update(_expand_range(a, b))
        for tok in _PARA_TOKEN_RE.findall(body):
            paras.add(tok)
        if paras:
            clauses.append(GoldClause(chapter=chapter, paras=paras, raw=ref))
    return clauses


def gold_para_set(clauses: list[GoldClause]) -> set[str]:
    """전체 gold 문단번호를 정규화 집합으로 모은다."""
    s: set[str] = set()
    for gc in clauses:
        s |= {_normalize_para(p) for p in gc.paras}
    return s


def extract_chunk_paras(content: str) -> set[str]:
    """청크/인용 본문에서 문단 헤더 번호를 정규화 집합으로 추출한다."""
    return {_normalize_para(p) for p in _CHUNK_PARA_RE.findall(content)}


def _paras_match(gold_paras: set[str], cand_paras: set[str], mode: str) -> set[str]:
    """후보 문단집합이 gold 문단집합과 매칭되는 부분을 반환한다.

    mode="exact"  : 동일 문단번호 교집합
    mode="prefix" : 점(.) 단위 계층 포함도 인정 (gold '2.6.5' ↔ cand '2.6')
    """
    if mode == "exact":
        return gold_paras & cand_paras
    hits: set[str] = set()
    for g in gold_paras:
        for c in cand_paras:
            if g == c or g.startswith(c + ".") or c.startswith(g + "."):
                hits.add(g)
                break
    return hits


def rank_hit(contents: list[str], gold_paras: set[str], mode: str) -> tuple[int | None, set[str]]:
    """순위대로 정렬된 후보 본문 리스트에서 첫 hit 순위(1-based)와 누적 커버 문단을 반환한다."""
    first_hit: int | None = None
    covered: set[str] = set()
    if not gold_paras:
        return None, covered
    for rank, content in enumerate(contents, start=1):
        inter = _paras_match(gold_paras, extract_chunk_paras(content), mode)
        if inter:
            covered |= inter
            if first_hit is None:
                first_hit = rank
    return first_hit, covered


def legacy_substring_hit(references: list[str], citations) -> bool:
    """현행 test_reference_coverage 재현: 라벨 문자열이 citation 본문에 부분일치하는가."""
    joined = " ".join(c.content for c in citations)
    return any(ref in joined for ref in references)


# ════════════════════════════════ 측정 ════════════════════════════════
@dataclass
class CaseResult:
    case_id: str
    chapter: str
    measurable: bool
    gold_paras: list[str]
    metrics: dict = field(default_factory=dict)
    diag: dict = field(default_factory=dict)
    error: str | None = None


def get_indexed_chapters() -> set[str]:
    """현재 pgvector chunks 테이블에 적재된 chapter 집합을 조회한다."""
    from src.db.connection import get_pool

    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT metadata->>'chapter' FROM chunks")
        return {r[0] for r in cur.fetchall() if r[0]}


def measure_case(case: BenchmarkCase, k: int) -> CaseResult:
    from tests.integration.helpers import run_workflow_to_completion

    clauses = parse_gold_clauses(case.references)
    gold_paras = gold_para_set(clauses)
    chapter = clauses[0].chapter if clauses else "?"
    res = CaseResult(
        case_id=case.id,
        chapter=chapter,
        measurable=True,
        gold_paras=sorted(gold_paras),
    )
    try:
        state = run_workflow_to_completion(case.query, standard_filter=case.standard)
    except Exception as e:  # 케이스 격리: 한 건 실패해도 전체 측정 계속
        res.error = f"{type(e).__name__}: {e}"
        res.diag["traceback"] = traceback.format_exc()[-1500:]
        return res

    fr = state.get("final_response")
    reranked = state.get("reranked_chunks") or []
    retrieved = state.get("retrieved_chunks") or []
    citations = list(fr.citations) if fr else []

    search_contents = [r.chunk.content for r in reranked]
    cite_contents = [c.content for c in citations]

    metrics: dict = {}
    for stage, contents in (("retrieval", search_contents), ("generation", cite_contents)):
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
    res.metrics = metrics

    # 진단 정보 (오답 분석용)
    rq = state.get("rewritten_query")
    ev = state.get("evaluation")
    res.diag = {
        "strategy": getattr(rq, "strategy", None),
        "rewrite_count": state.get("rewrite_count"),
        "n_retrieved": len(retrieved),
        "n_reranked": len(reranked),
        "n_citations": len(citations),
        "needs_external": getattr(ev, "needs_external", None),
        "eval_reasoning": (getattr(ev, "reasoning", "") or "")[:200],
        "retrieval_chapters": [r.chunk.metadata.chapter for r in reranked][:10],
        "citation_paras": sorted({p for c in citations for p in extract_chunk_paras(c.content)}),
        "answer_head": (fr.answer[:200] if fr else ""),
        "error_logs": state.get("error_logs") or [],
    }
    return res


def aggregate(results: list[CaseResult], k: int) -> dict:
    """측정 가능했던 케이스에 대해 지표별 적중 건수/비율을 집계한다."""
    rows = [r for r in results if r.measurable and r.error is None]
    n = len(rows)
    # 지표 우선순위: "조항 검색이 1순위, LLM 답변은 참고용" (2026-06-13 결정).
    # 회계사에게 실제 제공되는 인용(생성단계) 조항 Hit, 특히 Hit@1/MRR("가장 적절한 조항이 최상단")이 헤드라인.
    # 검색단계는 진단용(검색 실패 vs 인용 누락 분리), legacy/answerable은 대조군/가드레일.
    keys = [
        "generation_exact_hit@1",       # ★ NFR-002 1차 후보
        f"generation_exact_hit@{k}",
        "generation_prefix_hit@1",
        f"generation_prefix_hit@{k}",
        "retrieval_exact_hit@1",        # 진단: 검색이 최상단에 정답을 올렸나
        f"retrieval_exact_hit@{k}",
        f"retrieval_prefix_hit@{k}",
        "legacy_substring",             # 대조군(현행 결함)
        "is_answerable",                # 가드레일
    ]
    summary: dict = {"n_measured": n}
    for key in keys:
        hits = sum(1 for r in rows if r.metrics.get(key))
        summary[key] = {"hits": hits, "rate": round(hits / n, 4) if n else 0.0}
    for stage in ("generation", "retrieval"):
        summary[f"{stage}_exact_mrr_avg"] = (
            round(sum(r.metrics.get(f"{stage}_exact_mrr", 0.0) for r in rows) / n, 4) if n else 0.0
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NFR-002 벤치마크 베이스라인 측정 (#96)")
    parser.add_argument("--k", type=int, default=10, help="Hit@k 의 k (기본 10 = TOP_K_RETRIEVAL)")
    parser.add_argument("--case", help="특정 케이스 ID만 측정")
    parser.add_argument("--all-cases", action="store_true", help="미적재 장 케이스도 강제 측정")
    parser.add_argument("--out-dir", default="docs/measurements", help="결과 저장 디렉토리")
    args = parser.parse_args(argv)

    from src.db.connection import init_pool, close_pool
    from tests.utils.infra_check import check_docker_infrastructure

    infra_error = check_docker_infrastructure()
    if infra_error:
        print(f"[중단] 인프라 점검 실패: {infra_error}")
        return 2
    if not os.getenv("OPENAI_API_KEY"):
        print("[중단] OPENAI_API_KEY 미설정 — 라이브 측정 불가")
        return 2

    init_pool()
    try:
        indexed = get_indexed_chapters()
        cases = load_benchmark()
        if args.case:
            cases = [c for c in cases if c.id == args.case]
            if not cases:
                print(f"[중단] 케이스를 찾지 못함: {args.case}")
                return 2

        print(f"적재된 장: {sorted(indexed, key=lambda x: int(x))}")
        print(f"측정 대상 케이스: {len(cases)}건 (k={args.k})\n")

        results: list[CaseResult] = []
        for i, case in enumerate(cases, 1):
            clauses = parse_gold_clauses(case.references)
            chapter = clauses[0].chapter if clauses else "?"
            if chapter not in indexed and not args.all_cases:
                print(f"[{i}/{len(cases)}] {case.id} (제{chapter}장) — 미적재 → SKIP")
                results.append(
                    CaseResult(case_id=case.id, chapter=chapter, measurable=False,
                               gold_paras=sorted(gold_para_set(clauses)))
                )
                continue

            t0 = time.time()
            print(f"[{i}/{len(cases)}] {case.id} (제{chapter}장) 측정 중…", flush=True)
            res = measure_case(case, args.k)
            dt = time.time() - t0
            res.diag["elapsed_sec"] = round(dt, 1)
            if res.error:
                print(f"    ✗ 에러: {res.error} ({dt:.1f}s)")
            else:
                m = res.metrics
                print(
                    f"    legacy={m['legacy_substring']!s:5} | "
                    f"검색 exact@{args.k}={m[f'retrieval_exact_hit@{args.k}']!s:5} "
                    f"prefix@{args.k}={m[f'retrieval_prefix_hit@{args.k}']!s:5} | "
                    f"생성 exact@{args.k}={m[f'generation_exact_hit@{args.k}']!s:5} | "
                    f"answerable={m['is_answerable']!s:5} | "
                    f"CRAG={res.diag.get('rewrite_count')} ({dt:.1f}s)"
                )
            results.append(res)

        summary = aggregate(results, args.k)
        print("\n" + "=" * 64)
        print("집계 (측정 가능 케이스 기준)")
        print("=" * 64)
        print(f"측정 건수: {summary['n_measured']}")
        for key, v in summary.items():
            if isinstance(v, dict):
                print(f"  {key:32} {v['hits']:>2}/{summary['n_measured']}  ({v['rate']:.1%})")
        print(f"  {'retrieval_exact_mrr_avg':32} {summary['retrieval_exact_mrr_avg']}")

        # 결과 저장
        stamp = datetime.now(KST).strftime("%Y%m%d_%H%M")
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"baseline_{stamp}.json"
        payload = {
            "generated_at": datetime.now(KST).isoformat(),
            "k": args.k,
            "indexed_chapters": sorted(indexed, key=lambda x: int(x)),
            "summary": summary,
            "cases": [
                {
                    "case_id": r.case_id,
                    "chapter": r.chapter,
                    "measurable": r.measurable,
                    "gold_paras": r.gold_paras,
                    "metrics": r.metrics,
                    "diag": r.diag,
                    "error": r.error,
                }
                for r in results
            ],
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n결과 저장: {out_path}")
        return 0
    finally:
        close_pool()


if __name__ == "__main__":
    raise SystemExit(main())
