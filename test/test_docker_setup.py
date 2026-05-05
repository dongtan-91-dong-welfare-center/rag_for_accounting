import os
# 환경 변수에서 읽어오고, 없으면 기본값(accounting_db) 사용
DB_NAME = os.getenv("POSTGRES_DB", "accounting_db")
DB_USER = os.getenv("POSTGRES_USER", "accounting_user")
# 파이썬 프로그램 내부에서 외부 프로그램이나 쉘 명령어(ls, cd, docker, git 등)를 실행하고
# 그 결과(출력 내용, 에러 메시지, 종료 코드 등)를 파이썬으로 가져올 때 사용하는 표준 라이브러리
import subprocess
import pytest

def run_command(command):
    """지정된 쉘 명령어를 실행하고 결과를 반환합니다."""
    result = subprocess.run(
        command, 
        shell=True, # 명령어를 기본 쉘을 통해 실행하겠음
        capture_output=True, # 표준 출력(std_out) 및 에러(std_err)를 변수에 저장하겠음
        text=True # 사람이 읽을 수 있는 문자열 형태로 결과를 반환하겠음
    )
    return result

def test_containers_running():
    """앱과 데이터베이스 컨테이너가 정상적으로 실행 중인지 확인합니다."""
    # 앱 컨테이너 상태 확인
    res_app = run_command(f"docker inspect -f '{{{{.State.Running}}}}' accounting_app")
    assert res_app.returncode == 0 # 0이면 정상(에러 없음)
    # assert [조건], [에러 메시지]
    assert "true" in res_app.stdout.lower(), "accounting_app 컨테이너가 실행 중이 아닙니다."

    # DB 컨테이너 상태 확인
    res_db = run_command(f"docker inspect -f '{{{{.State.Running}}}}' {DB_NAME}")
    assert res_db.returncode == 0
    assert "true" in res_db.stdout.lower(), f"{DB_NAME} 컨테이너가 실행 중이 아닙니다."

def test_postgres_extensions_and_libraries():
    """PostgreSQL에서 age 라이브러리가 로드되었고, vector 및 age 확장이 생성되는지 확인합니다."""
    # 1. shared_preload_libraries 에 age 가 포함되어 있는지 확인
    res_preload = run_command(
        f"docker exec {DB_NAME} psql -U {DB_USER} -d {DB_NAME} -t -c 'SHOW shared_preload_libraries;'"
    )
    assert res_preload.returncode == 0
    assert "age" in res_preload.stdout, "shared_preload_libraries에 'age'가 로드되지 않았습니다."

    # 2. vector 확장 생성 확인
    res_vector = run_command(
        f"docker exec {DB_NAME} psql -U {DB_USER} -d {DB_NAME} -c 'CREATE EXTENSION IF NOT EXISTS vector;'"
    )
    assert res_vector.returncode == 0, "vector 확장 생성에 실패했습니다."

    # 3. age 확장 생성 확인
    res_age = run_command(
        f"docker exec {DB_NAME} psql -U {DB_USER} -d {DB_NAME} -c 'CREATE EXTENSION IF NOT EXISTS age;'"
    )
    assert res_age.returncode == 0, "age 확장 생성에 실패했습니다."

def test_app_environment():
    """app 컨테이너 내부에 파이썬 패키지들과 pytest가 실행 가능한지 검증합니다."""
    # 1. uv pip list 가 에러 없이 실행되는지 확인
    res_pip = run_command("docker exec accounting_app uv pip list")
    assert res_pip.returncode == 0, "uv pip list 명령어가 실패했습니다."

    # 2. pytest 명령어 확인
    res_pytest = run_command("docker exec accounting_app pytest --version")
    assert res_pytest.returncode == 0, "pytest 환경이 접근 불가능합니다."
    # pytest --version 결과는 stderr로 출력될 수도 있고 stdout일 수도 있음
    output = res_pytest.stdout.lower() + res_pytest.stderr.lower()
    assert "pytest" in output, "pytest 실행결과를 확인할 수 없습니다."
