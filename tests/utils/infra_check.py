"""
Docker 인프라 동작 검증 유틸리티

Docker 컨테이너 실행 상태, PostgreSQL 확장(pgvector/AGE)을 검증합니다.
통합 테스트 실행 전에 이 함수를 호출하여 인프라를 가드합니다.
"""
import os
import subprocess

# tests/conftest.py에서 load_dotenv()로 .env를 로드했기 때문에 사용 가능
DB_NAME = os.getenv("POSTGRES_DB", "accounting_db")
DB_USER = os.getenv("POSTGRES_USER", "accounting_user")

def run_command(command):
    """지정된 쉘 명령어를 실행하고 결과를 반환합니다."""
    return subprocess.run(command, shell=True, capture_output=True, text=True)

def check_docker_infrastructure():
    """
    1. Docker 데몬 실행 여부
    2. accounting_app 컨테이너 구동 상태
    3. DB 컨테이너 구동 상태
    4. PostgreSQL 확장(age, vector) 로드 상태
    를 점검하고, 실패 사유를 반환합니다. 정상이면 None을 반환
    """
    try:
        res_info = subprocess.run("docker info", shell=True, capture_output=True, text=True, timeout=5)
        if res_info.returncode != 0:
            return "Docker 데몬이 실행 중이지 않습니다."
    except Exception as e:
        return f"Docker 실행 점검 중 에러 발생: {e}"

    res_app = run_command(f"docker inspect -f '{{{{.State.Running}}}}' accounting_app")
    if res_app.returncode != 0 or "true" not in res_app.stdout.lower():
        return "accounting_app 컨테이너가 실행 중이 아닙니다."

    res_db = run_command(f"docker inspect -f '{{{{.State.Running}}}}' {DB_NAME}")
    if res_db.returncode != 0 or "true" not in res_db.stdout.lower():
        return f"{DB_NAME} 컨테이너가 실행 중이 아닙니다."

    res_preload = run_command(
        f"docker exec {DB_NAME} psql -U {DB_USER} -d {DB_NAME} -t -c 'SHOW shared_preload_libraries;'"
    )
    if res_preload.returncode != 0 or "age" not in res_preload.stdout:
        return "shared_preload_libraries에 'age'가 로드되지 않았습니다."

    res_vector = run_command(f"docker exec {DB_NAME} psql -U {DB_USER} -d {DB_NAME} -c 'CREATE EXTENSION IF NOT EXISTS vector;'")
    if res_vector.returncode != 0:
        return "vector 확장 생성/조회에 실패했습니다."

    res_age = run_command(f"docker exec {DB_NAME} psql -U {DB_USER} -d {DB_NAME} -c 'CREATE EXTENSION IF NOT EXISTS age;'")
    if res_age.returncode != 0:
        return "age 확장 생성/조회에 실패했습니다."

    return None
