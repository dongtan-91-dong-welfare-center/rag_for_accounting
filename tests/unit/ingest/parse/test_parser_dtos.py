"""
[FUNC-001] 문서 파싱 스키마 단위 테스트

대상 모듈: src/models/schemas.py
검증 범위:
    - ParsedDocument 스키마 기본값 동작 검증
"""
import pytest


@pytest.mark.unit
class TestParsedDocumentSchema:
    """ParsedDocument 스키마 기본값 및 필드 동작 검증."""

    def test_tables_metadata_default_to_empty(self):
        # tables·metadata 미지정 시 빈 컬렉션 기본값 생성 보장
        from src.models.schemas import ParsedDocument
        doc = ParsedDocument(title="t", text="body")
        assert doc.tables == []
        assert doc.metadata == {}
        assert doc.title == "t"
        assert doc.text == "body"

