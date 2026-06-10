"""
[FUNC-005] 하이브리드 검색 통합 테스트 (Docker DB 환경)

본 테스트는 실제 PostgreSQL + pgvector 컨테이너 환경에서 데이터를 삽입하고 검색 쿼리를 수행하여 시스템 레벨의 연동을 검증합니다.
`docker-compose up -d` 상태에서만 실행되어야 합니다.
"""
import pytest
from unittest.mock import patch
from src.retrieval.searcher import search_chunks
from src.utils.config import CHUNKS_TABLE, EMBEDDING_DIM
from src.db.connection import get_pool, init_pool

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """테스트용 임시 테이블 생성 및 데이터 적재, 종료 시 삭제"""
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
    
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # 테스트용 테이블 스키마 생성
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {CHUNKS_TABLE} (
                    chunk_id SERIAL PRIMARY KEY,
                    document_id TEXT,
                    content TEXT,
                    metadata JSONB,
                    embedding vector({EMBEDDING_DIM})
                )
            """)

            # 테스트 데이터 삽입
            # (실제 임베딩 벡터와 동일한 차원의 dummy vector 사용)
            dummy_vec_1 = f"[{','.join(['0.1']*EMBEDDING_DIM)}]"
            dummy_vec_2 = f"[{','.join(['0.2']*EMBEDDING_DIM)}]"
            
            cur.execute(f"""
                INSERT INTO {CHUNKS_TABLE} (document_id, content, metadata, embedding)
                VALUES 
                ('DOC-1', '유형자산 감가상각 인식 기준은 정액법을 기본으로 합니다.', '{{"standard_type": "K-GAAP"}}', %s::vector),
                ('DOC-2', '재고자산의 단가산정방식은 선입선출법을 따른다.', '{{"standard_type": "K-IFRS"}}', %s::vector)
            """, [dummy_vec_1, dummy_vec_2])
            
            conn.commit()
            
    yield
    
    # 종료 시 테이블 삭제
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {CHUNKS_TABLE}")
            conn.commit()


@pytest.mark.system
class TestHybridSearchIntegration:
    """실제 DB가 띄워진 상태에서의 E2E 검색 검증"""
    
    def test_end_to_end_kgaap_search(self):
        """K-GAAP 청크 데이터 하이브리드 검색 검증"""
        # "유형자산 감가상각"에 대한 쿼리
        # embed_query() 내부에서 KURE-v1 모델 로드(다운로드)가 발생할 수 있으므로
        # 통합 테스트의 목적(DB 연동)에 맞게 embed_query만 mock 처리
        with patch("src.retrieval.searcher.embed_query") as mock_embed:
            mock_embed.return_value = [0.1] * EMBEDDING_DIM
            
            results = search_chunks(
                query="유형자산 감가상각 인식 기준",
                top_k=5,
                metadata_filter={"standard_type": "K-GAAP"}
            )
            
            assert len(results) >= 1    # 쿼리당 최소 1개 결과 보장
            assert results[0].metadata.standard_type == "K-GAAP" # K-GAAP 데이터가 잘 검색되었는지 확인
            assert "유형자산" in results[0].content # '유형자산' 키워드가 포함되었는지 확인

