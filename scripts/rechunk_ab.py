#!/usr/bin/env python
"""조항 재청킹 A/B 1단 측정 — 검색 전용(LLM·워크플로 미통과)

운영 chunks(노드 단위) vs chunks_fine(조항 경계 분할)를 동일 케이스로 `search_chunks`
직접 호출해 검색 조항 Hit@1 / Hit@k / MRR(exact)을 나란히 대조한다.

공정성: 양쪽 컬렉션을 case 정답 장(metadata_filter의 chapter)으로 제한해 코퍼스 범위를
동일하게 맞추고 재청킹만 변수로 둔다. "장 검색"(정답 장을 맞히는가)은 이 A/B 범위 밖이다.
rerank·rewrite·CRAG 미통과 → 결정적·수초. 시스템 최종 정확도 전파는 2단(풀 워크플로) 별도.

채점 로직은 tests/utils/benchmark_metrics(parse_gold_clauses·gold_para_set·rank_hit)를
재사용해 baseline 측정과 동일 기준을 공유한다.

전제: 측정 전 --after 컬렉션에 6·21장이 clause-level로 적재돼 있어야 한다(호스트 MPS):
  uv run python -m src.main ingest --collection chunks_fine --reset \
    --clause-level --max-tokens 1024 --ontology-dir <6·21장 JSON 디렉토리>

실행:
  uv run python scripts/rechunk_ab.py                       # chunks vs chunks_fine, 6·21장
  uv run python scripts/rechunk_ab.py --chapters 6 21 --k 10
  uv run python scripts/rechunk_ab.py --before chunks --after chunks   # 스모크(Δ=0)
"""
from __future__ import annotations

import argparse
import os
import sys
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

from src.utils.config import KST  # noqa: E402
from tests.utils.benchmark_loader import load_benchmark  # noqa: E402
from tests.utils.benchmark_metrics import (  # noqa: E402
    gold_para_set,
    parse_gold_clauses,
    rank_hit,
)


def _measure(contents: list[str], gold_paras: set[str], k: int) -> dict:
    """순위 정렬된 검색 본문 리스트에서 조항 Hit@1 / Hit@k / MRR(exact)을 산출한다."""
    fh, _ = rank_hit(contents, gold_paras, "exact")
    return {
        "first_hit": fh,
        "hit@1": fh == 1,
        f"hit@{k}": fh is not None and fh <= k,
        "mrr": round(1.0 / fh, 4) if fh else 0.0,
    }


