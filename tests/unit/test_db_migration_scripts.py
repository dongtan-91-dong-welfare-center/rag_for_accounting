"""
db_dump.sh 및 db_restore.sh 단위 테스트

[테스트 목적]
결함 해소 검증:
1. scripts/lib/container_runtime.sh 및 scripts/lib/env_file.sh 호환 경로 검증
2. db_dump.sh 및 db_restore.sh의 인자 검증 및 도움말(-h/--help)
3. 컨테이너 미실행 시 런타임 추상화 기반 친절한 안내 메시지(${COMPOSE[*]} up -d) 출력
4. db_dump.sh의 운영 테이블 선별 덤프 및 .meta 사이드카 생성
5. db_restore.sh의 TOC 필터를 통한 Apache AGE 및 실험 테이블/로그 제거 검증
6. db_restore.sh의 복원 후 청크 건수 검증 (0건 실패, 불일치 실패, 정상 통과, .meta 자동 인식)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.utils.shell_test_helpers import (
    BASH_PATH as _BASH,
    make_bin as _make_bin,
    make_mock_env as _make_mock_env,
)

_ROOT = Path(__file__).resolve().parents[2] # tests/unit/test_db_migration_scripts.py
_DUMP_SH = _ROOT / "db_dump.sh"
_RESTORE_SH = _ROOT / "db_restore.sh"
_LIB_RUNTIME = _ROOT / "scripts" / "container_runtime.sh"
_LIB_ENV = _ROOT / "scripts" / "env_file.sh"


@pytest.mark.unit
def test_scripts_runtime_and_env_exports():
    """scripts/ 하위의 공유 유틸리티 스크립트들이 올바르게 함수를 노출하는지 검증."""
    # set -euo pipefail: 쉘 스크립트의 엄격 모드
    # -e: 명령어가 실패하면 즉시 중단
    # -u: 정의되지 않은 환경변수 사용 시 에러 처리
    # -o pipefail: 파이프라인 중간 단계에서 실패해도 전체 실패로 처리
    # type: 명령어가 쉘 세션에 실제로 존재하는지 확인
    cmd = f"""set -euo pipefail
source "{_LIB_RUNTIME}"
source "{_LIB_ENV}"
type detect_container_runtime >/dev/null
type read_env >/dev/null
echo "OK"
"""
    proc = subprocess.run([_BASH, "-c", cmd], capture_output=True, text=True)
    assert proc.returncode == 0 # 0은 성공을 의미하는 종료코드
    assert "OK" in proc.stdout  # OK 문자열이 출력됐는지 확인


@pytest.mark.unit
def test_dump_help():
    """db_dump.sh --help 실행 시 사용법을 출력하고 정상 종료(0)해야 한다."""
    proc = subprocess.run([_BASH, str(_DUMP_SH), "--help"], cwd=_ROOT, capture_output=True, text=True)
    assert proc.returncode == 0 # 0은 성공을 의미하는 종료코드
    assert "사용법: " in proc.stdout  # 사용법: 문자열이 출력됐는지 확인
    assert "accounting_db" in proc.stdout  # accounting_db 문자열이 출력됐는지 확인


@pytest.mark.unit
def test_restore_help_and_missing_arg():
    """db_restore.sh --help 및 인자 누락 검증."""
    # --help 플래그는 0으로 종료
    proc_help = subprocess.run([_BASH, str(_RESTORE_SH), "--help"], cwd=_ROOT, capture_output=True, text=True)
    assert proc_help.returncode == 0  # 0은 성공을 의미하는 종료코드
    assert "사용법: " in proc_help.stdout # 사용법: 문자열이 출력됐는지 확인

    proc_no_arg = subprocess.run([_BASH, str(_RESTORE_SH)], cwd=_ROOT, capture_output=True, text=True)
    assert proc_no_arg.returncode == 1  # 1은 실패를 의미하는 종료코드
    assert "사용법: " in proc_no_arg.stdout # 사용법: 문자열이 출력됐는지 확인


@pytest.mark.unit
def test_restore_file_not_found(tmp_path: Path):
    """존재하지 않는 덤프 파일 전달 시 에러 메시지와 함께 종료 코드 1 반환."""
    fake_dump = tmp_path / "non_existent.dump"
    proc = subprocess.run([_BASH, str(_RESTORE_SH), str(fake_dump)], cwd=_ROOT, capture_output=True, text=True)
    assert proc.returncode == 1 # 1은 실패를 의미하는 종료코드
    assert "[FAIL] 파일 없음" in proc.stderr  # [FAIL] 파일 없음 문자열이 출력됐는지 확인


@pytest.mark.unit
def test_restore_empty_file(tmp_path: Path):
    """0바이트의 빈 덤프 파일 전달 시 에러 메시지와 함께 종료 코드 1 반환."""
    empty_dump = tmp_path / "empty.dump"
    empty_dump.write_bytes(b"")
    proc = subprocess.run([_BASH, str(_RESTORE_SH), str(empty_dump)], cwd=_ROOT, capture_output=True, text=True)
    assert proc.returncode == 1 # 1은 실패를 의미하는 종료코드
    assert "[FAIL] 덤프 파일이 비어 있습니다" in proc.stderr # [FAIL] 덤프 파일이 비어 있습니다 문자열이 출력됐는지 확인


@pytest.mark.unit
def test_dump_container_not_running(tmp_path: Path):
    """컨테이너가 실행 중이지 않을 때 적절한 compose 실행 힌트를 출력하고 실패해야 한다."""
    # docker compose version은 성공하지만 docker ps 목록에는 accounting_db가 없는 가짜 docker
    fake_docker = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"
  exit 0
fi
if [ "$1" = "ps" ]; then
  echo "other_container"
  exit 0
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": fake_docker})
    env = _make_mock_env(bin_dir)

    out_file = tmp_path / "test.dump"
    proc = subprocess.run([_BASH, str(_DUMP_SH), str(out_file)], cwd=_ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode == 1 # 1은 실패를 의미하는 종료코드
    assert "accounting_db 컨테이너가 실행 중이 아닙니다" in proc.stderr # accounting_db 컨테이너가 실행 중이 아닙니다 문자열이 출력됐는지 확인
    assert "docker compose up -d" in proc.stderr # docker compose up -d 문자열이 출력됐는지 확인


@pytest.mark.unit
def test_restore_container_not_running_podman(tmp_path: Path):
    """podman 환경에서 컨테이너 미실행 시 podman-compose up -d 안내가 출력되는지 검증."""
    fake_podman_compose = """#!/bin/sh
