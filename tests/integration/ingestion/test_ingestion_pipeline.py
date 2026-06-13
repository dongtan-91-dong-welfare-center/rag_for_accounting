"""
[데이터 수집 파이프라인 통합 테스트

문서 파싱(Docling) → 온톨로지 그래프 → 청킹(FUNC-002/003) → 벡터 인덱싱(pgvector)
연쇄 동작에서 데이터 전달 정합성과 상태 진화를 검증한다.

설계 원칙:
    - 외부 의존(파싱·임베딩·DB)만 모킹하고 실제 청킹·인덱싱 모듈을 그대로 관통한다.
      청킹은 `src.db.ontology.chunker.chunk_graph`, 인덱싱은 `src.db.vector_store.index_documents`를 모킹 없이 호출하여, 시뮬레이션 헬퍼가 가렸던 실제 데이터 흐름의 정합성을 검증한다.
    - 라이브 인프라(Docker/모델 다운로드) 없이 통과한다. 임베딩·DB·파서는 conftest 픽스처로 차단하고, 청킹 토큰 카운터는 모델 로드를 피하려고 가벼운 단어 수 함수를 주입한다.
    - 온톨로지 그래프는 LLM 빌드(build_graph) 대신 git에 추적되는 `data/ontology/*.json`을 역직렬화해 입력한다. 이는 main.py의 기본 ingest 경로(미리 빌드된 온톨로지 JSON 적재)와 동일하다.
"""
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from src.db.ontology.chunker import chunk_graph
from src.db.ontology.models import OntologyGraph
from src.db.vector_store import index_documents
from src.models.schemas import ParsedDocument
from src.parse.parser import DoclingParser

# 온톨로지 JSON 디렉터리, 청킹 입력 그래프의 출처
ONTOLOGY_DIR = Path(__file__).resolve().parents[2].parent / "data" / "ontology"


def _word_count(text: str) -> int:
    """모델 로드를 피하는 가벼운 토큰 카운터 — 공백 기준 단어 수.

    청킹의 토큰 한도 분할은 chunker 단위 테스트가 검증하므로,
    통합 테스트에서는 KURE-v1 토크나이저 대신 이 함수를 주입해 인프라 없이 결정적으로 동작시킨다.
    """
    return len(text.split())


def _load_graph(chapter: str) -> OntologyGraph:
    """data/ontology/<chapter>.json을 OntologyGraph로 역직렬화한다."""
    path = ONTOLOGY_DIR / f"{chapter}.json"
    return OntologyGraph.model_validate_json(path.read_text(encoding="utf-8"))


# ── 전체 Ingestion 파이프라인 ──

