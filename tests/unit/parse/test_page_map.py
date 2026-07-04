"""
src/parse/page_map.py — 청크 content ↔ PDF 페이지 정렬 코어 단위테스트 (순수 — Docling·DB 불필요).

export_to_markdown()이 잃는 페이지 정보를, Docling 텍스트 아이템(prov.page_no)으로 만든 페이지별 텍스트 맵과 청크 content(md 원문)의 앵커 라인 매칭으로 복원한다.

정렬 정확도 가정: reading order 재정렬·표 텍스트화·페이지 걸침으로 어긋날 수 있어 page_start/page_end 범위로 흡수하고, 미매칭은 None으로 드러낸다.
"""
from types import SimpleNamespace

from src.parse.page_map import (
    _normalize,
    assign_pages,
    build_page_texts,
    marker_pages,
    pages_from_markers,
    resolve_pdf_path,
)


def _item(text: str, page_no: int):
    """Docling 텍스트 아이템의 최소 형태 — parser.py 테이블 병합과 동일한 prov 계약."""
    return SimpleNamespace(text=text, prov=[SimpleNamespace(page_no=page_no)])


class TestBuildPageTexts:
    def test_groups_items_by_page_and_normalizes_whitespace(self):
        doc = SimpleNamespace(
            texts=[
                _item("이 장의 목적은 유형자산의 회계처리와", 1),
                _item("공시에 필요한 사항을 정하는 데 있다.", 1),
                _item("유형자산의 취득원가는 구입원가로 한다.", 2),
            ]
        )
        pages = build_page_texts(doc)
        assert set(pages) == {1, 2}
        # 공백을 전부 제거해 md ↔ PDF 추출 간 공백 차이를 흡수한다
        assert "이장의목적은유형자산의회계처리와" in pages[1]
        assert "취득원가는구입원가로한다" in pages[2]

    def test_skips_items_without_prov(self):
        doc = SimpleNamespace(texts=[_item("본문", 1), SimpleNamespace(text="prov 없음", prov=[])])
        assert set(build_page_texts(doc)) == {1}

    def test_includes_table_cell_texts(self):
        """표 셀 텍스트도 페이지 맵에 포함한다 — 표 조판 청크(용어의 정의·사례) 정렬용.

        ch10 파일럿 실측: 용어의 정의 7건·사례 표가 doc.texts에 없어 미매칭됐다(82.4%).
        """
        import pandas as pd

        table = SimpleNamespace(
            prov=[SimpleNamespace(page_no=4)],
            export_to_dataframe=lambda doc: pd.DataFrame(
                {"용어": ["원가"], "정의": ["자산을 취득하기 위하여 지급한 현금 및 현금성자산"]}
            ),
        )
        doc = SimpleNamespace(texts=[], tables=[table])
        pages = build_page_texts(doc)
        assert "자산을취득하기위하여지급한현금및현금성자산" in pages[4]