exit 0
"""
    fake_podman = """#!/bin/sh
if [ "$1" = "ps" ]; then
  echo "another_container"
  exit 0
fi
exit 0
"""
    # docker 없이 podman과 podman-compose만 있는 환경
    bin_dir = _make_bin(tmp_path, {"podman-compose": fake_podman_compose, "podman": fake_podman})
    env = _make_mock_env(bin_dir, isolate=True)

    dump_file = tmp_path / "valid.dump"
    dump_file.write_bytes(b"dummy pg_dump content")

    proc = subprocess.run([_BASH, str(_RESTORE_SH), str(dump_file)], cwd=_ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode == 1 # 1은 실패를 의미하는 종료코드
    assert "accounting_db 컨테이너가 실행 중이 아닙니다" in proc.stderr # accounting_db 컨테이너가 실행 중이 아닙니다 문자열이 출력됐는지 확인
    assert "podman-compose up -d" in proc.stderr # podman-compose up -d 문자열이 출력됐는지 확인


@pytest.mark.unit
def test_toc_filter_logic():
    """TOC 필터링 정규식이 Apache AGE 및 실험 테이블/개발 로그를 정확히 걸러내는지 검증."""
    sample_toc = """
; Archive created at 2026-08-22
; TOC Entries: 15
215; 1259 16400 TABLE public chunks accounting_user
216; 1259 16410 TABLE public chunks_morph accounting_user
217; 1259 16420 TABLE public chunks_2048 accounting_user
218; 1259 16430 TABLE public chunks_fine accounting_user
219; 1259 16440 TABLE public bench_indexing accounting_user
220; 1259 16450 TABLE public interaction_log accounting_user
300; 3079 16500 EXTENSION - age -
301; 0 0 COMMENT - EXTENSION age 
302; 2615 16510 SCHEMA - ag_catalog accounting_user
3170; 1259 16600 INDEX public chunks chunks_embedding_hnsw_idx accounting_user
3300; 0 16400 TABLE DATA public chunks accounting_user
3301; 0 16450 TABLE DATA public interaction_log accounting_user
"""
    # grep -viE:
    # -v: 정규식 패턴과 일치하지 않는 라인만 남깁니다(일치하는 라인 제거)
    # -i: 대소문자 구분 없음
    # -E: 확장 정규표현식(| OR 연산 등) 활성화
    filter_cmd = 'grep -viE "EXTENSION - age|COMMENT - EXTENSION age|ag_catalog|interaction_log|bench_indexing|chunks_2048|chunks_fine|chunks_smoke|chunks_test_"'
    proc = subprocess.run(filter_cmd, shell=True, input=sample_toc, capture_output=True, text=True)
    filtered = proc.stdout

    # AGE 관련 항목 제외 확인
    assert "EXTENSION - age" not in filtered  # EXTENSION - age 문자열이 출력되지 않는지 확인
    assert "ag_catalog" not in filtered  # ag_catalog 문자열이 출력되지 않는지 확인

    # 실험 테이블 및 로그 제외 확인
    assert "chunks_2048" not in filtered  # chunks_2048 문자열이 출력되지 않는지 확인
    assert "chunks_fine" not in filtered  # chunks_fine 문자열이 출력되지 않는지 확인
    assert "bench_indexing" not in filtered # bench_indexing 문자열이 출력되지 않는지 확인
    assert "interaction_log" not in filtered # interaction_log 문자열이 출력되지 않는지 확인

    # 운영 테이블 및 인덱스 유지 확인
    assert "TABLE public chunks accounting_user" in filtered  # TABLE public chunks accounting_user 문자열이 출력됐는지 확인
    assert "TABLE public chunks_morph accounting_user" in filtered # TABLE public chunks_morph accounting_user 문자열이 출력됐는지 확인
    assert "chunks_embedding_hnsw_idx" in filtered # chunks_embedding_hnsw_idx 문자열이 출력됐는지 확인
    assert "TABLE DATA public chunks accounting_user" in filtered # TABLE DATA public chunks accounting_user 문자열이 출력됐는지 확인


@pytest.mark.unit
def test_dump_successful_execution(tmp_path: Path):
    """모의 docker 환경에서 db_dump.sh가 운영 테이블을 선별하고 .meta 파일을 생성하는지 검증."""
    # $@: 스크립트나 함수에 전달된 모든 위치 매개변수($1, $2, $3, ...) 목록을 가리킵니다.
    # "$@": 따옴표(")로 감싸면 각 인자를 원래 전달받은 개별 단위로 분리 유지합니다
    # "$1" "$2" "$3" ... 와 동일하게 동작합니다.
    # 인자 내부에 공백이나 줄바꿈이 포함되어 있어도 하나로 쪼개지지 않고 단일 값으로 보존됩니다.
    # for arg in ...; do: 전달받은 인자들을 차례대로 arg라는 변수에 담아 done에 도달할 때까지 반복 실행
    # "$@": for 루프 안에서 $@를 따옴표로 감싸면 (예: for arg in "$@"; do), 모든 인자가 공백이나 특수문자를 포함하더라도 원래의 하나의 값 단위로 안전하게 순회됩니다.
    # 이것이 없다면(for arg in $...; do), 인자에 공백이 있을 때 셸이 이를 기준으로 분리해버려서 예상치 못한 동작을 유발합니다.
    fake_docker = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"
  exit 0
fi
if [ "$1" = "ps" ]; then
  echo "accounting_db"
  exit 0
fi
if [ "$1" = "exec" ]; then
  # psql 호출 검사
  for arg in "$@"; do
    if [ "$arg" = "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='chunks';" ]; then
      echo "1"
      exit 0
    fi
    if [ "$arg" = "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='chunks_morph';" ]; then
      echo "1"
      exit 0
    fi
    if [ "$arg" = "SELECT COUNT(*) FROM chunks;" ]; then
      echo "1507"
      exit 0
    fi
    if [ "$arg" = "pg_dump" ]; then
      echo "MOCK_PG_DUMP_BINARY_DATA"
      exit 0
    fi
  done
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": fake_docker})
    env = _make_mock_env(bin_dir)

    # pytest는 tmp_path를 통해 생성한 디렉터리와 전여 파일에 대해 주기적으로 청소를 진행하므로 명시적으로 삭제하지 않아도 된다
    out_file = tmp_path / "backups" / "test_dump.dump"
    proc = subprocess.run([_BASH, str(_DUMP_SH), str(out_file)], cwd=_ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, f"dump failed: stderr={proc.stderr}, stdout={proc.stdout}" # 0은 성공을 의미하는 종료코드
    assert out_file.exists() # test_dump.dump 파일이 존재하는지 확인
    assert "MOCK_PG_DUMP_BINARY_DATA" in out_file.read_text() # MOCK_PG_DUMP_BINARY_DATA 문자열이 출력됐는지 확인

    # .meta 사이드카 검증
    meta_file = Path(f"{out_file}.meta")
    assert meta_file.exists() # .meta 파일이 존재하는지 확인
    meta_content = meta_file.read_text()
    assert "CHUNKS_COUNT=1507" in meta_content  # CHUNKS_COUNT=1507 문자열이 출력됐는지 확인
    assert "TABLES=-t chunks -t chunks_morph" in meta_content  # TABLES=-t chunks -t chunks_morph 문자열이 출력됐는지 확인


@pytest.mark.unit
def test_restore_verification_zero_chunks_fails(tmp_path: Path):
    """복원 후 chunks 테이블이 0건이면 검증 실패로 판정되어 종료 코드 1 반환."""
    fake_docker = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"
  exit 0
fi
if [ "$1" = "ps" ]; then
  echo "accounting_db"
  exit 0
fi
if [ "$1" = "cp" ]; then
  exit 0
fi
if [ "$1" = "exec" ]; then
  for arg in "$@"; do
    if [ "$arg" = "pg_restore" ]; then
      exit 0
    fi
    if [ "$arg" = "SELECT COUNT(*) FROM chunks;" ]; then
      echo "0"
      exit 0
    fi
  done
  exit 0
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": fake_docker})
    env = _make_mock_env(bin_dir)

    dump_file = tmp_path / "valid.dump"
    dump_file.write_text("pg_dump data")

    proc = subprocess.run([_BASH, str(_RESTORE_SH), str(dump_file)], cwd=_ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode == 1 # 1은 실패를 의미하는 종료코드
    assert "[FAIL] 복원 검증 실패: chunks 테이블이 비어 있습니다 (0건)" in proc.stderr  # [FAIL] 복원 검증 실패: chunks 테이블이 비어 있습니다 (0건) 문자열이 출력됐는지 확인


@pytest.mark.unit
def test_restore_verification_mismatch_fails(tmp_path: Path):
    """기대 청크 수(1507)와 실제 복원 청크 수(1000)가 불일치할 때 실패 검증."""
    fake_docker = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"
  exit 0
fi
if [ "$1" = "ps" ]; then
  echo "accounting_db"
  exit 0
fi
if [ "$1" = "cp" ]; then
  exit 0
fi
if [ "$1" = "exec" ]; then
  for arg in "$@"; do
    if [ "$arg" = "pg_restore" ]; then
      exit 0
    fi
    if [ "$arg" = "SELECT COUNT(*) FROM chunks;" ]; then
      echo "1000"
      exit 0
    fi
  done
  exit 0
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": fake_docker})
    env = _make_mock_env(bin_dir)

    dump_file = tmp_path / "valid.dump"
    dump_file.write_text("pg_dump data")

    # 기대 청크 수로 1507 전달
    proc = subprocess.run([_BASH, str(_RESTORE_SH), str(dump_file), "1507"], cwd=_ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode == 1 # 1은 실패를 의미하는 종료코드
    assert "청크 수 불일치 (기대: 1507건, 실제 복원: 1000건)" in proc.stderr  # 청크 수 불일치 (기대: 1507건, 실제 복원: 1000건) 문자열이 출력됐는지 확인


@pytest.mark.unit
def test_restore_verification_success_with_meta(tmp_path: Path):
    """사이드카 .meta 파일의 CHUNKS_COUNT(1507)와 실제 복원 건수가 일치할 때 복원 성공."""
    fake_docker = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"
  exit 0
fi
if [ "$1" = "ps" ]; then
  echo "accounting_db"
  exit 0
fi
if [ "$1" = "cp" ]; then
  exit 0
fi
if [ "$1" = "exec" ]; then
  for arg in "$@"; do
    if [ "$arg" = "pg_restore" ]; then
      exit 0
    fi
    if [ "$arg" = "SELECT COUNT(*) FROM chunks;" ]; then
      echo "1507"
      exit 0
    fi
    if [ "$arg" = "SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'chunks';" ]; then
      echo "3"
      exit 0
    fi
  done
  exit 0
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": fake_docker})
    env = _make_mock_env(bin_dir)

    dump_file = tmp_path / "valid.dump"
    dump_file.write_text("pg_dump data")
    meta_file = tmp_path / "valid.dump.meta"
    meta_file.write_text("CHUNKS_COUNT=1507\nDATABASE=accounting_db\n")

    # 인자로 기대 청크 수를 명시하지 않아도 .meta 파일에서 읽어서 1507과 일치 검증
    proc = subprocess.run([_BASH, str(_RESTORE_SH), str(dump_file)], cwd=_ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, f"restore failed: stderr={proc.stderr}, stdout={proc.stdout}"  # 0은 성공을 의미하는 종료코드
    assert "valid.dump.meta 파일에서 기대 청크 수(1507건)를 읽었습니다" in proc.stdout  # valid.dump.meta 파일에서 기대 청크 수(1507건)를 읽었습니다 문자열이 출력됐는지 확인
    assert "청크 수 일치 검증 통과: 1507건" in proc.stdout  # 청크 수 일치 검증 통과: 1507건 문자열이 출력됐는지 확인
    assert "복원 완료: chunks 1507건, 인덱스 3개 정상" in proc.stdout  # 복원 완료: chunks 1507건, 인덱스 3개 정상 문자열이 출력됐는지 확인


@pytest.mark.unit
def test_dump_missing_chunks_table_fails(tmp_path: Path):
    """DB에 chunks 테이블이 없을 때 ALL_TABLES=1이 아니면 에러를 내며 종료해야 한다."""
    fake_docker = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"
  exit 0
fi
if [ "$1" = "ps" ]; then
  echo "accounting_db"
  exit 0
fi
if [ "$1" = "exec" ]; then
  # 테이블 존재 쿼리에 아무것도 반환하지 않음 (테이블 없음)
  exit 0
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": fake_docker})
    env = _make_mock_env(bin_dir)

    out_file = tmp_path / "test.dump"
    proc = subprocess.run([_BASH, str(_DUMP_SH), str(out_file)], cwd=_ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode == 1 # 1은 실패를 의미하는 종료코드
    assert "운영 테이블(chunks)을 DB에서 찾을 수 없습니다" in proc.stderr  # 운영 테이블(chunks)을 DB에서 찾을 수 없습니다 문자열이 출력됐는지 확인


@pytest.mark.unit
def test_dump_fails_and_cleans_empty_file(tmp_path: Path):
    """pg_dump 실패로 0바이트 빈 파일이 생겼을 때 파일을 남기지 않고 삭제하는지 검증."""
    fake_docker = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"
  exit 0
fi
if [ "$1" = "ps" ]; then
  echo "accounting_db"
  exit 0
fi
if [ "$1" = "exec" ]; then
  for arg in "$@"; do
    if [ "$arg" = "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='chunks';" ]; then
      echo "1"
      exit 0
    fi
    if [ "$arg" = "pg_dump" ]; then
      # 빈 내용만 출력하고 실패
      exit 1
    fi
  done
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": fake_docker})
    env = _make_mock_env(bin_dir)

    out_file = tmp_path / "test_empty.dump"
    proc = subprocess.run([_BASH, str(_DUMP_SH), str(out_file)], cwd=_ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode == 1 # 1은 실패를 의미하는 종료코드
    assert "pg_dump 실행에 실패했습니다" in proc.stderr or "덤프 파일이 비어있거나 생성되지 않았습니다" in proc.stderr  # pg_dump 실행에 실패했습니다 또는 덤프 파일이 비어있거나 생성되지 않았습니다 문자열이 출력됐는지 확인
    assert not out_file.exists() # test_empty.dump 파일이 존재하지 않는지 확인


@pytest.mark.unit
def test_restore_zero_indexes_warns(tmp_path: Path):
    """복원 후 chunks 인덱스 개수가 0개일 때 경고 로그를 출력하는지 검증."""
    fake_docker = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"
  exit 0
fi
if [ "$1" = "ps" ]; then
  echo "accounting_db"
  exit 0
fi
if [ "$1" = "cp" ]; then
  exit 0
fi
if [ "$1" = "exec" ]; then
  for arg in "$@"; do
    if [ "$arg" = "pg_restore" ]; then
      exit 0
    fi
    if [ "$arg" = "SELECT COUNT(*) FROM chunks;" ]; then
      echo "1507"
      exit 0
    fi
    if [ "$arg" = "SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'chunks';" ]; then
      echo "0"
      exit 0
    fi
  done
  exit 0
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": fake_docker})
    env = _make_mock_env(bin_dir)

    dump_file = tmp_path / "valid.dump"
    dump_file.write_text("pg_dump data")

    proc = subprocess.run([_BASH, str(_RESTORE_SH), str(dump_file), "1507"], cwd=_ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode == 0 # 0은 성공을 의미하는 종료코드
    assert "[WARN] chunks 테이블에 생성된 인덱스가 없습니다." in proc.stderr  # [WARN] chunks 테이블에 생성된 인덱스가 없습니다. 문자열이 출력됐는지 확인
