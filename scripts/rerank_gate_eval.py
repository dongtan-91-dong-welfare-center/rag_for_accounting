"""#428 리랭커 점수 기반 품질 게이트 오프라인 실측 하니스.

벤치마크 질의마다 두 케이스를 만든다(dump).
  - 양성: 전체 코퍼스 하이브리드 검색 top-10 (정답 근거 존재)
  - 음성: 넓게(top-50) 검색한 뒤 정답 장(chapter) 청크를 제거한 top-10 (같은 도메인의 hard negative)
이어서 후보 Cross-Encoder별로 질의-청크 점수를 산출하고(score), 질의별 최고 점수로
AUC·임계값별 차단율/오차단율·확신 구간·CPU 지연을 집계한다. LLM 호출이 없으므로 비용이 없다.

사용 (호스트 실행, DB 기동·chunks 적재 전제, `uv sync --extra reranker`):
  uv run python scripts/rerank_gate_eval.py dump
  uv run python scripts/rerank_gate_eval.py score --dump-file docs/measurements/issue428/gate_dump_<stamp>.json

H1 판정 기준(#428): 음성 차단율 ≥ 70% AND 양성 오차단율 ≤ 10%.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.utils.config import KST  # noqa: E402

BENCHMARK_PATH = _ROOT / "data" / "test_data" / "benchmark.jsonl"
OUT_DIR = _ROOT / "docs" / "measurements" / "issue428"
# gold 확정 대기(#183) — rerank_replay.py와 같은 기준으로 모집단에서 제외한다.
EXCLUDED_CASE_IDS = frozenset({"TEST-K-GAAP-003", "TEST-K-GAAP-005", "TEST-K-GAAP-012"})
CANDIDATE_MODELS = (
    "BAAI/bge-reranker-v2-m3",
    "dragonkue/bge-reranker-v2-m3-ko",
    "nlpai-lab/KURE-Reranker-base",
)
TOP_N = 10
NEG_POOL_K = 50  # 정답 장 제거 후에도 top-10을 채우기 위한 넓은 검색 풀
H1_MIN_BLOCK_RATE = 0.70
H1_MAX_FALSE_BLOCK_RATE = 0.10

_CHAPTER_RE = re.compile(r"제\s*(\d+)\s*장")


def extract_gold_chapters(references: list[str]) -> set[str]:
    """references 조항 문자열("일반기업회계기준 제2장 2.65조")에서 정답 장 번호 집합을 뽑는다."""
    chapters: set[str] = set()
    for ref in references:
        chapters.update(_CHAPTER_RE.findall(ref))
    return chapters


def exclude_chapters(chunks: list[dict], gold_chapters: set[str], n: int = TOP_N) -> list[dict]:
    """정답 장 청크를 제거한 상위 n개를 돌려준다. chapter 메타데이터가 없는 청크는 판정 불가로 함께 제거한다."""
    kept = [c for c in chunks if c.get("chapter") and str(c["chapter"]) not in gold_chapters]
    return kept[:n]


def sigmoid(x: float) -> float:
    """reranker.py와 같은 정규화. 이미 [0,1] 확률을 내는 모델은 호출하지 않는다."""
    return 1.0 / (1.0 + math.exp(-x))


def auc(pos_scores: list[float], neg_scores: list[float]) -> float:
    """양성 점수가 음성 점수보다 클 확률(Mann-Whitney U, 동점 0.5)로 ROC AUC를 계산한다."""
    if not pos_scores or not neg_scores:
        return float("nan")
    wins = 0.0
    for p in pos_scores:
        for q in neg_scores:
            wins += 1.0 if p > q else 0.5 if p == q else 0.0
    return wins / (len(pos_scores) * len(neg_scores))


def rates_at(threshold: float, pos_scores: list[float], neg_scores: list[float]) -> tuple[float, float]:
    """최고 점수 < threshold면 차단한다. (음성 차단율, 양성 오차단율)을 돌려준다."""
    block = sum(s < threshold for s in neg_scores) / len(neg_scores)
    false_block = sum(s < threshold for s in pos_scores) / len(pos_scores)
    return block, false_block


def select_threshold(
    pos_scores: list[float], neg_scores: list[float], max_false_block: float = H1_MAX_FALSE_BLOCK_RATE
) -> dict:
    """오차단율 상한 안에서 음성 차단율이 최대인 임계값을 고른다(후보는 관측 점수 전부)."""
    best = {"threshold": 0.0, "block_rate": 0.0, "false_block_rate": 0.0}
    for t in sorted(set(pos_scores) | set(neg_scores)):
        block, false_block = rates_at(t, pos_scores, neg_scores)
        if false_block <= max_false_block and block > best["block_rate"]:
            best = {"threshold": t, "block_rate": block, "false_block_rate": false_block}
    return best


def select_bands(pos_scores: list[float], neg_scores: list[float]) -> dict:
    """3구간 경계를 정한다.

    low: 양성 오차단이 0건인 최대 임계값(이 미만은 즉시 차단해도 양성을 잃지 않는다).
    high: 음성 통과가 0건인 최소 임계값(이 이상은 즉시 통과해도 음성을 놓치지 않는다).
    그 사이는 LLM 평가에 위임한다.
    """
    low = min(pos_scores)
    high = max(neg_scores) + 1e-9
    if high < low:  # 완전 분리 — 위임 구간이 없다
        low = high = (low + high) / 2
    total = len(pos_scores) + len(neg_scores)
    all_scores = pos_scores + neg_scores
    return {
        "low": low,
        "high": high,
        "block_share": sum(s < low for s in all_scores) / total,
        "delegate_share": sum(low <= s < high for s in all_scores) / total,
        "pass_share": sum(s >= high for s in all_scores) / total,
    }


def h1_verdict(block_rate: float, false_block_rate: float) -> bool:
    return block_rate >= H1_MIN_BLOCK_RATE and false_block_rate <= H1_MAX_FALSE_BLOCK_RATE


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return ordered[idx]


def _chunk_record(chunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "chapter": chunk.metadata.chapter,
        "content": chunk.content,
    }


def run_dump(dense_only: bool = False) -> Path:
    from src.db.connection import close_pool, init_pool
    from src.retrieval.searcher import search_chunks

    init_pool()
    try:
        return _dump_cases(search_chunks, dense_only)
    finally:
        close_pool()


def _dump_cases(search_chunks, dense_only: bool) -> Path:
    cases = [json.loads(line) for line in BENCHMARK_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = []
    for case in cases:
        if case["id"] in EXCLUDED_CASE_IDS:
            continue
        gold = extract_gold_chapters(case.get("references", []))
        if not gold:
            print(f"[skip] {case['id']}: 정답 장 추출 불가")
            continue
        pool = [_chunk_record(c) for c in search_chunks(case["query"], top_k=NEG_POOL_K, include_sparse=not dense_only)]
        positive = pool[:TOP_N]
        negative = exclude_chapters(pool, gold)
        records.append({
            "id": case["id"],
            "query": case["query"],
            "gold_chapters": sorted(gold),
            "positive_gold_in_top": any(str(c["chapter"]) in gold for c in positive),
            "positive": positive,
            "negative": negative,
        })
        print(f"[dump] {case['id']}: gold={sorted(gold)} neg={len(negative)}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"gate_dump{'_dense' if dense_only else ''}_{datetime.now(KST):%Y%m%d_%H%M}.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"덤프 저장: {out}")
    return out


def _score_case(model, query: str, chunks: list[dict], apply_sigmoid: bool) -> tuple[float, float]:
    """(최고 점수, 지연초)를 돌려준다."""
    if not chunks:
        return 0.0, 0.0
    started = time.perf_counter()
    raw = model.predict([(query, c["content"]) for c in chunks])
    elapsed = time.perf_counter() - started
    scores = [sigmoid(float(s)) if apply_sigmoid else float(s) for s in raw]
    return max(scores), elapsed


def run_score(dump_file: Path, models: list[str], require_gold_in_top: bool, max_length: int | None) -> Path:
    from sentence_transformers import CrossEncoder

    records = json.loads(dump_file.read_text(encoding="utf-8"))
    if require_gold_in_top:
        records = [r for r in records if r["positive_gold_in_top"]]
    results = {}
    for name in models:
        print(f"[model] {name} 로드", flush=True)
        # 근거: 길이 상한이 없으면 bge-m3 계열이 8,192토큰까지 처리하여 CPU 실측이 수 시간 걸린다.
        model = CrossEncoder(name, device="cpu", max_length=max_length)
        # 단일 로짓 모델은 활성화 없이 로짓을 내므로 reranker.py와 같이 sigmoid를 적용한다.
        probe = float(model.predict([("a", "b")])[0])
        apply_sigmoid = not (0.0 <= probe <= 1.0)
        pos, neg, latencies, per_case = [], [], [], []
        for i, r in enumerate(records, start=1):
            p, tp = _score_case(model, r["query"], r["positive"], apply_sigmoid)
            n, tn = _score_case(model, r["query"], r["negative"], apply_sigmoid)
            pos.append(p)
            neg.append(n)
            latencies += [tp, tn]
            per_case.append({"id": r["id"], "pos_max": p, "neg_max": n})
            if i % 10 == 0:
                print(f"[progress] {name}: {i}/{len(records)}", flush=True)
        best = select_threshold(pos, neg)
        results[name] = {
            "n": len(records),
            "max_length": max_length,
            "auc": auc(pos, neg),
            "best": best,
            "h1_pass": h1_verdict(best["block_rate"], best["false_block_rate"]),
            "rates_at_0.5": dict(zip(("block_rate", "false_block_rate"), rates_at(0.5, pos, neg))),
            "bands": select_bands(pos, neg),
            "latency_p50_s": statistics.median(latencies),
            "latency_p95_s": _percentile(latencies, 0.95),
            "pos_median": statistics.median(pos),
            "neg_median": statistics.median(neg),
            "per_case": per_case,
        }
        print(f"[result] {name}: AUC={results[name]['auc']:.3f} best={best} h1={results[name]['h1_pass']}")
    out = OUT_DIR / f"gate_scores_{datetime.now(KST):%Y%m%d_%H%M}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"점수 저장: {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    dump = sub.add_parser("dump")
    dump.add_argument("--dense-only", action="store_true",
                      help="Sparse를 생략한 Dense 단독 후보 풀로 덤프한다(sparse 영향 분리용)")
    score = sub.add_parser("score")
    score.add_argument("--dump-file", type=Path, required=True)
    score.add_argument("--models", nargs="+", default=list(CANDIDATE_MODELS))
    score.add_argument("--require-gold-in-top", action="store_true",
                       help="양성 top-10에 정답 장이 실제로 있는 질의만 사용한다")
    score.add_argument("--max-length", type=int, default=512,
                       help="질의+청크 토큰 상한(0이면 모델 기본값)")
    args = parser.parse_args()
    if args.cmd == "dump":
        run_dump(args.dense_only)
    else:
        run_score(args.dump_file, args.models, args.require_gold_in_top, args.max_length or None)


if __name__ == "__main__":
    main()
