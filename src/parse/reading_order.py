"""
Reading Order 재정렬 모듈

1. body.children을 top y 기준 위→아래 정렬 (group은 topmost child 기준 위치)
2. group 내부 children도 동일하게 정렬
3. 같은 라인(top y 근접)이면 left→right 정렬

※ group 해제(flatten)는 불가 — Docling이 parent-child 계층을 검증하므로
   group ref는 body.children에 유지하고, 위치 기준으로만 정렬한다.
"""

import logging
from docling_core.types.doc import DoclingDocument
from docling_core.types.doc.document import RefItem
from src.parse.parser_dtos import _ItemInfo, SAME_LINE_RATIO

_log = logging.getLogger(__name__)


def _resolve_ref(doc: DoclingDocument, ref: str):
    for collection in (doc.texts, doc.tables, doc.pictures, doc.groups):
        for item in collection:
            if hasattr(item, "self_ref") and item.self_ref == ref:
                return item
    return None


def _get_item_info(doc: DoclingDocument, ref: RefItem) -> _ItemInfo | None:
    """RefItem → 위치 정보. PDF 좌표를 화면 좌표(y 반전)로 변환.
    group은 topmost child의 위치를 사용."""
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

    # group: topmost child 기준
    if hasattr(item, "children") and item.children:
        best = None
        for child in item.children:
            ci = _get_item_info(doc, child)
            if ci and (best is None or ci.top < best.top):
                best = ci
        if best:
            return _ItemInfo(
                ref=ref, page_no=best.page_no,
                left=best.left, top=best.top, right=best.right, bottom=best.bottom,
                width=best.width,
            )
    return None


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


def _reorder_children(doc: DoclingDocument, children: list[RefItem]) -> list[RefItem]:
    """children을 페이지별로 top y 정렬."""
    if not children:
        return children

    item_infos: list[_ItemInfo] = []
    no_info_refs: list[RefItem] = []

    for ref in children:
        info = _get_item_info(doc, ref)
        if info:
            item_infos.append(info)
        else:
            no_info_refs.append(ref)

    if not item_infos:
        return children

    pages: dict[int, list[_ItemInfo]] = {}
    for info in item_infos:
        pages.setdefault(info.page_no, []).append(info)

    sorted_items: list[_ItemInfo] = []
    for page_no in sorted(pages.keys()):
        sorted_items.extend(_sort_items(pages[page_no]))

    new_children = [info.ref for info in sorted_items]
    new_children.extend(no_info_refs)
    return new_children


def reorder_reading_order(doc: DoclingDocument) -> DoclingDocument:
    """문서 reading order 재정렬.

    1. group 내부 children 정렬 (top y 위→아래)
    2. body.children 정렬 (top y 위→아래, group은 topmost child 기준 위치)
    """
    if not doc.body.children:
        return doc

    # 1. group 내부 children 재정렬
    groups_reordered = 0
    for group in doc.groups:
        if hasattr(group, "children") and group.children:
            old = [r.cref for r in group.children]
            group.children = _reorder_children(doc, group.children)
            if [r.cref for r in group.children] != old:
                groups_reordered += 1

    # 2. body.children 재정렬
    original_order = [ref.cref for ref in doc.body.children]
    doc.body.children = _reorder_children(doc, doc.body.children)
    new_order = [ref.cref for ref in doc.body.children]

    changed = sum(1 for a, b in zip(original_order, new_order) if a != b)
    _log.info(
        f"Reading order 재정렬: "
        f"body {len(doc.body.children)}개 중 {changed}개 변경, "
        f"groups {groups_reordered}/{len(doc.groups)}개 내부 정렬"
    )

    return doc
