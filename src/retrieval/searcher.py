# FUNC-005: 하이브리드 검색 (Dense + Sparse) 매니저

import json
from typing import LiteralString, cast
from psycopg import errors, sql

from src.models.schemas import RetrievedChunk
from src.utils.config import (
    RRF_K,
    CHUNKS_TABLE,
    SEARCH_TIMEOUT_SECONDS,
    EMBEDDING_MODEL,
    SPARSE_FUSION_WEIGHT
)
from src.utils.exception import SearchTimeoutError, DatabaseQueryError, NoContextFoundError
from src.clients.embedding import embed_texts
from src.db.connection import get_pool
from src.retrieval.tokenizer import tokenize_morph
from src.utils.logger import get_logger

logger = get_logger(__name__)


def embed_query(query: str) -> list[float]:
    """KURE-v1 임베딩 모델을 사용하여 질의를 벡터로 변환한다.

    인덱싱(FUNC-003)과 동일한 embed_texts()를 공유하므로 모델·차원이 항상 일치한다.
    실패 시 embed_texts()가 LLMAPIConnectionError(CM-002, node="search")를 발생시킨다.
    """
    return embed_texts([query], node="search")[0]


def _build_where_clause(metadata_filter: dict | None) -> tuple[str, list]:
    """metadata_filter 딕셔너리로부터 JSONB 쿼리용 WHERE 절과 파라미터를 생성한다."""
    # 메타데이터 필터링
    if not metadata_filter:
        return "", []
    
    conditions = []   # 조건절 리스트(예: ["metadata->>%s = %s"])
    params = []       # 파라미터 리스트(예: ["period", "2024"], ["accounting_standard", "K-IFRS"])
    for key, value in metadata_filter.items():
        # metadata 컬럼이 JSONB 타입이라고 가정하고 ->> 연산자 사용
        # metadata: 적재(인덱싱) 로직에서 JSONB로 저장됨
        conditions.append(f"metadata->>%s = %s")    # JSONB 타입의 metadata에서 key에 해당하는 값을 string으로 반환하여 비교
        params.extend([key, str(value)])          # 메타데이터의 key와 value를 파라미터로 전달

    # 예시: ("WHERE metadata->>%s = %s AND metadata->>%s = %s", ["period", "2024", "accounting_standard", "K-IFRS"])
    return " WHERE " + " AND ".join(conditions), params 


def dense_search(query_embedding: list[float], top_k: int, metadata_filter: dict | None = None, collection: str = CHUNKS_TABLE) -> list[RetrievedChunk]:
    """Bi-Encoder 임베딩 기반 Dense 검색 (pgvector ANN). collection으로 검색 대상 테이블을 지정한다(기본: 운영 CHUNKS_TABLE)."""
    where_clause, params = _build_where_clause(metadata_filter)

    # query_embedding은 %s::vector 타입으로 캐스팅하여 비교
    # embedding <=> %s::vector: 두 벡터 간의 코사인 거리를 계산 (0=동일, 2=정반대). 거리이므로 값이 작을수록 더 유사하다.
    # 1 - (코사인 거리) = 코사인 유사도 -> 점수로 사용하면 유사도가 높을수록 점수도 높음
    # 테이블명은 sql.Identifier로 인용해 식별자 안전성을 보장한다(vector_store와 동일 규약).
    # where_clause/%s 플레이스홀더는 sql.SQL 조각으로 그대로 전달되어 execute 시 params로 바인딩된다.
    query_sql = sql.SQL("""
        SELECT chunk_id, document_id, content, metadata,
               1 - (embedding <=> %s::vector) AS score
        FROM {table}
        {where}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """).format(table=sql.Identifier(collection), where=sql.SQL(where_clause))
    query_params = [query_embedding] + params + [query_embedding, top_k]

    return _execute_search_query(query_sql, query_params, "Dense")


