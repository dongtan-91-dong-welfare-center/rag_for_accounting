"""운영 chunks에 page_start/page_end metadata를 백필한다.

원본 PDF를 Docling으로 재파싱(파싱만 — 온톨로지 빌드·재임베딩 없음)해 페이지 맵을 만들고,
기존 청크 content를 정렬(src/parse/page_map.assign_pages)해 metadata JSONB에 페이지 범위를 병합(UPDATE)한다.
content·embedding은 불변이므로 검색 결과에 영향이 없다.

사용 (호스트에서 실행, DB는 docker — POSTGRES_HOST 보정 필요):
    # dry-run: 매칭률 리포트만 출력(DB 변경 없음)
    POSTGRES_HOST=localhost uv run python scripts/backfill_page_map.py --documents gaap-ch10
    # 전 문서 dry-run → 확인 후 반영
    POSTGRES_HOST=localhost uv run python scripts/backfill_page_map.py
    POSTGRES_HOST=localhost uv run python scripts/backfill_page_map.py --apply

주의:
- 재파싱은 적재 시점과 동일 Docling 버전이어야 한다(uv.lock 고정) — 리포트에 버전을 스탬프한다.
- reading order 재정렬(reorder_reading_order)은 페이지 귀속(prov.page_no)과 무관하므로 생략한다.
- 미매칭 청크는 건드리지 않는다(페이지 키 부재 → 뷰어 버튼 미표시로 자연 강등).
- 리포트의 '페이지 걸침'과 '표 포함' 청크 목록은 DoD 95% 게이트의 수동 대조 표본 (강제 포함 유형)을 뽑는 데 쓴다.
"""
from __future__ import annotations

import argparse
import sys
from importlib.metadata import version as pkg_version
from pathlib import Path

# ── 프로젝트 루트를 import 경로에 추가 (src.* 재사용) ──
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from psycopg.types.json import Jsonb

from src.db.connection import close_pool, get_pool, init_pool
from src.parse.page_map import (
    assign_pages,
    build_page_texts,
    marker_pages,
    pages_from_markers,
    resolve_pdf_path,
)
from src.utils.config import CHUNKS_TABLE, PDF_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _load_chunks(document_id: str) -> list[tuple[str, str]]:
    """document의 (chunk_id, content) 목록을 로드한다."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT chunk_id, content FROM {CHUNKS_TABLE} WHERE document_id = %s ORDER BY chunk_id",
            (document_id,),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]


def _list_document_ids() -> list[str]:
    """DB에서 모든 document_id를 조회한다."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT DISTINCT document_id FROM {CHUNKS_TABLE} ORDER BY document_id")
        return [r[0] for r in cur.fetchall()]


