"""
[FUNC-001] 문서 파싱 단위 테스트 Stub

대상 모듈: src/parse/parser.py
검증 범위:
    - DoclingParser 인스턴스 생성 및 설정값 보존
    - parse() 메서드의 반환 타입(ParsedDocument) 규격 검증
    - table_to_text() 표 → 텍스트 변환 로직

TODO: 실제 Docling 연동 후 @pytest.mark.skip을 제거하고 Mock → 실제 호출로 교체
"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


@pytest.mark.unit
class TestDoclingParserInit:
    """DoclingParser 초기화 및 설정값 검증"""

    def test_parser_default_init(self):
        """기본 생성자 호출 시 threshold가 None으로 초기화"""
        from src.parse.parser import DoclingParser
        parser = DoclingParser()
        assert parser._overlap_threshold is None
        assert parser._containment_threshold is None
        assert parser._converter is None

    def test_parser_custom_thresholds(self):
        """커스텀 threshold 지정 시 값이 보존되는지 확인"""
        from src.parse.parser import DoclingParser
        parser = DoclingParser(overlap_threshold=0.15, containment_threshold=0.2)
        assert parser._overlap_threshold == 0.15
        assert parser._containment_threshold == 0.2

    def test_parser_injected_converter(self):
        """외부 converter 주입 시 _get_converter()가 주입된 객체를 반환"""
        from src.parse.parser import DoclingParser
        mock_converter = MagicMock()
        parser = DoclingParser(converter=mock_converter)
        assert parser._get_converter() is mock_converter


@pytest.mark.unit
class TestTableToText:
    """표(table) → 텍스트 변환 로직 검증"""

    def test_basic_table_conversion(self):
        """단순 2×2 표의 '헤더: 값' 변환 검증"""
        from src.parse.parser import DoclingParser
        parser = DoclingParser()
        table = {
            "headers": ["과목", "금액"],
            "rows": [["매출", "1000"], ["비용", "500"]]
        }
        result = parser.table_to_text(table)
        assert "과목: 매출, 금액: 1000" in result
        assert "과목: 비용, 금액: 500" in result

    def test_empty_table(self):
        """빈 rows 테이블 변환 시 빈 문자열 반환"""
        from src.parse.parser import DoclingParser
        parser = DoclingParser()
        table = {"headers": ["A", "B"], "rows": []}
        result = parser.table_to_text(table)
        assert result == ""

    def test_single_column_table(self):
        """단일 컬럼 테이블 변환"""
        from src.parse.parser import DoclingParser
        parser = DoclingParser()
        table = {"headers": ["항목"], "rows": [["자산"], ["부채"]]}
        result = parser.table_to_text(table)
        assert "항목: 자산" in result
        assert "항목: 부채" in result


@pytest.mark.unit
class TestParseMethod:
    """parse() 메서드 반환값 규격 검증"""

    @pytest.mark.skip(reason="FUNC-001 실제 Docling 연동 후 활성화 예정 — PDF 파일 필요")
    def test_parse_returns_parsed_document(self):
        """
        입력: file_path (str)
        출력: ParsedDocument 객체 (title, text, tables, metadata 필드 포함)
        """
        from src.parse.parser import DoclingParser
        from src.parse.parser_dtos import ParsedDocument

        parser = DoclingParser()
        result = parser.parse("data/회계_sample.pdf")
        assert isinstance(result, ParsedDocument)
        assert result.title is not None
        assert isinstance(result.text, str)
        assert isinstance(result.tables, list)
        assert "source_path" in result.metadata

    @pytest.mark.skip(reason="FUNC-001 실제 Docling 연동 후 활성화 예정 — PDF 파일 필요")
    def test_parse_invalid_path_raises_error(self):
        """존재하지 않는 파일 경로 전달 시 적절한 예외 발생"""
        from src.parse.parser import DoclingParser

        parser = DoclingParser()
        with pytest.raises(Exception):
            parser.parse("nonexistent.pdf")


@pytest.mark.unit
class TestParsedDocumentDefinition:
    """ParsedDocument 이원 정의 통합 — parser_dtos ↔ schemas 단일 정본 검증."""

    def test_single_definition_across_import_paths(self):
        # parser_dtos와 schemas 두 경로가 동일 클래스 객체로 귀결되어야 한다(이원 정의 제거).
        from src.parse.parser_dtos import ParsedDocument as FromParser
        from src.models.schemas import ParsedDocument as FromSchemas
        assert FromParser is FromSchemas

    def test_tables_metadata_default_to_empty(self):
        # dataclass의 호출 편의(기본값)를 보존 — tables·metadata 미지정 시 빈 컬렉션.
        from src.models.schemas import ParsedDocument
        doc = ParsedDocument(title="t", text="body")
        assert doc.tables == []
        assert doc.metadata == {}
