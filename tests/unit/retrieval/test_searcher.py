"""
[FUNC-005] 하이브리드 검색 단위 테스트

대상 모듈: src/retrieval/searcher.py
검증 범위:
    - dense_search(): Dense 검색 DB 쿼리 및 반환 규격
    - sparse_search(): Sparse 검색 DB 쿼리 및 반환 규격
    - reciprocal_rank_fusion(): RRF 순위 기반 병합 로직
    - search_chunks(): DENSE/SPARSE RRF 병합, 중복 처리, 필터 적용
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
    reciprocal_rank_fusion,
    search_chunks
)
from src.utils import config
from src.utils.config import EMBEDDING_DIM

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
    """KURE-v1 공유 임베딩 함수(embed_texts)를 mock하는 픽스처"""
    with patch("src.retrieval.searcher.embed_texts") as mock_embed_texts:
        mock_embed_texts.return_value = [[0.1] * EMBEDDING_DIM]
        yield mock_embed_texts


@pytest.mark.unit
class TestHybridSearchComponents:
    """검색 구성요소 단위 검증"""

    def test_dense_search_returns_chunks(self, mock_db_pool):
        """Dense 검색이 list[RetrievedChunk] 반환 검증"""
        mock_db_pool.fetchall.return_value = MOCK_DB_ROWS_DENSE
        
        results = dense_search([0.1]*EMBEDDING_DIM, top_k=2)
        
        assert len(results) == 2    # top_k 만큼 반환
        assert isinstance(results[0], RetrievedChunk)   # RetrievedChunk 타입
        assert results[0].chunk_id == "1"   # chunk_id 반환
        assert results[0].score == 0.9    # score 반환
        assert results[0].metadata.standard_type == "K-GAAP"   # metadata 명시 필드 반환
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
        assert results[0].metadata.standard_type == "K-GAAP"   # metadata 명시 필드 반환
        # SET statement_timeout 1회, SELECT 1회
        assert mock_db_pool.execute.call_count == 2
        
    def test_reciprocal_rank_fusion_rank_based(self):
        """RRF가 점수가 아닌 순위(리스트 위치) 기반으로 병합하는지 검증"""
        k = config.RRF_K
        # 점수 절댓값이 극단적으로 달라도 순위만 반영되어야 함
        results = [
            RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=999.0, metadata={}),
            RetrievedChunk(chunk_id="2", document_id="D2", content="c2", score=0.001, metadata={}),
        ]

        fused = reciprocal_rank_fusion([results])

        # rank는 1부터 시작: 1/(k+1), 1/(k+2)
        assert fused[0].chunk_id == "1" # 999.0 > 0.001 이므로 1번이 0번 인덱스로
        assert fused[0].score == pytest.approx(1.0 / (k + 1))   # 1/(k+1)
        assert fused[1].chunk_id == "2" # 0.001 < 999.0 이므로 2번이 1번 인덱스로
        assert fused[1].score == pytest.approx(1.0 / (k + 2))   # 1/(k+2)

    def test_reciprocal_rank_fusion_merges_duplicates(self):
        """여러 리스트에 동일 chunk_id가 있으면 RRF 점수를 합산하는지 검증"""
        k = config.RRF_K
        dense = [RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=0.9, metadata={})]
        sparse = [RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=0.5, metadata={})]

        fused = reciprocal_rank_fusion([dense, sparse])

        assert len(fused) == 1   # 중복 병합
        assert fused[0].score == pytest.approx(2.0 / (k + 1))   # 양쪽 모두 1위(rank=1): 1/(k+1) + 1/(k+1)

    def test_reciprocal_rank_fusion_single_list_fallback(self):
        """한쪽 리스트가 비어도(폴백) 나머지 리스트로 정상 병합되는지 검증"""
        k = config.RRF_K
        dense = [RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=0.9, metadata={})]

        fused = reciprocal_rank_fusion([dense, []])

        assert len(fused) == 1  # 한쪽 리스트가 비어도 나머지 리스트로 정상 병합되는지 검증
        assert fused[0].chunk_id == "1" # dense에만 chunk_id가 있으므로 1번이 반환
        assert fused[0].score == pytest.approx(1.0 / (k + 1)) # 1/(k+1)

    def test_reciprocal_rank_fusion_empty(self):
        """모든 리스트가 비면 빈 결과 반환"""
        assert reciprocal_rank_fusion([[], []]) == []

    def test_reciprocal_rank_fusion_does_not_mutate_input(self):
        """RRF가 호출자의 원본 객체 score를 변형하지 않는지 검증 (불변 반환)"""
        chunks = [
            RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=10.0, metadata={}),
            RetrievedChunk(chunk_id="2", document_id="D2", content="c2", score=0.0, metadata={}),
        ]

        fused = reciprocal_rank_fusion([chunks])

        # 원본 객체의 score는 그대로 보존되어야 함
        assert chunks[0].score == 10.0   # 원본값은 10.0
        assert chunks[1].score == 0.0    # 원본값은 0.0
        assert all(f is not c for f, c in zip(fused, chunks)) # 반환된 객체는 원본과 다른 인스턴스


@pytest.mark.unit
class TestWeightedRRF:
    """
    리스트별 가중 RRF 검증 — sparse 활성화 시 dense 상위를 지키는 레버.

    가중은 운영 기본 동작을 바꾸지 않아야 한다. 
    기존 RRF 테스트가 그 불변을 지키고, 이 클래스는 가중을 켰을 때의 억제 동작을 고정한다.
    """

    @staticmethod
    def _chunk(chunk_id: str, score: float = 0.0) -> RetrievedChunk:
        return RetrievedChunk(chunk_id=chunk_id, document_id=f"D{chunk_id}", content=f"c{chunk_id}", score=score, metadata={})

    def test_weights_none_equals_all_ones(self):
        """weights 미지정은 전부 1.0과 같은 결과 — 현행 동작 무변경 보장"""
        dense = [self._chunk("1"), self._chunk("2")]
        sparse = [self._chunk("2"), self._chunk("3")]

        default = reciprocal_rank_fusion([dense, sparse])
        explicit = reciprocal_rank_fusion([dense, sparse], weights=[1.0, 1.0])

        assert [c.chunk_id for c in default] == [c.chunk_id for c in explicit]
        assert [c.score for c in default] == [c.score for c in explicit]

    def test_weight_scales_list_contribution(self):
        """가중치는 해당 리스트의 순위 점수에 그대로 곱해진다"""
        k = config.RRF_K
        dense = [self._chunk("1")]
        sparse = [self._chunk("2")]

        fused = reciprocal_rank_fusion([dense, sparse], weights=[1.0, 0.2])
        by_id = {c.chunk_id: c.score for c in fused}

        assert by_id["1"] == pytest.approx(1.0 / (k + 1))
        assert by_id["2"] == pytest.approx(0.2 / (k + 1))

    def test_weight_suppresses_summation_regression(self):
        """
        sparse 가중을 낮추면 양쪽 리스트 합산이 dense 단독 1위를 밀어내지 못한다.

        실측된 회귀 메커니즘 재현: 밀어내는 청크("2")는 dense 하위(10위) ∩ sparse 1위라 양쪽에서 점수를 받는다.
        대칭 RRF(w=1.0)에서는 그 합산이 dense 단독 1위("1")를 넘고,w를 낮추면 dense의 순위 격차(1/61 − 1/70)가 다시 이겨 1위가 보존된다.
        """
        fillers = [self._chunk(f"f{i}") for i in range(2, 10)]
        dense = [self._chunk("1"), *fillers, self._chunk("2")]   # "2"는 dense 10위
        sparse = [self._chunk("2")]

        symmetric = reciprocal_rank_fusion([dense, sparse], weights=[1.0, 1.0])
        weighted = reciprocal_rank_fusion([dense, sparse], weights=[1.0, 0.1])

        assert symmetric[0].chunk_id == "2"   # 합산이 dense 1위를 밀어냄 (회귀)
        assert weighted[0].chunk_id == "1"    # 가중으로 억제하면 dense 1위 보존

    def test_zero_weight_keeps_candidate_without_influencing_rank(self):
        """가중 0이면 순위에 기여하지 않되 후보 풀에는 남는다(재현율은 유지)"""
        dense = [self._chunk("1")]
        sparse = [self._chunk("2")]

        fused = reciprocal_rank_fusion([dense, sparse], weights=[1.0, 0.0])

        assert [c.chunk_id for c in fused] == ["1", "2"]
        assert fused[1].score == 0.0

    def test_weights_length_mismatch_raises(self):
        """weights 길이가 리스트 수와 다르면 즉시 실패 — 조용히 잘리면 측정이 무의미해진다"""
        dense = [self._chunk("1")]

        with pytest.raises(ValueError, match="weights 길이"):
            reciprocal_rank_fusion([dense, []], weights=[1.0])


@pytest.mark.unit
class TestSparseSearchMorph:
    """
    형태소 sparse 검색의 계약 — 질의 토큰화와 매칭 대상 컬럼.

    색인이 content_morph를 같은 토크나이저로 채우므로, 여기서 고정할 계약은 질의 쪽이 ① 조사·어미를 떼고 ② 그 컬럼을 OR 술어로 매칭하는가다.
    하나라도 어긋나면 매칭이 조용히 깨져 sparse가 다시 전 케이스 0건(하이브리드 무력화)으로 돌아간다.
    """

    def test_no_noun_query_skips_db(self):
        """명사류가 없는 질의는 DB 왕복 없이 빈 결과 — dense 단독 폴백의 정상 입구다"""
        with patch("src.retrieval.searcher.get_pool") as mock_get_pool:
            results = sparse_search("???", top_k=5)

        assert results == []
        mock_get_pool.assert_not_called()

    def test_matches_morph_column_with_or_predicate(self, mock_db_pool):
        """매칭은 content_morph 컬럼 + websearch_to_tsquery, 검색식은 조사를 뗀 형태소 OR 연결"""
        mock_db_pool.fetchall.return_value = MOCK_DB_ROWS_SPARSE

        sparse_search("퇴직급여를 인식", top_k=2)

        # execute 호출: [0] SET statement_timeout, [1] SELECT
        query_obj, params = mock_db_pool.execute.call_args_list[1].args
        rendered = query_obj.as_string(None)
        assert "content_morph" in rendered
        assert "websearch_to_tsquery" in rendered
        assert "plainto_tsquery" not in rendered
        # 검색식: 조사(를)가 떨어진 형태소들의 OR 연결, SELECT 점수식과 WHERE 매칭식에 동일 전달
        assert params[0] == "퇴직 or 급여 or 인식"
        assert params[-2] == params[0]
        assert params[-1] == 2      # LIMIT top_k


@pytest.mark.unit
class TestHybridSearchIntegration:
    """하이브리드 검색 통합 흐름 검증 (DB 호출 분리 모킹)"""

    @patch("src.retrieval.searcher.dense_search")
    @patch("src.retrieval.searcher.sparse_search")
    def test_hybrid_merges_results(self, mock_sparse, mock_dense, mock_embed):
        """Dense + Sparse 가중 RRF 병합 검증 — dense 가중 1.0 고정, sparse는 SPARSE_FUSION_WEIGHT"""
        k = config.RRF_K
        w = config.SPARSE_FUSION_WEIGHT
        mock_dense.return_value = [
            RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=1.0, metadata={}),
            RetrievedChunk(chunk_id="2", document_id="D2", content="c2", score=0.5, metadata={}),
        ]
        mock_sparse.return_value = [
            RetrievedChunk(chunk_id="3", document_id="D3", content="c3", score=1.0, metadata={}),
            RetrievedChunk(chunk_id="4", document_id="D4", content="c4", score=0.0, metadata={}),
        ]

        results = search_chunks("query", top_k=5)

        assert len(results) == 4    # top_k 만큼 반환
        # 가중 RRF (rank는 1부터, 중복 없음):
        # Dense  -> "1": 1/(k+1),  "2": 1/(k+2)
        # Sparse -> "3": w/(k+1),  "4": w/(k+2)
        scores = {r.chunk_id: r.score for r in results}
        assert scores["1"] == pytest.approx(1.0 / (k + 1))   # Dense 1위
        assert scores["2"] == pytest.approx(1.0 / (k + 2))   # Dense 2위
        assert scores["3"] == pytest.approx(w / (k + 1))     # Sparse 1위 — 가중 반영
        assert scores["4"] == pytest.approx(w / (k + 2))     # Sparse 2위 — 가중 반영

        # 기본 가중(w=0.1)에서 sparse 단독 청크는 dense 전체 뒤로 정렬된다(w/(k+1) < 1/(k+2)).
        # sparse가 dense 후보를 밀어내지 않고 재정렬 신호로만 작동한다는 계약이다.
        assert [r.chunk_id for r in results] == ["1", "2", "3", "4"]

    @patch("src.retrieval.searcher.dense_search")
    @patch("src.retrieval.searcher.sparse_search")
    def test_duplicate_dedup(self, mock_sparse, mock_dense, mock_embed):
        """동일 chunk_id 반환 시 RRF 점수 합산(병합) 검증"""
        k = config.RRF_K
        mock_dense.return_value = [
            RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=1.0, metadata={})
        ]
        mock_sparse.return_value = [
            RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=1.0, metadata={})
        ]

        results = search_chunks("query", top_k=5)

        # ID 1이 양쪽에서 1위 -> dense 1/(k+1) + sparse w/(k+1)
        w = config.SPARSE_FUSION_WEIGHT
        assert len(results) == 1    # 중복 제거
        assert results[0].chunk_id == "1"   # chunk_id
        assert results[0].score == pytest.approx((1.0 + w) / (k + 1))  # 가중 RRF 점수 합산

    @patch("src.retrieval.searcher.dense_search")
    @patch("src.retrieval.searcher.sparse_search")
    def test_hybrid_with_standard_filter(self, mock_sparse, mock_dense, mock_embed):
        """metadata_filter 파라미터가 개별 검색 함수로 잘 전달되는지 검증"""
        mock_dense.return_value = [RetrievedChunk(chunk_id="1", document_id="D1", content="c1", score=1.0, metadata={})]
        mock_sparse.return_value = []
        
        metadata_filter = {"standard_type": "K-GAAP"}
        search_chunks("query", top_k=5, metadata_filter=metadata_filter)

        # 호출 인자 검증 (collection은 기본값=운영 CHUNKS_TABLE이 그대로 전달됨)
        mock_dense.assert_called_once_with(mock_embed.return_value[0], 5, metadata_filter, config.CHUNKS_TABLE)
        mock_sparse.assert_called_once_with("query", 5, metadata_filter, config.CHUNKS_TABLE)

    @patch("src.retrieval.searcher.dense_search")
    @patch("src.retrieval.searcher.sparse_search")
    def test_no_results_raises_SE103(self, mock_sparse, mock_dense, mock_embed):
        """검색 결과 0건 시 NoContextFoundError(SE-103) 발생 검증"""
        mock_dense.return_value = []
        mock_sparse.return_value = []
        
        with pytest.raises(NoContextFoundError) as exc_info:
            search_chunks("query", top_k=5)
            
        assert "검색 결과가 존재하지 않습니다" in str(exc_info.value)   # 검색 결과 0건


@pytest.mark.unit
class TestSearcherExceptions:
    """DB 연결 및 쿼리 수준의 예외 처리 검증 (SE-101, SE-102)"""

    def test_search_timeout_raises_SE101(self, mock_db_pool):
        """statement_timeout 시 SearchTimeoutError(SE-101) 발생 검증"""
        mock_db_pool.execute.side_effect = errors.QueryCanceled("canceling statement due to statement timeout")

        with pytest.raises(SearchTimeoutError) as exc_info:
            dense_search([0.1] * EMBEDDING_DIM, top_k=5)

        assert "응답 시간 초과" in str(exc_info.value)  # SE-101

    def test_db_error_raises_SE102(self, mock_db_pool):
        """기타 쿼리 실패 시 DatabaseQueryError(SE-102) 발생 검증"""
        mock_db_pool.execute.side_effect = Exception("DB 에러")

        with pytest.raises(DatabaseQueryError) as exc_info:
            dense_search([0.1] * EMBEDDING_DIM, top_k=5)

        assert "데이터베이스 쿼리 실행 실패" in str(exc_info.value) # SE-102

    def test_programming_error_propagates_without_wrapping(self, mock_db_pool):
        """재시도 불가 SQL 오류(ProgrammingError)는 DatabaseQueryError로 포장되지 않고 원본 전파"""
        mock_db_pool.execute.side_effect = errors.ProgrammingError("column \"foo\" does not exist")

        # DatabaseQueryError가 아니라 원본 ProgrammingError가 그대로 올라와야
        # 검색 노드가 무의미한 CRAG 재탐색을 트리거하지 않는다.
        with pytest.raises(errors.ProgrammingError):
            dense_search([0.1] * EMBEDDING_DIM, top_k=5)

    def test_undefined_table_propagates_without_wrapping(self, mock_db_pool):
        """재시도 불가 SQL 오류(UndefinedTable)도 원본 그대로 전파"""
        mock_db_pool.execute.side_effect = errors.UndefinedTable("존재하지 않는 테이블")

        with pytest.raises(errors.UndefinedTable):
            dense_search([0.1] * EMBEDDING_DIM, top_k=5)


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

        results = search_chunks("영업권 손상차손 인식 기준은?", top_k=5)

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

        results = search_chunks("영업권 손상차손 인식 기준은?", top_k=5)

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

        results = search_chunks("영업권 손상차손 인식 기준은?", top_k=5)

        assert len(results) == 1    # 최종 반환 결과 수
        assert results[0].chunk_id == "1"   # 반환 청크 ID

    @patch("src.retrieval.searcher.dense_search")
    @patch("src.retrieval.searcher.sparse_search")
    def test_both_failure_raises_SE102(self, mock_sparse, mock_dense, mock_embed):
        """양쪽 모두 장애 시 DatabaseQueryError 발생"""
        mock_dense.side_effect = DatabaseQueryError("Dense 실패")
        mock_sparse.side_effect = SearchTimeoutError("Sparse 타임아웃")

        with pytest.raises(DatabaseQueryError) as exc_info:
            search_chunks("영업권 손상차손 인식 기준은?", top_k=5)

        assert "모두 실패" in str(exc_info.value)   # 에러 메시지
