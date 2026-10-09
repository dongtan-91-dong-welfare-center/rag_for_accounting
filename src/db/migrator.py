"""
경량 SQL 마이그레이션 러너 모듈 (#380)

migrations/*.sql 디렉터리 내의 SQL 파일들을 버전 순서대로 감지하고,
PostgreSQL DB에 연결하여 schema_migrations 이력 테이블을 기준으로 신규 파일들을 순차 적용한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
import re
from typing import TYPE_CHECKING

from src.utils.logger import get_logger, log_kv

if TYPE_CHECKING:
    from psycopg import Connection

logger = get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    path: Path


def discover_migrations(directory: Path | None = None) -> list[Migration]:
    """지정된 디렉터리(기본: 프로젝트 루트의 migrations/)에서 SQL 마이그레이션 파일 목록을 탐색한다."""
    target_dir = directory or MIGRATIONS_DIR
    if not target_dir.exists():
        return []

    migrations: list[Migration] = []
    # 파일명 패턴: <버전>_<이름>.sql (예: 0001_initial.sql)
    pattern = re.compile(r"^(\d+)_(.+)\.sql$")

    for file in sorted(target_dir.glob("*.sql")):
        match = pattern.match(file.name)
        if match:
            version = match.group(1)
            migrations.append(Migration(version=version, name=file.name, path=file))
        else:
            log_kv(logger, logging.WARNING, "db", "마이그레이션 명명 규칙(숫자_이름.sql)에 맞지 않아 무시됩니다", 대상=file.name)

    return sorted(migrations, key=lambda m: m.version)


class MigrationRunner:
    """SQL 마이그레이션을 데이터베이스에 순차 적용하는 러너."""

    def __init__(self, migrations_dir: Path | None = None):
        self.migrations_dir = migrations_dir or MIGRATIONS_DIR

    def _ensure_migration_table(self, conn: Connection) -> None:
        """마이그레이션 이력을 추적하는 schema_migrations 테이블을 생성한다."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
        with conn.cursor() as cur:
            cur.execute(create_table_sql)
        conn.commit()

    def _get_applied_versions(self, conn: Connection) -> set[str]:
        """이미 데이터베이스에 적용된 마이그레이션 버전 집합을 반환한다."""
        with conn.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations;")
            rows = cur.fetchall()
            return {row[0] for row in rows}

    def apply(self, conn: Connection) -> list[Migration]:
        """신규 마이그레이션 파일들을 순차적으로 실행하고 적용된 목록을 반환한다."""
        self._ensure_migration_table(conn)
        applied_versions = self._get_applied_versions(conn)
        all_migrations = discover_migrations(self.migrations_dir)

        new_migrations = [m for m in all_migrations if m.version not in applied_versions]
        if not new_migrations:
            log_kv(logger, logging.INFO, "db", "적용할 신규 마이그레이션이 없습니다.")
            return []

        applied: list[Migration] = []
        for migration in new_migrations:
            log_kv(logger, logging.INFO, "db", "마이그레이션 적용 시작", 대상=migration.name, 버전=migration.version)
            sql_content = migration.path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                # SQL 파일 실행
                cur.execute(sql_content)
                # 이력 테이블에 적용 기록
                cur.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (%s, %s);",
                    (migration.version, migration.name),
                )
            conn.commit()
            log_kv(logger, logging.INFO, "db", "마이그레이션 적용 완료", 대상=migration.name)
            applied.append(migration)

        return applied


def run_migrations(migrations_dir: Path | None = None) -> list[Migration]:
    """DB 풀에서 커넥션을 얻어 마이그레이션을 실행하는 편의 함수."""
    from src.db.connection import get_pool, init_pool

    init_pool()
    with get_pool().connection() as conn:
        runner = MigrationRunner(migrations_dir=migrations_dir)
        return runner.apply(conn)
