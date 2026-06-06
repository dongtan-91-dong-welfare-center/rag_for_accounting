# FUNC-005: 하이브리드 검색 (Dense + Sparse) 매니저

import json
from typing import LiteralString, cast
from psycopg import errors, sql

from src.models.schemas import RetrievedChunk
from src.utils.config import (
    RRF_K,
    CHUNKS_TABLE,
    SEARCH_TIMEOUT_SECONDS,
    EMBEDDING_MODEL
)
from src.utils.exception import SearchTimeoutError, DatabaseQueryError, NoContextFoundError, LLMAPIConnectionError
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
        # 임베딩 실패는 DB 오류(SE-102)가 아니라 LLM/임베딩 API 호출 문제(인증·네트워크)이다.
        # CM-002로 분류해야 ① 로그상 원인이 'DB 쿼리 실패'로 둔갑하지 않고
        # ② 검색 노드의 DatabaseQueryError 핸들러가 무의미한 CRAG 재탐색을 트리거하지 않는다.
        raise LLMAPIConnectionError(f"임베딩 모델 호출 실패: {e}", node="search")


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
    # embedding <=> %s::vector: 두 벡터 간의 코사인 유사도를 계산 (0=동일, 2=정반대)
    # 1 - (코사인 거리) = 코사인 유사도 -> 점수로 사용하면 유사도가 높을수록 점수도 높음
    query_sql = f"""
        SELECT chunk_id, document_id, content, metadata,
               1 - (embedding <=> %s::vector) AS score
        FROM {CHUNKS_TABLE}
        {where_clause}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    query_params = [query_embedding] + params + [query_embedding, top_k]

    return _execute_search_query(query_sql, query_params, "Dense")


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
    query_sql = f"""
        SELECT chunk_id, document_id, content, metadata,
               ts_rank_cd(to_tsvector('simple', content), plainto_tsquery('simple', %s)) AS score
        FROM {CHUNKS_TABLE}
        {where_sql}
        ORDER BY score DESC
        LIMIT %s
    """
    query_params = [query] + filter_params + [query, top_k]

    return _execute_search_query(query_sql, query_params, "Sparse")


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
    except (errors.ProgrammingError, errors.UndefinedTable) as e:
        # 잘못된 SQL 문법·존재하지 않는 컬럼/테이블 등은 재시도로 해결되지 않는다.
        # DatabaseQueryError로 포장하면 검색 노드가 무의미한 CRAG 재탐색을
        # MAX_REWRITE_COUNT까지 반복하므로, 원본 예외를 그대로 전파해 즉시 중단한다.
        logger.error(f"{search_type} 검색 프로그래밍 오류 (재시도 불가): {e}", exc_info=True)
        raise  # 원본 예외 전파 → 파이프라인 즉시 중단
    except Exception as e:
        logger.error(f"{search_type} 검색 중 DB 오류: {e}")
        raise DatabaseQueryError(f"데이터베이스 쿼리 실행 실패: {e}")
        
    return results


def reciprocal_rank_fusion(
    result_lists: list[list[RetrievedChunk]], k: int = RRF_K
) -> list[RetrievedChunk]:
    """여러 검색 결과 리스트를 RRF(Reciprocal Rank Fusion)로 병합한다.

    각 결과 리스트는 점수 내림차순으로 정렬되어 있다고 가정한다(DB 쿼리에서 ORDER BY로 보장).
    동일 문서의 최종 점수는 각 리스트에서의 순위 기반 점수 합이다:
        score(doc) = Σ 1 / (k + rank(doc))   (rank는 1부터 시작)

    점수가 아닌 순위에 의존하므로 Min-Max 정규화와 달리 아웃라이어 점수에 영향받지 않고,
    가중치 튜닝 없이 분포가 다른 Dense/Sparse 결과를 안정적으로 결합한다.
    단일 리스트만 비어있지 않은 폴백 상황에서도 그대로 동작한다.
    """
    # 호출자가 보유한 원본 객체를 변형하지 않도록 model_copy로 새 객체를 사용한다.
    fused: dict[str, RetrievedChunk] = {}

    for results in result_lists:
        for rank, chunk in enumerate(results, start=1):
            rrf_score = 1.0 / (k + rank)
            if chunk.chunk_id in fused:
                fused[chunk.chunk_id].score += rrf_score
            else:
                merged_chunk = chunk.model_copy()
                merged_chunk.score = rrf_score
                fused[chunk.chunk_id] = merged_chunk

    return sorted(fused.values(), key=lambda x: x.score, reverse=True)


def search_chunks(query: str, top_k: int = 10, metadata_filter: dict | None = None) -> list[RetrievedChunk]:
    """
    하이브리드 검색 (Dense + Sparse) 전략을 통해 청크를 검색한다.
    - Dense/Sparse 독립 장애 처리: 한쪽 실패 시 나머지 결과만 반환, 양쪽 실패 시 DatabaseQueryError
    - 초기 검색 0건 시 top_k × 2로 1회 재탐색
    - 재탐색 후에도 0건이면 NoContextFoundError 발생
    """
    logger.info(f"하이브리드 검색 시작: query='{query[:30]}...', top_k={top_k}")

    query_vector = embed_query(query)

    # Dense 및 Sparse 검색 실행 (각각 top_k만큼 가져와서 병합 풀 확보)
    merged = _search_and_merge(query, query_vector, top_k, metadata_filter)
    final_results = merged[:top_k]

    if not final_results:
        retry_top_k = top_k * 2
        logger.info(f"검색 결과 0건, top_k={retry_top_k}로 재탐색")
        merged = _search_and_merge(query, query_vector, retry_top_k, metadata_filter)
        final_results = merged[:top_k]

    if not final_results:
        logger.warning("재탐색 후에도 검색 결과 0건")
        raise NoContextFoundError("질의에 대한 검색 결과가 존재하지 않습니다.")

    logger.info(f"하이브리드 검색 완료: {len(final_results)}건 반환")
    return final_results

def _search_and_merge(query: str, query_vector: list[float], top_k: int, metadata_filter: dict | None) -> list[RetrievedChunk]:
    """Dense + Sparse 검색을 독립 실행하고 RRF로 병합한다. 양쪽 모두 실패 시 DatabaseQueryError를 발생시킨다."""
    dense_results: list[RetrievedChunk] = []
    sparse_results: list[RetrievedChunk] = []
    dense_failed = False
    sparse_failed = False

    try:
        dense_results = dense_search(query_vector, top_k, metadata_filter)
    except (SearchTimeoutError, DatabaseQueryError) as e:
        dense_failed = True
        logger.warning(f"Dense 검색 실패, Sparse 단독 진행: {e}")

    try:
        sparse_results = sparse_search(query, top_k, metadata_filter)
    except (SearchTimeoutError, DatabaseQueryError) as e:
        sparse_failed = True
        logger.warning(f"Sparse 검색 실패, Dense 단독 진행: {e}")

    if dense_failed and sparse_failed:
        raise DatabaseQueryError("Dense 및 Sparse 검색 모두 실패")

    if dense_failed:
        logger.info("검색 모드: Sparse 단독")
    elif sparse_failed:
        logger.info("검색 모드: Dense 단독")
    else:
        logger.info("검색 모드: Dense + Sparse 하이브리드")

    # Dense/Sparse 결과는 각 쿼리의 ORDER BY로 점수 내림차순 정렬되어 있으므로
    # 리스트 내 위치가 곧 순위가 된다. RRF가 순위 기반으로 병합한다.
    return reciprocal_rank_fusion([dense_results, sparse_results])
