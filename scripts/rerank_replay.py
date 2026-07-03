"""search-only 덤프 + 오프라인 리랭크 리플레이 하니스.

벤치마크 14질의의 dense/sparse 사이드별 top-10을 1회 덤프한 뒤(dump),
RRF-k {30,60,90,120} × 후보 리랭커 매트릭스를 재검색·LLM 없이 오프라인으로
재정렬·채점한다(replay). 전체 워크플로 A/B와 달리 CRAG/LLM 변동이 섞이지
않아 결정적이며, 모델 간 상대 비교에 쓴다. 채점은 benchmark_metrics를 재사용한다.

사용 (호스트 실행, DB 기동·chunks 적재 전제):
  uv run python scripts/rerank_replay.py dump
  uv run python scripts/rerank_replay.py replay --dump-file docs/measurements/rerank_replay_dump_<stamp>.json

채택/롤백 기준(2026-07-04 사전 확정):
  retrieval Hit@1 순증 ≥ +2건 AND 기존 hit 회귀 0건 AND MRR 순증 > 0 AND 쿼리당 지연 p50 ≤ 1s.
  #183 gold 확정 대기 케이스는 델타만 기록하고 판정 모집단에서 제외한다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.models.schemas import RetrievedChunk  # noqa: E402
from src.retrieval.searcher import reciprocal_rank_fusion  # noqa: E402
from src.utils.config import KST, RRF_K  # noqa: E402

# gold 확정 대기 — 델타는 기록하되 채택 판정 모집단에서 제외
EXCLUDED_CASE_IDS = frozenset({"TEST-K-GAAP-003", "TEST-K-GAAP-005", "TEST-K-GAAP-012"})
ADOPT_MIN_GAINS = 2      # retrieval Hit@1 순증 최소 건수
ADOPT_MAX_P50_S = 1.0    # 쿼리당 rerank 지연 p50 상한(초)
SWEEP_KS = (30, 60, 90, 120)  # RRF-k 스윕 통합
TOP_N = 10


def fuse_top_n(
    dense: list[RetrievedChunk], sparse: list[RetrievedChunk], k: int, n: int = TOP_N
) -> list[RetrievedChunk]:
    """덤프된 사이드별 리스트를 라이브와 동일한 RRF(순수 함수)로 병합해 top-n을 자른다."""
    return reciprocal_rank_fusion([dense, sparse], k=k)[:n]


def _mrr(first_hits: dict[str, int | None], population: list[str]) -> float:
    """모집단의 MRR — 정답 최초 등장 순위의 역수 평균(미검출 0)."""
    if not population:
        return 0.0
    return sum((1.0 / first_hits[cid]) if first_hits[cid] else 0.0 for cid in population) / len(population)


def judge_adoption(
    base_first_hits: dict[str, int | None],
    cand_first_hits: dict[str, int | None],
    p50_latency_s: float,
    excluded_ids: frozenset[str] = EXCLUDED_CASE_IDS,
) -> dict:
    """사전 확정 기준으로 채택/롤백을 판정한다.

    first_hits: case_id → 정답 조항 최초 등장 순위(1부터, 미검출 None).
    반환 reasons가 비어 있으면 채택(adopt=True), 아니면 롤백 사유 목록이다.
    """
    population = sorted((set(base_first_hits) & set(cand_first_hits)) - set(excluded_ids))
    gains = [cid for cid in population if base_first_hits[cid] != 1 and cand_first_hits[cid] == 1]
    regressions = [cid for cid in population if base_first_hits[cid] == 1 and cand_first_hits[cid] != 1]
    mrr_delta = _mrr(cand_first_hits, population) - _mrr(base_first_hits, population)

    reasons = []
    if len(gains) < ADOPT_MIN_GAINS:
        reasons.append(f"Hit@1 순증 {len(gains)}건 < 기준 {ADOPT_MIN_GAINS}건")
    if regressions:
        reasons.append(f"기존 hit@1 회귀 {len(regressions)}건: {', '.join(regressions)}")
    if mrr_delta <= 0:
        reasons.append(f"MRR 순증 없음 (Δ={mrr_delta:+.4f})")
    if p50_latency_s > ADOPT_MAX_P50_S:
        reasons.append(f"쿼리당 지연 p50 {p50_latency_s:.2f}s > 기준 {ADOPT_MAX_P50_S}s")

    return {
        "adopt": not reasons,
        "gains": gains,
        "regressions": regressions,
        "mrr_delta": mrr_delta,
        "population": population,
        "reasons": reasons,
    }


# ════════════════════════════════ replay 모드 ════════════════════════════════

# 후보 리랭커. max_length는 (질의+청크) 쌍 기준 — 청크 상한 2048토큰(CHUNK_MAX_TOKENS)을 여유 있게 덮는다.
# ms-marco는 현행 대조군(512 절단, 한국어는 BERT 토크나이저 토큰 폭증으로 절단 심화).
REPLAY_MODELS = {
    "bge-reranker-v2-m3": {"name": "BAAI/bge-reranker-v2-m3", "max_length": 4096, "trust_remote_code": False},
    "gte-multilingual-reranker-base": {"name": "Alibaba-NLP/gte-multilingual-reranker-base", "max_length": 4096, "trust_remote_code": True},
    "ms-marco-MiniLM-L-6-v2": {"name": "cross-encoder/ms-marco-MiniLM-L-6-v2", "max_length": 512, "trust_remote_code": False},
}


def _sigmoid(x: float) -> float:
    """reranker.compute_relevance_scores와 동일한 로지스틱 정규화."""
    import math

    return 1.0 / (1.0 + math.exp(-x))


def _hist(scores: list[float], bins: int = 10) -> list[int]:
    """0~1 점수를 bins개 구간으로 집계(임계값 캘리브레이션 근거용)."""
    counts = [0] * bins
    for s in scores:
        counts[min(int(s * bins), bins - 1)] += 1
    return counts


def run_replay(dump_file: str, ks: tuple[int, ...], out_dir: str) -> int:
    """덤프를 후보 모델 × RRF-k 매트릭스로 오프라인 재정렬·채점한다 (재검색·LLM 없음)."""
    import statistics
    import time

    from tests.utils.benchmark_loader import load_benchmark
    from tests.utils.benchmark_metrics import (
        extract_chunk_paras,
        gold_para_set,
        parse_gold_clauses,
        rank_hit,
        resolve_core_paras,
        retrieval_pass,
    )

    dump = json.loads(Path(dump_file).read_text(encoding="utf-8"))
    if dump["selfcheck_mismatches"]:
        print(f"덤프 self-check 실패 이력 {dump['selfcheck_mismatches']} — 재덤프 필요", file=sys.stderr)
        return 1
    cases_by_id = {c.id: c for c in load_benchmark()}

    # 케이스별 gold·사이드 리스트 복원
    replay_cases = []
    for dc in dump["cases"]:
        case = cases_by_id[dc["case_id"]]
        clauses = parse_gold_clauses(case.references)
        gold = gold_para_set(clauses)
        replay_cases.append({
            "id": dc["case_id"],
            "query": dc["query"],
            "gold": gold,
            "core": resolve_core_paras(case, gold),
            "dense": [RetrievedChunk(**d) for d in dc["dense"]],
            "sparse": [RetrievedChunk(**d) for d in dc["sparse"]],
        })

    top_n = dump["top_n"]
    result: dict = {
        "generated_at": datetime.now(KST).isoformat(),
        "dump_file": dump_file,
        "corpus": dump["corpus"],
        "ks": list(ks),
        "baseline": {},   # k → {case_id: first_hit}
        "models": {},     # model_key → {"by_k": {k: {case_id: first_hit}}, "latency": ..., ...}
    }

    # ── 베이스라인(리랭크 없음): k별 RRF 순서 그대로 채점 ──
    for k in ks:
        by_case = {}
        pass_cnt = 0
        for rc in replay_cases:
            contents = [c.content for c in fuse_top_n(rc["dense"], rc["sparse"], k=k, n=top_n)]
            fh, _ = rank_hit(contents, rc["gold"], "exact")
            by_case[rc["id"]] = fh
            pass_cnt += retrieval_pass(contents, rc["core"])
        result["baseline"][k] = by_case
        n = len(replay_cases)
        hit1 = sum(1 for v in by_case.values() if v == 1)
        mrr = _mrr(by_case, sorted(by_case))
        print(f"baseline k={k:>3}: Hit@1 {hit1}/{n} · MRR {mrr:.3f} · retrieval_pass {pass_cnt}/{n}")

    # ── 모델별 리플레이 ──
    for key, spec in REPLAY_MODELS.items():
        print(f"\n[{key}] 로드 중... ({spec['name']})")
        t0 = time.perf_counter()
        try:
            from sentence_transformers import CrossEncoder

            model = CrossEncoder(spec["name"], max_length=spec["max_length"],
                                 trust_remote_code=spec["trust_remote_code"])
            # 워밍업 1회(콜드스타트에 포함) — 이후 지연 측정은 웜 상태 기준
            model.predict([(replay_cases[0]["query"], replay_cases[0]["dense"][0].content)])
        except Exception as e:  # 가용성 확인: 로드 실패 모델은 기록하고 건너뛴다
            print(f"  로드 실패 — 건너뜀: {type(e).__name__}: {e}", file=sys.stderr)
            result["models"][key] = {"load_error": f"{type(e).__name__}: {e}"}
            continue
        cold_start_s = time.perf_counter() - t0

        # 케이스별 후보(사이드 합집합) 점수는 k와 무관 — 1회만 추론하고 k별로 재정렬만 한다.
        scores_by_case: dict[str, dict[str, float]] = {}
        latencies = []
        gold_scores, nongold_scores = [], []
        n_pairs = n_truncated = 0
        for rc in replay_cases:
            union, seen = [], set()
            for c in rc["dense"] + rc["sparse"]:
                if c.chunk_id not in seen:
                    seen.add(c.chunk_id)
                    union.append(c)
            pairs = [(rc["query"], c.content) for c in union]

            t0 = time.perf_counter()
            raw = model.predict(pairs)
            latencies.append(time.perf_counter() - t0)

            scores = {c.chunk_id: _sigmoid(float(s)) for c, s in zip(union, raw)}
            scores_by_case[rc["id"]] = scores
            for c in union:
                s = scores[c.chunk_id]
                (gold_scores if extract_chunk_paras(c.content) & rc["gold"] else nongold_scores).append(s)
                n_pairs += 1
                tokens = model.tokenizer(rc["query"], c.content, truncation=False)["input_ids"]
                n_truncated += len(tokens) > spec["max_length"]

        by_k = {}
        for k in ks:
            by_case = {}
            pass_cnt = 0
            for rc in replay_cases:
                fused = fuse_top_n(rc["dense"], rc["sparse"], k=k, n=top_n)
                ordered = sorted(fused, key=lambda c: scores_by_case[rc["id"]][c.chunk_id], reverse=True)
                contents = [c.content for c in ordered]
                fh, _ = rank_hit(contents, rc["gold"], "exact")
                by_case[rc["id"]] = fh
                pass_cnt += retrieval_pass(contents, rc["core"])
            by_k[k] = {"first_hits": by_case, "retrieval_pass": pass_cnt}

        p50 = statistics.median(latencies)
        result["models"][key] = {
            "hf_name": spec["name"],
            "max_length": spec["max_length"],
            "device": str(getattr(model, "device", "?")),
            "cold_start_s": round(cold_start_s, 2),
            "latency_p50_s": round(p50, 4),
            "latency_max_s": round(max(latencies), 4),
            "truncation": {"n_pairs": n_pairs, "n_truncated": n_truncated,
                           "rate": round(n_truncated / n_pairs, 4) if n_pairs else 0.0},
            "score_hist": {"gold": _hist(gold_scores), "nongold": _hist(nongold_scores)},
            "by_k": by_k,
        }
        for k in ks:
            fhs = by_k[k]["first_hits"]
            hit1 = sum(1 for v in fhs.values() if v == 1)
            verdict = judge_adoption(result["baseline"][k], fhs, p50)
            mark = "채택기준 충족" if verdict["adopt"] else f"미충족({len(verdict['reasons'])})"
            print(f"  k={k:>3}: Hit@1 {hit1}/{len(fhs)} · MRR {_mrr(fhs, sorted(fhs)):.3f} "
                  f"· pass {by_k[k]['retrieval_pass']} · {mark}")
        print(f"  cold {cold_start_s:.1f}s · p50 {p50*1000:.0f}ms · 절단률 {result['models'][key]['truncation']['rate']:.1%}")

    ts = datetime.now(KST)
    out_path = Path(out_dir) / f"rerank_replay_result_{ts.strftime('%Y%m%d_%H%M')}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out_path}")
    return 0


# ════════════════════════════════ dump 모드 ════════════════════════════════


def _case_filter(standard: str) -> dict | None:
    """workflow.py의 standard_filter → metadata_filter 변환을 그대로 미러링한다."""
    return None if standard == "ALL" else {"standard_type": standard}


def run_dump(out_dir: str, top_n: int) -> int:
    """벤치마크 전 질의의 dense/sparse 사이드별 top-N을 1회 덤프한다.

    질의별 self-check(오프라인 병합 == 라이브 search_chunks 순서)로 리플레이 경로의
    정합을 산출물 안에서 증명한다. 하나라도 어긋나면 덤프는 남기되 비정상 종료한다.
    """
    # 호스트 실행 시 DB 호스트 보정 (benchmark_baseline.py와 동일)
    if os.getenv("POSTGRES_HOST") == "database":
        os.environ["POSTGRES_HOST"] = "localhost"

    from src.db.connection import init_pool, close_pool
    from src.retrieval.searcher import dense_search, sparse_search, search_chunks, embed_query
    from tests.utils.benchmark_loader import load_benchmark
    from tests.utils.benchmark_metrics import get_chunk_count, get_indexed_chapters

    cases = load_benchmark()
    init_pool()
    try:
        n_chunks = get_chunk_count()
        chapters = sorted(get_indexed_chapters(), key=int)
        print(f"코퍼스: {n_chunks}청크 · {len(chapters)}장 · RRF_K={RRF_K} · top_n={top_n}")

        dumped_cases = []
        mismatches = []
        for case in cases:
            metadata_filter = _case_filter(case.standard)
            vec = embed_query(case.query)
            dense = dense_search(vec, top_n, metadata_filter)
            sparse = sparse_search(case.query, top_n, metadata_filter)

            fused_ids = [c.chunk_id for c in fuse_top_n(dense, sparse, k=RRF_K, n=top_n)]
            live_ids = [c.chunk_id for c in search_chunks(case.query, top_n, metadata_filter)]
            ok = fused_ids == live_ids
            if not ok:
                mismatches.append(case.id)

            dumped_cases.append({
                "case_id": case.id,
                "standard": case.standard,
                "query": case.query,
                "dense": [c.model_dump() for c in dense],
                "sparse": [c.model_dump() for c in sparse],
                "selfcheck_pass": ok,
            })
            print(f"  {case.id}: dense {len(dense)} · sparse {len(sparse)} · self-check {'✓' if ok else '✗'}")
    finally:
        close_pool()

    ts = datetime.now(KST)
    out_path = Path(out_dir) / f"rerank_replay_dump_{ts.strftime('%Y%m%d_%H%M')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": ts.isoformat(),
        "corpus": {"n_chunks": n_chunks, "chapters": chapters},
        "rrf_k_default": RRF_K,
        "top_n": top_n,
        "selfcheck_mismatches": mismatches,
        "cases": dumped_cases,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"덤프 저장: {out_path}")

    if mismatches:
        print(f"self-check 실패 {len(mismatches)}건: {mismatches} — 리플레이 진행 금지", file=sys.stderr)
        return 1
    print("self-check 전 케이스 통과 — 오프라인 병합 경로가 라이브와 동일")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="search-only 덤프 + 오프라인 리랭크 리플레이")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dump = sub.add_parser("dump", help="벤치마크 질의의 dense/sparse 사이드별 top-N 덤프 (DB 필요)")
    p_dump.add_argument("--out-dir", default="docs/measurements", help="산출물 저장 디렉토리")
    p_dump.add_argument("--top-n", type=int, default=TOP_N, help="사이드별 검색 상위 N (기본 10)")

    p_replay = sub.add_parser("replay", help="덤프를 모델 × RRF-k 매트릭스로 오프라인 재정렬·채점 (DB 불필요)")
    p_replay.add_argument("--dump-file", required=True, help="dump 산출물 JSON 경로")
    p_replay.add_argument("--ks", default=",".join(map(str, SWEEP_KS)), help="RRF k 목록 (쉼표 구분)")
    p_replay.add_argument("--out-dir", default="docs/measurements", help="산출물 저장 디렉토리")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "dump":
        return run_dump(args.out_dir, args.top_n)
    if args.cmd == "replay":
        ks = tuple(int(x) for x in args.ks.split(","))
        return run_replay(args.dump_file, ks, args.out_dir)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
