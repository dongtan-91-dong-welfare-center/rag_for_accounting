"""sparse 검색 2차 실측 하니스 — LLM 키워드를 sparse에 넣어 술어별 재질의·채점 (#211 2차).

[배경] 1차(scripts/sparse_predicate_replay.py)는 질의 문장을 통째로 단어 분해해 OR로 묶었다.
  그러자 "회사가"·"때"·"보유하고" 같은 일반어 토큰이 순위 함수(ts_rank_cd)를 지배해 sparse
  상위 10건이 무관 문서로 채워졌고, 이 노이즈가 RRF 병합에서 dense가 올려둔 정답을 밀어내
  기각됐다(Hit@1 4→3). ts_rank_cd는 BM25가 아니라 IDF(흔한 단어를 자동으로 덜 세는 가중치)가
  없어, 흔한 단어를 스스로 걸러내지 못하는 것이 근본 원인이다.

[목적] rewrite가 뽑을 법한 "깨끗한 키워드"(조사 없는 표준 용어)를 sparse에 넣으면 그 노이즈가
  사라지는지를, 검색 조건식(술어: SQL WHERE 절에 들어가는 검색 조건식)을 바꿔가며 실측한다.
  측정 arm(비교 단위)은 4종이다 — 예로 질의 "회사가 퇴직급여를 어떻게 인식하나요?" 기준:
    plainto     (기준)  원 질의 그대로 plainto_tsquery — 현행 sparse (전 질의 0건, 사실상 dense 단독)
    keyword_and         키워드를 AND로  → "퇴직급여충당부채" & "인식" (둘 다 든 문서만)
    keyword_or          키워드를 OR로   → "퇴직급여충당부채 or 인식" (하나라도 든 문서)
    stopword_or (대조군) 불용어만 걷어낸 원 질의를 OR → "회사가 or 퇴직급여를 or 인식하나요"
  마지막 대조군은 LLM 없이 되는 싼 레버의 천장을 잰다. 비싼 키워드 추출이 그보다 실제로 더
  버는지(특히 질의에 없는 표준 용어를 넣어 어휘 간극을 메우는지)를 한 실행에서 가리는 것이 핵심이다.

[제약] LLM 키워드 추출은 비결정적이라(모델·시점에 따라 출력이 흔들림) 그대로 두면 재실행 때
  판정이 바뀐다 — "실측"이 재현 불가가 된다. 그래서 키워드를 1회만 뽑아
  fixture(tests/fixtures/sparse_keywords_211.json)로 얼려 커밋하고, 채점은 이 고정 fixture에서만
  돈다. 1차의 "LLM 0회·결정적" 성질을 키워드 단계에도 복원하는 장치다.
  운영 스키마(RewrittenQuery)·프롬프트는 건드리지 않는다 — 측정이 아래 기준을 통과할 때만 운영화한다.

[판정 기준] (측정 전 확정, 1차·#159와 동일)
  Hit@1(정답 조항이 검색 1위인 질의 수) 순증 ≥ +2 · 기존 1위 회귀 0 · MRR(정답 순위 역수 평균)
  Δ>0 · sparse SQL 지연 p50(중앙값) ≤ 1s · k=RRF_K(60) 고정. 판정 모집단은 gold(정답 라벨)
  확정 대기 3건을 뺀 11건. 정성으로는 1차가 해친 004·007·010·014가 회복되는지, 1차가 못 구제한
  미검출 5건(특히 011 — 질의 "순액으로만 표시"에 없는 "상계"를 키워드가 넣어야 잡힌다)을 본다.

사용 (호스트 실행, DB 기동·chunks 적재 전제):
  # 최초 1회 — LLM로 키워드를 뽑아 fixture 생성 (OPENAI_API_KEY 필요)
  uv run python scripts/sparse_keyword_replay.py --refresh-keywords
  # 이후 — 고정된 fixture로 결정적 재실측
  uv run python scripts/sparse_keyword_replay.py
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

from src.models.schemas import RetrievedChunk  # noqa: E402
from src.utils.config import KST, OPENAI_MODEL, RRF_K  # noqa: E402
from scripts.rerank_replay import SWEEP_KS, TOP_N, _mrr, fuse_top_n, judge_adoption  # noqa: E402
from scripts.sparse_predicate_replay import (  # noqa: E402
    PREDICATES,
    SMOKE_QUERIES,
    sparse_search_predicate,
    tokenize,
)

# 키워드 fixture — LLM 출력을 얼려 커밋하는 파일. 채점은 항상 이 파일에서만 읽어 결정적으로 돈다.
KEYWORD_FIXTURE = _ROOT / "tests" / "fixtures" / "sparse_keywords_211.json"

# 불용어(stopword) — 홀로 선 일반어·의문사만 담은 최소 목록.
# 'simple' 토크나이저는 형태소 분석이 없어 조사가 붙은 채로 한 토큰이 되므로("회사가"는
# "회사"+조사가 아니라 한 덩어리), 이 목록은 "및"·"때"처럼 홀로 선 일반어만 잡을 수 있고
# "회사가"·"보유하고"처럼 조사 부착 내용어는 못 잡는다. 이 천장(#81 형태소 트랙에서 기각된 한계)을
# 그대로 드러내는 것이 이 대조군의 목적이라, 목록을 벤치마크에 맞춰 늘리지 않는다.
STOPWORDS: frozenset[str] = frozenset({
    "어떻게", "무엇", "무엇인가", "무엇인가요", "언제", "왜", "어디", "어디서",
    "얼마", "얼마나", "어느", "어떤", "무슨",
    "및", "또는", "그리고", "혹은", "등", "등의",
    "때", "경우", "관련", "대한", "대해", "위한", "위해",
})

# 프로토타입 키워드 추출 프롬프트 — 이 스크립트 안에만 산다(운영 프롬프트 미반영).
# 측정이 판정 기준을 통과할 때만 운영 rewrite로 옮긴다.
KEYWORD_PROMPT: str = """당신은 한국 회계기준서 검색을 위한 키워드 추출기입니다.
아래 질의에서 관련 조항을 찾는 데 가장 변별력 있는 회계 용어를 2~5개 뽑으세요.

