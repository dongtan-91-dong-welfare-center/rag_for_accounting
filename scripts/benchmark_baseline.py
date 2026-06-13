"""
NFR-002 벤치마크 정확도 베이스라인 측정 하니스 (CLI)

측정 로직은 `tests/utils/benchmark_metrics.py`로 공용화되어, 이 스크립트와 Phase 2 관리 테스트
(`tests/integration/test_benchmark_accuracy.py`)가 동일한 채점·집계를 공유한다.
이 파일은 인프라 점검·케이스 순회·콘솔 출력·raw JSON 저장만 담당하는 얇은 CLI다.

산출 지표·채점 방식은 benchmark_metrics 모듈 docstring 참조.

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
import sys
import time
from pathlib import Path

# ── 프로젝트 루트를 import 경로에 추가 (tests.*, src.* 재사용) ──
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv()
# tests/integration/conftest.py 와 동일하게, 호스트 실행 시 DB 호스트를 localhost로 보정한다.
if os.getenv("POSTGRES_HOST") == "database":
    os.environ["POSTGRES_HOST"] = "localhost"

from datetime import datetime  # noqa: E402

from src.utils.config import KST, USE_RERANKER  # noqa: E402
from tests.utils.benchmark_loader import load_benchmark  # noqa: E402
from tests.utils.benchmark_metrics import (  # noqa: E402
    CaseResult,
    aggregate,
    get_chunk_count,
    get_indexed_chapters,
    gold_para_set,
    measure_case,
    parse_gold_clauses,
    write_markdown_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NFR-002 벤치마크 베이스라인 측정")
    parser.add_argument("--k", type=int, default=10, help="Hit@k 의 k (기본 10 = TOP_K_RETRIEVAL)")
    parser.add_argument("--case", help="특정 케이스 ID만 측정")
    parser.add_argument("--all-cases", action="store_true", help="미적재 장 케이스도 강제 측정")
    parser.add_argument("--out-dir", default="docs/measurements", help="결과 저장 디렉토리")
    parser.add_argument("--no-report", action="store_true", help="마크다운 리포트 생성 생략")
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

        # 결과 저장 (raw JSON)
        ts = datetime.now(KST)
        stamp = ts.strftime("%Y%m%d_%H%M")
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"baseline_{stamp}.json"
        payload = {
            "generated_at": ts.isoformat(),
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

        # 사람이 읽는 마크다운 리포트
        if not args.no_report:
            report_path = write_markdown_report(
                results,
                summary,
                k=args.k,
                indexed_chapters=sorted(indexed, key=lambda x: int(x)),
                n_chunks=get_chunk_count(),
                use_reranker=USE_RERANKER,
                out_dir=out_dir,
                generated_at=ts,
            )
            print(f"리포트 저장: {report_path}")
        return 0
    finally:
        close_pool()


if __name__ == "__main__":
    raise SystemExit(main())
