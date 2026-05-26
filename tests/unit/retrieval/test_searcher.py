"""
[FUNC-005] 하이브리드 검색 단위 테스트

대상 모듈: src/retrieval/searcher.py
검증 범위:
    - dense_search(): Dense 검색 DB 쿼리 및 반환 규격
    - sparse_search(): Sparse 검색 DB 쿼리 및 반환 규격
    - normalize_scores(): Min-Max 정규화 로직
    - hybrid_search(): DENSE/SPARSE 가중 병합, 중복 처리, 필터 적용
    - 예외 처리 (SE-101, SE-102, SE-103)
"""
import pytest
from unittest.mock import patch, MagicMock
from psycopg import errors

from src.models.schemas import RetrievedChunk
from src.utils.exception import SearchTimeoutError, DatabaseQueryError, NoContextFoundError
from src.retrieval.searcher import (
    dense_search,
    sparse_search,
    normalize_scores,
    hybrid_search
)
from src.utils import config

# 테스트용 DB 행 데이터 (chunk_id, document_id, content, metadata, score)
MOCK_DB_ROWS_DENSE = [
    (1, "DOC-1", "dense content 1", '{"standard_type": "K-GAAP"}', 0.9),
    (2, "DOC-2", "dense content 2", '{"standard_type": "K-IFRS"}', 0.8),
]

MOCK_DB_ROWS_SPARSE = [
    (1, "DOC-1", "sparse content 1", '{"standard_type": "K-GAAP"}', 0.5), # 중복 ID (dense와 겹침)
    (3, "DOC-3", "sparse content 3", '{"standard_type": "K-GAAP"}', 0.9),
]

@pytest.fixture
def mock_db_pool():
    """psycopg3 커넥션 풀과 커서를 mock하는 픽스처"""
    with patch("src.retrieval.searcher.get_pool") as mock_get_pool:
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        
        mock_get_pool.return_value = mock_pool
        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        yield mock_cur

@pytest.fixture
def mock_embed():
    """OpenAI 임베딩 API를 mock하는 픽스처"""
    with patch("src.retrieval.searcher.client.embeddings.create") as mock_create:
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_create.return_value = mock_response
        yield mock_create


@pytest.mark.unit
class TestHybridSearchComponents:
    """검색 구성요소 단위 검증"""

    def test_dense_search_returns_chunks(self, mock_db_pool):
        """Dense 검색이 list[RetrievedChunk] 반환 검증"""
        mock_db_pool.fetchall.return_value = MOCK_DB_ROWS_DENSE
        
        results = dense_search([0.1]*1536, top_k=2)
        
        assert len(results) == 2    # top_k 만큼 반환
        assert isinstance(results[0], RetrievedChunk)   # RetrievedChunk 타입
        assert results[0].chunk_id == "1"   # chunk_id 반환
        assert results[0].score == 0.9    # score 반환
        assert results[0].metadata == {"standard_type": "K-GAAP"}   # metadata 반환
        # SET statement_timeout 1회, SELECT 1회
        assert mock_db_pool.execute.call_count == 2 

    def test_sparse_search_returns_chunks(self, mock_db_pool):
        """Sparse 검색이 list[RetrievedChunk] 반환 검증"""
        mock_db_pool.fetchall.return_value = MOCK_DB_ROWS_SPARSE
        
        results = sparse_search("query", top_k=2)
        
        assert len(results) == 2    # top_k 만큼 반환
        assert isinstance(results[0], RetrievedChunk)   # RetrievedChunk 타입
        assert results[0].chunk_id == "1"   # chunk_id 반환
        assert results[0].score == 0.5    # score 반환
        assert results[0].metadata == {"standard_type": "K-GAAP"}   # metadata 반환
        # SET statement_timeout 1회, SELECT 1회
        assert mock_db_pool.execute.call_count == 2
        
    def test_normalize_scores(self):
        """Min-Max 정규화 로직 검증"""
        chunks = [
            RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=10.0, metadata={}),
            RetrievedChunk(chunk_id="2", document_id="D2", content="c2", score=5.0, metadata={}),
            RetrievedChunk(chunk_id="3", document_id="D3", content="c3", score=0.0, metadata={}),
        ]
        
        normalized = normalize_scores(chunks)
        assert normalized[0].score == 1.0   # max_score / max_score
        assert normalized[1].score == 0.5   # min_score / max_score
        assert normalized[2].score == 0.0   # 0 / max_score

    def test_normalize_scores_same_values(self):
        """정규화 시 모든 점수가 같으면 1.0 부여 검증"""
        chunks = [
            RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=5.0, metadata={}),
            RetrievedChunk(chunk_id="2", document_id="D2", content="c2", score=5.0, metadata={}),
        ]
        normalized = normalize_scores(chunks)
        assert normalized[0].score == 1.0   # min = max이므로 1.0 반환
        assert normalized[1].score == 1.0   # min = max이므로 1.0 반환


