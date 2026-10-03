"""
Docker 인프라 동작 검증 유틸리티

Docker 컨테이너 실행 상태, PostgreSQL 확장(pgvector)을 검증합니다.
통합 테스트 실행 전에 이 함수를 호출하여 인프라를 가드합니다.
"""
import os
import subprocess

# src.agent.workflow를 임포트하면 그 안에서 config.py가 전이적으로 로드되고,config.py 최상단의 load_dotenv() 호출로 .env가 읽힌다.
# 그래서 이 파일은 별도 로드 없이 os.getenv()를 바로 쓸 수 있다.
DB_CONTAINER_NAME = os.getenv("POSTGRES_CONTAINER_NAME", "accounting_db")
DB_NAME = os.getenv("POSTGRES_DB", "accounting_db")
DB_USER = os.getenv("POSTGRES_USER", "accounting_user")

def run_command(command):
    """지정된 쉘 명령어를 실행하고 결과를 반환합니다."""
    return subprocess.run(command, shell=True, capture_output=True, text=True)

def check_docker_infrastructure(
    require_app: bool = False,
    db_container_name: str | None = None,
    db_name: str | None = None,
    db_user: str | None = None,
) -> str | None:
    """
    1. Docker 데몬 실행 여부
    2. accounting_app 컨테이너 구동 상태 (require_app=True 일 때만)
    3. DB 컨테이너 구동 상태
    4. PostgreSQL 확장(vector) 로드 상태
    를 점검하고, 실패 사유를 반환합니다. 정상이면 None을 반환
    """
    container_name = db_container_name or os.getenv("POSTGRES_CONTAINER_NAME", "accounting_db")
    database_name = db_name or os.getenv("POSTGRES_DB", "accounting_db")
    database_user = db_user or os.getenv("POSTGRES_USER", "accounting_user")

    try:
        res_info = subprocess.run("docker version", shell=True, capture_output=True, text=True, timeout=15)
        if res_info.returncode != 0:
            return "Docker 데몬이 실행 중이지 않습니다."
    except Exception as e:
        return f"Docker 실행 점검 중 에러 발생: {e}"

    if require_app:
        # docker inspect -f '{{.State.Running}}':
        # -f(--format) 플래그는 Docker의 Go 템플릿(Go template) 문법을 사용합니다.
        # 컨테이너 전체 메타데이터 JSON을 파싱하지 않고 .State.Running 필드의 불리언 상태값('true' 또는 'false')만 표준 출력으로 직접 추출합니다.
        res_app = run_command("docker inspect -f '{{.State.Running}}' accounting_app")
        if res_app.returncode != 0 or "true" not in res_app.stdout.lower():
            return "accounting_app 컨테이너가 실행 중이 아닙니다."

    # 파이썬 f-string 환경에서는 중괄호({, })를 리터럴로 표현하기 위해 이스케이프({{, }})가 필요하므로
    # 셸에 '{{.State.Running}}' 문자열을 온전히 전달하기 위해 '{{{{.State.Running}}}}' 형태로 작성합니다.
    res_db = run_command(f"docker inspect -f '{{{{.State.Running}}}}' {container_name}")
    if res_db.returncode != 0 or "true" not in res_db.stdout.lower():
        return f"{container_name} 컨테이너가 실행 중이 아닙니다."

    res_vector = run_command(f'docker exec {container_name} psql -U {database_user} -d {database_name} -c "CREATE EXTENSION IF NOT EXISTS vector;"')
    if res_vector.returncode != 0:
        return "vector 확장 생성/조회에 실패했습니다."

    return None
