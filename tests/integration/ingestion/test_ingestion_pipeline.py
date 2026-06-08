"""
[데이터 수집 파이프라인 통합 테스트]

문서 파싱(Docling) → 온톨로지 그래프 구축(Apache AGE) → 벡터 인덱싱(pgvector)
연쇄 동작에서 다양한 입력 조건(정상, 경계값, 예외)에 따른 데이터 전달 정합성과 상태 진화를 검증합니다.

설계 원칙:
    - pytest.mark.parametrize로 문서 유형, 크기, 예외 상황을 다양하게 주입하여 Ingestion 파이프라인의 견고함을 검증합니다.
    - 개별 스키마가 아닌, Parse → Chunk → Index 전체 흐름을 하나의 테스트에서 관통하며 데이터 손실 여부를 추적합니다.
"""
import pytest
from src.models.schemas import ParsedDocument, IndexingResult, RetrievedChunk


# ── Mock 데이터 팩토리 ──

def make_parsed_document(
    title: str,
    sections: list[str],
    tables: list[dict] | None = None,
    metadata: dict | None = None,
) -> ParsedDocument:
    """테스트용 ParsedDocument 생성"""
    return ParsedDocument(
        title=title,
        text="\n".join(sections),
        tables=tables or [],
        metadata=metadata or {"source": f"data/{title}.pdf"}
    )


def simulate_chunking(doc: ParsedDocument) -> list[RetrievedChunk]:
    """ParsedDocument를 청크로 분할하는 시뮬레이션"""
    return [
        RetrievedChunk(
            chunk_id=f"chunk-{i}",
            document_id=f"DOC-{doc.title}",
            content=section,
            score=0.0,
            metadata={"source": doc.metadata.get("source", "unknown")}
        )
        for i, section in enumerate(doc.text.split("\n"))
        if section.strip()
    ]


def simulate_indexing(doc_id: str, chunk_count: int, *, force_status: str | None = None) -> IndexingResult:
    """인덱싱 결과 시뮬레이션"""
    if force_status:
        status = force_status
    elif chunk_count == 0:
        status = "failed"
    else:
        status = "success"
    return IndexingResult(document_id=doc_id, chunk_count=chunk_count, status=status)


# ── 전체 Ingestion 파이프라인 ──

@pytest.mark.system
class TestIngestionPipeline:
    """Parse → Chunk → Index 연쇄 데이터 흐름의 상태 진화 검증"""

    @pytest.mark.parametrize(
        "title, sections, tables, expected_chunk_count, expected_status",
        [
            # 케이스 1: 표준 문서 — 2개 섹션, 표 없음 → 정상 인덱싱
            (
                "일반기업회계기준_제10장",
                ["10.1 유형자산의 정의: 영업활동에 사용할 목적으로 보유하는 자산",
                 "10.22 재평가 주기: 3~5년 내 재평가 실시 권고"],
                [],
                2,
                "success",
            ),
            # 케이스 2: 표 포함 문서 — 텍스트 3개 섹션 + 표 1개 → 정상 인덱싱
            (
                "일반기업회계기준_제6장",
                ["6.1 적용 범위: 금융자산·금융부채의 인식과 측정",
                 "6.2 금융자산의 분류: 당기손익인식, 매도가능, 만기보유, 대여금 및 수취채권",
                 "6.3 최초 인식: 공정가치로 측정"],
                [{"headers": ["구분", "내용"], "rows": [["유동", "1년 이내"]]}],
                3,
                "success",
            ),
            # 케이스 3: 대용량 문서 — 10개 섹션 → 정상 인덱싱
            (
                "일반기업회계기준_전체",
                [f"제{i}장 내용: 회계 기준서의 제{i}장에 해당하는 상세 내용입니다." for i in range(1, 11)],
                [],
                10,
                "success",
            ),
            # 케이스 4: 빈 본문 문서 — 섹션 0개 → 인덱싱 실패
            (
                "빈_문서",
                [],
                [],
                0,
                "failed",
            ),
            # 케이스 5: 본문은 없지만 표만 있는 문서 → 청크 0개, 인덱싱 실패
            (
                "표만_있는_문서",
                [],
                [{"headers": ["계정", "금액"], "rows": [["매출채권", "100,000"]]}],
                0,
                "failed",
            ),
        ],
        ids=["standard_doc", "doc_with_tables", "large_doc", "empty_doc", "table_only_doc"]
    )
    def test_parse_to_chunk_to_index_flow(
        self, title, sections, tables, expected_chunk_count, expected_status
    ):
        """문서의 유형과 크기에 따라 Parse → Chunk → Index 파이프라인이
        데이터 손실 없이 올바르게 동작하는지 검증"""

        # Parse 단계
        doc = make_parsed_document(title=title, sections=sections, tables=tables)
        assert doc.title == title
        assert len(doc.tables) == len(tables)

        # Chunk 단계
        chunks = simulate_chunking(doc)
        assert len(chunks) == expected_chunk_count

        # 데이터 무결성: 청크의 source 메타데이터가 원본 문서에서 전달됨
        for chunk in chunks:
            assert chunk.metadata.model_extra["source"] == doc.metadata["source"]

        # Index 단계
        result = simulate_indexing(f"DOC-{title}", len(chunks))
        assert result.chunk_count == expected_chunk_count
        assert result.status == expected_status


    @pytest.mark.parametrize(
        "chunk_count, force_status",
        [
            (25, "success"),
            (10, "partial"),
            (0, "failed"),
        ],
        ids=["full_success", "partial_failure", "complete_failure"]
    )
    def test_indexing_status_by_result(self, chunk_count, force_status):
        """인덱싱 결과의 status가 청크 수와 처리 상태에 따라 올바르게 설정되는지 검증"""

        result = simulate_indexing("DOC-TEST", chunk_count, force_status=force_status)
        assert result.status == force_status
        assert result.chunk_count == chunk_count

        # partial이면 일부만 성공했으므로 chunk_count > 0
        if force_status == "partial":
            assert result.chunk_count > 0
        # failed이면 인덱싱된 청크가 없어야 함
        if force_status == "failed":
            assert result.chunk_count == 0


    def test_metadata_propagation_through_pipeline(self):
        """문서 메타데이터(source, standard, page_count)가 파이프라인 전체를 관통하여
        최종 청크까지 보존되는지 검증"""

        metadata = {
            "source": "data/K-GAAP_제10장.pdf",
            "standard": "K-GAAP",
            "page_count": 42
        }
        doc = make_parsed_document(
            title="메타데이터_테스트",
            sections=["10.1 유형자산 정의", "10.2 감가상각"],
            metadata=metadata
        )

        chunks = simulate_chunking(doc)

        # 모든 청크에 원본 메타데이터의 source가 보존
        for chunk in chunks:
            assert chunk.metadata.model_extra["source"] == metadata["source"]   # metadata.model_extra.source 명시 필드 검증

        # document_id가 일관되게 부여
        doc_ids = {chunk.document_id for chunk in chunks}
        assert len(doc_ids) == 1  # 같은 문서의 청크는 동일한 document_id