@pytest.mark.unit
class TestHybridSearchIntegration:
    """하이브리드 검색 통합 흐름 검증 (DB 호출 분리 모킹)"""

    @patch("src.retrieval.searcher.dense_search")
    @patch("src.retrieval.searcher.sparse_search")
    def test_hybrid_merges_results(self, mock_sparse, mock_dense, mock_embed):
        """Dense + Sparse 가중 병합 검증"""
        mock_dense.return_value = [
            RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=1.0, metadata={}),
            RetrievedChunk(chunk_id="2", document_id="D2", content="c2", score=0.5, metadata={}),
        ]
        mock_sparse.return_value = [
            RetrievedChunk(chunk_id="3", document_id="D3", content="c3", score=1.0, metadata={}),
            RetrievedChunk(chunk_id="4", document_id="D4", content="c4", score=0.0, metadata={}),
        ]
        
        # 가중치: Dense=0.4, Sparse=0.6 가정
        with patch.object(config, "DENSE_WEIGHT", 0.4), patch.object(config, "SPARSE_WEIGHT", 0.6):
            results = hybrid_search("query", top_k=5)
            
        assert len(results) == 4    # top_k 만큼 반환
        # 정규화:
        # Dense -> "1": 1.0, "2": 0.0
        # Sparse -> "3": 1.0, "4": 0.0
        # 병합 (Dense*0.4 + Sparse*0.6):
        # "1" = 1.0*0.4 = 0.4
        # "2" = 0.0*0.4 = 0.0
        # "3" = 1.0*0.6 = 0.6
        # "4" = 0.0*0.6 = 0.0
        scores = {r.chunk_id: r.score for r in results}
        assert scores["3"] == 0.6   # Sparse 가중치 적용
        assert scores["1"] == 0.4   # Dense 가중치 적용
        assert scores["2"] == 0.0   # Sparse 가중치 적용
        assert scores["4"] == 0.0   # Sparse 가중치 적용
        
        # 내림차순 정렬 확인
        assert results[0].chunk_id == "3"   # 가장 높은 점수
        assert results[1].chunk_id == "1"   # 두 번째로 높은 점수

    @patch("src.retrieval.searcher.dense_search")
    @patch("src.retrieval.searcher.sparse_search")
    def test_duplicate_dedup(self, mock_sparse, mock_dense, mock_embed):
        """동일 chunk_id 반환 시 가중합(병합) 검증"""
        mock_dense.return_value = [
            RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=1.0, metadata={})
        ]
        mock_sparse.return_value = [
            RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=1.0, metadata={})
        ]
        
        with patch.object(config, "DENSE_WEIGHT", 0.4), patch.object(config, "SPARSE_WEIGHT", 0.6):
            results = hybrid_search("query", top_k=5)
            
        # ID 1이 양쪽에 존재 -> 정규화 후 각각 1.0 -> 1.0*0.4 + 1.0*0.6 = 1.0
        assert len(results) == 1    # 중복 제거
        assert results[0].chunk_id == "1"   # chunk_id
        assert results[0].score == 1.0  # 가중합(병합)

    @patch("src.retrieval.searcher.dense_search")
    @patch("src.retrieval.searcher.sparse_search")
    def test_hybrid_with_standard_filter(self, mock_sparse, mock_dense, mock_embed):
        """metadata_filter 파라미터가 개별 검색 함수로 잘 전달되는지 검증"""
        mock_dense.return_value = [RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=1.0, metadata={})]
        mock_sparse.return_value = []
        
        metadata_filter = {"standard_type": "K-GAAP"}
        hybrid_search("query", top_k=5, metadata_filter=metadata_filter)
        
        # 호출 인자 검증
        mock_dense.assert_called_once_with(mock_embed().data[0].embedding, 5, metadata_filter)
        mock_sparse.assert_called_once_with("query", 5, metadata_filter)

    @patch("src.retrieval.searcher.dense_search")
    @patch("src.retrieval.searcher.sparse_search")
    def test_no_results_raises_SE103(self, mock_sparse, mock_dense, mock_embed):
        """검색 결과 0건 시 NoContextFoundError(SE-103) 발생 검증"""
        mock_dense.return_value = []
        mock_sparse.return_value = []
        
        with pytest.raises(NoContextFoundError) as exc_info:
            hybrid_search("query", top_k=5)
            
        assert "검색 결과가 존재하지 않습니다" in str(exc_info.value)   # 검색 결과 0건