규칙:
- 조사·의문사·일반어("회사가", "어떻게", "때")는 빼고, 기준서에 실릴 표준 용어형(명사)으로만 씁니다.
- 질의가 개념을 풀어 썼다면 기준서의 표준 용어를 추가하세요. 예: "순액으로만 표시" → "상계".

질의: {query}

반드시 JSON으로만 답하세요:
{{"keywords": ["용어1", "용어2"]}}"""


def strip_stopwords(query: str) -> str:
    """질의에서 불용어 토큰을 걷어내고 남은 토큰을 공백으로 잇는다.

    예: "퇴직급여 및 인식 시점은 언제" → "퇴직급여 인식 시점은" ("및"·"언제" 제거)
    남는 토큰이 없으면 빈 문자열을 돌려주고, 이 경우 sparse는 0건으로 처리된다.
    """
    return " ".join(t for t in tokenize(query) if t not in STOPWORDS)


def _kw_str(keywords_by_case: dict[str, list[str]], case_id: str) -> str:
    """케이스별 키워드 리스트를 검색식 입력용 공백 연결 문자열로 만든다.

    예: ["퇴직급여충당부채", "인식"] → "퇴직급여충당부채 인식"
    fixture에 없거나 빈 리스트면 빈 문자열 → sparse_search_predicate가 0건으로 처리한다.
    """
    return " ".join(keywords_by_case.get(case_id, []))


# 측정 arm — (표시 키) → (술어 키, 입력 소스 함수).
#   입력 소스 함수는 (case, 키워드 fixture)를 받아 검색식에 넣을 원문 문자열을 만든다.
#   술어는 1차에서 안전성이 실증된 plainto/or만 재사용한다(신규 raw 조립 없음):
#     plainto = plainto_tsquery('simple', 입력)      — 입력의 전 단어 AND
#     or      = websearch_to_tsquery('simple', 'a or b') — OR
ARMS: dict[str, tuple[str, Callable]] = {
    "plainto":     ("plainto", lambda case, kws: case.query),                # 기준: 현행 sparse와 동일
    "keyword_and": ("plainto", lambda case, kws: _kw_str(kws, case.id)),     # 키워드 AND
    "keyword_or":  ("or",      lambda case, kws: _kw_str(kws, case.id)),     # 키워드 OR
    "stopword_or": ("or",      lambda case, kws: strip_stopwords(case.query)),  # 불용어 제거 + OR (대조군)
}


def _arm_sparse(arm_key, case, keywords, top_n, metadata_filter=None):
    """arm의 (술어, 입력)을 풀어 1차의 sparse_search_predicate로 실행한다(운영과 동일 경로)."""
    pred_key, input_fn = ARMS[arm_key]
    return sparse_search_predicate(pred_key, input_fn(case, keywords), top_n, metadata_filter)


def _arm_input_tokens(arm_key, case, keywords) -> list[str]:
    """arm이 실제로 검색에 쓴 입력의 토큰 — 정성 증거(어떤 토큰이 gold를 끌어올렸나)용."""
    _pred_key, input_fn = ARMS[arm_key]
    return tokenize(input_fn(case, keywords))


def extract_keywords(query: str) -> list[str]:
    """질의에서 검색용 키워드를 LLM으로 뽑는다. 실패 시 빈 리스트(폴백은 호출자가 판단)."""
    from src.utils.llm_client import client

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": KEYWORD_PROMPT.format(query=query)}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    data = json.loads(resp.choices[0].message.content)
    kws = data.get("keywords", [])
    # 문자열 리스트만 통과시킨다(LLM이 딕셔너리·숫자를 섞어 넣는 경우 방어)
    return [str(k).strip() for k in kws if str(k).strip()]


def load_or_build_keywords(cases, refresh: bool) -> dict[str, list[str]]:
    """키워드를 fixture에서 읽거나(결정적 재실측), 없거나 refresh면 LLM으로 뽑아 저장한다.

    fixture가 있으면 그대로 읽어 재현성을 보장하고, refresh=True이거나 파일이 없을 때만
    LLM을 호출한다(호출 시 사용 모델을 함께 기록해 감사 가능하게 한다).
    """
    if KEYWORD_FIXTURE.exists() and not refresh:
        data = json.loads(KEYWORD_FIXTURE.read_text(encoding="utf-8"))
        return data["keywords"]

    print(f"키워드 추출(LLM {len(cases)}회, model={OPENAI_MODEL}) — fixture 생성 중…")
    keywords = {}
    for case in cases:
        keywords[case.id] = extract_keywords(case.query)
        print(f"  {case.id}: {keywords[case.id]}")
    payload = {
        "generated_at": datetime.now(KST).isoformat(),
        "model": OPENAI_MODEL,
        "prompt": KEYWORD_PROMPT,
        "keywords": keywords,
    }
    KEYWORD_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    KEYWORD_FIXTURE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"fixture 저장: {KEYWORD_FIXTURE}")
    return keywords


def run_measure(out_dir: str, top_n: int, ks: tuple[int, ...], refresh: bool) -> int:
    """벤치마크 전 질의를 arm별로 재질의하고, 결과를 채점해 채택 여부를 판정한다.

    흐름: 키워드 확보(fixture/LLM) → 안전 점검 → arm별 검색 결과 수집(+self-check) → 채점 → 판정 → 저장.
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
    keywords = load_or_build_keywords(cases, refresh)
    missing = [c.id for c in cases if not keywords.get(c.id)]
    if missing:
        print(f"키워드 없음 {len(missing)}건: {missing} — keyword_* arm이 0건이 된다. "
              f"--refresh-keywords로 재생성 필요", file=sys.stderr)

    init_pool()
    try:
        n_chunks = get_chunk_count()
        chapters = sorted(get_indexed_chapters(), key=int)
        print(f"코퍼스: {n_chunks}청크 · {len(chapters)}장 · RRF_K={RRF_K} · top_n={top_n}")

        # ── 특수문자 안전 점검: arm이 쓰는 술어(plainto/or)에 위험한 꼴 질의를 실제 실행.
        #    SQL 문법 오류가 나면 여기서 중단된다(1차가 실증한 술어라 재현 확인 목적).
        used_preds = sorted({pred for pred, _ in ARMS.values()})
        for pred in used_preds:
            for q in SMOKE_QUERIES:
                sparse_search_predicate(pred, q, top_n)
        print(f"특수문자 스모크 통과: {len(used_preds)}술어 × {len(SMOKE_QUERIES)}질의 — 예외 0")

        # ── arm별 검색 결과 수집: dense 1회 + arm별 sparse.
        #    self-check: plainto arm(원 질의+plainto술어)의 오프라인 병합이 라이브 search_chunks와
        #    같아야(현행 동작 동일) 이 하니스의 측정을 신뢰할 수 있다.
        measured = []
        mismatches = []
        latencies: dict[str, list[float]] = {arm: [] for arm in ARMS}
        for case in cases:
            metadata_filter = _case_filter(case.standard)
            vec = embed_query(case.query)
            dense = dense_search(vec, top_n, metadata_filter)

            sparse_by_arm: dict[str, list[RetrievedChunk]] = {}
            for arm in ARMS:
                t0 = time.perf_counter()
                sparse_by_arm[arm] = _arm_sparse(arm, case, keywords, top_n, metadata_filter)
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
                "keywords": keywords.get(case.id, []),
                "tokens": {arm: _arm_input_tokens(arm, case, keywords) for arm in ARMS},
                "gold": gold,
                "core": resolve_core_paras(case, gold),
                "dense": dense,
                "sparse": sparse_by_arm,
            })
            counts = "/".join(str(len(sparse_by_arm[a])) for a in ARMS)
            print(f"  {case.id}: dense {len(dense)} · sparse {counts} ({'/'.join(ARMS)}) "
                  f"· self-check {'✓' if ok else '✗'}")
    finally:
        close_pool()

    # ── 채점: arm별로 dense와 sparse를 RRF로 합친 뒤 정답 조항 최초 등장 순위(first_hit)를 기록.
    #    병합은 운영과 동일한 fuse_top_n, k는 여러 값을 돌려 민감도도 본다.
    scores: dict[int, dict[str, dict]] = {}
    for k in ks:
        scores[k] = {}
        for arm in ARMS:
            by_case: dict[str, int | None] = {}
            pass_cnt = 0
            for rc in measured:
                contents = [c.content for c in fuse_top_n(rc["dense"], rc["sparse"][arm], k=k, n=top_n)]
                fh, _ = rank_hit(contents, rc["gold"], "exact")
                by_case[rc["id"]] = fh
                pass_cnt += retrieval_pass(contents, rc["core"])
            scores[k][arm] = {"first_hits": by_case, "retrieval_pass": pass_cnt}

    # ── 정성 증거: arm sparse가 정답 조항을 몇 위로 잡았고, 그 arm 입력의 어떤 토큰이
    #    실제 본문에 등장했는지 기록("무엇이 정답을 끌어올렸나"). keyword arm이면 토큰=키워드 ──
    evidence: dict[str, dict[str, dict]] = {}
    for arm in ARMS:
        evidence[arm] = {}
        for rc in measured:
            for rank, chunk in enumerate(rc["sparse"][arm], start=1):
                if extract_chunk_paras(chunk.content) & rc["gold"]:
                    evidence[arm][rc["id"]] = {
                        "sparse_rank": rank,
                        "matched_tokens": [t for t in rc["tokens"][arm] if t in chunk.content],
                    }
                    break

    # ── 판정: 사전 확정 기준으로 arm별 채택/롤백. 비교 기준(baseline)은 plainto, k는 RRF_K 고정 ──
    n = len(measured)
    base_fh = scores[RRF_K]["plainto"]["first_hits"]
    print(f"\n판정 (k={RRF_K} 고정 · baseline=plainto · 모집단 {len(judge_adoption(base_fh, base_fh, 0)['population'])}건):")
    verdicts: dict[str, dict] = {}
    for arm in ARMS:
        fhs = scores[RRF_K][arm]["first_hits"]
        p50 = statistics.median(latencies[arm])
        hit1 = sum(1 for v in fhs.values() if v == 1)
        line = (f"  {arm:<12} Hit@1 {hit1}/{n} · MRR {_mrr(fhs, sorted(fhs)):.4f} "
                f"· pass {scores[RRF_K][arm]['retrieval_pass']}/{n} · sparse p50 {p50*1000:.1f}ms")
        if arm == "plainto":
            print(line + " · (baseline)")
            continue
        verdicts[arm] = judge_adoption(base_fh, fhs, p50)
        v = verdicts[arm]
        mark = "채택기준 충족" if v["adopt"] else f"미충족: {'; '.join(v['reasons'])}"
        print(line + f" · 순증{v['gains']} 회귀{v['regressions']} MRRΔ{v['mrr_delta']:+.4f} → {mark}")

    # ── 케이스별 first_hit 테이블 (정답 조항이 처음 등장한 순위, None=top{n} 미검출) ──
    print(f"\n케이스별 first_hit (k={RRF_K}, None=top{top_n} 미검출):")
    print(f"  {'case_id':<18}" + "".join(f"{a:>13}" for a in ARMS))
    for rc in measured:
        row = f"  {rc['id']:<18}"
        for arm in ARMS:
            row += f"{str(scores[RRF_K][arm]['first_hits'][rc['id']]):>13}"
        print(row)

    # ── k 민감도 (sparse 활성 상태에서 k 레버 효과 참고용, 판정 변수 아님) ──
    print("\nk 민감도 (Hit@1, 부수 기록):")
    for k in ks:
        cells = " · ".join(
            f"{a} {sum(1 for v in scores[k][a]['first_hits'].values() if v == 1)}" for a in ARMS
        )
        print(f"  k={k:>3}: {cells}")

    # ── 산출물 저장: 원본 JSON은 git 추적 제외(판정 리포트 md만 수기 커밋, 1차 관행) ──
    ts = datetime.now(KST)
    result = {
        "generated_at": ts.isoformat(),
        "keyword_model": OPENAI_MODEL,
        "corpus": {"n_chunks": n_chunks, "chapters": chapters},
        "rrf_k": RRF_K,
        "ks": list(ks),
        "top_n": top_n,
        "arms": {arm: {"predicate": pred} for arm, (pred, _fn) in ARMS.items()},
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
                "keywords": rc["keywords"],
                "dense": [c.model_dump() for c in rc["dense"]],
                "sparse": {arm: [c.model_dump() for c in chunks] for arm, chunks in rc["sparse"].items()},
            }
            for rc in measured
        ],
    }
    out_path = Path(out_dir) / f"sparse_keyword_replay_{ts.strftime('%Y%m%d_%H%M')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out_path}")

    if mismatches:
        print(f"self-check 실패 {len(mismatches)}건: {mismatches} — 판정 신뢰 불가", file=sys.stderr)
        return 1
    print("self-check 전 케이스 통과 — 오프라인 병합 경로가 라이브와 동일")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="sparse 2차 실측 — LLM 키워드 × 술어 arm 재질의·채점 (#211)")
    parser.add_argument("--out-dir", default="docs/measurements", help="산출물 저장 디렉토리")
    parser.add_argument("--top-n", type=int, default=TOP_N, help="사이드별 검색 상위 N (기본 10)")
    parser.add_argument("--ks", default=",".join(map(str, SWEEP_KS)), help="RRF k 목록 (쉼표 구분, 판정은 RRF_K 고정)")
    parser.add_argument("--refresh-keywords", action="store_true",
                        help="fixture를 무시하고 LLM으로 키워드를 다시 뽑아 저장 (OPENAI_API_KEY 필요)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ks = tuple(int(x) for x in args.ks.split(","))
    if RRF_K not in ks:
        ks = (RRF_K,) + ks  # 판정 k는 항상 포함
    return run_measure(args.out_dir, args.top_n, ks, args.refresh_keywords)


if __name__ == "__main__":
    raise SystemExit(main())