def sparse_search(query: str, top_k: int, metadata_filter: dict | None = None, collection: str = CHUNKS_TABLE) -> list[RetrievedChunk]:
    """형태소 키워드 기반 Sparse 검색. collection으로 검색 대상 테이블을 지정한다(기본: 운영 CHUNKS_TABLE).

    질의를 형태소 명사류로 쪼개(OR 연결) 사전토큰화 컬럼 content_morph에서 매칭한다.
    content에 plainto_tsquery를 사용한 검색은 'simple' 설정이 조사를 못 떼고 전 토큰 AND라
    문장형 질의에서 전 케이스 0건을 반환했다.

    색인과 질의가 같은 토크나이저·품사 화이트리스트를 사용하므로, 다른 필터를 타면 매칭이 조용히 깨진다.
    - ts_rank_cd에는 IDF(흔한 단어를 자동으로 덜 세는 가중치)가 없어 품사 필터가 유일한 노이즈 방어선이고, 남는 회귀는 병합 가중이 억제한다.

    전제: content_morph가 채워져 있어야 한다(신규 적재는 자동, 비어 있으면 매칭 0건 → dense 단독 폴백으로 동작).
    """
    # 명사류가 하나도 없으면 검색식을 만들 수 없다 — 0건 확정이므로 DB 왕복 없이 반환한다
    # (sparse 0건은 dense 단독으로 병합되는 정상 폴백 경로다).
    tokens = tokenize_morph(query)
    if not tokens:
        logger.info("Sparse 검색 생략: 질의에 명사류 형태소 없음")
        return []
    # websearch_to_tsquery가 'or'를 OR 연산자로 해석한다(예: "퇴직급여 or 인식").
    # 사용자 입력이 특수문자를 품어도 문법 오류를 내지 않는 함수라 to_tsquery 조립보다 안전하다.
    ts_query = " or ".join(tokens)

    # WHERE 조건이 있다면 AND로 연결, 없으면 WHERE로 시작
    filter_clause, filter_params = _build_where_clause(metadata_filter)
    match_expr = "to_tsvector('simple', content_morph) @@ websearch_to_tsquery('simple', %s)"
    if filter_clause:
        where_sql = f"{filter_clause} AND {match_expr}"
    else:
        where_sql = f" WHERE {match_expr}"

    # content_morph는 형태소를 공백으로 이어 붙인 문자열이므로 'simple' 설정이 그 공백을 토큰 경계로 그대로 받아 형태소 단위 매칭이 성립한다.
    # 반환은 원문으로 한다 이후 파이프라인(재정렬·인용)이 청크 본문을 그대로 쓰기 때문이다.
    # 테이블명은 sql.Identifier로 인용(식별자 안전성). where_sql의 %s는 sql.SQL 조각으로 그대로 전달된다.
    query_sql = sql.SQL("""
        SELECT chunk_id, document_id, content, metadata,
               ts_rank_cd(to_tsvector('simple', content_morph), websearch_to_tsquery('simple', %s)) AS score
        FROM {table}
        {where}
        ORDER BY score DESC
        LIMIT %s
    """).format(table=sql.Identifier(collection), where=sql.SQL(where_sql))
    query_params = [ts_query] + filter_params + [ts_query, top_k]

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
    result_lists: list[list[RetrievedChunk]], k: int = RRF_K, weights: list[float] | None = None
) -> list[RetrievedChunk]:
    """여러 검색 결과 리스트를 RRF(Reciprocal Rank Fusion)로 병합한다.

    각 결과 리스트는 점수 내림차순으로 정렬되어 있다고 가정한다(DB 쿼리에서 ORDER BY로 보장).
    동일 문서의 최종 점수는 각 리스트에서의 순위 기반 점수 합이다:
        score(doc) = Σ wᵢ / (k + rankᵢ(doc))   (rank는 1부터 시작)

    점수가 아닌 순위에 의존하므로 Min-Max 정규화와 달리 아웃라이어 점수에 영향받지 않는다.
    단일 리스트만 비어있지 않은 폴백 상황에서도 그대로 동작한다.

    weights는 리스트별 가중치이며, 미지정이면 전부 1.0 — 대칭 RRF로 현행과 동일 출력이다.
    가중이 필요한 이유는 순위 합산의 부작용에 있다: 양쪽 리스트에 모두 등장하는 청크는
    점수가 합산되므로, sparse를 활성화하면 (dense 중위 ∩ sparse 상위) 청크가 dense 단독 1위를 넘어서는 회귀가 생긴다.
    sparse 가중을 낮추면 이 합산만 억제하고 sparse의 재현율 이득은 남는다.
    (동점 시에는 result_lists 앞쪽 리스트가 먼저 삽입되므로 그 리스트의 순서가 유지된다. Dense를 앞에 두면 동점에서 dense 순서가 이긴다.)
    """
    if weights is None:
        weights = [1.0] * len(result_lists)
    elif len(weights) != len(result_lists):
        # 조용히 잘리거나 채워지면 어느 리스트가 어떤 가중을 받았는지 알 수 없어 측정이 무의미해진다.
        raise ValueError(f"weights 길이({len(weights)})가 result_lists({len(result_lists)})와 다릅니다")

    # 호출자가 보유한 원본 객체를 변형하지 않도록 model_copy로 새 객체를 사용한다.
    fused: dict[str, RetrievedChunk] = {}

    for results, weight in zip(result_lists, weights):
        for rank, chunk in enumerate(results, start=1):
            rrf_score = weight / (k + rank)
            if chunk.chunk_id in fused:
                fused[chunk.chunk_id].score += rrf_score
            else:
                merged_chunk = chunk.model_copy()
                merged_chunk.score = rrf_score
                fused[chunk.chunk_id] = merged_chunk

    return sorted(fused.values(), key=lambda x: x.score, reverse=True)


