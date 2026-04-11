"""
Reading Order 재정렬 모듈

1. group 컨테이너를 해제하여 모든 아이템을 flat하게 펼침
2. top y 기준 위→아래 정렬
3. 같은 라인(top y 근접)이면 left→right 정렬
"""

import logging
from docling_core.types.doc import DoclingDocument
from docling_core.types.doc.document import RefItem
from src.parse.parser_dtos import _ItemInfo

_log = logging.getLogger(__name__)



def _resolve_ref(doc: DoclingDocument, ref: str):
    for collection in (doc.texts, doc.tables, doc.pictures, doc.groups):
        for item in collection:
            if hasattr(item, "self_ref") and item.self_ref == ref:
                return item
    return None


def _get_item_info(doc: DoclingDocument, ref: RefItem) -> _ItemInfo | None:
    """RefItem → 위치 정보. PDF 좌표를 화면 좌표(y 반전)로 변환."""
    item = _resolve_ref(doc, ref.cref)
    if item is None:
        return None

    if hasattr(item, "prov") and item.prov:
        p = item.prov[0]
        nt, nb = -p.bbox.t, -p.bbox.b
        if nt > nb:
            nt, nb = nb, nt
        return _ItemInfo(
            ref=ref, page_no=p.page_no,
            left=p.bbox.l, top=nt, right=p.bbox.r, bottom=nb,
            width=p.bbox.r - p.bbox.l,
        )
    return None


def _flatten_children(doc: DoclingDocument, children: list[RefItem]) -> list[RefItem]:
    """group을 재귀적으로 풀어서 leaf 아이템(texts/tables/pictures)만 남긴다."""
    result = []
    for ref in children:
        item = _resolve_ref(doc, ref.cref)
        if item is None:
            result.append(ref)
            continue

        # group이면 children을 재귀적으로 풀기
        if hasattr(item, "children") and item.children and not (hasattr(item, "prov") and item.prov):
            result.extend(_flatten_children(doc, item.children))
        else:
            result.append(ref)

    return result


def _is_same_line(a: _ItemInfo, b: _ItemInfo) -> bool:
    """top y 기준 같은 라인 판별"""
    dist = abs(a.top - b.top)
    min_h = min(a.bottom - a.top, b.bottom - b.top)
    if min_h <= 0:
        min_h = max(a.bottom - a.top, b.bottom - b.top)
    if min_h <= 0:
        return dist < 5.0
    return dist <= min_h * SAME_LINE_RATIO


def _sort_items(items: list[_ItemInfo]) -> list[_ItemInfo]:
    """top y 기준 라인 그룹핑 → 위→아래, 같은 라인은 왼→오른 정렬."""
    if len(items) <= 1:
        return items

    sorted_by_top = sorted(items, key=lambda i: i.top)

    lines: list[list[_ItemInfo]] = [[sorted_by_top[0]]]
    for item in sorted_by_top[1:]:
        merged = False
        for line in lines:
            if _is_same_line(line[0], item):
                line.append(item)
                merged = True
                break
        if not merged:
            lines.append([item])

    result = []
    for line in sorted(lines, key=lambda ln: min(i.top for i in ln)):
        result.extend(sorted(line, key=lambda i: i.left))
    return result


def reorder_reading_order(doc: DoclingDocument) -> DoclingDocument:
    """문서 reading order 재정렬.

    1. body.children의 group을 해제하여 flat하게 펼침
    2. 페이지별로 top y 정렬 (위→아래, 같은 라인은 왼→오른)
    """
    if not doc.body.children:
        return doc

    original_count = len(doc.body.children)

    # 1. group 해제 → flat
    flat_refs = _flatten_children(doc, doc.body.children)

    # 2. 위치 정보 추출
    item_infos: list[_ItemInfo] = []
    no_info_refs: list[RefItem] = []
    for ref in flat_refs:
        info = _get_item_info(doc, ref)
        if info:
            item_infos.append(info)
        else:
            no_info_refs.append(ref)

    if not item_infos:
        return doc

    # 3. 페이지별 정렬
    pages: dict[int, list[_ItemInfo]] = {}
    for info in item_infos:
        pages.setdefault(info.page_no, []).append(info)

    sorted_items: list[_ItemInfo] = []
    for page_no in sorted(pages.keys()):
        sorted_items.extend(_sort_items(pages[page_no]))

    # 4. body.children 교체
    new_children = [info.ref for info in sorted_items]
    new_children.extend(no_info_refs)
    doc.body.children = new_children

    _log.info(
        f"Reading order 재정렬: "
        f"group 해제 {original_count}→{len(flat_refs)}개, "
        f"정렬 완료 {len(doc.body.children)}개"
    )

    return doc
