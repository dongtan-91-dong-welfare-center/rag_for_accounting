"""
청크 content ↔ 원본 PDF 페이지 정렬 코어.

페이지 정보 소실 지점은 parser.py의 export_to_markdown() 한 곳이다.
온톨로지 재빌드나 재임베딩 없이, Docling 문서의 텍스트 아이템(prov.page_no — 테이블 병합과 동일 계약)으로 페이지별 텍스트 맵을 만들고, 
기존 청크 content(md 원문)의 앵커 라인을 그 맵에서 찾아 page_start/page_end 범위를 복원한다. 
content·embedding은 불변 — metadata만 채운다.

정렬 정확도 가정: reading order 재정렬·표 텍스트화·페이지 걸침으로 어긋날 수 있어 범위로 흡수하고, 
판단 불가한 청크는 None으로 드러낸다(backfill 리포트가 집계).

매칭 규칙 (ch10 파일럿 실측으로 보강):
- 공백·숫자·구두점·md 마크업을 제거해 비교한다 — md ↔ PDF 추출 간 공백 차이에 더해,
  PDF 레이아웃상 본문 중간에 끼는 조항 번호(예: "정10.1하는")와 볼드(**)까지 흡수.
- 표 셀 텍스트도 페이지 맵에 포함한다 — 표로 조판된 청크(용어의 정의·사례)가 doc.texts에 없어 미매칭되는 것을 해소.
  표 행 앵커는 정규화 후 길이가 충분한(긴 셀) 행만 살아남는다.
- 여러 페이지에서 발견되는 앵커(반복 상용구)는 투표에서 제외한다 — 범위 부풀림 방지.
- 긴 앵커(페이지 경계 걸침 가능)는 머리/꼬리 조각으로 나눠 시작·끝 페이지를 각각 잡는다.
"""
from __future__ import annotations

import re
from pathlib import Path

# 앵커 최소 길이(정규화 후) — 이보다 짧으면 반복 문구·조항 번호일 가능성이 높아 제외한다.
MIN_ANCHOR_LEN = 12
# 청크당 최대 앵커 수 — 첫/끝 라인을 항상 포함해 페이지 범위(min/max)가 좁아지지 않게 한다.
MAX_ANCHORS = 8
# 전체 앵커가 단일 페이지에서 발견되지 않을 때(페이지 경계 걸침) 머리/꼬리 폴백 조각 길이.
PROBE_LEN = 30

# md 주석(<!-- page N --> 등) — #101 md 정본이 남긴 마커. 앵커 추출 전에 제거하고,
# 페이지 번호는 marker_pages()로 뽑아 정렬 결과의 자동 크로스체크에 쓴다.
_MD_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_PAGE_MARKER_RE = re.compile(r"<!--\s*page\s+(\d+)\s*-->")

# 공백·숫자·구두점·md 마크업(|, *, #) 제거 — 양쪽에 대칭 적용되는 비교 기준.
# 숫자를 제거하는 이유: PDF 레이아웃에서 조항 번호가 본문 중간에 삽입되고(ch10 실측),
# md에서는 헤더로 분리돼 있어 숫자를 남기면 연속 substring이 구조적으로 깨진다.
_STRIP_RE = re.compile(r"[\s\d.,()%|*#·-]+")


def _normalize(text: str) -> str:
    """공백·숫자·구두점·md 마크업을 제거한다 — md와 PDF 추출 텍스트의 표기 차이를 흡수하는 비교 기준."""
    return _STRIP_RE.sub("", text)


def build_page_texts(doc) -> dict[int, str]:
    """Docling 문서의 텍스트·표 아이템을 페이지별 정규화 텍스트로 묶는다.

    parser.py의 테이블 병합과 동일하게 prov[0].page_no를 페이지 귀속 기준으로 쓴다.
    prov가 없는 아이템은 페이지를 알 수 없어 건너뛴다.
    표 셀 텍스트(export_to_dataframe — parser.py와 동일 계약)도 포함해, 표로 조판된
    원문(용어의 정의·사례 등)에서 온 청크가 정렬되게 한다. 셀은 헤더→행 순서로 잇는다
    (md 표의 행 순서와 대응해 행 단위 앵커가 substring으로 매칭된다).
    """
    pages: dict[int, str] = {}

    def _append(page_no: int, text: str) -> None:
        if text:
            pages[page_no] = pages.get(page_no, "") + text

    for item in getattr(doc, "texts", []):
        if not item.prov:
            continue
        _append(item.prov[0].page_no, _normalize(item.text or ""))

    for table in getattr(doc, "tables", []):
        if not table.prov:
            continue
        df = table.export_to_dataframe(doc)
        cells = list(df.columns) + [cell for row in df.values for cell in row]
        joined = "".join(str(cell) for cell in cells if cell is not None and str(cell) != "nan")
        _append(table.prov[0].page_no, _normalize(joined))

    return pages