@pytest.mark.system
class TestIngestionPipeline:
    """Parse → Chunk → Index 연쇄 데이터 흐름의 상태 진화 검증"""

    @pytest.mark.parametrize(
        "chapter, expected_status",
        [
            # gaap-ch1: content 노드 3개 → 청크 3개, 전량 적재 성공
            ("gaap-ch1", "success"),
            # gaap-ch6: content 노드 200개 → 다수 청크, 전량 적재 성공 (배치 분할 포함)
            ("gaap-ch6", "success"),
        ],
        ids=["small_chapter", "large_chapter"],
    )
    def test_parse_to_chunk_to_index_flow(
        self, chapter, expected_status, mock_db_pool, mock_embedding
    ):
        """실제 온톨로지 JSON을 입력으로 Parse → Chunk → Index 파이프라인이 데이터 손실 없이(고아 청크 0건) 동작하는지 검증."""

        # Parse 단계 — DoclingParser.parse를 모킹해 FUNC-001 출력 스펙(source_path)을 재현
        source_path = f"data/raw/{chapter}.pdf"
        with patch_parser(source_path):
            parsed = DoclingParser().parse(source_path)
        assert parsed.metadata["source_path"] == source_path

        # Chunk 단계 — 실제 chunk_graph 관통 (그래프는 JSON 역직렬화로 입력)
        graph = _load_graph(chapter)
        chunks = chunk_graph(
            graph,
            source_path=parsed.metadata["source_path"],
            token_counter=_word_count,
        )
        assert len(chunks) > 0

        # 데이터 무결성: 고아 청크 0건 — 모든 청크가 ontology_node_id를 보유
        assert all(c.metadata.ontology_node_id for c in chunks)
        # source 메타데이터가 파싱 → 청크까지 전달됨 (spec: "source" → "source_path")
        assert all(c.metadata.model_extra["source_path"] == source_path for c in chunks)

        # Index 단계 — 실제 index_documents 관통 (임베딩·DB는 모킹)
        result = index_documents(chunks, collection="test_collection")
        assert result.status == expected_status
        assert result.chunk_count == len(chunks)
        assert result.document_id == chunks[0].document_id

    def test_empty_graph_yields_failed_indexing(self, mock_db_pool, mock_embedding):
        """content 노드가 없는 그래프 → 청크 0개 → 인덱싱 failed (실모듈 관통)."""
        chunks = chunk_graph(
            OntologyGraph(),
            document_id="DOC-EMPTY",
            token_counter=_word_count,
        )
        assert chunks == []

        result = index_documents(chunks, collection="test_collection")
        assert result.chunk_count == 0
        assert result.status == "failed"

    @pytest.mark.parametrize(
        "scenario, expected_status, expected_count",
        [
            ("success", "success", 3),    # 모든 배치 성공
            ("partial", "partial", 2),    # 중간 배치 1개만 DB 오류 → 부분 커밋
            ("failed", "failed", 0),      # 빈 입력 → 적재 대상 없음
        ],
        ids=["full_success", "partial_failure", "complete_failure"],
    )
    def test_indexing_status_by_result(
        self, scenario, expected_status, expected_count, mock_db_pool, mock_embedding
    ):
        """실제 index_documents의 success / partial / failed 3상태를 실동작 기반으로 검증.

        partial은 단위 테스트가 토큰 한도 스킵 케이스를 이미 검증하므로, 여기서는
        배치 경계 케이스(배치 단위 부분 커밋) 1건으로 충분하다.
        """
        if scenario == "failed":
            # 빈 입력은 DB 접근 없이 즉시 failed
            result = index_documents([], collection="test_collection")
            assert result.status == expected_status
            assert result.chunk_count == expected_count
            return

        chunks = chunk_graph(_load_graph("gaap-ch1"), token_counter=_word_count)
        assert len(chunks) == 3

        if scenario == "partial":
            # 배치 크기 1 → 3개 배치 중 두 번째 배치만 DB 오류로 실패시킨다.
            # 부분 커밋 정책상 1·3번째 배치는 유지되어 chunk_count=2, status=partial.
            mock_db_pool.executemany.side_effect = [None, Exception("일시 장애"), None]
            with patch("src.db.vector_store.BATCH_SIZE", 1):
                result = index_documents(chunks, collection="test_collection")
        else:
            result = index_documents(chunks, collection="test_collection")

        assert result.status == expected_status
        assert result.chunk_count == expected_count

    def test_metadata_propagation_through_pipeline(self, mock_db_pool, mock_embedding):
        """문서 메타데이터(source_path)와 온톨로지 식별자(standard_type·chapter)가  파이프라인 전체를 관통하여 최종 청크까지 보존되는지 검증."""

        source_path = "data/raw/K-GAAP_제6장.pdf"
        with patch_parser(source_path):
            parsed = DoclingParser().parse(source_path)

        graph = _load_graph("gaap-ch6")
        chunks = chunk_graph(
            graph,
            source_path=parsed.metadata["source_path"],
            token_counter=_word_count,
        )

        # 모든 청크에 원본 source_path 보존
        assert all(c.metadata.model_extra["source_path"] == source_path for c in chunks)
        # standard_type·chapter는 Standard 노드 기준으로 전 청크에 전파
        assert all(c.metadata.standard_type == "GAAP" for c in chunks)
        assert all(c.metadata.chapter == "6" for c in chunks)
        # 같은 문서의 청크는 동일한 document_id (Standard 노드 id 기준)
        assert {c.document_id for c in chunks} == {"gaap-ch6"}


# ── 헬퍼 ──


@contextmanager
def patch_parser(source_path: str):
    """DoclingParser.parse를 모킹해 ParsedDocument를 반환한다.

    parser 실제 스펙(`src/parse/parser.py`)대로 metadata={"source_path": ...}를 싣는다.
    """
    parsed = ParsedDocument(
        title=Path(source_path).stem,
        text="(parsing mocked)",
        tables=[],
        metadata={"source_path": source_path},
    )
    with patch.object(DoclingParser, "parse", return_value=parsed):
        yield
