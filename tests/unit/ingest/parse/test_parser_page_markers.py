"""[#297] 파싱 시점 페이지 마커 삽입 단위 테스트

대상: src/ingest/parse/parser.py의 export_markdown_with_page_markers
검증 범위:
    - 페이지별 export 결과 앞에 `<!-- page N -->` 마커 줄을 붙여 이어붙인다.
    - 페이지 정보가 없는 문서는 기존 전체 export 결과를 그대로 반환한다.
    - 본문은 html.unescape를 거친 기존 동작을 유지한다.
"""
from unittest.mock import MagicMock

import pytest


def _doc(pages: dict[int, str]):
    doc = MagicMock()
    doc.pages = {n: object() for n in pages}
    doc.export_to_markdown.side_effect = lambda **kw: (
        pages[kw["page_no"]] if "page_no" in kw else "\n\n".join(pages.values())
    )
    return doc


@pytest.mark.unit
class TestExportMarkdownWithPageMarkers:
    def test_markers_precede_each_page_in_page_order(self):
        from src.ingest.parse.parser import export_markdown_with_page_markers

        text = export_markdown_with_page_markers(_doc({2: "둘째 쪽 본문", 1: "첫째 쪽 본문"}))
        assert text == "<!-- page 1 -->\n첫째 쪽 본문\n\n<!-- page 2 -->\n둘째 쪽 본문"

    def test_empty_pages_are_skipped(self):
        from src.ingest.parse.parser import export_markdown_with_page_markers

        text = export_markdown_with_page_markers(_doc({1: "본문", 2: "  ", 3: "끝"}))
        assert "<!-- page 2 -->" not in text
        assert "<!-- page 3 -->" in text

    def test_falls_back_to_whole_export_without_pages(self):
        from src.ingest.parse.parser import export_markdown_with_page_markers

        doc = MagicMock()
        doc.pages = {}
        doc.export_to_markdown.return_value = "전체 &amp; 본문"
        assert export_markdown_with_page_markers(doc) == "전체 & 본문"

    def test_html_entities_are_unescaped(self):
        from src.ingest.parse.parser import export_markdown_with_page_markers

        text = export_markdown_with_page_markers(_doc({1: "A &amp; B"}))
        assert "A & B" in text