class TestAssignPages:
    PAGES = {
        1: "제10장유형자산10.1이장의목적은유형자산의회계처리와공시에필요한사항을정하는데있다.",
        2: "10.2유형자산의취득원가는구입원가또는제작원가로한다.취득부대비용을가산한다.",
        3: "10.3유형자산의감가상각은자산의내용연수에걸쳐체계적으로배분한다.",
    }

    def test_single_page_chunk(self):
        content = "#### 10.1\n이 장의 목적은 유형자산의 회계처리와 공시에 필요한 사항을 정하는 데 있다."
        assert assign_pages(content, self.PAGES) == (1, 1)

    def test_page_spanning_chunk_returns_range(self):
        """페이지 걸침 청크는 (min, max) 범위로 흡수한다 — 게이트 표본 강제 포함 유형."""
        content = (
            "#### 10.2\n유형자산의 취득원가는 구입원가 또는 제작원가로 한다.\n"
            "#### 10.3\n유형자산의 감가상각은 자산의 내용연수에 걸쳐 체계적으로 배분한다."
        )
        assert assign_pages(content, self.PAGES) == (2, 3)

    def test_short_table_rows_do_not_disturb_alignment(self):
        """짧은 표 행(숫자·구분자 위주)은 정규화 후 앵커 최소 길이에 못 미쳐 전후 문단으로 정렬한다."""
        content = (
            "#### 10.2\n유형자산의 취득원가는 구입원가 또는 제작원가로 한다.\n"
            "| 구분 | 금액 |\n|---|---|\n| 토지 | 1,000 |"
        )
        assert assign_pages(content, self.PAGES) == (2, 2)

    def test_table_only_chunk_matches_via_cell_texts(self):
        """표 단독 청크는 긴 셀 텍스트를 앵커로 페이지 맵의 표 텍스트와 매칭된다."""
        pages = {7: "용어정의원가자산을취득하기위하여지급한현금및현금성자산또는기타대가의공정가치"}
        content = "| 용어 | 정의 |\n|---|---|\n| 원가 | 자산을 취득하기 위하여 지급한 현금 및 현금성자산 또는 기타 대가의 공정가치 |"
        assert assign_pages(content, pages) == (7, 7)

    def test_inline_clause_numbers_in_page_text_are_absorbed(self):
        """
        PDF 레이아웃상 조항 번호가 본문 중간에 끼어도(예: '정10.1하는') 매칭된다.

        ch10 파일럿 실측: 번호 컬럼이 본문 텍스트에 삽입돼 연속 substring이 깨졌다.
        정규화가 숫자·구두점을 제거해 흡수한다.
        """
        raw_page = "목적 이 장의 목적은 유형자산의 회계처리와 공시에 필요한 사항을 정10.1하는 데 있다."
        content = "#### 10.1\n이 장의 목적은 유형자산의 회계처리와 공시에 필요한 사항을 정하는 데 있다."
        assert assign_pages(content, {2: _normalize(raw_page)}) == (2, 2)

    def test_whole_anchor_failure_falls_back_to_head_tail_probes(self):
        """
        전체 앵커가 어느 페이지에도 연속으로 없으면(경계 걸침) 머리/꼬리 조각으로 폴백한다.

        ch10 실측: 59자 앵커가 페이지 16→17에 걸쳐 전체 substring이 실패했다.
        """
        head = "자산의 원가에서 감가상각누계액과 손상차손누계액을 뺀 금액이나 원가를 대체한"
        tail = "다른 금액에서 감가상각누계액과 손상차손누계액을 차감하여 계산한 잔여 금액을 말한다"
        pages = {16: "본문" + _normalize(head), 17: _normalize(tail) + "본문"}
        # 폴백 조각은 앞/뒤 30자 — 경계가 앵커의 30자 안쪽이면 못 잡는 한계는 남는다(실측 게이트로 수용)
        assert assign_pages(f"{head} {tail}", pages) == (16, 17)

    def test_md_comments_do_not_pollute_anchors(self):
        """content의 md 주석(<!-- page N --> 등)은 앵커 추출 전에 제거한다."""
        content = (
            "유형자산의 취득원가는 구입원가 또는 제작원가로 한다.<!-- page 17 -->\n"
            "<!-- 다른 주석 -->"
        )
        assert assign_pages(content, self.PAGES) == (2, 2)


    def test_unmatched_content_returns_none(self):
        """코퍼스에 없는 내용은 None — backfill 리포트가 미매칭으로 드러낸다."""
        assert assign_pages("완전히 다른 문서의 문장입니다. 매칭될 수 없습니다.", self.PAGES) is None

    def test_short_lines_do_not_match(self):
        """짧은 라인(조항 번호 등)은 앵커가 못 된다 — 중복 오매칭 방지."""
        assert assign_pages("#### 10.1\n간단.", self.PAGES) is None

    def test_ambiguous_anchor_found_on_multiple_pages_is_skipped(self):
        """여러 페이지에 반복되는 문구는 투표에서 제외 — 범위 부풀림 방지."""
        pages = {
            1: "다음각호의사항은주석으로기재한다.유형자산의회계처리와공시에필요한사항",
            2: "다음각호의사항은주석으로기재한다.",
        }
        content = "다음 각 호의 사항은 주석으로 기재한다.\n유형자산의 회계처리와 공시에 필요한 사항"
        # 첫 라인은 1·2페이지 모두에 있어 스킵되고, 둘째 라인(1페이지 고유)만 투표한다
        assert assign_pages(content, pages) == (1, 1)

    def test_long_anchor_spanning_page_boundary_matches_by_head_tail(self):
        """페이지 경계에 걸친 긴 문단은 머리/꼬리 조각 probe로 시작·끝 페이지를 잡는다."""
        long_head = "유형자산의 손상차손은 회수가능액이 장부금액에 미달하는 경우에 인식하며 그 미달액을 말한다"
        long_tail = "손상차손누계액은 유형자산의 장부금액에서 차감하는 형식으로 표시하고 주석으로 공시한다"
        pages = {
            5: "앞부분본문" + long_head.replace(" ", ""),
            6: long_tail.replace(" ", "") + "뒷부분본문",
        }
        content = f"{long_head} {long_tail}"  # 한 라인이 두 페이지에 걸침
        assert assign_pages(content, pages) == (5, 6)