def _apply_updates(updates: list[tuple[str, int, int]]) -> None:
    """(chunk_id, page_start, page_end)를 metadata JSONB에 병합한다 — content·embedding 불변."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.executemany(
            f"UPDATE {CHUNKS_TABLE} SET metadata = metadata || %s WHERE chunk_id = %s",
            [(Jsonb({"page_start": s, "page_end": e}), cid) for cid, s, e in updates],
        )


def backfill_document(document_id: str, pdf_dir: str, converter) -> dict:
    """문서 1건을 재파싱·정렬하고 결과를 집계한다. DB 변경은 하지 않는다(호출측 --apply 담당)."""
    pdf_path = resolve_pdf_path(document_id, pdf_dir)
    if pdf_path is None:
        return {"document_id": document_id, "status": "no_pdf"}

    doc = converter.convert(str(pdf_path)).document
    page_texts = build_page_texts(doc)

    chunks = _load_chunks(document_id)  # 청크ID와 컨텐츠 로드
    matched: list[tuple[str, int, int]] = []    # 매칭된 청크
    unmatched: list[str] = []   # 매칭되지 않은 청크
    spanning: list[str] = []    # 여러 페이지를 걸친 청크
    with_table: list[str] = []  # 표를 포함한 청크
    marker_checked = 0                  # 페이지 마커를 가진 매칭 청크 수
    marker_agree = 0                    # 그중 정렬 결과와 마커가 정합한 수
    marker_disagree: list[str] = []     # 불일치 상세(수동 대조 우선 표본)

    via_marker = 0                      # 앵커 실패 → 마커 폴백으로 구제된 청크 수(스캔본 등)
    for chunk_id, content in chunks:
        if "\n|" in content or content.startswith("|"):
            with_table.append(chunk_id)
        pages = assign_pages(content, page_texts)
        matched_via_marker = False
        if pages is None:
            # 앵커 정렬 불가(스캔본 PDF 등) — md 정본이 남긴 페이지 경계 마커로 폴백한다.
            pages = pages_from_markers(content)
            if pages is None:
                unmatched.append(chunk_id)
                continue
            via_marker += 1
            matched_via_marker = True
        start, end = pages
        matched.append((chunk_id, start, end))
        if start != end:
            spanning.append(chunk_id)

        # 자동 크로스체크 — content에 남은 페이지 경계 마커(<!-- page N -->)와 정렬 결과 대조.
        # 마커 N은 'N페이지 시작' 경계이므로 청크가 N-1~N 부근이면 정합: start ≤ N ≤ end+1.
        # (마커 폴백으로 부여된 청크는 정의상 정합이므로 앵커 정렬의 정확도 지표를 희석하지 않게 제외한다.)
        markers = marker_pages(content)
        if markers and not matched_via_marker:
            marker_checked += 1
            if all(start <= n <= end + 1 for n in markers):
                marker_agree += 1
            else:
                marker_disagree.append(f"{chunk_id}(정렬 {start}-{end} vs 마커 {markers})")

    return {
        "document_id": document_id,
        "status": "ok",
        "pdf": pdf_path.name,
        "pdf_pages": len(page_texts),
        "total": len(chunks),
        "matched": matched,
        "unmatched": unmatched,
        "spanning": spanning,
        "with_table": with_table,
        "marker_checked": marker_checked,
        "marker_agree": marker_agree,
        "marker_disagree": marker_disagree,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="chunks metadata에 page_start/page_end 백필")
    parser.add_argument("--pdf-dir", default=PDF_DIR, help=f"원본 PDF 디렉토리 (기본: {PDF_DIR})")
    parser.add_argument("--documents", nargs="*", help="대상 document_id 목록 (기본: 전체)")
    parser.add_argument("--apply", action="store_true", help="DB에 반영 (기본: dry-run 리포트만)")
    args = parser.parse_args()

    # Docling 모델 로드는 무겁다 — converter 1개를 전 문서에 재사용한다.
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()

    init_pool()
    try:
        documents = args.documents or _list_document_ids()
        print(f"# page backfill {'APPLY' if args.apply else 'DRY-RUN'}")
        print(f"docling={pkg_version('docling')} | pdf_dir={args.pdf_dir} | documents={len(documents)}")

        grand_total = grand_matched = grand_checked = grand_agree = 0
        all_updates: list[tuple[str, int, int]] = []
        for document_id in documents:
            r = backfill_document(document_id, args.pdf_dir, converter)
            if r["status"] == "no_pdf":
                print(f"\n## {document_id}: PDF 미해결(resolve_pdf_path=None) — skip")
                continue
            total, n_matched = r["total"], len(r["matched"])
            grand_total += total
            grand_matched += n_matched
            grand_checked += r["marker_checked"]
            grand_agree += r["marker_agree"]
            all_updates.extend(r["matched"])
            print(
                f"\n## {r['document_id']} ({r['pdf']}, {r['pdf_pages']}p): "
                f"{n_matched}/{total} 매칭 ({n_matched / total:.1%})"
                f" | 마커 대조 {r['marker_agree']}/{r['marker_checked']}"
                if total
                else f"\n## {r['document_id']}: 청크 없음"
            )
            if r["spanning"]:
                print(f"  걸침({len(r['spanning'])}): {', '.join(r['spanning'][:10])}")
            if r["with_table"]:
                print(f"  표 포함({len(r['with_table'])}): {', '.join(r['with_table'][:10])}")
            if r["unmatched"]:
                print(f"  미매칭({len(r['unmatched'])}): {', '.join(r['unmatched'])}")
            if r["marker_disagree"]:
                print(f"  마커 불일치({len(r['marker_disagree'])}): {', '.join(r['marker_disagree'][:10])}")

        if grand_total:
            print(f"\n# TOTAL: {grand_matched}/{grand_total} 매칭 ({grand_matched / grand_total:.1%})")
        if grand_checked:
            print(
                f"# 마커 크로스체크: {grand_agree}/{grand_checked} 정합 ({grand_agree / grand_checked:.1%})"
                " — content 내 <!-- page N --> 경계 마커와 자동 대조"
            )

        if args.apply and all_updates:
            _apply_updates(all_updates)
            print(f"# APPLIED: {len(all_updates)}개 청크 metadata 병합 완료 (content·embedding 불변)")
        elif not args.apply:
            print("# dry-run — DB 변경 없음. 반영하려면 --apply")
        return 0
    finally:
        close_pool()


if __name__ == "__main__":
    raise SystemExit(main())
