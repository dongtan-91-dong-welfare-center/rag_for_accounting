"""
배포 가능 sparse 셀 실측 하니스 — 형태소 사전토큰화 × ts_rank_cd(IDF 없음) × 융합 가중.

[재는 대상] 지금까지 형태소 토큰화의 이득은 오프라인 rank_bm25(IDF 내장)로만 확인됐다(#226).
그런데 운영 sparse는 ts_rank_cd로 IDF가 없어, 그 판정이 곧 배포 가능을 뜻하지 않는다.
반면 리포트는 IDF 단독은 무력하거나 해로웠고(bm25_ws 악화) 개선은 전적으로 토큰화 축에서 나왔다.
그렇다면 인프라 추가 없이 배포할 수 있는 셀 형태소 사전토큰화 + to_tsvector('simple', …) + ts_rank_cd 한 번도 측정되지 않았다.
이 하니스가 그 빈칸을 채운다. 
통과하면 "무엇을 배포하는가"가 자동으로 정해지고, 탈락하면 ParadeDB 등을 다시 생각하는 근거가 된다.

[두 축을 함께 재는 이유] sparse를 켜는 것만으로는 이득이 아니다. 
양쪽 리스트에 모두 있는 청크는 RRF 점수가 합산되므로, dense 단독 1위가 (dense 중위 ∩ sparse 상위) 청크에 밀리는 회귀가 생긴다. 그래서 융합 가중(sparse 억제)을 같은 격자에서 함께 잰다.
  축 1 — 매칭:   품사 필터 3종(morph_all / morph_core / morph_wide) × 술어 2종(AND / OR)
  축 2 — 융합:   sparse RRF 가중 w ∈ FUSION_WEIGHTS

[사전 확정 — 결과를 보고 바꾸지 않는다]
  탐색 격자와 선택 규칙을 아래 상수로 못 박는다.
  오프라인 채점은 비용이 0이라 격자를 넓히면 "게이트를 튜닝 목적함수로 쓰는" 함정(기준 대신 후보를 결과에 맞추기)에 빠지기 쉽다.
  방어책 둘: ① 격자·선택 규칙 사전 고정 ② 홀드아웃 분할 — 판정 모집단을 2/3 튜닝 · 1/3 확인으로
  갈라, 튜닝셋에서 고른 셀이 확인셋에서도 기준을 넘는지 별도 보고한다.

[판정 기준] 기준의 정본은 scripts/rerank_replay.py의 judge_adoption()이며(하니스 4종 공유), 이 하니스는 그 함수를 그대로 호출한다
  순증(net) ≥ 모집단 비례 기준선 · MRR 순증 > 0 · sparse p50 ≤ 상한.
  격자 24조합을 한 모집단으로 판정하면 다중비교 과적합이 생기므로, 승자 선택은 튜닝셋 판정으로 하고 전체 모집단 판정은 선택된 승자에 대해서만 보고한다.

[함께 보고하는 부수 지표] 낮은 w는 Hit@1을 최대화하지만 이 라인의 출발점이었던 재현율 이득을 포기한다(Hit@10·retrieval_pass 하락).
어느 쪽을 택하든 "무엇을 버렸는지"가 표에 남아야 한다.

[제약] 운영 chunks·검색 경로·적재는 건드리지 않는다.
매칭은 scripts/build_morph_shadow.py가 만든 그림자 테이블에서만 하고, 병합은 운영 reciprocal_rank_fusion(weights=…)을 그대로 호출한다.
재는 것이 곧 배포될 코드여야 판정을 채택 근거로 쓸 수 있다.

사용 (호스트 실행, DB 기동·chunks 적재·그림자 테이블 빌드 전제):
  uv sync --extra local-embedding    # dense 검색이 임베딩 모델을 로컬 로드한다(TEI 서버 없이)
  uv run python scripts/build_morph_shadow.py
  uv run python scripts/sparse_morph_replay.py
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from psycopg import sql  # noqa: E402

from src.models.schemas import RetrievedChunk  # noqa: E402
from src.retrieval.searcher import (  # noqa: E402
    _build_where_clause,
    _execute_search_query,
    reciprocal_rank_fusion,
)
from src.utils.config import (  # noqa: E402
    CHUNKS_TABLE,
    KST,
    MORPH_CHUNKS_TABLE,
    RRF_K,
    SPARSE_FUSION_WEIGHT,
)
from scripts.build_morph_shadow import MORPH_COLUMNS  # noqa: E402
from scripts.rerank_replay import (  # noqa: E402
    EXCLUDED_CASE_IDS,
    TOP_N,
    _mrr,
    judge_adoption,
)
from scripts.sparse_predicate_replay import SMOKE_QUERIES  # noqa: E402

# ════════════════════════ 사전 확정 파라미터 (측정 전 고정) ════════════════════════

# sparse 리스트 RRF 가중 격자. 1.0 = 대칭 RRF(현행). 낮출수록 sparse 합산이 억제된다.
FUSION_WEIGHTS: tuple[float, ...] = (1.0, 0.5, 0.2, 0.1)

# 술어 — 형태소 토큰을 tsquery로 바꾸는 방식.
#   and : plainto_tsquery = 전 토큰 AND. 
#         형태소 명사류가 질의당 4~6개라 "모두 가진 문단"이 없을 위험이 크다. 검색 결과가 적게 나온다.
#   or  : websearch_to_tsquery에 ' or '로 연결. 행은 반환되지만 IDF가 없어 흔한 형태소가 순위를 지배할 위험이 있다. 품사 필터가 그 방어선이다.
#         둘 다 사용자 입력을 그대로 받아도 문법 오류를 내지 않는 함수다(to_tsquery만 조립이 위험).
PREDICATES: dict[str, str] = {
    "and": "plainto_tsquery('simple', %s)",
    "or": "websearch_to_tsquery('simple', %s)",
}

# 채택 게이트는 이 파일에 두지 않는다. 순증(net) ≥ 모집단 비례 기준선 · MRR 순증 > 0 · p50 상한)이며 하니스 4종이 공유한다.
# 여기 상수를 복제하면 기준이 두 곳에서 따로 움직여 판정 이력이 끊긴다.

# 홀드아웃 분할 — 판정 모집단을 case_id 정렬 후 인덱스로 가른다.
# 난수를 쓰지 않는 이유: 재실행해도 같은 분할이어야 판정이 재현된다.
HOLDOUT_EVERY = 3           # 정렬 인덱스 % 3 == 2 → 확인셋(1/3), 나머지 튜닝셋(2/3)
HOLDOUT_OFFSET = 2


def cells() -> list[tuple[str, str]]:
    """측정할 (사전토큰화 컬럼, 술어) 셀 목록 — 격자 순서를 한 곳에 고정한다."""
    return [(column, pred) for column in MORPH_COLUMNS for pred in PREDICATES]


def cell_label(column: str, pred: str) -> str:
    """표·JSON에 쓰는 셀 표시명 (예: morph_core+or)."""
    return f"{column}+{pred}"


# ════════════════════════════════ 검색 ════════════════════════════════


def sparse_search_morph(
    column: str, pred: str, query: str, top_k: int, metadata_filter: dict | None = None
) -> list[RetrievedChunk]:
    """
    그림자 테이블의 사전토큰화 컬럼에서 매칭하고 원문을 반환한다.

    운영 searcher의 _build_where_clause·_execute_search_query를 재사용하므로 타임아웃·예외 정책이 운영과 같은 경로를 탄다.
    이 측정을 배포 근거로 쓸 수 있는 이유다.
    매칭은 {column}에서 하고 SELECT는 content로 하는 게 핵심이다.
    rank_hit 채점이 청크 본문에서 조항 번호를 추출하므로 결과는 원문이어야 한다.

    질의는 그 컬럼과 같은 화이트리스트로 토큰화한다.
    색인과 질의가 다른 필터를 타면 매칭이 조용히 깨지므로, tags를 MORPH_COLUMNS에서 끌어와 어긋날 여지를 없앤다.
    """
    from src.retrieval.tokenizer import morph_text, tokenize_morph

    tags = MORPH_COLUMNS[column]
    if pred == "or":
        # websearch_to_tsquery가 or를 OR 연산자로 해석한다 (예: "퇴직급여 or 인식").
        ts_input = " or ".join(tokenize_morph(query, tags))
    else:
        ts_input = morph_text(query, tags)
    if not ts_input:
        return []  # 남은 형태소가 없음 — 검색식을 만들 수 없다(0건 확정, dense 단독으로 폴백)

    filter_clause, filter_params = _build_where_clause(metadata_filter)
    tsq = PREDICATES[pred]
    match_expr = f"to_tsvector('simple', {column}) @@ {tsq}"
    where_sql = f"{filter_clause} AND {match_expr}" if filter_clause else f" WHERE {match_expr}"

    query_sql = sql.SQL("""
        SELECT chunk_id, document_id, content, metadata,
               ts_rank_cd(to_tsvector('simple', {col}), {tsq}) AS score
        FROM {table}
        {where}
        ORDER BY score DESC
        LIMIT %s
    """).format(
        col=sql.Identifier(column),
        tsq=sql.SQL(tsq),
        table=sql.Identifier(MORPH_CHUNKS_TABLE),
        where=sql.SQL(where_sql),
    )
    query_params = [ts_input] + filter_params + [ts_input, top_k]
    return _execute_search_query(query_sql, query_params, f"Sparse[{cell_label(column, pred)}]")


def sparse_search_baseline(
    query: str, top_k: int, metadata_filter: dict | None = None
) -> list[RetrievedChunk]:
    """현행 운영 sparse — 운영 chunks의 content에 plainto_tsquery(AND). 비교 기준."""
    from src.retrieval.searcher import sparse_search

    return sparse_search(query, top_k, metadata_filter, CHUNKS_TABLE)


def fuse(dense: list[RetrievedChunk], sparse: list[RetrievedChunk], w: float, n: int) -> list[RetrievedChunk]:
    """
    운영 RRF로 dense+sparse를 병합해 top-n을 자른다 — dense 가중 1.0 고정, sparse는 w.

    운영 reciprocal_rank_fusion을 직접 호출한다(하니스 사본을 두지 않는다).
    dense를 앞에 둬 동점 시 dense 순서가 유지되는 것까지 운영과 같다.
    """
    return reciprocal_rank_fusion([dense, sparse], k=RRF_K, weights=[1.0, w])[:n]


# ════════════════════════════════ 판정 ════════════════════════════════


def split_holdout(population: list[str]) -> tuple[frozenset[str], frozenset[str]]:
    """판정 모집단을 (튜닝셋, 확인셋)으로 결정적으로 가른다."""
    confirm = frozenset(
        cid for i, cid in enumerate(sorted(population)) if i % HOLDOUT_EVERY == HOLDOUT_OFFSET
    )
    return frozenset(population) - confirm, confirm


def select_winner(results: list[dict]) -> dict | None:
    """
    사전 확정 선택 규칙 — 튜닝셋 통과 셀 중 net_gain 최대, 동점 시 MRRΔ 최대.

    결과를 본 뒤 규칙을 바꾸지 않기 위해 여기 한 곳에만 둔다.
    """
    passed = [r for r in results if r["tune"]["adopt"]]
    if not passed:
        return None
    return max(passed, key=lambda r: (r["tune"]["net_gain"], r["tune"]["mrr_delta"]))


# ════════════════════════════════ 실행 ════════════════════════════════


def run_measure(out_dir: str, top_n: int) -> int:
    """
    벤치마크 전 질의를 셀별로 재질의하고, 가중 격자 위에서 채점·판정한다.

    흐름: 그림자 테이블 점검 → 특수문자 스모크 → 셀별 검색(+self-check) → (셀 × w) 채점 → 홀드아웃 판정 → 승자 선택 → 산출물 저장.
    """
    # 호스트 실행 시 DB 호스트 보정 (다른 하니스와 동일 규약)
    if os.getenv("POSTGRES_HOST") == "database":
        os.environ["POSTGRES_HOST"] = "localhost"

    from src.db.connection import init_pool, close_pool
    from src.retrieval.searcher import dense_search, embed_query, search_chunks
    from scripts.rerank_replay import _case_filter
    from tests.utils.benchmark_loader import load_benchmark
    from tests.utils.benchmark_metrics import (
        get_chunk_count,
        get_indexed_chapters,
        gold_para_set,
        parse_gold_clauses,
        rank_hit,
        resolve_core_paras,
        retrieval_pass,
    )

    grid = cells()
    cases = load_benchmark()
    init_pool()
    try:
        n_chunks = get_chunk_count()
        chapters = sorted(get_indexed_chapters(), key=int)
        print(f"코퍼스: {n_chunks}청크 · {len(chapters)}장 · RRF_K={RRF_K} · top_n={top_n}")
        print(f"격자: {len(grid)}셀 × w{list(FUSION_WEIGHTS)} = {len(grid) * len(FUSION_WEIGHTS)}조합 (사전 고정)")

        # ── self-check 전제: 이 하니스의 baseline은 "채택 이전 운영"(plainto sparse · 대칭 RRF w=1.0)이다.
        #    sparse_search 자체가 형태소 경로이고 기본 가중도 0.1이라 그 baseline이 더 이상 라이브에 존재하지 않는다.
        #    이 측정의 재현은 채택 커밋 이전 체크아웃에서 한다. 가중만 눈에 띄므로 그걸 신호로 끊는다.
        if SPARSE_FUSION_WEIGHT != 1.0:
            print(
                f"SPARSE_FUSION_WEIGHT={SPARSE_FUSION_WEIGHT} (≠1.0) — 이 하니스는 채택 이전 운영"
                "(plainto sparse·대칭 RRF)을 baseline으로 전제하는 측정 도구입니다. "
                file=sys.stderr,
            )
            return 2

        # ── 특수문자 안전 점검: 셀이 쓰는 두 술어에 위험한 꼴 질의를 실제 실행(예외 0이어야 진행). ──
        for column, pred in grid:
            for q in SMOKE_QUERIES:
                sparse_search_morph(column, pred, q, top_n)
        print(f"특수문자 스모크 통과: {len(grid)}셀 × {len(SMOKE_QUERIES)}질의 — 예외 0")

        # 셀별 검색 결과 수집: dense 1회 + baseline + 셀별 sparse.
        # self-check: baseline(현행 plainto·w=1.0)의 오프라인 병합이 라이브 search_chunks와 같아야 이 하니스의 병합 경로를 신뢰할 수 있다.
        measured = []
        mismatches = []
        latencies: dict[str, list[float]] = {"baseline": [], **{cell_label(c, p): [] for c, p in grid}}
        for case in cases:
            metadata_filter = _case_filter(case.standard)
            vec = embed_query(case.query)
            dense = dense_search(vec, top_n, metadata_filter)

            t0 = time.perf_counter()
            base_sparse = sparse_search_baseline(case.query, top_n, metadata_filter)
            latencies["baseline"].append(time.perf_counter() - t0)

            sparse_by_cell: dict[str, list[RetrievedChunk]] = {}
            for column, pred in grid:
                label = cell_label(column, pred)
                t0 = time.perf_counter()
                sparse_by_cell[label] = sparse_search_morph(column, pred, case.query, top_n, metadata_filter)
                latencies[label].append(time.perf_counter() - t0)

            fused_ids = [c.chunk_id for c in fuse(dense, base_sparse, 1.0, top_n)]
            live_ids = [c.chunk_id for c in search_chunks(case.query, top_n, metadata_filter)]
            ok = fused_ids == live_ids
            if not ok:
                mismatches.append(case.id)

            gold = gold_para_set(parse_gold_clauses(case.references))
            measured.append({
                "id": case.id,
                "query": case.query,
                "gold": gold,
                "core": resolve_core_paras(case, gold),
                "dense": dense,
                "baseline": base_sparse,
                "sparse": sparse_by_cell,
            })
            counts = "/".join(str(len(sparse_by_cell[cell_label(c, p)])) for c, p in grid)
            print(f"  {case.id}: dense {len(dense)} · baseline {len(base_sparse)} · cells {counts} "
                  f"· self-check {'✓' if ok else '✗'}")
    finally:
        close_pool()

    # ── 채점: baseline은 w=1.0 고정(현행), 셀은 (셀 × w) 조합마다 병합해 채점. ──
    def score(get_sparse, w: float) -> dict:
        first_hits: dict[str, int | None] = {}
        pass_cnt = 0
        for rc in measured:
            contents = [c.content for c in fuse(rc["dense"], get_sparse(rc), w, top_n)]
            fh, _ = rank_hit(contents, rc["gold"], "exact")
            first_hits[rc["id"]] = fh
            pass_cnt += retrieval_pass(contents, rc["core"])
        hit1 = sum(1 for v in first_hits.values() if v == 1)
        hit10 = sum(1 for v in first_hits.values() if v is not None)
        return {"first_hits": first_hits, "retrieval_pass": pass_cnt, "hit1": hit1, "hit10": hit10}

    base = score(lambda rc: rc["baseline"], 1.0)
    base_mrr = _mrr(base["first_hits"], sorted(base["first_hits"]))
    population = judge_adoption(base["first_hits"], base["first_hits"], 0.0)["population"]
    tune_ids, confirm_ids = split_holdout(population)
    print(f"\n홀드아웃: 튜닝 {len(tune_ids)}건 · 확인 {len(confirm_ids)}건 "
          f"(모집단 {len(population)}건 = 전체 {len(measured)} − gold 대기 {len(EXCLUDED_CASE_IDS)})")

    # 튜닝셋 판정은 확인셋을, 확인셋 판정은 튜닝셋을 제외 대상에 더해 각각 독립 모집단으로 만든다.
    exclude_for_tune = EXCLUDED_CASE_IDS | confirm_ids
    exclude_for_confirm = EXCLUDED_CASE_IDS | tune_ids

    results = []
    for column, pred in grid:
        label = cell_label(column, pred)
        # 게이트의 지연 조건에는 이 셀의 sparse 검색 p50을 넣는다.
        # 융합 가중 w는 병합 시점의 곱셈이라 검색 지연과 무관하므로 셀 단위 p50을 전 w에 공유한다.
        p50_s = statistics.median(latencies[label])
        for w in FUSION_WEIGHTS:
            cand = score(lambda rc, _l=label: rc["sparse"][_l], w)
            results.append({
                "cell": label,
                "column": column,
                "predicate": pred,
                "w": w,
                "hit1": cand["hit1"],
                "hit10": cand["hit10"],
                "retrieval_pass": cand["retrieval_pass"],
                "mrr": _mrr(cand["first_hits"], sorted(cand["first_hits"])),
                "first_hits": cand["first_hits"],
                # tune으로 승자를 고르고 confirm으로 일반화를 재확인한다. 
                "tune": judge_adoption(base["first_hits"], cand["first_hits"], p50_s, exclude_for_tune),
                "confirm": judge_adoption(base["first_hits"], cand["first_hits"], p50_s, exclude_for_confirm),
                "full": judge_adoption(base["first_hits"], cand["first_hits"], p50_s),
            })

    # ── 결과 표: Hit@1(주 지표)과 함께 Hit@10·retrieval_pass를 항상 같이 낸다.
    #    낮은 w는 Hit@1을 올리지만 재현율 이득을 버리므로, 그 교환이 표에 보여야 한다.
    #    미충족 사유는 태그로 축약한다(net/MRR/p50)
    #    회귀 케이스 나열까지 든 원문 사유는 표를 부수므로 JSON에만 남긴다.
    def fail_tags(verdict: dict) -> str:
        tags = []
        if verdict["net_gain"] < verdict["min_net_gain"]:
            tags.append("net")
        if verdict["mrr_delta"] <= 0:
            tags.append("MRR")
        if len(verdict["reasons"]) > len(tags):   # 남은 사유는 지연 상한 초과뿐이다
            tags.append("p50")
        return "·".join(tags)

    print(f"\n결과 (k={RRF_K} 고정 · baseline=현행 plainto · 판정=튜닝셋 {len(tune_ids)}건 · "
          f"MRR은 전체 {len(measured)}건 기준):")
    print(f"  {'cell':<17}{'w':>5}{'Hit@1':>7}{'Hit@10':>8}{'pass':>6}{'MRR':>8}{'순증':>5}{'회귀':>5}"
          f"{'net':>5}{'MRRΔ':>9}{'p50ms':>8}  판정")
    print(f"  {'baseline':<17}{1.0:>5}{base['hit1']:>7}{base['hit10']:>8}{base['retrieval_pass']:>6}"
          f"{base_mrr:>8.4f}{'—':>5}{'—':>5}{'—':>5}{'—':>9}"
          f"{statistics.median(latencies['baseline']) * 1000:>8.1f}  (기준)")
    for r in results:
        t = r["tune"]
        mark = "충족" if t["adopt"] else f"미충족({fail_tags(t)})"
        print(f"  {r['cell']:<17}{r['w']:>5}{r['hit1']:>7}{r['hit10']:>8}{r['retrieval_pass']:>6}"
              f"{r['mrr']:>8.4f}{len(t['gains']):>5}{len(t['regressions']):>5}{t['net_gain']:>+5}"
              f"{t['mrr_delta']:>+9.4f}"
              f"{statistics.median(latencies[r['cell']]) * 1000:>8.1f}  {mark}")

    # ── 승자 선택 + 홀드아웃 확인: 튜닝셋에서 고른 셀이 확인셋에서도 기준을 넘는가. ──
    winner = select_winner(results)
    print("\n선택 (사전 확정 규칙: 튜닝셋 통과 셀 중 net 최대 · 동점 시 MRRΔ 최대):")
    if winner is None:
        print("  통과 셀 없음 — 이 스택에서 배포 가능한 sparse 구성이 없다는 뜻이다.")
    else:
        t, c, full = winner["tune"], winner["confirm"], winner["full"]
        confirm_mark = "기준 충족(일반화 확인)" if c["adopt"] else "미충족: " + "; ".join(c["reasons"])
        full_mark = "기준 충족" if full["adopt"] else "미충족: " + "; ".join(full["reasons"])
        print(f"  튜닝셋 승자: {winner['cell']} w={winner['w']} "
              f"(net {t['net_gain']:+d}/기준 {t['min_net_gain']} · MRRΔ {t['mrr_delta']:+.4f})")
        print(f"  확인셋 재검: net {c['net_gain']:+d}/기준 {c['min_net_gain']} · "
              f"MRRΔ {c['mrr_delta']:+.4f} → {confirm_mark}")
        print(f"  전체 모집단({len(full['population'])}건) 판정: net {full['net_gain']:+d}/기준 {full['min_net_gain']} · "
              f"MRRΔ {full['mrr_delta']:+.4f} → {full_mark}")
        print(f"  교환 명시: Hit@1 {base['hit1']}→{winner['hit1']} · "
              f"Hit@10 {base['hit10']}→{winner['hit10']} · pass {base['retrieval_pass']}→{winner['retrieval_pass']}")

    # ── 산출물: 케이스별 dense/셀별 sparse 전체를 남긴다.
    #    이 덤프가 있으면 가중 격자는 재검색 없이 결정적으로 재계산되므로, 이후 w 재판정에 DB가 필요 없다.
    ts = datetime.now(KST)
    result = {
        "generated_at": ts.isoformat(),
        "corpus": {"n_chunks": n_chunks, "chapters": chapters},
        "rrf_k": RRF_K,
        "top_n": top_n,
        "grid": {
            "columns": {c: list(t) if t else None for c, t in MORPH_COLUMNS.items()},
            "predicates": PREDICATES,
            "fusion_weights": list(FUSION_WEIGHTS),
        },
        "gate": {
            "source": "scripts/rerank_replay.py::judge_adoption",
            "selection_rule": "튜닝셋 통과 셀 중 net_gain 최대, 동점 시 MRRΔ 최대",
        },
        "holdout": {"tune": sorted(tune_ids), "confirm": sorted(confirm_ids)},
        "selfcheck_mismatches": mismatches,
        "latency_s": {
            label: {"p50": round(statistics.median(ls), 4), "max": round(max(ls), 4)}
            for label, ls in latencies.items() if ls
        },
        "baseline": {**base, "mrr": base_mrr},
        "results": results,
        "winner": None if winner is None else {"cell": winner["cell"], "w": winner["w"]},
        "cases": [
            {
                "case_id": rc["id"],
                "query": rc["query"],
                "dense": [c.model_dump() for c in rc["dense"]],
                "baseline": [c.model_dump() for c in rc["baseline"]],
                "sparse": {label: [c.model_dump() for c in chunks] for label, chunks in rc["sparse"].items()},
            }
            for rc in measured
        ],
    }
    out_path = Path(out_dir) / f"sparse_morph_replay_{ts.strftime('%Y%m%d_%H%M')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out_path}")

    if mismatches:
        print(f"self-check 실패 {len(mismatches)}건: {mismatches} — 판정 신뢰 불가", file=sys.stderr)
        return 1
    print("self-check 전 케이스 통과 — 오프라인 병합 경로가 라이브와 동일")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="배포 가능 sparse 셀 실측 — 형태소 사전토큰화 × 술어 × 융합 가중"
    )
    parser.add_argument("--out-dir", default="docs/benchmark", help="산출물 저장 디렉토리")
    parser.add_argument("--top-n", type=int, default=TOP_N, help="사이드별 검색 상위 N (기본 10)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_measure(args.out_dir, args.top_n)


if __name__ == "__main__":
    raise SystemExit(main())
