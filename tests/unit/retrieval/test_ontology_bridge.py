"""
청크-온톨로지 노드 매핑 어댑터 단위 테스트

대상 모듈: src/retrieval/ontology_bridge.py
검증 범위:
    - chunks_to_node_ids(): ontology_node_id 추출, Silent Skip, 순서 유지 중복 제거
"""
import pytest

from src.models.schemas import RetrievedChunk
from src.retrieval.ontology_bridge import chunks_to_node_ids


def _chunk(chunk_id: str, ontology_node_id=None, **extra) -> RetrievedChunk:
    """테스트용 RetrievedChunk 생성 헬퍼.

    ontology_node_id가 None이면 metadata에 명시하지 않아 누락 상황을 재현한다.
    """
    metadata = dict(extra)
    if ontology_node_id is not None:
        metadata["ontology_node_id"] = ontology_node_id
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id="D1",
        content="content",
        score=1.0,
        metadata=metadata,
    )


@pytest.mark.unit
class TestChunksToNodeIds:
    """chunks_to_node_ids 매핑 로직 검증"""

    def test_extracts_node_ids(self):
        """각 청크의 ontology_node_id가 순서대로 추출된다."""
        chunks = [
            _chunk("c1", "gaap-ch6-s1-최초인식"),
            _chunk("c2", "gaap-ch6-s2-후속측정"),
        ]
        assert chunks_to_node_ids(chunks) == ["gaap-ch6-s1-최초인식", "gaap-ch6-s2-후속측정"]   # ontology_node_id가 있는 청크는 순서대로 추출된다.

    def test_silent_skip_missing_node_id(self):
        """ontology_node_id가 없는 청크는 조용히 무시되고 유효한 ID만 남는다."""
        chunks = [
            _chunk("c1", "gaap-ch6-s1-최초인식"),
            _chunk("c2"),                       # 메타데이터에 ontology_node_id 없음 → None
            _chunk("c3", ""),                   # 빈 문자열도 무시
            _chunk("c4", "gaap-ch6-s2-후속측정"),
        ]
        assert chunks_to_node_ids(chunks) == ["gaap-ch6-s1-최초인식", "gaap-ch6-s2-후속측정"]   # ontology_node_id가 None인 청크는 조용히 무시되고 유효한 ID만 남는다.

    def test_dedup_preserves_first_occurrence_order(self):
        """동일 노드를 가리키는 중복 청크는 첫 등장 순서를 유지하며 제거된다."""
        chunks = [
            _chunk("c1", "node-A"),
            _chunk("c2", "node-B"),
            _chunk("c3", "node-A"),   # 중복
            _chunk("c4", "node-C"),
            _chunk("c5", "node-B"),   # 중복
        ]
        assert chunks_to_node_ids(chunks) == ["node-A", "node-B", "node-C"] # 중복 제거

    def test_empty_input(self):
        """빈 입력은 빈 리스트를 반환한다."""
        assert chunks_to_node_ids([]) == []   # 빈 입력은 빈 리스트를 반환한다.

    def test_all_missing_returns_empty(self):
        """모든 청크에 ontology_node_id가 없으면 빈 리스트를 반환한다."""
        chunks = [_chunk("c1"), _chunk("c2", "")]
        assert chunks_to_node_ids(chunks) == [] # ontology_node_id가 없는 청크는 조용히 무시되고 유효한 ID만 남는다.

    def test_ignores_other_metadata_keys(self):
        """ontology_node_id 외 다른 메타데이터는 결과에 영향을 주지 않는다."""
        chunks = [
            _chunk("c1", "node-A", standard_type="K-GAAP", source="data/x.pdf"),
        ]
        assert chunks_to_node_ids(chunks) == ["node-A"] # ontology_node_id 외 다른 메타데이터는 결과에 영향을 주지 않는다.
