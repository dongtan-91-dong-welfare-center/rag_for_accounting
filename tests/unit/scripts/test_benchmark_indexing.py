"""scripts/benchmark_indexing.py 리포트 생성 검증.

`indexing_bench_*.md`는 생성 산출물이므로, 
BLUF 판정은 파일이 아니라 생성기(`_write_report`)가 찍도록 한다. 
리포트가 raw 측정 덤프가 아니라 상단에 "그래서 좋은가/나쁜가"를 요약하는 한 줄을 포함하는지 확인한다.
"""
import pytest

from scripts.benchmark_indexing import _write_report

pytestmark = pytest.mark.unit


def _sample_payload() -> dict:
    """실측(indexing_bench_20260624_2114) 형태를 모사한 최소 payload."""
    return {
        "generated_at": "2026-06-27T10:00:00+09:00",
        "collection": "bench_indexing",
        "env": {"device": "mps", "threads": 10, "encode_batch_size": 16, "pipeline_batch_size": 100},
        "cold_start_sec": 9.29,
        "indexing": {
            "n_chunks_input": 1072, "n_stored": 1072, "n_skipped_ix201": 0,
            "n_count_tokens_calls": 1072, "n_embed_calls": 1072,
            "wall_sec": 119.818,
            "stage_sec": {"count_tokens": 0.393, "embed_texts": 115.853, "upsert": 2.628, "release": 0.943},
            "residual_sec": 0.0, "per_chunk_ms": 111.77, "cumulative": [],
        },
        "milestones": {"at_500": 51.628, "at_1000": 109.541},
        "search": {"query_embed_p50_ms": 62.54, "search_p50_ms": 8.23, "search_p95_ms": 9.64, "top1_score": 0.7277},
        "extrapolation": {
            "measured_chapters": 33, "per_chunk_sec": 0.1118, "per_chapter_chunks_avg": 32.5,
            "est_kifrs_chunks": 650, "est_total_chunks_53ch": 1722, "est_total_index_sec": 192.4,
            "assumptions": "K-IFRS 장당 청크=GAAP 평균, 청크당 시간 일정",
        },
    }


def test_report_includes_bluf_verdict(tmp_path):
    """리포트 상단에 핵심 수치를 요약한 BLUF 판정 한 줄이 온다."""
    path = _write_report(_sample_payload(), tmp_path, "20260627_1000")
    content = path.read_text(encoding="utf-8")

    bluf_line = next((ln for ln in content.splitlines() if "한 줄 요약(BLUF)" in ln), None)
    assert bluf_line is not None, "리포트에 BLUF 한 줄 요약이 없음"

    # 판정이 raw 덤프가 아니라 핵심 수치(청크당 적재·검색 p50·탑1·외삽)를 담는다
    for token in ("111.77", "8.23", "0.7277", "192.4"):
        assert token in bluf_line, f"BLUF 판정에 {token} 누락: {bluf_line!r}"

    # BLUF는 첫 측정 섹션('## 인덱싱')보다 앞(상단)에 위치한다
    assert content.index("한 줄 요약(BLUF)") < content.index("## 인덱싱")
