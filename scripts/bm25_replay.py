"""BM25 오프라인 실측 하니스 — 진짜 BM25(IDF 내장)가 조항 검색을 개선하는지 반증.

[배경] 이 시스템의 sparse 검색이 쓰는 PostgreSQL ts_rank_cd는 BM25가 아니라 IDF 흔한 단어일수록 가중치를 자동으로 낮추는 값)가 없다.
  그래서 "손익계산서"처럼 흔한 용어가 순위를 지배하고 #211에서 query 쪽 레버(술어·키워드·불용어)를 다 바꿔 봐도 이 병목을 못 넘어 전부 기각됐다. 
  남은 레버는 IDF를 내장한 진짜 BM25다.

[목적] BM25 랭킹(IDF)과 한국어 토큰화는 곱셈 관계인 두 축이다. 
  무거운 인프라(ParadeDB 등)를 들이기 전에, 운영 코퍼스를 오프라인으로 꺼내 rank_bm25로 BM25 점수를 매기고,
  토크나이저를 whitespace·문자 3-gram·형태소으로 갈아끼워 "IDF 순효과"와 "토큰화 순효과"를 분리 측정한다.

[제약] 운영 스키마·프롬프트·검색 경로는 건드리지 않는다. rank_bm25·kiwipiepy는 하니스 전용 dev 의존성이다.
판정이 아래 게이트를 통과한 (토크나이저 × IDF) 조합이 있을 때만 Phase 1로 간다.

[판정 기준] Hit@1(정답 조항이 검색 1위인 질의 수) 순증 ≥ +2 · 기존 1위 회귀 0 · MRR(정답 순위 역수 평균) Δ>0 ·
sparse 지연 p50(중앙값) ≤ 1s · RRF k=60 고정 · 판정 모집단은 gold(정답 라벨) 확정 대기 3건을 뺀 11건.

사용 (호스트 실행, DB 기동·chunks 적재 전제):
  uv run python scripts/bm25_replay.py
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from psycopg import sql  # noqa: E402
from rank_bm25 import BM25Okapi  # noqa: E402

from src.models.schemas import RetrievedChunk  # noqa: E402
from src.utils.config import CHUNKS_TABLE, KST, RRF_K  # noqa: E402
from scripts.rerank_replay import SWEEP_KS, TOP_N, _mrr, fuse_top_n, judge_adoption  # noqa: E402
from scripts.sparse_predicate_replay import (  # noqa: E402
    SMOKE_QUERIES,
    sparse_search_predicate,
    tokenize as tokenize_whitespace,
)

# n-gram 크기 — 한국어 부분일치를 만드는 최소 단위. 3이면 "외화환산"과 "외화환산손익"이
# {"외화환","화환산"}을 공유해 매칭된다(2면 흔한 조각이 많아 노이즈↑, 4면 부분일치 범위↓).
NGRAM_N = 3

_kiwi = None  # kiwipiepy Kiwi 싱글턴 — 로드가 무거워(초 단위) 최초 1회만 만든다.


def tokenize_ngram(text: str, n: int = NGRAM_N) -> list[str]:
    """
    단어별 문자 n-gram으로 쪼갠다. n자보다 짧은 단어는 통째로 한 토큰으로 둔다.

    예: "외화환산손익" → ["외화환","화환산","환산손","산손익"], "인식" → ["인식"].
    현행 'simple' 토크나이저는 "외화환산손익"을 한 덩어리로 둬 청크의 "외화환산"과 매칭조차 못 하지만
    3-gram은 겹치는 조각으로 이 간극을 우회한다.
    """
    grams: list[str] = []
    for word in tokenize_whitespace(text):
        if len(word) <= n:
            grams.append(word)
        else:
            grams.extend(word[i:i + n] for i in range(len(word) - n + 1))
    return grams


def tokenize_morph(text: str) -> list[str]:
    """
    kiwipiepy 형태소 분석으로 토큰화한다(각 형태소의 표면형 form만 취함).

    예: "외화환산손익 인식" → ["외화","환산","손익","인식"].
    조사·어미도 토큰에 남기되 품사 필터를 걸지 않는다
    흔한 형태소(조사 등)는 BM25의 IDF가 자동으로 감쇠하므로, 여기서 걸러 규칙을 늘리는 것은 불필요하다.
    """
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return [t.form for t in _kiwi.tokenize(text)]


# 토큰화 축 — 표시키 → 토크나이저. arm이 (토크나이저 × BM25) 조합을 만들 때 참조한다.
#   ws    : 단어(\w+) 분리 — 현행 'simple'과 근사, IDF 순효과를 재는 기준 토큰화
#   ngram : 문자 3-gram — 단어 내 부분일치 회복
#   morph : 형태소 분석 — 복합어를 표준 용어 단위로 분해
TOKENIZERS: dict[str, Callable[[str], list[str]]] = {
    "ws": tokenize_whitespace,
    "ngram": tokenize_ngram,
    "morph": tokenize_morph,
}


class Bm25Index:
    """
    오프라인 BM25 인덱스 — 문서 리스트와 토크나이저로 구축하고, 질의별 top-n을 돌려준다.

    운영 DB에는 BM25가 없어 ts_rank_cd(IDF 부재)만 쓸 수 있다. 
    이 클래스는 코퍼스를 메모리에서 BM25Okapi로 인덱싱해, IDF가 있을 때 순위가 어떻게 달라지는지를 인프라 도입 없이 측정한다.
    """

    def __init__(self, docs: list[str], tokenizer: Callable[[str], list[str]]):
        self.tokenizer = tokenizer
        self.bm25 = BM25Okapi([tokenizer(d) for d in docs])

    def rank(self, query: str, n: int) -> list[tuple[int, float]]:
        """
        질의 상위 n개를 (문서 인덱스, 점수) 리스트로 반환한다(점수 내림차순).

        질의 토큰이 하나도 없어 점수가 0 이하인 문서는 sparse 결과로 부적절하므로 제외한다 —
        현행 sparse가 매칭된 문서만 돌려주는 규약과 같아, dense와의 RRF 병합이 공정해진다.
        """
        scores = self.bm25.get_scores(self.tokenizer(query))
        ranked = sorted(enumerate(scores), key=lambda pair: pair[1], reverse=True)
        return [(i, float(s)) for i, s in ranked[:n] if s > 0]


# ════════════════════════════════ 측정 arm ════════════════════════════════
# arm 표시·판정 순서. baseline=plainto(현행), 이후 ts_or로 IDF 순효과(ts_or↔bm25_ws),
# bm25_* 3종끼리 토큰화 순효과를 가른다.
ARM_ORDER = ["plainto", "ts_or", "bm25_ws", "bm25_ngram", "bm25_morph"]
# DB 술어 arm — 운영과 동일한 sparse_search_predicate 경로(값=1차에서 안전성이 실증된 술어키).
DB_ARMS: dict[str, str] = {"plainto": "plainto", "ts_or": "or"}
# BM25 arm — 오프라인 인덱스 경로(값=TOKENIZERS 키).
BM25_ARMS: dict[str, str] = {"bm25_ws": "ws", "bm25_ngram": "ngram", "bm25_morph": "morph"}


def _passes_filter(chunk: RetrievedChunk, metadata_filter: dict | None) -> bool:
    """
    청크가 metadata_filter를 통과하는지 판정한다 — dense와 같은 후보 풀을 BM25에도 강제한다.

    벤치마크 필터는 {"standard_type": "GAAP"} 꼴뿐이라 명시 필드 비교로 충분하다.
    필터가 없으면 전 청크가 통과한다.
    """
    if not metadata_filter:
        return True
    return all(getattr(chunk.metadata, key, None) == value
               for key, value in metadata_filter.items())


def _bm25_sparse(
    index: Bm25Index, corpus: list[RetrievedChunk], query: str,
    top_n: int, metadata_filter: dict | None,
) -> list[RetrievedChunk]:
    """
    오프라인 BM25 순위에서 필터 통과 상위 top_n을 RetrievedChunk로 만든다.

    현행 sparse의 "매칭 문서만" 규약과 dense의 metadata 필터를 함께 지켜, dense와의 RRF 병합이 공정해진다.
    코퍼스 원본은 건드리지 않고 BM25 점수를 채운 복사본을 반환한다(같은 코퍼스를 여러 arm이 공유하므로 원본 불변이 안전하다).
    """
    out: list[RetrievedChunk] = []
    for i, score in index.rank(query, len(corpus)):
        chunk = corpus[i]
        if _passes_filter(chunk, metadata_filter):
            out.append(chunk.model_copy(update={"score": score}))
            if len(out) >= top_n:
                break
    return out


def _arm_query_tokens(arm: str, query: str) -> list[str]:
    """
    arm이 실제로 검색에 쓴 질의 토큰 — 정성 증거(어떤 토큰이 gold를 끌어올렸나)용.

    BM25 arm은 그 arm의 토크나이저 결과를, DB arm(plainto/or)은 원 질의 단어를 쓴다.
    """
    if arm in BM25_ARMS:
        return TOKENIZERS[BM25_ARMS[arm]](query)
    return tokenize_whitespace(query)


def load_corpus() -> list[RetrievedChunk]:
    """
    운영 chunks 테이블 전체를 메모리로 로드한다(BM25 오프라인 인덱싱용).

    dense/DB-sparse가 쓰는 _execute_search_query를 재사용해 metadata까지 동일하게 파싱한다.
    score 컬럼은 인덱싱에 쓰지 않으므로 0으로 채운다(BM25 점수는 rank 시점에 매긴다).
    """
    from src.retrieval.searcher import _execute_search_query

    query_sql = sql.SQL(
        "SELECT chunk_id, document_id, content, metadata, 0 AS score FROM {table}"
    ).format(table=sql.Identifier(CHUNKS_TABLE))
    return _execute_search_query(query_sql, [], "Corpus")


def run_measure(out_dir: str, top_n: int, ks: tuple[int, ...]) -> int:
    """
    벤치마크 전 질의를 arm별로 재질의하고, 결과를 채점해 채택 여부를 판정한다.

    흐름: 코퍼스 로드 → BM25 인덱스 구축 → DB arm 안전 점검 → arm별 검색(+self-check)
          → 채점 → #159 판정 → 산출물 저장.
    """
    # 호스트 실행 시 DB 호스트 보정 (1차·benchmark_baseline와 동일)
    if os.getenv("POSTGRES_HOST") == "database":
        os.environ["POSTGRES_HOST"] = "localhost"

    from src.db.connection import init_pool, close_pool
    from src.retrieval.searcher import dense_search, embed_query, search_chunks
    from scripts.rerank_replay import _case_filter
    from tests.utils.benchmark_loader import load_benchmark
    from tests.utils.benchmark_metrics import (
        extract_chunk_paras,
        get_chunk_count,
        get_indexed_chapters,
        gold_para_set,
        parse_gold_clauses,
        rank_hit,
        resolve_core_paras,
        retrieval_pass,
    )

    cases = load_benchmark()
    init_pool()
    try:
        n_chunks = get_chunk_count()
        chapters = sorted(get_indexed_chapters(), key=int)
        print(f"코퍼스: {n_chunks}청크 · {len(chapters)}장 · RRF_K={RRF_K} · top_n={top_n}")

        # ── BM25 오프라인 인덱스 구축(토크나이저당 1개). 케이스마다 재구축하지 않고 1회만 만든다.
        #    형태소 인덱스는 전 청크를 형태소 분석하므로 수 초 걸린다(질의당 비용이 아니라 1회 비용). ──
        corpus = load_corpus()
        docs = [c.content for c in corpus]
        t0 = time.perf_counter()
        indices = {tok: Bm25Index(docs, TOKENIZERS[tok]) for tok in BM25_ARMS.values()}
        print(f"BM25 인덱스 {len(indices)}종 구축: {time.perf_counter() - t0:.1f}s (코퍼스 {len(corpus)}청크)")

        # ── 특수문자 안전 점검: DB arm이 쓰는 술어(plainto/or)에 위험한 꼴 질의를 실제 실행.
        #    BM25 arm은 오프라인이라 SQL 문법 오류가 구조적으로 불가능해 대상이 아니다. ──
        used_preds = sorted(set(DB_ARMS.values()))
        for pred in used_preds:
            for q in SMOKE_QUERIES:
                sparse_search_predicate(pred, q, top_n)
        print(f"특수문자 스모크 통과: {len(used_preds)}술어 × {len(SMOKE_QUERIES)}질의 — 예외 0")

        # ── arm별 검색 결과 수집: dense 1회 + DB arm(술어) + BM25 arm(오프라인).
        #    self-check: plainto arm의 오프라인 병합이 라이브 search_chunks와 같아야 측정을 신뢰할 수 있다. ──
        measured = []
        mismatches = []
        latencies: dict[str, list[float]] = {arm: [] for arm in ARM_ORDER}
        for case in cases:
            metadata_filter = _case_filter(case.standard)
            vec = embed_query(case.query)
            dense = dense_search(vec, top_n, metadata_filter)

            sparse_by_arm: dict[str, list[RetrievedChunk]] = {}
            for arm, pred in DB_ARMS.items():
                t0 = time.perf_counter()
                sparse_by_arm[arm] = sparse_search_predicate(pred, case.query, top_n, metadata_filter)
                latencies[arm].append(time.perf_counter() - t0)
            for arm, tok in BM25_ARMS.items():
                t0 = time.perf_counter()
                sparse_by_arm[arm] = _bm25_sparse(indices[tok], corpus, case.query, top_n, metadata_filter)
                latencies[arm].append(time.perf_counter() - t0)

            fused_ids = [c.chunk_id for c in fuse_top_n(dense, sparse_by_arm["plainto"], k=RRF_K, n=top_n)]
            live_ids = [c.chunk_id for c in search_chunks(case.query, top_n, metadata_filter)]
            ok = fused_ids == live_ids
            if not ok:
                mismatches.append(case.id)

            gold = gold_para_set(parse_gold_clauses(case.references))
            measured.append({
                "id": case.id,
                "query": case.query,
                "tokens": {arm: _arm_query_tokens(arm, case.query) for arm in ARM_ORDER},
                "gold": gold,
                "core": resolve_core_paras(case, gold),
                "dense": dense,
                "sparse": sparse_by_arm,
            })
            counts = "/".join(str(len(sparse_by_arm[a])) for a in ARM_ORDER)
            print(f"  {case.id}: dense {len(dense)} · sparse {counts} ({'/'.join(ARM_ORDER)}) "
                  f"· self-check {'✓' if ok else '✗'}")
    finally:
        close_pool()

    # ── 채점: arm별로 dense와 sparse를 RRF로 합친 뒤 정답 조항 최초 등장 순위를 기록. ──
    scores: dict[int, dict[str, dict]] = {}
    for k in ks:
        scores[k] = {}
        for arm in ARM_ORDER:
            by_case: dict[str, int | None] = {}
            pass_cnt = 0
            for rc in measured:
                contents = [c.content for c in fuse_top_n(rc["dense"], rc["sparse"][arm], k=k, n=top_n)]
                fh, _ = rank_hit(contents, rc["gold"], "exact")
                by_case[rc["id"]] = fh
                pass_cnt += retrieval_pass(contents, rc["core"])
            scores[k][arm] = {"first_hits": by_case, "retrieval_pass": pass_cnt}

    # ── 정성 증거: arm sparse가 정답 조항을 몇 위로 잡았고, 그 arm 입력의 어떤 토큰이
    #    실제 본문에 등장했는지 기록("무엇이 정답을 끌어올렸나"). ──
    evidence: dict[str, dict[str, dict]] = {}
    for arm in ARM_ORDER:
        evidence[arm] = {}
        for rc in measured:
            for rank, chunk in enumerate(rc["sparse"][arm], start=1):
                if extract_chunk_paras(chunk.content) & rc["gold"]:
                    evidence[arm][rc["id"]] = {
                        "sparse_rank": rank,
                        "matched_tokens": [t for t in rc["tokens"][arm] if t in chunk.content],
                    }
                    break

    # ── 판정: 사전 확정 기준으로 arm별 채택/롤백. 비교 기준(baseline)은 plainto, k는 RRF_K 고정. ──
    n = len(measured)
    base_fh = scores[RRF_K]["plainto"]["first_hits"]
    print(f"\n판정 (k={RRF_K} 고정 · baseline=plainto · 모집단 {len(judge_adoption(base_fh, base_fh, 0)['population'])}건):")
    verdicts: dict[str, dict] = {}
    for arm in ARM_ORDER:
        fhs = scores[RRF_K][arm]["first_hits"]
        p50 = statistics.median(latencies[arm])
        hit1 = sum(1 for v in fhs.values() if v == 1)
        line = (f"  {arm:<12} Hit@1 {hit1}/{n} · MRR {_mrr(fhs, sorted(fhs)):.4f} "
                f"· pass {scores[RRF_K][arm]['retrieval_pass']}/{n} · sparse p50 {p50 * 1000:.1f}ms")
        if arm == "plainto":
            print(line + " · (baseline)")
            continue
        verdicts[arm] = judge_adoption(base_fh, fhs, p50)
        v = verdicts[arm]
        mark = "채택기준 충족" if v["adopt"] else f"미충족: {'; '.join(v['reasons'])}"
        print(line + f" · 순증{v['gains']} 회귀{v['regressions']} MRRΔ{v['mrr_delta']:+.4f} → {mark}")

    # ── 케이스별 first_hit 테이블 (정답 조항이 처음 등장한 순위, None=top{n} 미검출) ──
    print(f"\n케이스별 first_hit (k={RRF_K}, None=top{top_n} 미검출):")
    print(f"  {'case_id':<18}" + "".join(f"{a:>13}" for a in ARM_ORDER))
    for rc in measured:
        row = f"  {rc['id']:<18}"
        for arm in ARM_ORDER:
            row += f"{str(scores[RRF_K][arm]['first_hits'][rc['id']]):>13}"
        print(row)

    # ── k 민감도 (sparse 활성 상태에서 k 레버 효과 참고용, 판정 변수 아님) ──
    print("\nk 민감도 (Hit@1, 부수 기록):")
    for k in ks:
        cells = " · ".join(
            f"{a} {sum(1 for v in scores[k][a]['first_hits'].values() if v == 1)}" for a in ARM_ORDER
        )
        print(f"  k={k:>3}: {cells}")

    # ── 산출물 저장: 원본 JSON은 git 추적 제외(판정 리포트 md만 수기 커밋, 1·2차 관행) ──
    ts = datetime.now(KST)
    result = {
        "generated_at": ts.isoformat(),
        "corpus": {"n_chunks": n_chunks, "chapters": chapters},
        "rrf_k": RRF_K,
        "ks": list(ks),
        "top_n": top_n,
        "arms": {"db": DB_ARMS, "bm25": BM25_ARMS, "ngram_n": NGRAM_N},
        "selfcheck_mismatches": mismatches,
        "latency_s": {
            arm: {"p50": round(statistics.median(ls), 4), "max": round(max(ls), 4)}
            for arm, ls in latencies.items()
        },
        "scores": {
            k: {arm: {"first_hits": s["first_hits"], "retrieval_pass": s["retrieval_pass"]}
                for arm, s in by_arm.items()}
            for k, by_arm in scores.items()
        },
        "verdicts": verdicts,
        "gold_evidence": evidence,
        "cases": [
            {
                "case_id": rc["id"],
                "query": rc["query"],
                "tokens": rc["tokens"],
                "dense": [c.model_dump() for c in rc["dense"]],
                "sparse": {arm: [c.model_dump() for c in chunks] for arm, chunks in rc["sparse"].items()},
            }
            for rc in measured
        ],
    }
    out_path = Path(out_dir) / f"bm25_replay_{ts.strftime('%Y%m%d_%H%M')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out_path}")

    if mismatches:
        print(f"self-check 실패 {len(mismatches)}건: {mismatches} — 판정 신뢰 불가", file=sys.stderr)
        return 1
    print("self-check 전 케이스 통과 — 오프라인 병합 경로가 라이브와 동일")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BM25 오프라인 실측 — 토크나이저 × IDF arm 재질의·채점")
    parser.add_argument("--out-dir", default="docs/measurements", help="산출물 저장 디렉토리")
    parser.add_argument("--top-n", type=int, default=TOP_N, help="사이드별 검색 상위 N (기본 10)")
    parser.add_argument("--ks", default=",".join(map(str, SWEEP_KS)), help="RRF k 목록 (쉼표 구분, 판정은 RRF_K 고정)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ks = tuple(int(x) for x in args.ks.split(","))
    if RRF_K not in ks:
        ks = (RRF_K,) + ks  # 판정 k는 항상 포함
    return run_measure(args.out_dir, args.top_n, ks)


if __name__ == "__main__":
    raise SystemExit(main())
