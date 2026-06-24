"""
NFR-002 벤치마크 조항정확도 측정 공용 모듈

`scripts/benchmark_baseline.py`(독립 스크립트)와 Phase 2 관리 테스트
(`tests/integration/test_benchmark_accuracy.py`)가 동일한 측정 로직을 공유하도록, 조항키 매칭·케이스 측정·집계·리포트 생성을 한 곳으로 모은 모듈이다.
(scripts/ 는 __init__.py 없는 비패키지이므로, 공용 로직은 tests/ 트리의 이 모듈에 두고 스크립트·테스트가 단방향으로 import 한다.)

측정 지표(각 케이스별):
  - legacy_substring : 현행 test_reference_coverage 방식 재현(정답 라벨 문자열이 citation 본문에 부분일치하는가)
  - clause_exact     : 정규화 조항키 정확 매칭 (문단번호 집합 교집합)
  - clause_prefix    : 계층(prefix) 매칭 (gold "2.6.5" ↔ 청크 "2.6" 허용)
  - is_answerable    : 가드레일 지표

각 조항키 지표는 검색단계와 생성단계에서 각각 측정하여
"검색이 못 찾은 것"과 "찾았는데 인용에서 누락된 것"을 분리한다.
함께 Hit@1 / Hit@k / MRR / Recall, CRAG 루프 횟수, 재작성 전략, needs_external 판정, 에러 로그를 기록한다.

전제: pgvector(Docker) + 라이브 LLM. benchmark.jsonl은 K-GAAP 14건이고 적재 데이터도 GAAP뿐이므로,
gold references 중 "일반기업회계기준 …" 항목만 채점 대상으로 삼는다(K-IFRS 라벨은 미적재 → 채점 제외).
"""
from __future__ import annotations

import os
import re
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from src.utils.config import KST
from tests.utils.benchmark_loader import BenchmarkCase

# NFR-002 정확도 목표(리포트 갭 표기용, 하드게이트 아님)
NFR_002_TARGET = 0.90

# 검색 통과 기준: 핵심 조항이 검색 Top-N 안에 있으면 통과
RETRIEVAL_PASS_TOP_N = 5


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


def resolve_core_paras(case: BenchmarkCase, gold_paras: set[str]) -> set[str]:
    """핵심(core) 문단집합을 정규화해 반환한다. case.core_paras 미지정 시 gold 전체를 핵심으로 간주."""
    return {_normalize_para(p) for p in case.core_paras} or gold_paras


def retrieval_pass(
    search_contents: list[str], core_paras: set[str], top_n: int = RETRIEVAL_PASS_TOP_N
) -> bool:
    """핵심 조항이 검색 결과 상위 top_n 안에 있으면 검색 통과(True)."""
    fh, _ = rank_hit(search_contents, core_paras, "exact")
    return fh is not None and fh <= top_n


# ════════════════════════════════ 내용 통과(content_pass) ════════════════════════════════
# 검색 축(retrieval_pass)과 분리된 별도 LLM 판정 축. in-graph evaluate 노드의 CRAG reasoning과는
# 다른 판정으로, "생성된 답변이 기대 정답에 비춰 내용상 적절한가"만 본다(검색·인용 여부 무관)
class ContentVerdict(BaseModel):
    """답변 내용 적절성 LLM 판정 결과."""
    verdict: Literal["pass", "partial", "fail"]
    reasoning: str


CONTENT_JUDGE_PROMPT = """당신은 K-GAAP 회계 전문 평가자입니다. 아래 [질문]에 대한 [실제 답변]이 \
[기대 정답]에 비춰 회계적으로 적절한지 판정하세요. 검색·인용 여부가 아니라 답변 '내용'만 봅니다.

판정 기준:
- pass    : 기대 정답의 핵심 결론·방향과 일치하고 회계적으로 옳음
- partial : 부분적으로 맞으나 핵심 일부가 누락·모호함
- fail    : 핵심 결론이 기대 정답과 어긋나거나 회계적으로 틀림

[질문]
{query}

[기대 정답]
{expected_answer}

[실제 답변]
{answer}
"""


