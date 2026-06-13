"""
[FUNC-005] 하이브리드 검색 통합 테스트 (Docker DB 환경)

본 테스트는 실제 PostgreSQL + pgvector 컨테이너 환경에서 데이터를 삽입하고 검색 쿼리를 수행하여 시스템 레벨의 연동을 검증합니다.
`docker-compose up -d` 상태에서만 실행되어야 합니다.

데이터 격리:
    운영 chunks 테이블을 직접 건드리지 않고, 전용 컬렉션(chunks_test_hybrid_search)에
    index_documents로 적재한 뒤 search_chunks(collection=...)로 그 컬렉션만 검색한다.
    teardown은 DROP이 아니라 delete_collection(행 비우기)으로 정리하여, 운영 chunks 소실·오염 위험을 원천 차단한다.

    적재·검색 모두 KURE-v1 모델 로드 없이 결정적으로 동작하도록, 
    적재 경로의 임베딩/토큰 카운터와 검색 경로의 질의 임베딩을 dummy 벡터로 mock한다.
    메타데이터 필터링·sparse 텍스트 일치·RRF 병합이라는 DB 연동 검증 목적에 모델 정확도는 불필요하다.
"""
import pytest
from unittest.mock import patch

from src.retrieval.searcher import search_chunks
from src.utils.config import EMBEDDING_DIM
from src.db.connection import get_pool, init_pool
from src.db.vector_store import index_documents, delete_collection
from src.models.schemas import RetrievedChunk

# 운영 chunks 테이블과 분리된 전용 테스트 컬렉션
TEST_COLLECTION = "chunks_test_hybrid_search"

# 적재·검색에 공유하는 결정적 dummy 벡터 (실제 임베딩 차원과 동일)
_KGAAP_VEC = [0.1] * EMBEDDING_DIM
_KIFRS_VEC = [0.2] * EMBEDDING_DIM


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """전용 컬렉션에 테스트 데이터를 적재하고, 종료 시 행을 비운다(운영 chunks 미접촉)."""
    try:
        init_pool()
    except Exception as e:
        pytest.skip(f"통합 테스트 건너뜀: 커넥션 풀 초기화 불가 ({e})")
    pool = get_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # 간단한 연결 테스트. 실패하면 Docker가 띄워져 있지 않은 것
                cur.execute("SELECT 1")
    except Exception as e:
        pytest.skip(f"통합 테스트 건너뜀: DB 연결 불가 ({e})")

    # 프로덕션 스키마(chunk_id TEXT PK)에 맞춘 테스트 청크 2건
    chunks = [
        RetrievedChunk(
            chunk_id="TEST-CHUNK-1",
            document_id="DOC-1",
            content="유형자산 감가상각 인식 기준은 정액법을 기본으로 합니다.",
            score=0.0,
            metadata={"standard_type": "K-GAAP"},
        ),
        RetrievedChunk(
            chunk_id="TEST-CHUNK-2",
            document_id="DOC-2",
            content="재고자산의 단가산정방식은 선입선출법을 따른다.",
            score=0.0,
            metadata={"standard_type": "K-IFRS"},
        ),
    ]

    # index_documents 내부의 토큰 카운터·임베딩을 mock해 KURE-v1 로드 없이 결정적으로 적재한다.
    # embed_texts는 valid_chunks 순서대로 벡터를 매핑하므로 [K-GAAP, K-IFRS] 순으로 반환한다.
    with (
        patch("src.db.vector_store.count_tokens", return_value=10),
        patch("src.db.vector_store.embed_texts", return_value=[_KGAAP_VEC, _KIFRS_VEC]),
    ):
        result = index_documents(chunks, collection=TEST_COLLECTION)
    assert result.status == "success", f"테스트 데이터 적재 실패: {result.status}"

    yield

    # 종료 시 행만 비운다(테이블·인덱스 보존). 운영 chunks는 건드리지 않는다.
    delete_collection(TEST_COLLECTION)


@pytest.mark.system
class TestHybridSearchIntegration:
    """실제 DB가 띄워진 상태에서의 E2E 검색 검증"""

    def test_end_to_end_kgaap_search(self):
        """K-GAAP 청크 데이터 하이브리드 검색 검증"""
        # "유형자산 감가상각"에 대한 쿼리
        # 질의 임베딩은 적재한 K-GAAP dummy 벡터와 동일하게 mock하여 모델 로드 없이 결정적으로 동작
        with patch("src.retrieval.searcher.embed_query") as mock_embed:
            mock_embed.return_value = _KGAAP_VEC

            results = search_chunks(
                query="유형자산 감가상각 인식 기준",
                top_k=5,
                metadata_filter={"standard_type": "K-GAAP"},
                collection=TEST_COLLECTION,
            )

            assert len(results) >= 1    # 쿼리당 최소 1개 결과 보장
            assert results[0].metadata.standard_type == "K-GAAP" # K-GAAP 데이터가 잘 검색되었는지 확인
            assert "유형자산" in results[0].content # '유형자산' 키워드가 포함되었는지 확인
