#!/usr/bin/env python
"""pgvector 인덱싱 성능 벤치마크 — 배치 임베딩/적재 지연 측정

`vector_store.index_documents`의 배치 루프(count_tokens → embed_texts → _upsert_batch → _release_heap)를 계측용으로 재현해 구간별 시간을 분해한다.
※ index_documents의 배치 루프 로직이 바뀌면 이 재현(_measure_indexing)도 동기화할 것.

측정 항목:
  - 콜드 스타트: warmup_model() 최초 모델 로드 시간 (요청/측정 경로 밖)
  - 3구간 + gc 잔차: count_tokens(전체 청크) / embed_texts(유효 청크) / _upsert_batch / _release_heap
    분모 구분 — count_tokens는 전체 청크, embed는 IX-201 통과 유효 청크에만 호출
  - 누적 구간: 적재량 0→500→1000 마일스톤별 누적 시간(HNSW 삽입 비선형성)
  - similarity_search: N회 반복 p50/p95, 쿼리 임베딩 시간 분리
  - 환경 스탬프: device/threads/encode_batch_size/pipeline_batch_size(재현성)
  - sanity check: #105 0차(193청크, 탑1 0.7524) 대비 청크당 시간·탑1 스코어
  - 34장 외삽: GAAP 실측 → K-IFRS 20장 외삽(가정 명기)

전용 컬렉션(기본 bench_indexing)에 적재하고 종료 시 정리한다 → 운영 chunks 미오염.
LLM 불필요(라이브 API 미사용). 단 임베딩은 KURE-v1(HF 다운로드) + GPU(MPS는 호스트 실행) 전제.

실행:
  uv run python scripts/benchmark_indexing.py                       # gaap 전 장, bench_indexing
  uv run python scripts/benchmark_indexing.py --chapters 6 8        # 특정 장만(스모크)
  uv run python scripts/benchmark_indexing.py --batch-size 50 --search-iters 30
  uv run python scripts/benchmark_indexing.py --synthetic-oversize 3  # IX-201 스킵 경로 측정
  uv run python scripts/benchmark_indexing.py --keep                # 측정 후 컬렉션 보존(기본 정리)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from time import perf_counter

# ── 프로젝트 루트를 import 경로에 추가 (tests.*, src.* 재사용) ──
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv()
# tests/integration/conftest.py 와 동일하게, 호스트 실행 시 DB 호스트를 localhost로 보정한다.
if os.getenv("POSTGRES_HOST") == "database":
    os.environ["POSTGRES_HOST"] = "localhost"

from datetime import datetime  # noqa: E402

from src.utils.config import (  # noqa: E402
    BATCH_SIZE,
    EMBEDDING_ENCODE_BATCH_SIZE,
    EMBEDDING_MAX_TOKENS,
    KST,
    TOP_K_RETRIEVAL,
)

# #105 0차 스모크 베이스라인 (2026-06-12) — 측정 신뢰 교차 대조용
_SMOKE_BASELINE = {"n_chunks": 193, "top1_score": 0.7524, "source": "#105 2026-06-12"}

# 검색 지연 측정용 대표 질의 (적합성보다 응답 시간이 목적; 탑1 스코어는 첫 질의로 sanity)
_DEFAULT_QUERIES = [
    "재고자산의 취득원가는 어떻게 측정하는가",
    "금융자산의 최초 인식 시점",
    "유형자산의 감가상각 방법",
]


def _percentile(values: list[float], p: float) -> float:
    """정렬 기반 백분위(p∈[0,1]). 빈 입력은 0.0."""
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, int(p * len(s)))
    return s[idx]


def _resolve_env(batch_size: int) -> dict:
    """처리량에 직접 영향을 주는 실행 환경을 결과에 스탬프한다(재현성)."""
    from src.utils.config import EMBEDDING_DEVICE
    from src.utils.embedding import _resolve_device, _resolve_thread_count

    return {
        "device": _resolve_device(EMBEDDING_DEVICE),
        "threads": _resolve_thread_count(),
        "encode_batch_size": EMBEDDING_ENCODE_BATCH_SIZE,
        "pipeline_batch_size": batch_size,
    }


def _load_graph(path: Path):
    """저장된 온톨로지 그래프 JSON을 OntologyGraph로 역직렬화한다(main._load_graph_from_json과 동일)."""
    from src.db.ontology.models import OntologyGraph

    return OntologyGraph.model_validate_json(path.read_text(encoding="utf-8"))


def _synthetic_oversize(n: int) -> list:
    """EMBEDDING_MAX_TOKENS(8192)를 초과하는 합성 청크 n개. IX-201 스킵 경로 측정용.

    2048 상한 청킹(#160) 후 실 청크에는 8192 초과가 없으므로, IX-201 오버헤드는 합성으로만 측정 가능.
    """
    from src.models.schemas import ChunkMetadata, RetrievedChunk

    big = "초과 " * 20000  # KURE-v1 토크나이저 기준 8192 토큰 초과 유도
    return [
        RetrievedChunk(
            chunk_id=f"synth-oversize-{i}",
            document_id="synthetic",
            content=big,
            score=0.0,
            metadata=ChunkMetadata(chapter="synthetic"),
        )
        for i in range(n)
    ]


def _load_chunks(ontology_dir: Path, chapters: list[str] | None, synthetic_oversize: int) -> list:
    """data/ontology/gaap-ch*.json → chunk_graph로 실 청크 생성. 합성 초과 청크 보강."""
    from src.db.ontology.chunker import chunk_graph

    json_files = sorted(ontology_dir.glob("gaap-ch*.json"))
    if chapters:
        wanted = {f"gaap-ch{c}.json" for c in chapters}
        json_files = [f for f in json_files if f.name in wanted]

    chunks: list = []
    for jf in json_files:
        graph = _load_graph(jf)
        chunks.extend(chunk_graph(graph, source_path=str(jf)))

    if synthetic_oversize:
        chunks.extend(_synthetic_oversize(synthetic_oversize))
    return chunks, [f.name for f in json_files]


def _measure_indexing(chunks: list, collection: str, batch_size: int) -> dict:
    """index_documents의 배치 루프를 재현해 구간별 시간을 분해 측정한다.

    ※ vector_store.index_documents(151~179)와 동일 순서를 복제. 로직 변경 시 동기화 필요.
    """
    from src.db.vector_store import (
        _ensure_collection,
        _release_heap,
        _upsert_batch,
        delete_collection,
    )
    from src.utils.embedding import count_tokens, embed_texts

    # 깨끗한 상태에서 0부터 누적(HNSW 비선형성을 0→N으로 관측).
    # 테이블을 먼저 보장한 뒤 행을 비운다 — 첫 실행(테이블 부재)에서 DELETE가 ERROR 로그를 남기지 않도록 순서 주의.
    _ensure_collection(collection)
    delete_collection(collection)

    stages = {"count_tokens": 0.0, "embed_texts": 0.0, "upsert": 0.0, "release": 0.0}
    cumulative: list[tuple[int, float]] = []  # (적재 청크 누계, 벽시계 누적초)
    n_count_calls = 0  # count_tokens 분모 = 전체 청크
    n_embed_calls = 0  # embed 분모 = IX-201 통과 유효 청크
    n_skipped = 0
    stored = 0

    wall0 = perf_counter()
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]

        t = perf_counter()
        valid = []
        for c in batch:
            if count_tokens(c.content) <= EMBEDDING_MAX_TOKENS:
                valid.append(c)
            else:
                n_skipped += 1
        stages["count_tokens"] += perf_counter() - t
        n_count_calls += len(batch)

        if valid:
            t = perf_counter()
            vectors = embed_texts([c.content for c in valid], node="index")
            stages["embed_texts"] += perf_counter() - t
            n_embed_calls += len(valid)

            t = perf_counter()
            _upsert_batch(collection, valid, vectors)
            stages["upsert"] += perf_counter() - t
            stored += len(valid)

        t = perf_counter()
        _release_heap()
        stages["release"] += perf_counter() - t

        cumulative.append((start + len(batch), round(perf_counter() - wall0, 3)))

    wall = perf_counter() - wall0
    residual = wall - sum(stages.values())  # 루프/측정 오버헤드 잔차

    return {
        "n_chunks_input": len(chunks),
        "n_stored": stored,
        "n_skipped_ix201": n_skipped,
        "n_count_tokens_calls": n_count_calls,
        "n_embed_calls": n_embed_calls,
        "wall_sec": round(wall, 3),
        "stage_sec": {k: round(v, 3) for k, v in stages.items()},
        "residual_sec": round(residual, 3),
        "per_chunk_ms": round(wall / stored * 1000, 2) if stored else None,
        "cumulative": cumulative,
    }


def _milestones(cumulative: list[tuple[int, float]], targets=(500, 1000)) -> dict:
    """누적 기록에서 적재 N건 도달 시점의 벽시계 누적초를 뽑는다(HNSW 비선형성 관측)."""
    out = {}
    for target in targets:
        hit = next((sec for n, sec in cumulative if n >= target), None)
        if hit is not None:
            out[f"at_{target}"] = hit
    return out


def _measure_search(collection: str, queries: list[str], top_k: int, iters: int) -> dict:
    """similarity_search 응답 시간을 N회 반복 측정(p50/p95). 쿼리 임베딩 시간은 분리 기록."""
    from src.db.vector_store import similarity_search
    from src.retrieval.searcher import embed_query

    embed_times: list[float] = []
    search_times: list[float] = []
    top1_score = None

    for qi, q in enumerate(queries):
        t = perf_counter()
        qv = embed_query(q)
        embed_times.append(perf_counter() - t)

        results = []
        for _ in range(iters):
            t = perf_counter()
            results = similarity_search(qv, top_k, collection)
            search_times.append(perf_counter() - t)
        if qi == 0 and results:
            top1_score = round(results[0].score, 4)

    return {
        "iters_per_query": iters,
        "n_queries": len(queries),
        "query_embed_p50_ms": round(_percentile(embed_times, 0.5) * 1000, 2),
        "search_p50_ms": round(_percentile(search_times, 0.5) * 1000, 2),
        "search_p95_ms": round(_percentile(search_times, 0.95) * 1000, 2),
        "top1_score": top1_score,
    }


def _extrapolate(measured_files: list[str], n_stored: int, index_sec: float) -> dict:
    """측정한 GAAP 장 → 전체 코퍼스(GAAP 33 + K-IFRS 20장) 적재 소요 외삽.

    가정: ① K-IFRS 장당 청크 분포 = GAAP 평균, ② 청크당 적재 시간 일정
    (HNSW 삽입 비선형성 무시 → 보수적 하한 추정).
    """
    n_chapters = len(measured_files) or 1
    per_chunk = index_sec / n_stored if n_stored else 0.0
    per_chapter_chunks = n_stored / n_chapters
    GAAP_TOTAL, KIFRS_TOTAL = 33, 20
    est_total_chunks = per_chapter_chunks * (GAAP_TOTAL + KIFRS_TOTAL)
    return {
        "measured_chapters": n_chapters,
        "per_chunk_sec": round(per_chunk, 4),
        "per_chapter_chunks_avg": round(per_chapter_chunks, 1),
        "est_kifrs_chunks": round(per_chapter_chunks * KIFRS_TOTAL),
        "est_total_chunks_53ch": round(est_total_chunks),
        "est_total_index_sec": round(est_total_chunks * per_chunk, 1),
        "assumptions": "K-IFRS 장당 청크=GAAP 평균, 청크당 시간 일정(HNSW 비선형성 무시→하한)",
    }


def _write_report(payload: dict, out_dir: Path, stamp: str) -> Path:
    idx, srch, ext = payload["indexing"], payload["search"], payload["extrapolation"]
    ms = payload["milestones"]
    lines = [
        "# pgvector 인덱싱 성능 벤치마크",
        "",
        f"- 생성: {payload['generated_at']}",
        f"- 컬렉션: `{payload['collection']}` (전용, 측정 후 정리)",
        f"- 환경: {payload['env']}",
        f"- 콜드 스타트(모델 로드): {payload['cold_start_sec']}s",
        "",
        "## 인덱싱 (배치 루프 재현)",
        f"- 입력 {idx['n_chunks_input']}청크 → 적재 {idx['n_stored']} / IX-201 스킵 {idx['n_skipped_ix201']}",
        f"- 전체 {idx['wall_sec']}s · 청크당 {idx['per_chunk_ms']}ms",
        f"- 구간(s): {idx['stage_sec']} · 잔차 {idx['residual_sec']}",
        f"- 토크나이즈 분모: count_tokens {idx['n_count_tokens_calls']}회(전체) / embed {idx['n_embed_calls']}회(유효)",
        f"- 누적 마일스톤(s): {ms}",
        "",
        "## 검색 (similarity_search)",
        f"- 쿼리임베딩 p50 {srch['query_embed_p50_ms']}ms | 검색 p50 {srch['search_p50_ms']}ms / p95 {srch['search_p95_ms']}ms",
        f"- 탑1 스코어: {srch['top1_score']}",
        "",
        "## sanity check (#105 0차 대비)",
        f"- 0차: {_SMOKE_BASELINE['n_chunks']}청크, 탑1 {_SMOKE_BASELINE['top1_score']} ({_SMOKE_BASELINE['source']})",
        f"- 금회 탑1: {srch['top1_score']} (동급 코퍼스면 0.7 내외 기대)",
        "",
        "## 34장(기준서) 전체 적재 외삽",
        f"- 측정 {ext['measured_chapters']}장 · 장당 평균 {ext['per_chapter_chunks_avg']}청크 · 청크당 {ext['per_chunk_sec']}s",
        f"- 추정 전체(GAAP33+KIFRS20=53장) ~{ext['est_total_chunks_53ch']}청크 → ~{ext['est_total_index_sec']}s",
        f"- 가정: {ext['assumptions']}",
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"indexing_bench_{stamp}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="pgvector 인덱싱 성능 벤치마크")
    parser.add_argument("--collection", default="bench_indexing", help="측정 전용 컬렉션 (기본: bench_indexing)")
    parser.add_argument("--ontology-dir", default="data/ontology", help="온톨로지 JSON 디렉토리")
    parser.add_argument("--chapters", nargs="+", help="측정 대상 장 번호 (미지정 시 gaap 전 장)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help=f"파이프라인 배치 크기 (기본: {BATCH_SIZE})")
    parser.add_argument("--search-iters", type=int, default=20, help="쿼리당 검색 반복 횟수 (기본: 20)")
    parser.add_argument("--top-k", type=int, default=TOP_K_RETRIEVAL, help=f"검색 top_k (기본: {TOP_K_RETRIEVAL})")
    parser.add_argument("--synthetic-oversize", type=int, default=0, help="IX-201 측정용 합성 초과 청크 수 (기본: 0)")
    parser.add_argument("--keep", action="store_true", help="측정 후 컬렉션을 비우지 않고 보존")
    parser.add_argument("--out-dir", default="docs/measurements", help="결과 저장 디렉토리")
    parser.add_argument("--no-report", action="store_true", help="마크다운 리포트 생략")
    args = parser.parse_args(argv)

    from src.db.connection import close_pool, init_pool
    from src.utils.embedding import warmup_model
    from tests.utils.infra_check import check_docker_infrastructure

    infra_error = check_docker_infrastructure()
    if infra_error:
        print(f"[중단] 인프라 점검 실패: {infra_error}")
        return 2

    init_pool()
    try:
        # 콜드 스타트: 모델 최초 로드를 측정 경로 밖에서 1회 (#98 §1 = #168 공용 헬퍼).
        # 청크 로딩(chunk_graph→count_tokens)이 모델을 선점하면 콜드 스타트가 0으로 오염되므로 먼저 측정한다.
        t = perf_counter()
        warmup_model()
        cold_start = round(perf_counter() - t, 2)
        print(f"콜드 스타트(모델 로드): {cold_start}s")

        chunks, files = _load_chunks(Path(args.ontology_dir), args.chapters, args.synthetic_oversize)
        if not chunks:
            print(f"[중단] 청크가 비어 있음 (dir={args.ontology_dir}, chapters={args.chapters})")
            return 2
        print(f"입력 청크 {len(chunks)}개 ({len(files)}개 파일) | 컬렉션 '{args.collection}' | batch={args.batch_size}")

        indexing = _measure_indexing(chunks, args.collection, args.batch_size)
        milestones = _milestones(indexing["cumulative"])
        search = _measure_search(args.collection, _DEFAULT_QUERIES, args.top_k, args.search_iters)
        extrapolation = _extrapolate(files, indexing["n_stored"], indexing["wall_sec"])

        ts = datetime.now(KST)
        payload = {
            "generated_at": ts.isoformat(),
            "collection": args.collection,
            "env": _resolve_env(args.batch_size),
            "cold_start_sec": cold_start,
            "measured_files": files,
            "indexing": indexing,
            "milestones": milestones,
            "search": search,
            "smoke_baseline": _SMOKE_BASELINE,
            "extrapolation": extrapolation,
        }

        # 콘솔 요약
        print("\n" + "=" * 64)
        print(f"적재 {indexing['n_stored']}/{indexing['n_chunks_input']}청크 "
              f"(IX-201 스킵 {indexing['n_skipped_ix201']}) | 전체 {indexing['wall_sec']}s | "
              f"청크당 {indexing['per_chunk_ms']}ms")
        print(f"구간(s): {indexing['stage_sec']} | 잔차 {indexing['residual_sec']}")
        print(f"누적 마일스톤(s): {milestones}")
        print(f"검색 p50 {search['search_p50_ms']}ms / p95 {search['search_p95_ms']}ms | 탑1 {search['top1_score']}")
        print(f"sanity(#105): 0차 탑1 {_SMOKE_BASELINE['top1_score']} vs 금회 {search['top1_score']}")
        print(f"34장 외삽: ~{extrapolation['est_total_chunks_53ch']}청크 → ~{extrapolation['est_total_index_sec']}s")
        print("=" * 64)

        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = ts.strftime("%Y%m%d_%H%M")
        json_path = out_dir / f"indexing_bench_{stamp}.json"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n결과 저장: {json_path}")
        if not args.no_report:
            print(f"리포트 저장: {_write_report(payload, out_dir, stamp)}")
        return 0
    finally:
        if not args.keep:
            from src.db.vector_store import delete_collection

            delete_collection(args.collection)
            print(f"전용 컬렉션 정리 완료: {args.collection}")
        close_pool()


if __name__ == "__main__":
    raise SystemExit(main())