def judge_content(*, query: str, expected_answer: str, answer: str, model=None) -> ContentVerdict:
    """답변 내용 적절성을 LLM으로 판정한다(검색과 무관, 기대 정답 기준).

    model 미지정 시 openai-chat:OPENAI_MODEL로 실행. 테스트는 TestModel 등을 주입해 결정적으로 검증한다.
    """
    from pydantic_ai import Agent
    from src.utils.config import OPENAI_MODEL

    prompt = CONTENT_JUDGE_PROMPT.format(
        query=query, expected_answer=expected_answer, answer=answer
    )
    agent = Agent(model or f"openai-chat:{OPENAI_MODEL}", output_type=ContentVerdict)
    return agent.run_sync(prompt).output


def content_pass(verdict: ContentVerdict) -> bool:
    """내용 통과 = 'pass'만 통과(partial/fail은 불통과)."""
    return verdict.verdict == "pass"


# ════════════════════════════════ 코퍼스 상태 ════════════════════════════════
def get_indexed_chapters() -> set[str]:
    """현재 pgvector chunks 테이블에 적재된 chapter 집합을 조회한다."""
    from src.db.connection import get_pool

    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT metadata->>'chapter' FROM chunks")
        return {r[0] for r in cur.fetchall() if r[0]}


def get_chunk_count() -> int:
    """현재 pgvector chunks 테이블의 전체 청크 수를 조회한다(코퍼스 가드용)."""
    from src.db.connection import get_pool

    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM chunks")
        return int(cur.fetchone()[0])


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


def measure_case(case: BenchmarkCase, k: int) -> CaseResult:
    """단일 벤치마크 케이스를 실제 워크플로우로 1회 관통시켜 전 지표를 산출한다."""
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
        # 케이스 식별 정보를 LangSmith 트레이스에 부착. 트레이싱 비활성 시 무해하게 무시됨.
        state = run_workflow_to_completion(
            case.query,
            standard_filter=case.standard,
            metadata={"case_id": case.id, "gold": sorted(gold_paras)},
        )
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
    # 핵심(core) 조항이 검색 Top-5 안에 있으면 통과
    metrics["retrieval_pass"] = retrieval_pass(search_contents, resolve_core_paras(case, gold_paras))
    res.metrics = metrics

    # 진단 정보(오답 분석용) + 회계사 검토·content 판정용 전문 영속화
    # answer/eval_reasoning/expected_answer/citations 전문을 저장해 사람·LLM judge가 검토 가능하게 한다.
    rq = state.get("rewritten_query")
    ev = state.get("evaluation")
    res.diag = {
        "strategy": getattr(rq, "strategy", None),
        "rewrite_count": state.get("rewrite_count"),
        "n_retrieved": len(retrieved),
        "n_reranked": len(reranked),
        "n_citations": len(citations),
        "needs_external": getattr(ev, "needs_external", None),
        "eval_reasoning": (getattr(ev, "reasoning", "") or ""),
        "retrieval_chapters": [r.chunk.metadata.chapter for r in reranked][:10],
        "citation_paras": sorted({p for c in citations for p in extract_chunk_paras(c.content)}),
        "query": case.query,
        "expected_answer": case.expected_answer,
        "answer": (fr.answer if fr else ""),
        "citations": cite_contents,
        "error_logs": state.get("error_logs") or [],
    }

    # content_pass(내용 통과) 판정 — 옵트인(CONTENT_JUDGE). 검색축과 분리된 별도 LLM 판정 축.
    # expected_answer 신뢰성 전제
    if os.getenv("CONTENT_JUDGE"):
        try:
            verdict = judge_content(
                query=case.query,
                expected_answer=case.expected_answer,
                answer=(fr.answer if fr else ""),
            )
            res.metrics["content_pass"] = content_pass(verdict)
            res.diag["content_verdict"] = verdict.verdict
            res.diag["content_reasoning"] = verdict.reasoning
        except Exception as e:  # 판정 실패는 케이스를 죽이지 않음(내용축만 누락)
            res.diag["content_judge_error"] = f"{type(e).__name__}: {e}"
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
        "retrieval_pass",               # 검색 통과(핵심 Top-5)
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
    # 내용 통과: 판정이 수행된 케이스에 한해 별도 분모로 집계한다.
    # (검색 축과 분리. 미판정 케이스는 분모에서 제외 → 기본 측정 동작/요약은 불변)
    content_rows = [r for r in rows if "content_pass" in r.metrics]
    if content_rows:
        ch = sum(1 for r in content_rows if r.metrics["content_pass"])
        summary["content_pass"] = {
            "hits": ch,
            "rate": round(ch / len(content_rows), 4),
            "n": len(content_rows),
        }
    return summary


