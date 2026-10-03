"""
데이터베이스 마이그레이션 모듈 단위 테스트
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.db.migrator import Migration, MigrationRunner, discover_migrations


@pytest.fixture
def mock_migrations_dir(tmp_path: Path) -> Path:
    """테스트용 마이그레이션 파일이 포함된 임시 디렉터리를 생성한다."""
    (tmp_path / "0001_initial.sql").write_text("CREATE TABLE test_a (id INT);", encoding="utf-8")
    (tmp_path / "0002_add_column.sql").write_text("ALTER TABLE test_a ADD COLUMN name TEXT;", encoding="utf-8")
    (tmp_path / "README.md").write_text("Ignored file", encoding="utf-8")
    return tmp_path


@pytest.mark.unit
def test_discover_migrations(mock_migrations_dir: Path):
    """SQL 파일만 올바른 버전 순서로 탐색되는지 검증한다."""
    migrations = discover_migrations(mock_migrations_dir)
    assert len(migrations) == 2
    assert migrations[0].version == "0001"
    assert migrations[0].name == "0001_initial.sql"
    assert migrations[1].version == "0002"
    assert migrations[1].name == "0002_add_column.sql"


@pytest.mark.unit
def test_migration_runner_init_table():
    """schema_migrations 테이블 생성 DDL이 실행되는지 검증한다."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    runner = MigrationRunner(migrations_dir=Path("/tmp/dummy"))
    runner._ensure_migration_table(mock_conn)

    assert mock_cursor.execute.called
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "schema_migrations" in executed_sql


@pytest.mark.unit
def test_migration_runner_get_applied_versions():
    """이미 적용된 마이그레이션 버전 목록을 올바르게 조회하는지 검증한다."""
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("0001",), ("0002",)]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    runner = MigrationRunner(migrations_dir=Path("/tmp/dummy"))
    applied = runner._get_applied_versions(mock_conn)

    assert applied == {"0001", "0002"}


@pytest.mark.unit
def test_migration_runner_apply_new_migrations(mock_migrations_dir: Path):
    """신규 마이그레이션만 선별하여 실행하고 이력을 기록하는지 검증한다."""
    mock_cursor = MagicMock()
    # 0001은 이미 적용된 상태로 설정
    mock_cursor.fetchall.return_value = [("0001",)]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    runner = MigrationRunner(migrations_dir=mock_migrations_dir)
    applied = runner.apply(mock_conn)

    assert len(applied) == 1
    assert applied[0].version == "0002"
    assert applied[0].name == "0002_add_column.sql"

    # 0002의 SQL 내용과 schema_migrations INSERT가 실행되었는지 확인
    execute_calls = [c[0][0] for c in mock_cursor.execute.call_args_list]
    assert any("ALTER TABLE test_a ADD COLUMN name TEXT;" in str(call_arg) for call_arg in execute_calls)
    assert any("INSERT INTO schema_migrations" in str(call_arg) for call_arg in execute_calls)
    assert mock_conn.commit.called