@pytest.mark.unit
class TestSearcherExceptions:
    """DB 연결 및 쿼리 수준의 예외 처리 검증 (SE-101, SE-102)"""

    def test_search_timeout_raises_SE101(self, mock_db_pool):
        """statement_timeout 시 SearchTimeoutError(SE-101) 발생 검증"""
        mock_db_pool.execute.side_effect = errors.QueryCanceled("canceling statement due to statement timeout")

        with pytest.raises(SearchTimeoutError) as exc_info:
            dense_search([0.1] * 1536, top_k=5)

        assert "응답 시간 초과" in str(exc_info.value)  # SE-101

    def test_db_error_raises_SE102(self, mock_db_pool):
        """기타 쿼리 실패 시 DatabaseQueryError(SE-102) 발생 검증"""
        mock_db_pool.execute.side_effect = Exception("DB 에러")

        with pytest.raises(DatabaseQueryError) as exc_info:
            dense_search([0.1] * 1536, top_k=5)

        assert "데이터베이스 쿼리 실행 실패" in str(exc_info.value) # SE-102


@pytest.mark.unit
class TestSearchResilience:
    """하이브리드 검색 복원력 검증: top_k 재탐색 및 독립 장애 처리"""

    @patch("src.retrieval.searcher.dense_search")
    @patch("src.retrieval.searcher.sparse_search")
    def test_retry_with_double_top_k_on_empty_results(self, mock_sparse, mock_dense, mock_embed):
        """초기 검색 0건 시 top_k × 2로 재탐색하여 결과 반환"""
        mock_dense.side_effect = [
            [],
            [RetrievedChunk(chunk_id="1", document_id="D1", content="retry content", score=0.8, metadata={})],
        ]
        mock_sparse.side_effect = [[], []]

        results = hybrid_search("영업권 손상차손 인식 기준은?", top_k=5)

        assert len(results) == 1    # 최종 반환 결과 수
        assert mock_dense.call_count == 2   # 총 호출 수
        assert mock_dense.call_args_list[1][0][1] == 10  # top_k * 2

    @patch("src.retrieval.searcher.dense_search")
    @patch("src.retrieval.searcher.sparse_search")
    def test_dense_failure_returns_sparse_only(self, mock_sparse, mock_dense, mock_embed):
        """Dense 장애 시 Sparse 결과만 반환"""
        mock_dense.side_effect = DatabaseQueryError("Dense DB 연결 실패")
        mock_sparse.return_value = [
            RetrievedChunk(chunk_id="1", document_id="D1", content="sparse only", score=0.9, metadata={}),
        ]

        results = hybrid_search("영업권 손상차손 인식 기준은?", top_k=5)

        assert len(results) == 1    # 최종 반환 결과 수
        assert results[0].chunk_id == "1"   # 반환 청크 ID

    @patch("src.retrieval.searcher.dense_search")
    @patch("src.retrieval.searcher.sparse_search")
    def test_sparse_failure_returns_dense_only(self, mock_sparse, mock_dense, mock_embed):
        """Sparse 장애 시 Dense 결과만 반환"""
        mock_dense.return_value = [
            RetrievedChunk(chunk_id="1", document_id="D1", content="dense only", score=0.9, metadata={}),
        ]
        mock_sparse.side_effect = SearchTimeoutError("Sparse 타임아웃")

        results = hybrid_search("영업권 손상차손 인식 기준은?", top_k=5)

        assert len(results) == 1    # 최종 반환 결과 수
        assert results[0].chunk_id == "1"   # 반환 청크 ID

    @patch("src.retrieval.searcher.dense_search")
    @patch("src.retrieval.searcher.sparse_search")
    def test_both_failure_raises_SE102(self, mock_sparse, mock_dense, mock_embed):
        """양쪽 모두 장애 시 DatabaseQueryError 발생"""
        mock_dense.side_effect = DatabaseQueryError("Dense 실패")
        mock_sparse.side_effect = SearchTimeoutError("Sparse 타임아웃")

        with pytest.raises(DatabaseQueryError) as exc_info:
            hybrid_search("영업권 손상차손 인식 기준은?", top_k=5)

        assert "모두 실패" in str(exc_info.value)   # 에러 메시지