class TestMarkerPages:
    """content에 남아 있는 페이지 경계 마커(<!-- page N -->) — 정렬 결과의 자동 크로스체크 소스."""

    def test_extracts_marker_page_numbers(self):
        content = "본문 앞부분\n<!-- page 17 -->\n본문 뒷부분 <!-- page 18 -->"
        assert marker_pages(content) == [17, 18]

    def test_no_marker_returns_empty(self):
        assert marker_pages("마커 없는 본문") == []

    def test_pages_from_markers_spans_boundary(self):
        """마커 N은 'N페이지 시작' 경계 — 청크는 (N-1, N)에 걸친 것으로 부여한다.

        앵커 정렬이 불가능한 스캔본 PDF(ch9 실측: 14p 추출 텍스트 37자)의 폴백 소스.
        """
        assert pages_from_markers("앞 본문\n<!-- page 17 -->\n뒤 본문") == (16, 17)
        assert pages_from_markers("<!-- page 5 -->\n중간\n<!-- page 7 -->") == (4, 7)

    def test_pages_from_markers_clamps_to_first_page(self):
        assert pages_from_markers("<!-- page 1 -->본문") == (1, 1)

    def test_pages_from_markers_none_without_marker(self):
        assert pages_from_markers("마커 없는 본문") is None


class TestResolvePdfPath:
    """document_id → 원본 PDF 소재 규약 — source_path(온톨로지 JSON 경로) 의존 제거."""

    def test_explicit_document_id_pdf_takes_priority(self, tmp_path):
        (tmp_path / "gaap-ch10.pdf").write_bytes(b"%PDF")
        (tmp_path / "제10장_유형자산.pdf").write_bytes(b"%PDF")
        assert resolve_pdf_path("gaap-ch10", tmp_path) == tmp_path / "gaap-ch10.pdf"

    def test_chapter_glob_fallback_matches_current_raw_naming(self, tmp_path):
        (tmp_path / "제10장_유형자산(2017년_개정_반영).pdf").write_bytes(b"%PDF")
        (tmp_path / "제1장_재무회계개념체계.pdf").write_bytes(b"%PDF")
        assert resolve_pdf_path("gaap-ch10", tmp_path).name.startswith("제10장")
        # 제1장 글롭이 제10장을 오매칭하지 않는다
        assert resolve_pdf_path("gaap-ch1", tmp_path).name.startswith("제1장_")

    def test_ambiguous_glob_returns_none(self, tmp_path):
        (tmp_path / "제10장_a.pdf").write_bytes(b"%PDF")
        (tmp_path / "제10장_b.pdf").write_bytes(b"%PDF")
        assert resolve_pdf_path("gaap-ch10", tmp_path) is None

    def test_missing_or_unknown_pattern_returns_none(self, tmp_path):
        assert resolve_pdf_path("gaap-ch99", tmp_path) is None
        assert resolve_pdf_path("kifrs-x", tmp_path) is None
