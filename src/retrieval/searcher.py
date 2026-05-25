# FUNC-005: 하이브리드 검색 (Dense + Sparse) 매니저

import json
from typing import LiteralString, cast
from psycopg import errors, sql

from src.models.schemas import RetrievedChunk
from src.utils.config import (
    DENSE_WEIGHT, 
    SPARSE_WEIGHT, 
    CHUNKS_TABLE, 
    SEARCH_TIMEOUT_SECONDS, 
    EMBEDDING_MODEL
)
from src.utils.exception import SearchTimeoutError, DatabaseQueryError, NoContextFoundError
from src.utils.llm_client import client
from src.db.connection import get_pool
from src.utils.logger import get_logger

logger = get_logger(__name__)


def embed_query(query: str) -> list[float]:
    """OpenAI 임베딩 모델을 사용하여 질의를 벡터로 변환한다."""
    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=query
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"임베딩 생성 실패: {e}")
        # 임베딩 생성 실패는 DB 에러가 아니지만, 검색 진행이 불가하므로
        # 통합 예외 처리를 위해 DatabaseQueryError 사용
        raise DatabaseQueryError(f"임베딩 모델 호출 실패: {e}")


def _build_where_clause(metadata_filter: dict | None) -> tuple[str, list]:
    """metadata_filter 딕셔너리로부터 JSONB 쿼리용 WHERE 절과 파라미터를 생성한다."""
    # 메타데이터 필터링
    if not metadata_filter:
        return "", []
    
    conditions = []   # 조건절 리스트(예: ["metadata->>%s = %s"])
    params = []       # 파라미터 리스트(예: ["period", "2024"], ["accounting_standard", "K-IFRS"])
    for key, value in metadata_filter.items():
        # metadata 컬럼이 JSONB 타입이라고 가정하고 ->> 연산자 사용
        # metadata: ingester.py에서 JSONB로 저장
        conditions.append(f"metadata->>%s = %s")    # JSONB 타입의 metadata에서 key에 해당하는 값을 string으로 반환하여 비교
        params.extend([key, str(value)])          # 메타데이터의 key와 value를 파라미터로 전달

    # 예시: ("WHERE metadata->>%s = %s AND metadata->>%s = %s", ["period", "2024", "accounting_standard", "K-IFRS"])
    return " WHERE " + " AND ".join(conditions), params 


