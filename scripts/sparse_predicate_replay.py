"""sparse 검색 조건(술어) 후보 실측 하니스 — 후보별 DB 재질의 + 검색 결과 덤프·채점.

[배경] 이 시스템의 검색은 두 갈래 결과를 합친다:
  dense  — 질의를 숫자 벡터로 바꿔 "의미가 비슷한" 문서를 찾는 검색
  sparse — 질의에 든 "단어가 실제로 등장하는" 문서를 찾는 키워드 검색
현행 sparse가 쓰는 plainto_tsquery는 질의의 모든 단어가 다 들어있는 문서만 찾는
AND 방식이라, 문장형 질의(벤치마크 14건 전부)에서 0건을 반환한다 — 사실상 dense 단독 동작.

[목적] AND를 "단어 중 하나라도 들어있으면 매칭"(OR)으로 바꾸는 후보 3종을 LLM 호출 없이
실측 비교한다. 여기서 술어(predicate)란 SQL WHERE 절에 들어가는 검색 조건식을 말한다.
현행 plainto가 비교 기준(baseline):
  or                 후보① 질의를 단어로 쪼개 ' or '로 연결 → websearch_to_tsquery
                     (예: "퇴직급여 인식" → "퇴직급여 or 인식")
  or_prefix          후보② 단어마다 앞부분 일치(:*)를 허용하고 '|'(OR)로 연결 → to_tsquery
                     (예: "'퇴직급여':* | '인식':*" — "퇴직급여를"처럼 조사가 붙어도 매칭)
  websearch_control  대조군③ 원 질의 그대로 websearch_to_tsquery
                     (plainto와 같은 AND 연결이므로 0건이 그대로 재현되는지 확인하는 용도)

[안전 제약] 사용자 질의를 to_tsquery 입력에 문자열로 이어붙이는 조립은 금지 —
특수문자 질의가 SQL 문법 오류(ProgrammingError)를 내면 재시도 불가 정책상 파이프라인이
즉시 중단되기 때문. or_prefix는 특수문자를 걷어낸 토큰만 따옴표로 감싸 조립하므로
문법 오류가 구조적으로 불가능하며, 측정 전 특수문자 스모크로 이를 실증한다.

[채택/롤백 기준] (측정 전에 확정해 둔 기준, k=RRF_K 고정 판정)
  Hit@1(정답 조항이 검색 1위에 나온 질의 수) 순증 ≥ +2건
  AND 기존 1위 케이스가 밀려나는 회귀 0건
  AND MRR(정답의 등장 순위 역수 평균, 높을수록 상위 노출) 순증 > 0
  AND 쿼리당 sparse SQL 지연 p50(중앙값) ≤ 1s.
  판정 모집단은 gold(정답 조항 라벨) 확정 대기 3건을 제외한 11건.

사용 (호스트 실행, DB 기동·chunks 적재 전제):
  uv run python scripts/sparse_predicate_replay.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from psycopg import sql  # noqa: E402

from src.models.schemas import RetrievedChunk  # noqa: E402
from src.retrieval.searcher import _build_where_clause, _execute_search_query  # noqa: E402
from src.utils.config import CHUNKS_TABLE, KST, RRF_K  # noqa: E402
from scripts.rerank_replay import SWEEP_KS, TOP_N, _mrr, fuse_top_n, judge_adoption  # noqa: E402


def tokenize(query: str) -> list[str]:
    """질의를 단어문자(\\w: 한글·영숫자·밑줄)가 이어지는 단위로 쪼갠다.

    예: "퇴직급여충당부채는 어떻게 인식하나요?" → ["퇴직급여충당부채는", "어떻게", "인식하나요"]
    따옴표나 tsquery 연산자(& | ! : * 괄호) 같은 특수문자는 토큰에 남지 않으므로,
    이 토큰으로 조립한 검색식은 SQL 문법 오류가 구조적으로 불가능하다.
    """
    return re.findall(r"\w+", query)


def build_or_input(query: str) -> str:
    """후보① — 단어들을 ' or '로 연결한다. websearch_to_tsquery가 or를 OR 연산자로 해석한다.

    예: "퇴직급여 인식" → "퇴직급여 or 인식" (둘 중 하나라도 등장하는 문서가 매칭)
    """
    return " or ".join(tokenize(query))


def build_or_prefix_input(query: str) -> str:
    """후보② — 단어마다 앞부분 일치 표기("'단어':*")를 만들어 '|'(OR)로 연결한다.

    예: "퇴직급여 인식" → "'퇴직급여':* | '인식':*"
    :*는 그 단어로 시작하는 모든 형태를 매칭한다("퇴직급여를"처럼 조사가 붙어도 잡힘).
    따옴표는 to_tsquery가 단어 내용을 연산자로 오해하지 않게 하는 안전장치다.
    """
    return " | ".join(f"'{t}':*" for t in tokenize(query))


# 검색 조건(술어) 후보 목록.
#   tsquery     — SQL에 들어갈 질의 변환식 (%s 자리에 값이 1회 바인딩된다)
#   build_input — 그 %s 자리에 바인딩할 문자열을 만드는 함수
PREDICATES: dict[str, dict] = {
    "plainto": {
        "tsquery": "plainto_tsquery('simple', %s)",
        "build_input": lambda q: q,
    },
    "or": {
        "tsquery": "websearch_to_tsquery('simple', %s)",
        "build_input": build_or_input,
    },
    "or_prefix": {
        "tsquery": "to_tsquery('simple', %s)",
        "build_input": build_or_prefix_input,
    },
    "websearch_control": {
        "tsquery": "websearch_to_tsquery('simple', %s)",
        "build_input": lambda q: q,
    },
}

# 안전 점검용 질의 — 빈 질의·SQL 주입 꼴·tsquery 연산자 꼴. 모든 후보가
# 예외 없이 통과해야(결과 0건은 무방) 측정을 진행한다.
SMOKE_QUERIES = (
    "",
    "???",
    "'; DROP TABLE chunks;--",
    "퇴직 & 연금 | !급여 (:*)",
    "K-IFRS 제1019호",
)


def sparse_search_predicate(
    pred_key: str, query: str, top_k: int, metadata_filter: dict | None = None, collection: str = CHUNKS_TABLE
) -> list[RetrievedChunk]:
    """운영 코드(searcher.sparse_search)와 같은 구조로 검색 조건식만 바꿔 실행한다.

    searcher의 내부 함수를 재사용하므로 실측이 운영과 동일한
    타임아웃·예외 정책 경로를 탄다 — 측정 결과를 운영 채택 근거로 쓸 수 있는 이유.
    """
    spec = PREDICATES[pred_key]
    ts_input = spec["build_input"](query)
    if not ts_input:
        return []  # 특수문자뿐인 질의라 남은 단어가 없음 — 검색식을 만들 수 없다 (0건 확정)

    filter_clause, filter_params = _build_where_clause(metadata_filter)
    match_expr = f"to_tsvector('simple', content) @@ {spec['tsquery']}"
    where_sql = f"{filter_clause} AND {match_expr}" if filter_clause else f" WHERE {match_expr}"

    query_sql = sql.SQL("""
        SELECT chunk_id, document_id, content, metadata,
               ts_rank_cd(to_tsvector('simple', content), {tsq}) AS score
        FROM {table}
        {where}
        ORDER BY score DESC
        LIMIT %s
    """).format(tsq=sql.SQL(spec["tsquery"]), table=sql.Identifier(collection), where=sql.SQL(where_sql))
    query_params = [ts_input] + filter_params + [ts_input, top_k]

    return _execute_search_query(query_sql, query_params, f"Sparse[{pred_key}]")


def run_measure(out_dir: str, top_n: int, ks: tuple[int, ...]) -> int:
    """벤치마크 전 질의를 후보별로 DB에 다시 질의하고, 결과를 채점해 채택 여부를 판정한다.

    흐름: 안전 점검 → 질의별 검색 결과 수집(+자체 검증) → 채점 → 판정 → JSON 저장.
    """
    # 호스트 실행 시 DB 호스트 보정 (benchmark_baseline.py와 동일)
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

        # ── 특수문자 안전 점검: 후보별로 위험한 꼴의 질의를 실제 실행해 본다.
        #    SQL 문법 오류(ProgrammingError)가 나면 여기서 그대로 중단된다 — 후보 탈락 근거.
        for pred in PREDICATES:
            for q in SMOKE_QUERIES:
                sparse_search_predicate(pred, q, top_n)
        print(f"특수문자 스모크 통과: {len(PREDICATES)}술어 × {len(SMOKE_QUERIES)}질의 — 예외 0")

        # ── 질의별 검색 결과 수집: dense 1회 + 후보별 sparse.
        #    함께 self-check: 현행 조건(plainto)의 결과를 실제 서비스 검색과
        #    비교해 순서가 같아야 이 하니스의 측정을 신뢰할 수 있다.
        measured = []
        mismatches = []
        latencies: dict[str, list[float]] = {pred: [] for pred in PREDICATES}
        for case in cases:
            metadata_filter = _case_filter(case.standard)
            vec = embed_query(case.query)
            dense = dense_search(vec, top_n, metadata_filter)

            sparse_by_pred: dict[str, list[RetrievedChunk]] = {}
            for pred in PREDICATES:
                t0 = time.perf_counter()
                sparse_by_pred[pred] = sparse_search_predicate(pred, case.query, top_n, metadata_filter)
                latencies[pred].append(time.perf_counter() - t0)

            fused_ids = [c.chunk_id for c in fuse_top_n(dense, sparse_by_pred["plainto"], k=RRF_K, n=top_n)]
            live_ids = [c.chunk_id for c in search_chunks(case.query, top_n, metadata_filter)]
            ok = fused_ids == live_ids
            if not ok:
                mismatches.append(case.id)

            gold = gold_para_set(parse_gold_clauses(case.references))
            measured.append({
                "id": case.id,
                "query": case.query,
                "tokens": tokenize(case.query),
                "gold": gold,
                "core": resolve_core_paras(case, gold),
                "dense": dense,
                "sparse": sparse_by_pred,
            })
            counts = "/".join(str(len(sparse_by_pred[p])) for p in PREDICATES)
            print(f"  {case.id}: dense {len(dense)} · sparse {counts} ({'/'.join(PREDICATES)}) "
                  f"· self-check {'✓' if ok else '✗'}")
    finally:
        close_pool()

    # ── 채점: 후보별로 dense와 sparse를 RRF(순위 기반 병합)로 합친 뒤,
    #    정답 조항이 처음 등장한 순위(first_hit)를 기록한다. 병합은 운영과 동일한 함수를 쓰고,
    #    RRF의 k 상수(순위 간 점수 격차를 조절)는 여러 값을 돌려 민감도도 함께 본다.
    scores: dict[int, dict[str, dict]] = {}
    for k in ks:
        scores[k] = {}
        for pred in PREDICATES:
            by_case: dict[str, int | None] = {}
            pass_cnt = 0
            for rc in measured:
                contents = [c.content for c in fuse_top_n(rc["dense"], rc["sparse"][pred], k=k, n=top_n)]
                fh, _ = rank_hit(contents, rc["gold"], "exact")
                by_case[rc["id"]] = fh
                pass_cnt += retrieval_pass(contents, rc["core"])
            scores[k][pred] = {"first_hits": by_case, "retrieval_pass": pass_cnt}

    # ── 정성 증거: 후보 sparse가 정답 조항을 몇 위로 잡았고,
    #    질의의 어떤 단어가 그 본문에 실제로 등장했는지("무엇이 정답을 끌어올렸나") 기록 ──
    evidence: dict[str, dict[str, dict]] = {}
    for pred in PREDICATES:
        evidence[pred] = {}
        for rc in measured:
            for rank, chunk in enumerate(rc["sparse"][pred], start=1):
                if extract_chunk_paras(chunk.content) & rc["gold"]:
                    evidence[pred][rc["id"]] = {
                        "sparse_rank": rank,
                        "matched_tokens": [t for t in rc["tokens"] if t in chunk.content],
                    }
                    break

    # ── 판정: 모듈 docstring의 사전 확정 기준으로 후보별 채택/롤백을 가른다.
    #    비교 기준(baseline)은 현행 plainto, k는 운영값(RRF_K) 고정 ──
    n = len(measured)
    base_fh = scores[RRF_K]["plainto"]["first_hits"]
    print(f"\n판정 (k={RRF_K} 고정 · baseline=plainto · 모집단 {len(judge_adoption(base_fh, base_fh, 0)['population'])}건):")
    verdicts: dict[str, dict] = {}
    for pred in PREDICATES:
        fhs = scores[RRF_K][pred]["first_hits"]
        p50 = statistics.median(latencies[pred])
        hit1 = sum(1 for v in fhs.values() if v == 1)
        line = (f"  {pred:<18} Hit@1 {hit1}/{n} · MRR {_mrr(fhs, sorted(fhs)):.4f} "
                f"· pass {scores[RRF_K][pred]['retrieval_pass']}/{n} · sparse p50 {p50*1000:.1f}ms")
        if pred == "plainto":
            print(line + " · (baseline)")
            continue
        verdicts[pred] = judge_adoption(base_fh, fhs, p50)
        v = verdicts[pred]
        mark = "채택기준 충족" if v["adopt"] else f"미충족: {'; '.join(v['reasons'])}"
        print(line + f" · 순증{v['gains']} 회귀{v['regressions']} MRRΔ{v['mrr_delta']:+.4f} → {mark}")

    # ── 케이스별 first_hit(정답 조항이 처음 등장한 순위) 테이블 ──
    print(f"\n케이스별 first_hit (k={RRF_K}, None=top{top_n} 미검출):")
    header = f"  {'case_id':<18}" + "".join(f"{p:>18}" for p in PREDICATES)
    print(header)
    for rc in measured:
        row = f"  {rc['id']:<18}"
        for pred in PREDICATES:
            row += f"{str(scores[RRF_K][pred]['first_hits'][rc['id']]):>18}"
        print(row)

    # ── k 민감도: RRF의 k 값을 바꾸면 결과가 얼마나 달라지는지 참고용 기록 (판정에는 쓰지 않음) ──
    print("\nk 민감도 (Hit@1, 부수 기록):")
    for k in ks:
        cells = " · ".join(
            f"{p} {sum(1 for v in scores[k][p]['first_hits'].values() if v == 1)}" for p in PREDICATES
        )
        print(f"  k={k:>3}: {cells}")

    # ── 산출물 저장: 원본 데이터 JSON은 git 추적 제외, 판정 리포트 md만 수기 작성해 커밋 ──
    ts = datetime.now(KST)
    result = {
        "generated_at": ts.isoformat(),
        "corpus": {"n_chunks": n_chunks, "chapters": chapters},
        "rrf_k": RRF_K,
        "ks": list(ks),
        "top_n": top_n,
        "smoke_queries": list(SMOKE_QUERIES),
        "selfcheck_mismatches": mismatches,
        "latency_s": {
            pred: {"p50": round(statistics.median(ls), 4), "max": round(max(ls), 4)}
            for pred, ls in latencies.items()
        },
        "scores": {
            k: {
                pred: {"first_hits": s["first_hits"], "retrieval_pass": s["retrieval_pass"]}
                for pred, s in by_pred.items()
            }
            for k, by_pred in scores.items()
        },
        "verdicts": verdicts,
        "gold_evidence": evidence,
        "cases": [
            {
                "case_id": rc["id"],
                "query": rc["query"],
                "tokens": rc["tokens"],
                "dense": [c.model_dump() for c in rc["dense"]],
                "sparse": {pred: [c.model_dump() for c in chunks] for pred, chunks in rc["sparse"].items()},
            }
            for rc in measured
        ],
    }
    out_path = Path(out_dir) / f"sparse_predicate_replay_{ts.strftime('%Y%m%d_%H%M')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out_path}")

    if mismatches:
        print(f"self-check 실패 {len(mismatches)}건: {mismatches} — 판정 신뢰 불가", file=sys.stderr)
        return 1
    print("self-check 전 케이스 통과 — 오프라인 병합 경로가 라이브와 동일")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="sparse 술어 후보 실측 — 재질의·재덤프·채점 (#211)")
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
