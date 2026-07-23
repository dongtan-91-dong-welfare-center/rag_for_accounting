# 설계 결정 요약:
#   - vector_store.py의 임베딩 테이블과는 별도 테이블이다. 로그에는 벡터가 없으므로 pgvector에 의존하지 않는다.
#   - INSERT 실패는 API 요청을 막지 않는다 — 로깅은 부가 기능이지 핵심 경로가 아니므로, 테이블 미존재·DB 순단 등으로 실패해도 예외를 삼키고 경고만 남긴 뒤 정상 응답을 이어간다.
#   - evaluation은 EvaluationResult 필드를 그대로 컬럼화한다 — CRAG 판정 축을 SQL로 바로 집계·필터링할 수 있게 하기 위함이다.
#   - citations는 건수가 가변인 리스트라 컬럼화하지 않고 JSONB 배열로 저장한다.

from typing import Sequence

from psycopg import sql
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from src.db.connection import get_pool
from src.models.schemas import EvaluationResult
from src.utils.logger import get_logger

logger = get_logger(__name__)

_TABLE = "interaction_log"


def ensure_interaction_log_table() -> None:
    """테이블·인덱스가 없으면 생성한다. 서버 기동(lifespan) 시 1회 호출한다."""
    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        """
                        CREATE TABLE IF NOT EXISTS {table} (
                            id BIGSERIAL PRIMARY KEY,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                            thread_id TEXT NOT NULL,
                            endpoint TEXT NOT NULL,
                            query TEXT NOT NULL,
                            standard_filter TEXT,
                            status TEXT NOT NULL,
                            answer TEXT,
                            is_answerable BOOLEAN,
                            confidence DOUBLE PRECISION,
                            error_code TEXT,
                            eval_is_relevant BOOLEAN,
                            eval_needs_external BOOLEAN,
                            eval_confidence DOUBLE PRECISION,
                            eval_reasoning TEXT,
                            citations JSONB,
                            elapsed_ms INTEGER
                        )
                        """
                    ).format(table=sql.Identifier(_TABLE))
                )
                cur.execute(
                    sql.SQL(
                        "CREATE INDEX IF NOT EXISTS {index} ON {table} (thread_id)"
                    ).format(
                        index=sql.Identifier(f"{_TABLE}_thread_id_idx"),
                        table=sql.Identifier(_TABLE),
                    )
                )
    except Exception as e:
        logger.warning(f"interaction_log 테이블 준비 실패 — 운영 로깅 없이 계속 진행: {e}")


def log_interaction(
    *,
    thread_id: str,
    endpoint: str,
    query: str,
    standard_filter: str | None,
    status: str,
    answer: str | None = None,
    is_answerable: bool | None = None,
    confidence: float | None = None,
    error_code: str | None = None,
    evaluation: EvaluationResult | None = None,
    citations: Sequence[BaseModel] | None = None,
    elapsed_ms: int | None = None,
) -> None:
    """질의/응답 1건을 interaction_log에 적재한다.

    citations는 model_dump()만 있으면 되므로 src.models.schemas.Citation과
    src.api.schemas.CitationOut(페이지 필드가 추가된 API 표현) 어느 쪽을 넘겨도 된다.

    실패해도 예외를 올리지 않고 경고만 남긴다 — 운영 로깅이 사용자 응답 경로를
    막아서는(요청 실패·지연) 안 되기 때문이다.
    """
    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        """
                        INSERT INTO {table} (
                            thread_id, endpoint, query, standard_filter, status,
                            answer, is_answerable, confidence, error_code,
                            eval_is_relevant, eval_needs_external, eval_confidence, eval_reasoning,
                            citations, elapsed_ms
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                    ).format(table=sql.Identifier(_TABLE)),
                    (
                        thread_id, endpoint, query, standard_filter, status,
                        answer, is_answerable, confidence, error_code,
                        evaluation.is_relevant if evaluation is not None else None,
                        evaluation.needs_external if evaluation is not None else None,
                        evaluation.confidence if evaluation is not None else None,
                        evaluation.reasoning if evaluation is not None else None,
                        Jsonb([c.model_dump() for c in citations]) if citations is not None else None,
                        elapsed_ms,
                    ),
                )
    except Exception as e:
        logger.warning(f"interaction_log 적재 실패(무시하고 계속): thread_id={thread_id}, {e}")
