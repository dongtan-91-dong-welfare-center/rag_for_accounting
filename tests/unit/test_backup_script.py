"""
scripts/backup.sh 단위 테스트

[테스트 목적]
1. backup.sh의 인자 검증 및 도움말(-h/--help)
2. 잘못된 RETENTION_DAYS(음수, 문자열 등) 입력 시 에러 종료 검증
3. BACKUP_DIR 위험 경로(/, $HOME) 방어 및 존재하지 않는 경로 자동 생성/검증
4. db_dump.sh 호출 래핑 및 모의 실행 성공 확인
5. 보관 주기(Retention) 자동 정리:
   - RETENTION_DAYS 초과된 파일(*.dump, *.meta, *.tar.gz) 삭제 검증
   - 보관 기간 이내의 최근 파일 보존 검증
6. INCLUDE_PDF=1 설정 시 data/raw_data 아카이빙 동작 검증
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.utils.shell_test_helpers import (
    BASH_PATH as _BASH,
    make_bin as _make_bin,
    make_mock_env as _make_mock_env,
    run_shell as _run_shell,
)

_ROOT = Path(__file__).resolve().parents[2]
_BACKUP_SH = _ROOT / "scripts" / "backup.sh"


def _exec(
    cmd: list[str] | str,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """BASH_PATH를 적용하여 셸 명령을 실행합니다."""
    return _run_shell(cmd, cwd=cwd or _ROOT, env=env)


@pytest.mark.unit
def test_backup_script_help():
    """-h 또는 --help 플래그 입력 시 도움말이 정상 출력되고 종료코드 0을 반환하는지 검증합니다."""
    proc_h = _exec([_BASH, str(_BACKUP_SH), "-h"])
    assert proc_h.returncode == 0
    assert "사용법:" in proc_h.stdout
    assert "RETENTION_DAYS" in proc_h.stdout

    proc_help = _exec([_BASH, str(_BACKUP_SH), "--help"])
    assert proc_help.returncode == 0
    assert "사용법:" in proc_help.stdout


@pytest.mark.unit
def test_backup_script_invalid_retention_days():
    """RETENTION_DAYS 환경변수에 숫자가 아닌 값이 주어지면 에러와 함께 종료코드 1을 반환해야 합니다."""
    env = os.environ.copy()
    env["RETENTION_DAYS"] = "invalid_number"
    proc = _exec([_BASH, str(_BACKUP_SH)], env=env)
    assert proc.returncode != 0
    assert "RETENTION_DAYS는 0 이상의 정수여야 합니다" in proc.stderr


@pytest.mark.unit
def test_backup_script_unsafe_backup_dir():
    """BACKUP_DIR이 루트(/) 또는 홈($HOME)으로 지정될 경우 안전장치에 의해 거부되어야 합니다."""
    env = os.environ.copy()
    env["BACKUP_DIR"] = "/"
    proc_root = _exec([_BASH, str(_BACKUP_SH)], env=env)
    assert proc_root.returncode != 0
    assert "루트(/) 또는 홈 디렉터리로 설정할 수 없습니다" in proc_root.stderr

    env["BACKUP_DIR"] = os.path.expanduser("~")
    proc_home = _exec([_BASH, str(_BACKUP_SH)], env=env)
    assert proc_home.returncode != 0
    assert "루트(/) 또는 홈 디렉터리로 설정할 수 없습니다" in proc_home.stderr


@pytest.mark.unit
def test_backup_script_retention_rotation(tmp_path: Path):
    """
    보관 주기(RETENTION_DAYS)를 초과한 파일은 삭제되고,
    보관 기간 이내의 최근 파일은 안전하게 보존되는지 검증합니다.
    """
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # 1. 40일 전 파일 생성 (삭제 대상)
    old_dump = backup_dir / "old_20260101.dump"
    old_meta = backup_dir / "old_20260101.dump.meta"
    old_pdf_tar = backup_dir / "old_pdf_20260101.tar.gz"
    old_dump.write_text("old dump content", encoding="utf-8")
    old_meta.write_text("old meta content", encoding="utf-8")
    old_pdf_tar.write_text("old tar content", encoding="utf-8")

    # 2. 최근 파일 생성 (보존 대상)
    recent_dump = backup_dir / "recent_20261001.dump"
    recent_meta = backup_dir / "recent_20261001.dump.meta"
    recent_dump.write_text("recent dump content", encoding="utf-8")
    recent_meta.write_text("recent meta content", encoding="utf-8")

    # touch -t 명령으로 과거 타임스탬프 부여 (2020년 1월 1일 00:00)
    subprocess.run(["touch", "-t", "202001010000", str(old_dump)], check=True)
    subprocess.run(["touch", "-t", "202001010000", str(old_meta)], check=True)
    subprocess.run(["touch", "-t", "202001010000", str(old_pdf_tar)], check=True)

    # 모의 db_dump.sh 준비 (새 덤프 생성 시뮬레이션)
    fake_dump_sh = tmp_path / "db_dump.sh"
    fake_dump_sh.write_text(
        """#!/usr/bin/env bash
out="${1:-backups/new_backup.dump}"
mkdir -p "$(dirname "$out")"
echo "new dump content" > "$out"
echo "new meta content" > "${out}.meta"
echo "[DUMP OK] $out"
""",
        encoding="utf-8",
    )
    fake_dump_sh.chmod(0o755)

    env = os.environ.copy()
    env["BACKUP_DIR"] = str(backup_dir)
    env["RETENTION_DAYS"] = "30"
    env["DUMP_SCRIPT"] = str(fake_dump_sh)

    proc = _exec([_BASH, str(_BACKUP_SH)], env=env)
    assert proc.returncode == 0
    assert "백업 작업이 완료되었습니다" in proc.stdout

    # 과거 파일은 삭제되어야 함
    assert not old_dump.exists()
    assert not old_meta.exists()
    assert not old_pdf_tar.exists()

    # 최근 파일 및 신규 파일은 유지되어야 함
    assert recent_dump.exists()
    assert recent_meta.exists()


@pytest.mark.unit
def test_backup_script_include_pdf(tmp_path: Path):
    """INCLUDE_PDF=1 설정 시 data/raw_data가 tar.gz로 안전하게 압축 백업되는지 검증합니다."""
    backup_dir = tmp_path / "backups"
    raw_data_dir = tmp_path / "data" / "raw_data"
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    (raw_data_dir / "sample.pdf").write_bytes(b"%PDF-1.4 sample content")

    fake_dump_sh = tmp_path / "db_dump.sh"
    fake_dump_sh.write_text(
        """#!/usr/bin/env bash
out="${1:-backups/mock.dump}"
mkdir -p "$(dirname "$out")"
echo "mock" > "$out"
echo "mock" > "${out}.meta"
""",
        encoding="utf-8",
    )
    fake_dump_sh.chmod(0o755)

    env = os.environ.copy()
    env["BACKUP_DIR"] = str(backup_dir)
    env["RAW_DATA_DIR"] = str(raw_data_dir)
    env["INCLUDE_PDF"] = "1"
    env["DUMP_SCRIPT"] = str(fake_dump_sh)

    proc = _exec([_BASH, str(_BACKUP_SH)], env=env)
    assert proc.returncode == 0

    tar_files = list(backup_dir.glob("raw_data_*.tar.gz"))
    assert len(tar_files) == 1
    assert tar_files[0].stat().st_size > 0