# ════════════════════════════════ 리포트 ════════════════════════════════
# 리포트 요약표에 노출할 지표(라벨, summary 키). k 의존 키는 caller가 포맷한다.
def _summary_rows(k: int) -> list[tuple[str, str]]:
    return [
        ("생성 조항 Hit@1 (★ NFR-002 1차)", "generation_exact_hit@1"),
        (f"생성 조항 Hit@{k}", f"generation_exact_hit@{k}"),
        ("검색 통과(핵심 Top-5) (★ #163)", "retrieval_pass"),
        ("검색 조항 Hit@1", "retrieval_exact_hit@1"),
        (f"검색 조항 Hit@{k} (★ 비회귀 플로어)", f"retrieval_exact_hit@{k}"),
        ("legacy 문자열(현행 대조군)", "legacy_substring"),
        ("is_answerable (가드레일)", "is_answerable"),
    ]


def write_markdown_report(
    results: list[CaseResult],
    summary: dict,
    *,
    k: int,
    indexed_chapters: list[str],
    n_chunks: int | None,
    use_reranker: bool,
    out_dir: Path | str = "docs/measurements",
    generated_at: datetime | None = None,
) -> Path:
    """사람이 읽을 수 있는 측정 결과 리포트(.md)를 생성하고 경로를 반환한다.

    요약표 + 케이스별 hit/miss + 90% 목표 대비 갭 + USE_RERANKER/적재청크수 메타를 포함한다.
    """
    ts = generated_at or datetime.now(KST)
    stamp = ts.strftime("%Y%m%d_%H%M")
    n = summary.get("n_measured", 0)

    lines: list[str] = []
    lines.append("# 벤치마크 조항정확도 리포트 (NFR-002)")
    lines.append("")
    lines.append(f"- 생성 시각: {ts.isoformat()}")
    lines.append(f"- Hit@k 의 k: {k}")
    lines.append(f"- 적재 장: {len(indexed_chapters)}개")
    lines.append(f"- 적재 청크 수: {n_chunks if n_chunks is not None else '미상'}")
    lines.append(f"- USE_RERANKER: {use_reranker}")
    lines.append(f"- 측정 케이스: {n}건")
    lines.append("")

    # ── 지표 요약 (90% 목표 갭 포함) ──
    lines.append(f"## 지표 요약 (NFR-002 목표 {NFR_002_TARGET:.0%})")
    lines.append("")
    lines.append("| 지표 | 적중 | 비율 | 목표 갭 |")
    lines.append("|------|------|------|---------|")
    for label, key in _summary_rows(k):
        v = summary.get(key)
        if not isinstance(v, dict):
            continue
        rate = v["rate"]
        gap = rate - NFR_002_TARGET
        lines.append(f"| {label} | {v['hits']}/{n} | {rate:.1%} | {gap:+.1%}p |")
    lines.append("")
    lines.append(
        f"- 평균 MRR(exact): 생성 {summary.get('generation_exact_mrr_avg', 0.0)} / "
        f"검색 {summary.get('retrieval_exact_mrr_avg', 0.0)}"
    )
    lines.append("")

    # ── 케이스별 결과 ──
    lines.append("## 케이스별 결과")
    lines.append("")
    lines.append("| 케이스 | 장 | gold 문단 | 검색 exact@k | 생성 exact@1 | answerable | CRAG | 상태 |")
    lines.append("|--------|----|-----------|--------------|--------------|------------|------|------|")
    for r in results:
        if not r.measurable:
            lines.append(f"| {r.case_id} | {r.chapter} | {', '.join(r.gold_paras)} | — | — | — | — | 미적재 SKIP |")
            continue
        if r.error:
            lines.append(f"| {r.case_id} | {r.chapter} | {', '.join(r.gold_paras)} | — | — | — | — | ✗ {r.error[:40]} |")
            continue
        m = r.metrics
        def _mark(b: bool) -> str:
            return "✅" if b else "❌"
        lines.append(
            f"| {r.case_id} | {r.chapter} | {', '.join(r.gold_paras)} | "
            f"{_mark(m.get(f'retrieval_exact_hit@{k}'))} | {_mark(m.get('generation_exact_hit@1'))} | "
            f"{_mark(m.get('is_answerable'))} | {r.diag.get('rewrite_count')} | OK |"
        )
    lines.append("")

    # ── miss 진단 (정답 미적중 케이스) ──
    misses = [
        r for r in results
        if r.measurable and r.error is None and not r.metrics.get(f"retrieval_exact_hit@{k}")
    ]
    if misses:
        lines.append(f"## 검색 미적중 진단 ({len(misses)}건)")
        lines.append("")
        for r in misses:
            lines.append(
                f"- **{r.case_id}** (제{r.chapter}장, gold={r.gold_paras}): "
                f"검색 장={r.diag.get('retrieval_chapters')}, 인용 문단={r.diag.get('citation_paras')}, "
                f"전략={r.diag.get('strategy')}, needs_external={r.diag.get('needs_external')}"
            )
        lines.append("")

    # ── 케이스별 회계사 검토 대조표 ──
    lines.append("## 케이스별 회계사 검토 대조표")
    lines.append("")
    lines.append(
        "> 케이스별 [질문 · 예상정답+근거 · 실제답변+근거 · 판정]을 대조한다. "
        "⑤ 회계사 검토란을 직접 채워 답변 정확성·근거 적절성을 판정한다."
    )
    lines.append("")

    def _mk(b) -> str:
        return "✅" if b else "❌"

    for r in results:
        if not r.measurable or r.error:
            continue
        d, m = r.diag, r.metrics
        lines.append(f"### {r.case_id} (제{r.chapter}장)")
        lines.append("")
        lines.append(
            f"**판정:** 검색통과(핵심Top-5) {_mk(m.get('retrieval_pass'))} · "
            f"검색 exact@{k} {_mk(m.get(f'retrieval_exact_hit@{k}'))} · "
            f"생성 exact@1 {_mk(m.get('generation_exact_hit@1'))} · "
            f"answerable {_mk(m.get('is_answerable'))} · CRAG {d.get('rewrite_count')}"
        )
        lines.append("")
        lines.append("**① 질문**  ")
        lines.append(d.get("query") or "")
        lines.append("")
        lines.append("**② 예상 정답**  ")
        lines.append(d.get("expected_answer") or "")
        lines.append("")
        lines.append(f"**②' 예상 근거(gold)**: {', '.join(r.gold_paras) or '—'}")
        lines.append("")
        lines.append("**③ 실제 답변**  ")
        lines.append(d.get("answer") or "(답변 없음)")
        lines.append("")
        lines.append(
            f"**③' 실제 근거(인용 문단)**: {', '.join(d.get('citation_paras') or []) or '—'}  ·  "
            f"검색된 장: {d.get('retrieval_chapters') or []}"
        )
        lines.append("")
        if d.get("eval_reasoning"):
            lines.append(f"**④ 판정 근거(LLM eval)**: {d['eval_reasoning']}")
            lines.append("")
        lines.append(
            "**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  "
            "근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: "
        )
        lines.append("")
        lines.append("---")
        lines.append("")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"benchmark_result_{stamp}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
