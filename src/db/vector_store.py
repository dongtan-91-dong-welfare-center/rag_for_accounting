# FUNC-003: pgvector를 이용한 문서 임베딩 저장 및 조회 (이슈 #93 설계 확정)
#
# 설계 결정 요약:
#   - 임베딩: KURE-v1 1024차원, 인덱싱·검색이 src/utils/embedding.embed_texts()를 공유
#   - 스키마: chunk_id TEXT PK / document_id / content / metadata JSONB / embedding vector(1024)
#   - 인덱스: HNSW + vector_cosine_ops (코사인 거리 <=> 연산자와 정합)
#   - upsert: INSERT ... ON CONFLICT(chunk_id) DO UPDATE — 재실행 멱등성 보장
#   - 부분 실패 정책: 배치 단위 부분 커밋. 실패 배치는 건너뛰고 계속 진행하며,
#     upsert 멱등성 덕분에 전체 재실행으로 누락분을 복구할 수 있다.
#     (전체 롤백 대신 부분 커밋을 택한 이유: 수천 청크 인덱싱 중 일시 장애로
#      전부 버리는 것보다 partial 상태를 드러내고 재시도하는 쪽이 운영상 단순하다)

import json

from psycopg import errors, sql
from psycopg.types.json import Jsonb

from src.db.connection import get_pool
from src.models.schemas import RetrievedChunk, IndexingResult
from src.utils.config import BATCH_SIZE, EMBEDDING_DIM, EMBEDDING_MAX_TOKENS, SEARCH_TIMEOUT_SECONDS
from src.utils.embedding import embed_texts, count_tokens
from src.utils.exception import (
    AccountingRAGError,
    DatabaseQueryError,
    EmbeddingTokenLimitError,
    SearchTimeoutError,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _ensure_collection(collection: str) -> None:
    """컬렉션(테이블)과 HNSW 인덱스가 없으면 생성한다.

    - sql.Identifier로 테이블명을 인용해 SQL 주입을 차단한다.
    - HNSW를 선택한 이유: IVFFlat은 데이터 적재 후 인덱스 생성(학습)이 필요하지만
      HNSW는 점진적 적재에도 검색 품질이 유지되어 upsert 중심 운영에 적합하다.
    :raises DatabaseQueryError: DDL 실행 실패 시 (SE-102, node="index")
    """
    table = sql.Identifier(collection)
    index = sql.Identifier(f"{collection}_embedding_hnsw_idx")
    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute(
                    sql.SQL(
                        """
                        CREATE TABLE IF NOT EXISTS {table} (
                            chunk_id TEXT PRIMARY KEY,
                            document_id TEXT NOT NULL,
                            content TEXT NOT NULL,
                            metadata JSONB,
                            embedding vector({dim}) NOT NULL
                        )
                        """
                    ).format(table=table, dim=sql.Literal(EMBEDDING_DIM))
                )
                cur.execute(
                    sql.SQL(
                        "CREATE INDEX IF NOT EXISTS {index} ON {table} "
                        "USING hnsw (embedding vector_cosine_ops)"
                    ).format(index=index, table=table)
                )
    except Exception as e:
        logger.error(f"컬렉션 생성 실패: collection={collection}, {e}")
        raise DatabaseQueryError(f"컬렉션 생성 실패: {e}", node="index")


def _upsert_batch(collection: str, batch: list[RetrievedChunk], vectors: list[list[float]]) -> None:
    """배치 하나를 단일 트랜잭션으로 upsert한다. 커넥션 컨텍스트 종료 시 커밋된다.

    :raises DatabaseQueryError: 쿼리 실행 실패 시 (SE-102, node="index")
    """
    query = sql.SQL(
        """
        INSERT INTO {table} (chunk_id, document_id, content, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s::vector)
        ON CONFLICT (chunk_id) DO UPDATE SET
            document_id = EXCLUDED.document_id,
            content = EXCLUDED.content,
            metadata = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding
        """
    ).format(table=sql.Identifier(collection))

    params = [
        (
            chunk.chunk_id,
            chunk.document_id,
            chunk.content,
            # 명시 필드 중 None은 제외하고, extra="allow" 비정형 키(source 등)는 포함해 저장
            Jsonb(chunk.metadata.model_dump(exclude_none=True)),
            vector,
        )
        for chunk, vector in zip(batch, vectors)
    ]
    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(query, params)
    except Exception as e:
        logger.error(f"배치 upsert 실패: collection={collection}, batch_size={len(batch)}, {e}")
        raise DatabaseQueryError(f"배치 upsert 실패: {e}", node="index")


def index_documents(chunks: list[RetrievedChunk], collection: str) -> IndexingResult:
    """
    청크 리스트를 pgvector에 저장한다.
    - 각 청크의 content를 KURE-v1로 임베딩하여 vector(1024) 컬럼에 저장
    - 중복 chunk_id는 ON CONFLICT로 upsert 처리 (재실행 멱등)
    - EMBEDDING_MAX_TOKENS 초과 청크는 IX-201로 기록하고 청크 단위 스킵
    - 배치(BATCH_SIZE) 단위 부분 커밋: 실패 배치는 건너뛰고 나머지를 계속 처리

    :return: IndexingResult — status는 전량 성공 "success" / 일부 성공 "partial" / 전량 실패 "failed"
    """
    if not chunks:
        # 빈 입력은 저장할 것이 없는 비정상 호출이므로 failed로 보고한다 (인제스트 테스트 규약)
        return IndexingResult(document_id="", chunk_count=0, status="failed")

    document_id = chunks[0].document_id

    try:
        _ensure_collection(collection)
    except AccountingRAGError as e:
        # 테이블조차 보장할 수 없으면 어떤 배치도 성공할 수 없으므로 즉시 failed 반환
        logger.error(f"인덱싱 중단 — 컬렉션 보장 실패: {e.message}")
        return IndexingResult(document_id=document_id, chunk_count=0, status="failed")

    success_count = 0
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]
        try:
            # IX-201: 토큰 한도 초과 청크는 잘린 벡터가 저장되지 않도록 사전에 걸러 스킵한다
            valid_chunks = []
            for chunk in batch:
                token_count = count_tokens(chunk.content)
                if token_count > EMBEDDING_MAX_TOKENS:
                    error = EmbeddingTokenLimitError(
                        f"청크 토큰 한도 초과로 스킵: chunk_id={chunk.chunk_id}, "
                        f"tokens={token_count} > {EMBEDDING_MAX_TOKENS}"
                    )
                    logger.warning(f"[{error.error_type}] {error.message}")
                else:
                    valid_chunks.append(chunk)

            if not valid_chunks:
                continue

            vectors = embed_texts([chunk.content for chunk in valid_chunks], node="index")
            _upsert_batch(collection, valid_chunks, vectors)
            success_count += len(valid_chunks)
        except AccountingRAGError as e:
            # CM-002(임베딩)·SE-102(DB) 등 배치 단위 실패 — 부분 커밋 정책에 따라 다음 배치 계속
            logger.error(f"[{e.error_type}] 배치 인덱싱 실패 (chunks[{start}:{start + len(batch)}]): {e.message}")
            continue

    if success_count == len(chunks):
        status = "success"
    elif success_count > 0:
        status = "partial"
    else:
        status = "failed"

    logger.info(
        f"인덱싱 완료: document_id={document_id}, collection={collection}, "
        f"{success_count}/{len(chunks)}건 저장, status={status}"
    )
    return IndexingResult(document_id=document_id, chunk_count=success_count, status=status)


