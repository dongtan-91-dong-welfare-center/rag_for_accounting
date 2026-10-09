"""#428 리랭커 점수 기반 품질 게이트 오프라인 실측 하니스.

목적:
  CRAG 품질 게이트(evaluate)의 LLM 평가 호출을 Cross-Encoder 리랭커 점수로 대체하거나
  일부 위임할 수 있는지를, LLM 호출 없이(비용 없이) 판정한다.

절차:
  1. dump: 벤치마크 질의마다 리랭커에 넣을 청크 묶음 두 개를 만들어 JSON으로 저장한다.
     - 양성(근거 있음): 전체 코퍼스 하이브리드 검색 상위 10개 청크
     - 음성(근거 없음): 상위 50개를 검색한 뒤 정답 장(chapter)의 청크를 제거하고 남은 상위 10개
       → 같은 질의·같은 도메인이지만 정답 근거가 없는 hard negative를 인위적으로 만든다.
     덤프를 먼저 고정해 두므로 모든 후보 모델이 완전히 같은 입력으로 비교된다.
  2. score: 후보 모델별로 질의-청크 점수를 산출하고, 질의별 "최고 점수" 하나를 게이트 신호로 삼는다.
     양성·음성 최고 점수 분포로 AUC, 임계값별 차단율/오차단율, 3구간(즉시 차단·LLM 위임·즉시 통과),
     CPU 지연을 집계한다.

사용 (호스트 실행, DB 기동·chunks 적재 전제, `uv sync --extra reranker`):
  uv run python scripts/rerank_gate_eval.py dump [--dense-only]
  uv run python scripts/rerank_gate_eval.py score --dump-file docs/measurements/issue428/gate_dump_<stamp>.json

H1 판정 기준(#428): 음성 차단율 ≥ 70% AND 양성 오차단율 ≤ 10%.
용어:
  - 차단: 질의의 최고 점수가 임계값 미만이어서 "근거 없음"으로 판정하는 것
  - 음성 차단율: 음성 케이스 중 차단된 비율(높을수록 좋다)
  - 양성 오차단율: 양성 케이스 중 잘못 차단된 비율(낮을수록 좋다)
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
# #428 후보 모델. KURE-Reranker-base는 Qwen3 1.7B 기반이라 CPU 실측이 사실상 불가능했다(리포트 2장).
CANDIDATE_MODELS = (
    "BAAI/bge-reranker-v2-m3",
    "dragonkue/bge-reranker-v2-m3-ko",
    "nlpai-lab/KURE-Reranker-nano",
    "nlpai-lab/KURE-Reranker-base",
)
TOP_N = 10  # 운영 TOP_K_RETRIEVAL과 같은 크기로 리랭커에 넣는 청크 수
NEG_POOL_K = 50  # 정답 장 제거 후에도 top-10을 채우기 위한 넓은 검색 풀
H1_MIN_BLOCK_RATE = 0.70  # LLM 평가기 차단율(88.4%)의 약 80%
H1_MAX_FALSE_BLOCK_RATE = 0.10

# references 예: "일반기업회계기준 제2장 2.65조", "제 21 장" → 장 번호 숫자만 캡처한다.
_CHAPTER_RE = re.compile(r"제\s*(\d+)\s*장")


def extract_gold_chapters(references: list[str]) -> set[str]:
    """벤치마크 references에서 정답 장 번호 집합을 추출한다.

    benchmark.jsonl에는 정답 청크 ID가 없고 조항 문자열만 있으므로, 장 단위로 정답 근거를 판정한다.
    청크 메타데이터의 chapter가 문자열("6")이므로 같은 타입(str)으로 돌려준다.

    Args:
        references: 조항 문자열 목록(예: ["일반기업회계기준 제2장 2.65조"]).

    Returns:
        장 번호 문자열 집합(예: {"2"}). 장을 찾지 못하면 빈 집합이다.
    """
    chapters: set[str] = set()
    for ref in references:
        chapters.update(_CHAPTER_RE.findall(ref))
    return chapters


def exclude_chapters(chunks: list[dict], gold_chapters: set[str], n: int = TOP_N) -> list[dict]:
    """정답 장 청크를 제거하여 음성(근거 없음) 케이스의 청크 묶음을 만든다.

    검색 순위는 유지한 채 정답 장 청크만 빼므로, 남는 청크는 질의와 용어를 공유하는
    다른 장의 유사 오답(hard negative)이 된다.

    Args:
        chunks: 검색 순위 순서의 청크 레코드(`chapter` 키 포함).
        gold_chapters: 제거할 정답 장 번호 집합.
        n: 돌려줄 최대 청크 수.

    Returns:
        정답 장이 아닌 청크 상위 n개. chapter 메타데이터가 없는 청크는 정답 장인지 판정할 수 없으므로
        음성에 섞이지 않도록 함께 제거한다.
    """
    kept = [c for c in chunks if c.get("chapter") and str(c["chapter"]) not in gold_chapters]
    return kept[:n]


def sigmoid(x: float) -> float:
    """로짓을 [0, 1] 점수로 정규화한다.

    운영 `src/retrieval/reranker.py`와 같은 정규화를 써야 측정한 임계값을
    `RERANK_THRESHOLD`에 그대로 옮길 수 있다. 이미 [0, 1] 확률을 내는 모델에는 호출하지 않는다.
    """
    return 1.0 / (1.0 + math.exp(-x))


def auc(pos_scores: list[float], neg_scores: list[float]) -> float:
    """양성·음성 점수 분포의 ROC AUC를 계산한다.

    AUC는 "무작위 양성 하나의 점수가 무작위 음성 하나보다 높을 확률"과 같다(Mann-Whitney U).
    모든 쌍을 비교하고 동점은 0.5로 센다. 표본이 111×111 수준이므로 O(n²)로 충분하며,
    sklearn 의존성을 추가하지 않기 위해 직접 계산한다.

    Returns:
        0.5(구분 불가) ~ 1.0(완전 분리). 한쪽 표본이 비면 nan이다.
    """
    if not pos_scores or not neg_scores:
        return float("nan")
    wins = 0.0
    for p in pos_scores:
        for q in neg_scores:
            wins += 1.0 if p > q else 0.5 if p == q else 0.0
    return wins / (len(pos_scores) * len(neg_scores))


def rates_at(threshold: float, pos_scores: list[float], neg_scores: list[float]) -> tuple[float, float]:
    """주어진 임계값에서 게이트의 차단율과 오차단율을 계산한다.

    운영 `rerank()`와 같이 최고 점수가 임계값 "미만"이면 차단한다(같으면 통과).

    Returns:
        (음성 차단율, 양성 오차단율).
    """
    block = sum(s < threshold for s in neg_scores) / len(neg_scores)
    false_block = sum(s < threshold for s in pos_scores) / len(pos_scores)
    return block, false_block


def select_threshold(
    pos_scores: list[float], neg_scores: list[float], max_false_block: float = H1_MAX_FALSE_BLOCK_RATE
) -> dict:
    """오차단율 상한을 지키면서 음성 차단율이 최대가 되는 임계값을 고른다.

    차단율·오차단율은 관측 점수 지점에서만 바뀌므로 관측된 점수 전체를 후보로 훑으면 최적값을 놓치지 않는다.
    차단율이 같은 후보가 여럿이면 가장 낮은(먼저 만난) 임계값을 유지해 오차단을 최소화한다.

    Returns:
        {"threshold", "block_rate", "false_block_rate"}. 조건을 만족하는 후보가 없으면 모두 0.0이다.
    """
    best = {"threshold": 0.0, "block_rate": 0.0, "false_block_rate": 0.0}
    for t in sorted(set(pos_scores) | set(neg_scores)):
        block, false_block = rates_at(t, pos_scores, neg_scores)
        # 오차단 상한을 넘는 임계값은 제외하고, 차단율이 엄격히 개선될 때만 갱신한다.
        if false_block <= max_false_block and block > best["block_rate"]:
            best = {"threshold": t, "block_rate": block, "false_block_rate": false_block}
    return best


def select_bands(pos_scores: list[float], neg_scores: list[float]) -> dict:
    """2단계 위임 방식(H2)의 3구간 경계와 구간별 비율을 계산한다.

    - low: 양성 최저 점수. 이 미만은 양성이 하나도 없으므로 LLM 없이 즉시 차단해도 양성을 잃지 않는다.
    - high: 음성 최고 점수 바로 위. 이 이상은 음성이 하나도 없으므로 즉시 통과해도 음성을 놓치지 않는다.
    - 그 사이는 리랭커만으로 판단할 수 없으므로 LLM 평가에 위임한다.
    위임 비율이 클수록 LLM 호출 절감 효과가 작다.

    Returns:
        {"low", "high", "block_share", "delegate_share", "pass_share"}. 비율은 전체(양성+음성) 대비이다.
    """
    low = min(pos_scores)
    # 음성 최고점 자체도 "통과"가 아니라 위임 구간에 들도록 미세하게 올린다(경계는 s >= high가 통과).
    high = max(neg_scores) + 1e-9
    if high < low:  # 양성·음성이 완전히 분리된 경우: 위임 구간이 없으므로 두 경계를 중간값으로 합친다.
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
    """H1(판별력) 채택 여부를 판정한다: 음성 차단율 ≥ 70%이면서 양성 오차단율 ≤ 10%이면 채택이다."""
    return block_rate >= H1_MIN_BLOCK_RATE and false_block_rate <= H1_MAX_FALSE_BLOCK_RATE


def _percentile(values: list[float], q: float) -> float:
    """nearest-rank 방식 백분위수를 돌려준다(보간 없음, 지연 p95 집계용)."""
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return ordered[idx]


def _chunk_record(chunk) -> dict:
    """RetrievedChunk를 덤프용 dict로 줄인다. 채점에 필요한 본문과 음성 판정에 필요한 chapter만 남긴다."""
    return {
        "chunk_id": chunk.chunk_id,
        "chapter": chunk.metadata.chapter,
        "content": chunk.content,
    }


def run_dump(dense_only: bool = False) -> Path:
    """DB 커넥션 풀을 열고 양성·음성 케이스를 덤프한 뒤 풀을 닫는다.

    search_chunks는 전역 커넥션 풀을 사용하므로 앱과 같이 init_pool()을 먼저 호출해야 한다.
    DB·임베딩 의존 import는 score만 실행할 때 불필요하므로 함수 안에서 지연 import한다.

    Args:
        dense_only: True면 Sparse를 생략한 Dense 단독 후보 풀로 덤프한다(Sparse 영향 분리용).

    Returns:
        저장한 덤프 JSON 경로.
    """
    from src.db.connection import close_pool, init_pool
    from src.retrieval.searcher import search_chunks

    init_pool()
    try:
        return _dump_cases(search_chunks, dense_only)
    finally:
        close_pool()


def _dump_cases(search_chunks, dense_only: bool) -> Path:
    """벤치마크 질의마다 양성·음성 청크 묶음을 만들어 JSON으로 저장한다.

    질의당 검색은 1회(top-50)만 수행하고, 양성은 그 상위 10개, 음성은 정답 장을 뺀 상위 10개로 만든다.
    따라서 양성·음성이 같은 검색 결과에서 파생되며 검색 변동이 끼어들지 않는다.

    Args:
        search_chunks: 하이브리드 검색 함수(테스트 주입을 위해 인자로 받는다).
        dense_only: True면 include_sparse=False로 검색한다.

    Returns:
        저장한 덤프 JSON 경로. 파일명에 Dense 단독 여부와 KST 시각을 넣는다.
    """
    cases = [json.loads(line) for line in BENCHMARK_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = []
    for case in cases:
        if case["id"] in EXCLUDED_CASE_IDS:
            continue
        gold = extract_gold_chapters(case.get("references", []))
        if not gold:
            # 정답 장을 모르면 음성을 만들 수 없으므로 모집단에서 뺀다.
            print(f"[skip] {case['id']}: 정답 장 추출 불가")
            continue
        pool = [_chunk_record(c) for c in search_chunks(case["query"], top_k=NEG_POOL_K, include_sparse=not dense_only)]
        positive = pool[:TOP_N]
        negative = exclude_chapters(pool, gold)
        records.append({
            "id": case["id"],
            "query": case["query"],
            "gold_chapters": sorted(gold),
            # 양성 top-10에 정답 장이 실제로 있는지 기록한다. score --require-gold-in-top 필터에 쓴다.
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
    """한 케이스(질의 + 청크 최대 10개)를 채점하여 게이트 신호와 지연을 돌려준다.

    운영 rerank()와 같이 청크 전체를 한 번의 predict 배치로 채점하므로, 지연은 질의당 실제 비용에 해당한다.

    Returns:
        (청크 점수 중 최고값, predict 소요 초). 청크가 없으면 (0.0, 0.0)으로, 근거가 없으므로 항상 차단된다.
    """
    if not chunks:
        return 0.0, 0.0
    started = time.perf_counter()
    raw = model.predict([(query, c["content"]) for c in chunks])
    elapsed = time.perf_counter() - started
    scores = [sigmoid(float(s)) if apply_sigmoid else float(s) for s in raw]
    return max(scores), elapsed


def run_score(dump_file: Path, models: list[str], require_gold_in_top: bool, max_length: int | None) -> Path:
    """덤프된 케이스를 후보 모델별로 채점하고 게이트 지표를 집계하여 JSON으로 저장한다.

    모델은 하나씩 순서대로 로드한다. 운영 reranker.py는 모듈 전역 싱글턴이라 모델을 바꿔 가며 비교할 수 없으므로,
    여기서는 CrossEncoder를 직접 생성한다.

    Args:
        dump_file: run_dump가 저장한 덤프 JSON.
        models: HuggingFace 모델 ID 목록.
        require_gold_in_top: True면 양성 top-10에 정답 장이 있는 질의만 집계한다.
        max_length: 질의+청크 토큰 상한. None이면 모델 기본값(bge-m3 계열은 8,192)을 쓴다.

    Returns:
        저장한 점수 JSON 경로. 모델별 요약 지표와 케이스별 최고 점수(per_case)를 담는다.
    """
    from sentence_transformers import CrossEncoder

    records = json.loads(dump_file.read_text(encoding="utf-8"))
    if require_gold_in_top:
        records = [r for r in records if r["positive_gold_in_top"]]
    results = {}
    for name in models:
        print(f"[model] {name} 로드", flush=True)
        # 근거: 길이 상한이 없으면 bge-m3 계열이 8,192토큰까지 처리하여 CPU 실측이 수 시간 걸린다.
        model = CrossEncoder(name, device="cpu", max_length=max_length)
        # 출력이 로짓인지 확률인지를 더미 입력 하나로 판별한다.
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
                # CPU 실측은 수십 분이 걸리므로 진행 상황을 즉시 출력한다(flush).
                print(f"[progress] {name}: {i}/{len(records)}", flush=True)
        best = select_threshold(pos, neg)
        results[name] = {
            "n": len(records),
            "max_length": max_length,
            "auc": auc(pos, neg),
            "best": best,
            "h1_pass": h1_verdict(best["block_rate"], best["false_block_rate"]),
            # 현행 RERANK_THRESHOLD 기본값(0.5)을 그대로 쓸 때의 성능도 함께 남긴다.
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
    """CLI 진입점: dump 또는 score 하위 명령을 실행한다."""
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
        # 0은 "상한 없음"을 뜻하므로 None으로 바꿔 모델 기본값을 쓰게 한다.
        run_score(args.dump_file, args.models, args.require_gold_in_top, args.max_length or None)


if __name__ == "__main__":
    main()