def _write_report(rows: list[dict], args, generated_at: datetime) -> Path:
    """케이스별 전/후 대조표 + 집계 마크다운 리포트를 생성하고 경로를 반환한다."""
    k, n = args.k, len(rows)

    def mk(b: bool) -> str:
        return "✅" if b else "❌"

    def rate(side: str, key: str) -> float:
        return sum(1 for r in rows if r[side][key]) / n if n else 0.0

    lines: list[str] = [
        "# 조항 재청킹 A/B 1단 (검색 전용)",
        "",
        f"- 생성 시각: {generated_at.isoformat()}",
        f"- 전(노드 단위): `{args.before}` / 후(조항 단위): `{args.after}`",
        f"- k={k}, 대상 {n}건",
        "- 공정성: 양쪽 모두 case 정답 장(chapter)으로 필터 → 코퍼스 동일, 재청킹만 변수.",
        "- 검색 전용(rerank·rewrite·CRAG 미통과). 시스템 최종 전파는 2단(풀 워크플로) 별도.",
        "",
        f"| 케이스 | 장 | gold | 전 hit@1 | 후 hit@1 | 전 hit@{k} | 후 hit@{k} | 전 MRR | 후 MRR |",
        "|--------|----|------|----------|----------|-----------|-----------|--------|--------|",
    ]
    for r in rows:
        b, a = r["before"], r["after"]
        lines.append(
            f"| {r['case_id']} | {r['chapter']} | {', '.join(r['gold'])} | "
            f"{mk(b['hit@1'])} | {mk(a['hit@1'])} | {mk(b[f'hit@{k}'])} | {mk(a[f'hit@{k}'])} | "
            f"{b['mrr']:.3f} | {a['mrr']:.3f} |"
        )
    lines += [
        "",
        "## 집계 (전 → 후)",
        "",
        f"- hit@1: {rate('before', 'hit@1'):.1%} → {rate('after', 'hit@1'):.1%}",
        f"- hit@{k}: {rate('before', f'hit@{k}'):.1%} → {rate('after', f'hit@{k}'):.1%}",
        f"- MRR(exact): {sum(r['before']['mrr'] for r in rows) / n if n else 0:.3f} → "
        f"{sum(r['after']['mrr'] for r in rows) / n if n else 0:.3f}",
        "",
        "> 해석 가이드: 003↔012는 동일 21.8 다발 노드(통제) — 012만 개선되면 분할 인과 증거. "
        "010(6.31 단독)은 음성 대조군(불변 기대). 005는 어휘격차로 분할만으론 부족할 수 있음.",
    ]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"rechunk_ab_{generated_at.strftime('%Y%m%d_%H%M')}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="#162 조항 재청킹 A/B 1단(검색 전용) 측정")
    parser.add_argument("--chapters", nargs="+", default=["6", "21"], help="측정 대상 장 (기본: 6 21)")
    parser.add_argument("--k", type=int, default=10, help="Hit@k 의 k (기본 10)")
    parser.add_argument("--before", default="chunks", help="기준(노드 단위) 컬렉션 (기본: chunks)")
    parser.add_argument(
        "--after", default="chunks_fine", help="재청킹(조항 단위) 컬렉션 (기본: chunks_fine)"
    )
    parser.add_argument("--out-dir", default="docs/measurements", help="리포트 저장 디렉토리")
    parser.add_argument("--no-report", action="store_true", help="마크다운 리포트 생략")
    args = parser.parse_args(argv)

    from src.db.connection import close_pool, init_pool
    from src.retrieval.searcher import search_chunks
    from tests.utils.infra_check import check_docker_infrastructure

    infra_error = check_docker_infrastructure()
    if infra_error:
        print(f"[중단] 인프라 점검 실패: {infra_error}")
        return 2

    chapters = set(args.chapters)
    init_pool()
    try:
        # gold 정답 장이 대상 장에 속하는 케이스만 측정 대상으로 삼는다.
        cases = []
        for c in load_benchmark():
            clauses = parse_gold_clauses(c.references)
            if clauses and clauses[0].chapter in chapters:
                cases.append((c, clauses))
        if not cases:
            print(f"[중단] 대상 장 {sorted(chapters)} 케이스 없음")
            return 2

        print(
            f"A/B: '{args.before}'(전) vs '{args.after}'(후) | "
            f"대상 장 {sorted(chapters)} | {len(cases)}건 | k={args.k}"
        )
        print("공정성: 양쪽 모두 case 정답 장으로 필터(코퍼스 동일, 재청킹만 변수). 장 검색은 범위 밖.\n")

        rows: list[dict] = []
        for case, clauses in cases:
            gold_paras = gold_para_set(clauses)
            chapter = clauses[0].chapter
            mf = {"chapter": chapter}  # 양쪽 동일 필터 → 코퍼스 범위 일치
            before = search_chunks(case.query, top_k=args.k, metadata_filter=mf, collection=args.before)
            after = search_chunks(case.query, top_k=args.k, metadata_filter=mf, collection=args.after)
            mb = _measure([c.content for c in before], gold_paras, args.k)
            ma = _measure([c.content for c in after], gold_paras, args.k)
            rows.append(
                {"case_id": case.id, "chapter": chapter, "gold": sorted(gold_paras), "before": mb, "after": ma}
            )

            def _fmt(m: dict) -> str:
                return (
                    f"hit@1={m['hit@1']!s:5} hit@{args.k}={m[f'hit@{args.k}']!s:5} "
                    f"mrr={m['mrr']:.3f} (rank={m['first_hit']})"
                )

            print(f"  {case.id} (제{chapter}장, gold={sorted(gold_paras)})")
            print(f"      전 : {_fmt(mb)}")
            print(f"      후 : {_fmt(ma)}")

        n = len(rows)

        def rate(side: str, key: str) -> float:
            return sum(1 for r in rows if r[side][key]) / n

        print("\n" + "=" * 60)
        print(f"집계 ({n}건)  —  전 → 후")
        for key in ["hit@1", f"hit@{args.k}"]:
            print(f"  {key:8}: {rate('before', key):.1%} → {rate('after', key):.1%}")
        print(
            f"  {'mrr':8}: {sum(r['before']['mrr'] for r in rows) / n:.3f} → "
            f"{sum(r['after']['mrr'] for r in rows) / n:.3f}"
        )

        if not args.no_report:
            path = _write_report(rows, args, datetime.now(KST))
            print(f"\n리포트 저장: {path}")
        return 0
    finally:
        close_pool()


if __name__ == "__main__":
    raise SystemExit(main())
