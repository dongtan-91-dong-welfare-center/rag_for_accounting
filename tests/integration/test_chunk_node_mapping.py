"""
[청킹 ↔ 온톨로지 노드 매핑 무결성 통합 테스트]

청킹 → 인덱싱 → 검색 → 온톨로지 노드 조회로 이어지는 연동 경로를, 라이브 pgvector 컨테이너와 실제 KURE-v1 임베딩으로 1회 관통하며 chunk_id ↔ node_id 매핑 무결성을 검증한다.

검증 항목:
    - 고아 청크 0건: 인덱싱된 모든 청크가 1개 이상의 온톨로지 노드에 매핑된다(ontology_node_id 보유)
    - dangling 참조 0건: 검색 결과 청크의 ontology_node_id가 실제 OntologyNode.id로 해소된다.
    - Subsection 노드의 paragraphs 정보와 청크 content의 정합성(샘플)
    - ontology_bridge 폴백: 매핑 없는 청크는 예외 없이 빈 매핑으로 처리된다.

전제:
    - 라이브 인프라(pgvector 컨테이너)·KURE-v1 모델이 필요하다. 인프라/환경이 없으면 상위
      tests/integration/conftest.py의 check_integration_env가 세션 단위로 skip 처리한다.
    - 적재는 검색기와 공유하는 운영 테이블을 오염시키지 않도록 전용 테스트 컬렉션을 쓰고,
      teardown에서 비운다(데이터 격리).
    - 온톨로지 그래프는 LLM 빌드 대신 git에 추적되는 data/ontology/*.json을 역직렬화해 입력한다.
"""
from pathlib import Path

import pytest

from src.db.connection import close_pool, init_pool
from src.db.ontology.chunker import chunk_graph
from src.db.ontology.models import OntologyGraph
from src.db.vector_store import delete_collection, index_documents, similarity_search
from src.models.schemas import RetrievedChunk
from src.retrieval.ontology_bridge import chunks_to_node_ids
from src.utils.embedding import embed_texts

ONTOLOGY_DIR = Path(__file__).resolve().parents[2] / "data" / "ontology"
CHAPTER = "gaap-ch1"                          # content 노드 3개로 적재·검색이 가볍다
TEST_COLLECTION = "chunks_test_ch1_mapping"   # 운영 chunks 테이블과 분리된 전용 컬렉션
SOURCE_PATH = f"data/ontology/{CHAPTER}.json"


@pytest.fixture(scope="class")
def indexed_chapter():
    """gaap-ch1을 청킹 → 인덱싱하여 전용 컬렉션에 적재하고 (graph, chunks)를 제공한다.

    teardown에서 delete_collection으로 적재분을 비워 운영 데이터 오염과 테스트 간 누출을 막는다.
    """
    graph = OntologyGraph.model_validate_json(
        (ONTOLOGY_DIR / f"{CHAPTER}.json").read_text(encoding="utf-8")
    )
    # 라이브 테스트는 main.py와 달리 풀 초기화가 자동으로 일어나지 않으므로 직접 연다.
    init_pool()
    try:
        # 적재 직전 잔여 행 정리 후 재적재 (멱등 보장)
        delete_collection(TEST_COLLECTION)

        chunks = chunk_graph(graph, source_path=SOURCE_PATH)
        assert chunks, "청킹 결과가 비어 있으면 매핑 검증을 진행할 수 없다"

        result = index_documents(chunks, collection=TEST_COLLECTION)
        assert result.status == "success", f"적재 실패: {result.status}"
        assert result.chunk_count == len(chunks)

        yield graph, chunks
    finally:
        delete_collection(TEST_COLLECTION)
        close_pool()


@pytest.mark.system
class TestChunkNodeMapping:
    """chunk_id ↔ node_id 매핑 무결성 검증 (라이브 pgvector)"""

    def test_no_orphan_chunks(self, indexed_chapter):
        """모든 인덱싱된 청크가 1개 이상의 노드에 매핑된다 (고아 청크 0건)."""
        _, chunks = indexed_chapter
        orphans = [c.chunk_id for c in chunks if not c.metadata.ontology_node_id]
        assert not orphans, f"고아 청크 발견(ontology_node_id 없음): {orphans}"

    def test_search_node_ids_resolve_to_real_nodes(self, indexed_chapter):
        """검색 결과 청크의 ontology_node_id가 실제 OntologyNode.id로 올바르게 연결하고 있는지 검증"""
        graph, chunks = indexed_chapter
        node_ids = {n.id for n in graph.nodes}

        query_vector = embed_texts(["일반기업회계기준의 목적과 적용 범위"], node="search")[0]
        results = similarity_search(query_vector, top_k=5, collection=TEST_COLLECTION)
        assert results, "검색 결과가 비어 있으면 매핑 무결성을 검증할 수 없다"

        # 검색 결과의 모든 ontology_node_id가 그래프에 실재하는지 — 실패 시 문제 쌍을 식별
        dangling = [
            (r.chunk_id, r.metadata.ontology_node_id)
            for r in results
            if r.metadata.ontology_node_id not in node_ids
        ]
        assert not dangling, f"dangling node_id 참조(chunk_id, node_id): {dangling}"

        # ontology_bridge의 그래프 탐색 진입점도 전부 실재 노드여야 한다
        entry_node_ids = chunks_to_node_ids(results)
        assert entry_node_ids, "검색 결과에서 진입 노드 ID를 하나도 추출하지 못했다"
        assert all(nid in node_ids for nid in entry_node_ids)

    def test_subsection_paragraph_consistency(self, indexed_chapter):
        """Subsection 노드의 paragraphs 문단 번호가 대응 청크 content에 등장하는지 샘플 검증."""
        graph, chunks = indexed_chapter
        # gaap-ch1은 노드↔청크 1:1(분할 없음)이므로 ontology_node_id로 청크를 찾는다
        chunk_by_node: dict[str, RetrievedChunk] = {}
        for c in chunks:
            chunk_by_node.setdefault(c.metadata.ontology_node_id, c)

        subsections = [
            n for n in graph.nodes
            if n.node_type == "Subsection" and n.paragraphs and n.id in chunk_by_node
        ]
        assert subsections, "paragraphs를 가진 Subsection 노드를 찾지 못했다"

        for node in subsections:
            chunk = chunk_by_node[node.id]
            present = [p for p in node.paragraphs if p in chunk.content]
            assert present, (
                f"노드 {node.id}의 문단 번호 {node.paragraphs}가 청크 content에 없음: "
                f"{chunk.content[:60]!r}"
            )

    def test_ontology_bridge_fallback_on_unmapped_chunk(self):
        """매핑 정보가 없는 청크는 예외 없이 빈 매핑으로 처리된다 (ontology_bridge 폴백)"""
        unmapped = RetrievedChunk(
            chunk_id="unmapped-1",
            document_id="DOC-X",
            content="온톨로지 노드에 매핑되지 않은 청크",
            score=0.1,
        )
        # ontology_node_id가 없으므로 Silent Skip → 빈 리스트, 예외 없음
        assert chunks_to_node_ids([unmapped]) == []