def search_chunks(query: str, top_k: int = 10, metadata_filter: dict | None = None, collection: str = CHUNKS_TABLE) -> list[RetrievedChunk]:
    """
    하이브리드 검색 (Dense + Sparse) 전략을 통해 청크를 검색한다.
    - Dense/Sparse 독립 장애 처리: 한쪽 실패 시 나머지 결과만 반환, 양쪽 실패 시 DatabaseQueryError
    - 초기 검색 0건 시 top_k × 2로 1회 재탐색
    - 재탐색 후에도 0건이면 NoContextFoundError 발생
    - collection: 검색 대상 테이블명(기본: 운영 CHUNKS_TABLE). 테스트가 전용 컬렉션을 가리키게 해
      운영 chunks 오염·소실 없이 격리하기 위한 주입점이다.
    """
    logger.info(f"하이브리드 검색 시작: query='{query[:30]}...', top_k={top_k}")

    query_vector = embed_query(query)

    # Dense 및 Sparse 검색 실행 (각각 top_k만큼 가져와서 병합 풀 확보)
    merged = _search_and_merge(query, query_vector, top_k, metadata_filter, collection)
    final_results = merged[:top_k]

    if not final_results:
        retry_top_k = top_k * 2
        logger.info(f"검색 결과 0건, top_k={retry_top_k}로 재탐색")
        merged = _search_and_merge(query, query_vector, retry_top_k, metadata_filter, collection)
        final_results = merged[:top_k]

    if not final_results:
        logger.warning("재탐색 후에도 검색 결과 0건")
        raise NoContextFoundError("질의에 대한 검색 결과가 존재하지 않습니다.")

    logger.info(f"하이브리드 검색 완료: {len(final_results)}건 반환")
    return final_results

def _search_and_merge(query: str, query_vector: list[float], top_k: int, metadata_filter: dict | None, collection: str) -> list[RetrievedChunk]:
    """Dense + Sparse 검색을 독립 실행하고 RRF로 병합한다. 양쪽 모두 실패 시 DatabaseQueryError를 발생시킨다."""
    dense_results: list[RetrievedChunk] = []
    sparse_results: list[RetrievedChunk] = []
    dense_failed = False
    sparse_failed = False

    try:
        dense_results = dense_search(query_vector, top_k, metadata_filter, collection)
    except (SearchTimeoutError, DatabaseQueryError) as e:
        dense_failed = True
        logger.warning(f"Dense 검색 실패, Sparse 단독 진행: {e}")

    try:
        sparse_results = sparse_search(query, top_k, metadata_filter, collection)
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
    # dense는 1.0 고정, sparse는 SPARSE_FUSION_WEIGHT(기본 1.0 = 대칭 RRF, 현행 동작).
    # dense를 앞에 둬 동점 시 dense 순서가 유지된다.
    return reciprocal_rank_fusion(
        [dense_results, sparse_results], weights=[1.0, SPARSE_FUSION_WEIGHT]
    )
