"""
[FUNC-003] 벡터 인덱싱 단위 테스트 Stub

대상 모듈: src/db/vector_store.py
검증 범위:
    - index_documents(): 청크 리스트 저장 및 IndexingResult 반환
    - similarity_search(): ANN 검색 반환 타입 검증
    - delete_collection(): 삭제 로직

TODO: vector_store.py 구현 완료 후 @pytest.mark.skip을 제거
"""
import pytest
from src.models.schemas import RetrievedChunk, IndexingResult


@pytest.mark.unit
class TestIndexDocuments:
    """index_documents() 인터페이스 규격 검증"""

    @pytest.mark.skip(reason="FUNC-003 vector_store 구현 후 활성화 예정 — DB 연동 필요")
    def test_index_returns_indexing_result(self):
        """
        입력: chunks (list[RetrievedChunk]), collection (str)
        출력: IndexingResult(document_id, chunk_count, status)
        """
        from src.db.vector_store import index_documents

        chunks = [
            RetrievedChunk(chunk_id="c1", document_id="D1", content="영업권 정의", score=0.0, metadata={}),
            RetrievedChunk(chunk_id="c2", document_id="D1", content="손상차손 인식", score=0.0, metadata={}),
        ]
        result = index_documents(chunks, collection="test_collection")
        assert isinstance(result, IndexingResult)
        assert result.status in ("success", "partial", "failed")
        assert result.chunk_count >= 0

    @pytest.mark.skip(reason="FUNC-003 vector_store 구현 후 활성화 예정 — DB 연동 필요")
    def test_index_empty_chunks(self):
        """빈 청크 리스트 전달 시 chunk_count=0"""
        from src.db.vector_store import index_documents

        result = index_documents([], collection="test_collection")
        assert result.chunk_count == 0


@pytest.mark.unit
class TestSimilaritySearch:
    """similarity_search() 인터페이스 규격 검증"""

    @pytest.mark.skip(reason="FUNC-003 vector_store 구현 후 활성화 예정 — DB 연동 필요")
    def test_search_returns_retrieved_chunks(self):
        """
        입력: query_vector (list[float]), top_k (int), collection (str)
        출력: list[RetrievedChunk]
        """
        from src.db.vector_store import similarity_search

        results = similarity_search(
            query_vector=[0.1] * 768, top_k=5, collection="test_collection"
        )
        assert isinstance(results, list)
        if results:
            assert isinstance(results[0], RetrievedChunk)


@pytest.mark.unit
class TestDeleteCollection:
    """delete_collection() 인터페이스 규격 검증"""

    @pytest.mark.skip(reason="FUNC-003 vector_store 구현 후 활성화 예정 — DB 연동 필요")
    def test_delete_returns_bool(self):
        """삭제 성공 시 True 반환"""
        from src.db.vector_store import delete_collection

        result = delete_collection("test_collection")
        assert isinstance(result, bool)