def _anchor_lines(content: str) -> list[str]:
    """청크 content에서 앵커 후보 라인(정규화)을 고른다.

    짧은 라인(조항 번호·짧은 표 행 등)은 정규화 후 최소 길이 미달로 자연 제외되고,
    표 행은 긴 셀 텍스트를 가진 행만 살아남아 페이지 맵의 표 텍스트와 매칭된다.
    후보가 많으면 첫/끝 라인을 포함해 균등 샘플한다 — 범위의 양 끝을 놓치지 않기 위함.
    """
    candidates: list[str] = []
    for line in _MD_COMMENT_RE.sub("", content).splitlines():
        normalized = _normalize(line)
        if len(normalized) >= MIN_ANCHOR_LEN:
            candidates.append(normalized)

    if len(candidates) > MAX_ANCHORS:
        n = len(candidates)
        indices = sorted({round(i * (n - 1) / (MAX_ANCHORS - 1)) for i in range(MAX_ANCHORS)})
        candidates = [candidates[i] for i in indices]
    return candidates


def assign_pages(content: str, page_texts: dict[int, str]) -> tuple[int, int] | None:
    """청크 content가 걸치는 페이지 범위 (page_start, page_end)를 정한다.

    단일 페이지에서만 발견된 앵커(조각)들의 페이지를 모아 (min, max)를 반환한다.
    앵커가 없거나 하나도 매칭되지 않으면 None — 호출측(backfill)이 미매칭으로 집계한다.
    """
    hit_pages: set[int] = set()
    for anchor in _anchor_lines(content):
        # 전체 앵커로 먼저 찾고, 단일 페이지에서 발견되지 않으면(경계 걸침 또는 부재)
        # 머리/꼬리 조각으로 폴백해 시작·끝 페이지를 각각 잡는다.
        probes = [anchor]
        if len(anchor) > PROBE_LEN:
            probes += [anchor[:PROBE_LEN], anchor[-PROBE_LEN:]]
        for probe in probes:
            found = [page for page, text in page_texts.items() if probe in text]
            if len(found) == 1:
                hit_pages.add(found[0])
                if probe is anchor:
                    break  # 전체가 단일 페이지에서 발견 — 폴백 불필요

    if not hit_pages:
        return None
    return (min(hit_pages), max(hit_pages))


def marker_pages(content: str) -> list[int]:
    """content에 남아 있는 페이지 경계 마커(<!-- page N -->)의 N 목록.

    마커는 'N페이지가 여기서 시작된다'는 경계라, 마커 N을 품은 청크는 N-1~N 부근에 있다.
    backfill 리포트가 앵커 정렬 결과와 대조하는 자동 크로스체크 소스로 쓴다.
    """
    return [int(m.group(1)) for m in _PAGE_MARKER_RE.finditer(content)]


def pages_from_markers(content: str) -> tuple[int, int] | None:
    """마커 N은 'N페이지 시작' 경계 — 청크는 (N-1, N)에 걸친 것으로 부여한다.

    앵커 정렬이 불가능한 스캔본 PDF의 폴백 소스.
    """
    markers = marker_pages(content)
    if not markers:
        return None
    start = max(1, min(markers) - 1)
    end = max(markers)
    return (start, end)



_CHAPTER_DOC_RE = re.compile(r"gaap-ch(\d+)")


def resolve_pdf_path(document_id: str, pdf_dir: Path | str) -> Path | None:
    """document_id의 원본 PDF 경로를 정한다 — BYO 소재 규약.

    청크 metadata의 source_path(온톨로지 JSON 경로)에 의존하지 않는다.
    1) {pdf_dir}/{document_id}.pdf — BYO 사용자가 명시 배치하는 정식 규약.
    2) gaap-chN이면 제N장*.pdf 글롭이 정확히 1건일 때 채택(현행 data/raw 파일명 호환).
    못 찾거나 모호하면 None — 서빙은 404로, 뷰어는 안내 메시지로 강등한다.
    """
    pdf_dir = Path(pdf_dir)
    explicit = pdf_dir / f"{document_id}.pdf"
    if explicit.is_file():
        return explicit

    m = _CHAPTER_DOC_RE.fullmatch(document_id)
    if m:
        matches = sorted(pdf_dir.glob(f"제{m.group(1)}장*.pdf"))
        if len(matches) == 1:
            return matches[0]
    return None