def dense_search(query_embedding: list[float], top_k: int, metadata_filter: dict | None = None) -> list[RetrievedChunk]:
    """Bi-Encoder 임베딩 기반 Dense 검색 (pgvector ANN)"""
    where_clause, params = _build_where_clause(metadata_filter)
    
    # query_embedding은 %s::vector 타입으로 캐스팅하여 비교
    # 1 - (embedding <=> %s::vector): 두 벡터 간의 코사인 유사도를 계산 
    # (1 - (유사도))를 점수로 사용 -> 유사도가 높을수록 점수도 높음
    sql = f"""
        SELECT chunk_id, document_id, content, metadata,
               1 - (embedding <=> %s::vector) AS score
        FROM {CHUNKS_TABLE}
        {where_clause}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    query_params = [query_embedding] + params + [query_embedding, top_k]
    
    return _execute_search_query(sql, query_params, "Dense")


def sparse_search(query: str, top_k: int, metadata_filter: dict | None = None) -> list[RetrievedChunk]:
    """PostgreSQL 내장 텍스트 검색 기능(BM25 유사)을 활용한 Sparse 검색"""
    # WHERE 조건이 있다면 AND로 연결, 없으면 WHERE로 시작
    filter_clause, filter_params = _build_where_clause(metadata_filter)
    
    if filter_clause:
        # filter_clause가 있으면 AND로 연결하여 WHERE 절 생성
        where_sql = f"{filter_clause} AND to_tsvector('simple', content) @@ plainto_tsquery('simple', %s)"
    else:
        # filter_clause가 없으면 WHERE 절로 시작
        where_sql = " WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', %s)"

    # to_tsvector('simple', content): 문서를 띄어쓰기 기준으로 토큰화하여 검색 가능한 벡터로 변환
    # plainto_tsquery('simple', %s): 사용자 검색어를 띄어쓰기 기준으로 토큰화하여 쿼리로 변환
    # 'simple' 설정은 한국어 형태소 분석을 지원하지 않으므로 정확한 단어 일치 검색만 수행됨
    # ts_rank_cd(to_tsvector, query): 인자로 주어진 두 텍스트에 대한 순위 점수를 반환 (0~1)
    # ts_rank_cd가 반환하는 점수: 두 텍스트의 관련성을 0~1 사이 점수로 반환 -> 유사도가 높을수록 점수도 높음
    sql = f"""
        SELECT chunk_id, document_id, content, metadata,
               ts_rank_cd(to_tsvector('simple', content), plainto_tsquery('simple', %s)) AS score
        FROM {CHUNKS_TABLE}
        {where_sql}
        ORDER BY score DESC
        LIMIT %s
    """
    query_params = [query] + filter_params + [query, top_k]
    
    return _execute_search_query(sql, query_params, "Sparse")


def _execute_search_query(sql_query: str | sql.SQL | sql.Composed, params: list, search_type: str) -> list[RetrievedChunk]:
    """DB 쿼리 실행 및 RetrievedChunk 리스트 반환 공통 로직"""
    results = []
    # 밀리초(ms) 단위 타임아웃 문자열 구성 (예: '5000ms')
    timeout_ms = SEARCH_TIMEOUT_SECONDS * 1000

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                # 쿼리 타임아웃 설정
                cur.execute(sql.SQL("SET LOCAL statement_timeout = {}").format(sql.Literal(f"{timeout_ms}ms")))
                
                # sql_query가 str 타입이면 sql.SQL로 변환, 아니면 그대로 사용
                # cast: 문법상 str이지만 LiteralString 타입으로 취급하겠다는 의미
                query_obj = sql.SQL(cast(LiteralString, sql_query)) if isinstance(sql_query, str) else sql_query
                cur.execute(query_obj, params)
                rows = cur.fetchall()
                
                for row in rows:
                    chunk_id, document_id, content, metadata, score = row
                    
                    # metadata가 문자열(JSON)로 반환될 경우 dict로 파싱
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except json.JSONDecodeError:
                            metadata = {}
                    elif metadata is None:
                        metadata = {}

                    results.append(RetrievedChunk(
                        chunk_id=str(chunk_id),
                        document_id=str(document_id),
                        content=str(content),
                        score=float(score),
                        metadata=metadata
                    ))
    except errors.QueryCanceled as e:
        logger.error(f"{search_type} 검색 타임아웃 초과: {e}")
        raise SearchTimeoutError(f"DB 검색 응답 시간 초과 ({SEARCH_TIMEOUT_SECONDS}s)")
    except Exception as e:
        logger.error(f"{search_type} 검색 중 DB 오류: {e}")
        raise DatabaseQueryError(f"데이터베이스 쿼리 실행 실패: {e}")
        
    return results


def normalize_scores(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """스코어를 [0, 1] 범위로 Min-Max 정규화한다."""
    if not chunks:
        return []
        
    scores = [c.score for c in chunks]
    min_score, max_score = min(scores), max(scores)
    
    # 모든 점수가 동일하거나 최대/최소가 같으면 1.0으로 통일
    if max_score == min_score:
        for c in chunks:
            c.score = 1.0
        return chunks
        
    for c in chunks:
        c.score = (c.score - min_score) / (max_score - min_score)
        
    return chunks


def hybrid_search(query: str, top_k: int = 10, metadata_filter: dict | None = None) -> list[RetrievedChunk]:
    """
    하이브리드 검색 (Dense + Sparse)
    - metadata_filter: 회계기준(K-IFRS/K-GAAP) 필터링 포함
    """
    logger.info(f"하이브리드 검색 시작: query='{query[:30]}...', top_k={top_k}")
    
    # 질의 임베딩 생성
    query_vector = embed_query(query)
    
    # Dense 및 Sparse 검색 실행 (각각 top_k만큼 가져와서 병합 풀 확보)
    dense_results = dense_search(query_vector, top_k, metadata_filter)
    sparse_results = sparse_search(query, top_k, metadata_filter)
    
    # 스코어 정규화
    dense_results = normalize_scores(dense_results)
    sparse_results = normalize_scores(sparse_results)
    
    # 가중 평균 병합
    # merged_map을 만드는 이유: Dense와 Sparse 검색 결과 중 중복되는 chunk_id를 하나의 딕셔너리로 관리
    # key: chunk_id, value: RetrievedChunk 객체
    merged_map: dict[str, RetrievedChunk] = {}
    
    for chunk in dense_results:
        # 모델의 깊은 복사본을 생성하여 점수 수정
        # model_copy(): Pydantic 모델의 깊은 복사를 수행하는 메서드
        # 병합 시 점수를 수정하므로 원본 데이터를 유지하기 위해 깊은 복사를 사용
        merged_chunk = chunk.model_copy()
        merged_chunk.score = chunk.score * DENSE_WEIGHT
        merged_map[chunk.chunk_id] = merged_chunk
        
    for chunk in sparse_results:
        if chunk.chunk_id in merged_map:
            merged_map[chunk.chunk_id].score += chunk.score * SPARSE_WEIGHT
        else:
            merged_chunk = chunk.model_copy()
            merged_chunk.score = chunk.score * SPARSE_WEIGHT
            merged_map[chunk.chunk_id] = merged_chunk
            
    # 최종 정렬 및 top_k 추출
    final_results = sorted(merged_map.values(), key=lambda x: x.score, reverse=True)[:top_k]
    
    if not final_results:
        logger.warning("검색 결과가 0건입니다.")
        raise NoContextFoundError("질의에 대한 검색 결과가 존재하지 않습니다.")
        
    logger.info(f"하이브리드 검색 완료: {len(final_results)}건 반환")
    return final_results