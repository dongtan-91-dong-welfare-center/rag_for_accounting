"""
[FUNC-001] 문서 파싱 DTO 단위 테스트

대상 모듈: src/ingest/parse/parser_dtos.py, src/models/schemas.py
검증 범위:
    - ParsedDocument가 parser_dtos·schemas 두 경로에서 동일 클래스로 정의되는지 검증
    - ParsedDocument 기본값 동작 검증
"""
import pytest


@pytest.mark.unit
class TestParsedDocumentDefinition:
    """ParsedDocument 이원 정의 통합 — parser_dtos ↔ schemas 단일 정본 검증."""

    def test_single_definition_across_import_paths(self):
        # parser_dtos와 schemas 두 경로가 동일 클래스 객체로 귀결되어야 한다(이원 정의 제거).
        from src.ingest.parse.parser_dtos import ParsedDocument as FromParser
        from src.models.schemas import ParsedDocument as FromSchemas
        assert FromParser is FromSchemas

    def test_tables_metadata_default_to_empty(self):
        # dataclass의 호출 편의(기본값)를 보존 — tables·metadata 미지정 시 빈 컬렉션.
        from src.models.schemas import ParsedDocument
        doc = ParsedDocument(title="t", text="body")
        assert doc.tables == []
        assert doc.metadata == {}