def similarity_search(query_vector: list[float], top_k: int, collection: str) -> list[RetrievedChunk]:
    """코사인 유사도 기반 근사 최근접 이웃(ANN) 검색. pgvector의 <=> 연산자 사용.

    - score = 1 - (코사인 거리) → 유사할수록 1에 가깝다 (HNSW vector_cosine_ops 인덱스 활용)
    - searcher.py와 동일하게 SEARCH_TIMEOUT_SECONDS를 적용한다

    :raises SearchTimeoutError: 쿼리 응답 시간 초과 시 (SE-101)
    :raises DatabaseQueryError: 그 외 DB 오류 시 (SE-102)
    """
    query = sql.SQL(
        """
        SELECT chunk_id, document_id, content, metadata,
               1 - (embedding <=> %s::vector) AS score
        FROM {table}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """
    ).format(table=sql.Identifier(collection))

    timeout_ms = SEARCH_TIMEOUT_SECONDS * 1000
    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL("SET LOCAL statement_timeout = {}").format(sql.Literal(f"{timeout_ms}ms")))
                cur.execute(query, [query_vector, query_vector, top_k])
                rows = cur.fetchall()
    except errors.QueryCanceled as e:
        logger.error(f"유사도 검색 타임아웃 초과: {e}")
        raise SearchTimeoutError(f"DB 검색 응답 시간 초과 ({SEARCH_TIMEOUT_SECONDS}s)")
    except Exception as e:
        logger.error(f"유사도 검색 중 DB 오류: {e}")
        raise DatabaseQueryError(f"데이터베이스 쿼리 실행 실패: {e}")

    results = []
    for chunk_id, document_id, content, metadata, score in rows:
        # metadata가 문자열(JSON)로 반환될 경우 dict로 파싱 (searcher와 동일한 방어 로직)
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
            metadata=metadata,
        ))
    return results


def delete_collection(collection: str) -> bool:
    """지정한 컬렉션의 모든 벡터를 삭제한다. 성공 시 True, 실패 시 False를 반환한다.

    테이블 자체는 유지하고 행만 비운다(DELETE). 재인덱싱 시 _ensure_collection()을
    다시 태울 필요가 없고, HNSW 인덱스 정의도 보존된다.
    """
    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL("DELETE FROM {table}").format(table=sql.Identifier(collection)))
        logger.info(f"컬렉션 삭제 완료: collection={collection}")
        return True
    except Exception as e:
        logger.error(f"컬렉션 삭제 실패: collection={collection}, {e}")
        return False
