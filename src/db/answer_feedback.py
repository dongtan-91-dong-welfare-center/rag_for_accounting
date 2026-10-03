# 설계 결정 요약:
#   - 질의 로그(interaction_log)를 변경하지 않고 별도 테이블로 둔다. 근거: 기존 로그 스키마와 운영 데이터에 영향을 주지 않아 위험이 작다.
#   - thread_id에는 외래 키를 걸지 않는다. 근거: interaction_log의 thread_id는 /query와 /resume마다 반복되어 유일하지 않으며, 로그 적재는 실패해도 무시되므로 참조 무결성이 보장되지 않는다. 집계 시에는 thread_id로 조인한다.
#   - 같은 thread_id에 대한 재평가는 행을 덮어쓰지 않고 추가한다. 근거: 평가 변경 이력을 보존하고 집계 시 최신 행을 사용한다.
#   - INSERT 실패는 예외를 그대로 올린다. 근거: 평가는 사용자가 명시적으로 보낸 요청이므로 저장 실패를 호출자(API)가 알려야 한다.

from typing import Literal

from psycopg import sql

from src.db.connection import get_pool
from src.utils.logger import get_logger

logger = get_logger(__name__)

_TABLE = "answer_feedback"

Rating = Literal["up", "down"]


def ensure_answer_feedback_table() -> None:
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
                            rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
                            reason TEXT
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
        logger.warning(f"answer_feedback 테이블 준비 실패 — 평가 저장 없이 계속 진행: {e}")


def save_feedback(*, thread_id: str, rating: Rating, reason: str | None = None) -> None:
    """답변 평가 1건을 저장한다. 실패하면 예외를 올린다."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "INSERT INTO {table} (thread_id, rating, reason) VALUES (%s, %s, %s)"
                ).format(table=sql.Identifier(_TABLE)),
                (thread_id, rating, reason),
            )
