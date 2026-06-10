"""
[FUNC-003] 벡터 인덱싱 단위 테스트

대상 모듈: src/db/vector_store.py
검증 범위:
    - index_documents(): 청크 리스트 저장 및 IndexingResult 반환, upsert/배치/부분 실패 정책
    - similarity_search(): ANN 검색 반환 타입 검증
    - delete_collection(): 삭제 로직

DB와 임베딩 모델은 mock으로 차단한다 (searcher 단위 테스트와 동일한 방식).

TODO: similarity_search/delete_collection 구현 완료 후 @pytest.mark.skip을 제거
"""
import pytest
from unittest.mock import patch, MagicMock

from src.models.schemas import RetrievedChunk, IndexingResult
from src.utils.config import EMBEDDING_DIM
from src.utils.exception import LLMAPIConnectionError


def make_chunks(count: int, document_id: str = "D1") -> list[RetrievedChunk]:
    """테스트용 RetrievedChunk 목록 생성"""
    return [
        RetrievedChunk(
            chunk_id=f"c{i}",
            document_id=document_id,
            content=f"청크 내용 {i}",
            score=0.0,
            metadata={"ontology_node_id": f"gaap-ch6-s{i}"},
        )
        for i in range(count)
    ]


@pytest.fixture
def mock_db_pool():
    """psycopg3 커넥션 풀과 커서를 mock하는 픽스처"""
    with patch("src.db.vector_store.get_pool") as mock_get_pool:
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()

        mock_get_pool.return_value = mock_pool
        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        yield mock_cur


@pytest.fixture
def mock_embedding():
    """KURE-v1 임베딩(embed_texts)·토큰 계산(count_tokens)을 mock하는 픽스처"""
    with patch("src.db.vector_store.embed_texts") as mock_embed, \
         patch("src.db.vector_store.count_tokens") as mock_count:
        mock_embed.side_effect = lambda texts, node="index": [[0.1] * EMBEDDING_DIM for _ in texts]
        mock_count.return_value = 10    # 기본: 토큰 한도 이내
        yield mock_embed, mock_count


@pytest.mark.unit
class TestIndexDocuments:
    """index_documents() 인터페이스 규격 및 정책 검증"""

    def test_index_returns_indexing_result(self, mock_db_pool, mock_embedding):
        """
        입력: chunks (list[RetrievedChunk]), collection (str)
        출력: IndexingResult(document_id, chunk_count, status)
        """
        from src.db.vector_store import index_documents

        result = index_documents(make_chunks(2), collection="test_collection")

        assert isinstance(result, IndexingResult)
        assert result.status == "success"
        assert result.chunk_count == 2
        assert result.document_id == "D1"

    def test_index_empty_chunks(self):
        """빈 청크 리스트 전달 시 chunk_count=0, status=failed (DB 접근 없음)"""
        from src.db.vector_store import index_documents

        result = index_documents([], collection="test_collection")

        assert result.chunk_count == 0
        assert result.status == "failed"

    def test_upsert_query_uses_on_conflict(self, mock_db_pool, mock_embedding):
        """upsert 쿼리가 ON CONFLICT(chunk_id) 분기를 사용하는지 검증"""
        from src.db.vector_store import index_documents

        index_documents(make_chunks(2), collection="test_collection")

        # executemany 1회 호출 (2건은 한 배치) — 쿼리에 ON CONFLICT 포함
        assert mock_db_pool.executemany.call_count == 1
        query_obj, params = mock_db_pool.executemany.call_args[0]
        assert "ON CONFLICT" in query_obj.as_string(None)
        assert len(params) == 2     # 청크 2건 모두 파라미터로 전달

    def test_batch_split_by_batch_size(self, mock_db_pool, mock_embedding):
        """BATCH_SIZE를 초과하는 입력이 배치로 나뉘어 처리되는지 검증"""
        from src.db.vector_store import index_documents

        mock_embed, _ = mock_embedding
        with patch("src.db.vector_store.BATCH_SIZE", 2):
            result = index_documents(make_chunks(5), collection="test_collection")

        assert result.status == "success"
        assert result.chunk_count == 5
        assert mock_embed.call_count == 3           # 2 + 2 + 1
        assert mock_db_pool.executemany.call_count == 3

    def test_token_limit_chunk_skipped_as_partial(self, mock_db_pool, mock_embedding):
        """토큰 한도 초과 청크는 IX-201로 스킵되고 status=partial (부분 커밋 정책)"""
        from src.db.vector_store import index_documents
        from src.utils.config import EMBEDDING_MAX_TOKENS

        _, mock_count = mock_embedding
        # 첫 번째 청크만 한도 초과
        mock_count.side_effect = [EMBEDDING_MAX_TOKENS + 1, 10]

        result = index_documents(make_chunks(2), collection="test_collection")

        assert result.status == "partial"
        assert result.chunk_count == 1

    def test_embedding_failure_returns_failed(self, mock_db_pool, mock_embedding):
        """임베딩 호출 실패(CM-002) 시 해당 배치 전체 실패 → 전량 실패면 status=failed"""
        from src.db.vector_store import index_documents

        mock_embed, _ = mock_embedding
        mock_embed.side_effect = LLMAPIConnectionError("임베딩 모델 호출 실패", node="index")

        result = index_documents(make_chunks(2), collection="test_collection")

        assert result.status == "failed"
        assert result.chunk_count == 0

    def test_db_failure_on_upsert_returns_failed(self, mock_db_pool, mock_embedding):
        """upsert 단계 DB 오류(SE-102) 시 예외를 삼키고 status=failed로 보고"""
        from src.db.vector_store import index_documents

        mock_db_pool.executemany.side_effect = Exception("DB 연결 끊김")

        result = index_documents(make_chunks(2), collection="test_collection")

        assert result.status == "failed"
        assert result.chunk_count == 0

    def test_partial_batch_failure_commits_remaining(self, mock_db_pool, mock_embedding):
        """일부 배치만 실패하면 성공 배치는 유지(부분 커밋)되고 status=partial"""
        from src.db.vector_store import index_documents

        # 배치 크기 2 → 3개 배치 중 두 번째만 DB 오류
        mock_db_pool.executemany.side_effect = [None, Exception("일시 장애"), None]
        with patch("src.db.vector_store.BATCH_SIZE", 2):
            result = index_documents(make_chunks(5), collection="test_collection")

        assert result.status == "partial"
        assert result.chunk_count == 3      # 배치1(2건) + 배치3(1건)

    def test_ensure_collection_failure_returns_failed(self, mock_embedding):
        """테이블 보장(DDL) 실패 시 어떤 배치도 시도하지 않고 즉시 failed"""
        from src.db.vector_store import index_documents

        mock_embed, _ = mock_embedding
        with patch("src.db.vector_store.get_pool", side_effect=Exception("DB down")):
            result = index_documents(make_chunks(2), collection="test_collection")

        assert result.status == "failed"
        assert result.chunk_count == 0
        mock_embed.assert_not_called()      # DDL 실패 시 임베딩 비용을 쓰지 않음


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
            query_vector=[0.1] * EMBEDDING_DIM, top_k=5, collection="test_collection"
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
