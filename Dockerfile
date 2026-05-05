FROM python:3.12-slim

# [기본 환경 설정]
# PYTHONUNBUFFERED=1: 파이썬 출력을 버퍼링 없이 즉각적으로 콘솔에 출력하게 하여, 실시간 로그 확인을 용이하게 합니다.
    # 버퍼링이 있는 경우, 로그를 일정량 모았다가 출력하는데 성능은 더 좋으나 비정상적인 앱 종료 시 마지막 로그를 출력하지 못 하는 경우가 존재한다.
# PYTHONDONTWRITEBYTECODE=1: .pyc 파일(바이트코드)이 생성되는 것을 방지하여 컨테이너 이미지를 가볍게 유지합니다.
    # 파이썬은 .py를 실행하기 전에 컴퓨터가 더 빨리 읽을 수 있는 이진 파일인 .pyc로 변환하여 컴파일한다.
    # 컨테이너 환경에서는 이미지가 빌드된 후 코드를 고정하므로, 런타임 중 소스코드가 수정될 일이 없어서 굳이 .pyc를 생성할 필요가 없다.
# UV_COMPILE_BYTECODE=1: uv에서 패키지 설치 시 바이트코드를 미리 컴파일하여 초기 실행 속도를 높입니다.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1

# [PATH 경로 설정]
# uv sync가 생성하는 가상환경(.venv)의 실행 파일 폴더를 시스템 PATH 최상단에 추가합니다.
# 이 설정을 통해 'docker exec'으로 접속했을 때 별도의 activate 과정 없이도 pytest, black 등의 명령어를 즉시 사용할 수 있습니다.
ENV PATH="/app/.venv/bin:$PATH"

# [uv 설치]
# 공식 astral-sh/uv 이미지에서 바이너리를 복사해옵니다.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 작업 디렉토리를 /app으로 설정합니다. 이후의 모든 RUN, COPY, CMD 명령어는 이 디렉토리를 기준으로 실행됩니다.
WORKDIR /app

# [의존성 정의 파일 복사]
# 전체 소스 코드를 복사하기 전에 환경 파일만 먼저 복사하여 Docker의 레이어 캐싱 효과를 극대화합니다.
    # Docker는 Dockerfile의 각 줄을 실행할 때마다 그 결과를 저장한다. 이 저장된 결과를 레이어라고 부른다.
    # 레이어(여기서는 환경(의존성))가 변경되지 않으면 Docker는 이전 레이어를 재사용하여 이미지 빌드 속도를 높인다.
# 소스 코드가 자주 변경되더라도 PyPI 패키지 목록이 변경되지 않았다면, 시간이 오래 걸리는 설치 단계(RUN uv sync)를 캐시에서 바로 가져올 수 있습니다.
COPY pyproject.toml uv.lock ./

# [개발 환경을 포함한 완벽한 의존성 설치]
# --locked: pyproject.toml과 uv.lock이 일치하지 않는 경우, 빌드를 중단합니다. 다만, 개발 환경에서는 자주 의존성이 변경되므로 이를 적용하지 않았습니다. 
# !TODO: 운영 환경에서는 --locked을 적용해야 합니다.
# --all-extras: pyproject.toml에 정의된 모든 선택적 의존성 그룹을 확인하여 관련 패키지를 한 번에 설치합니다.
# --dev: 운영 프로덕션용 패키지뿐만 아니라, pytest와 같은 개발 전용 의존성, 린터, 테스트 도구 등을 명시적으로 전부 포함하여 테스트 환경을 구축합니다.
RUN uv sync --all-extras --dev

# [애플리케이션 소스 코드 복사]
# 개발 중에는 docker-compose.yml에서 내 PC의 로컬 폴더를 마운트(연결)하여 사용하지만,
# 배포 환경은 마운트 없이 해당 컨테이너 이미지가 단독 구동하기 때문에 정상 동작을 보장하기 위해 기본 폴더 구조를 복사해 스냅샷을 뜹니다.
COPY src/ ./src/
COPY test/ ./test/

# [컨테이너 대기 모드 프로세스]
# 컨테이너가 특정 단일 스크립트를 완료하고 바로 즉시 종료되는 것을 방지하고자 무한 대기 상태로 유지시킵니다.
# 1단계 목표에 맞춰, 개발자가 컨테이너 구동 직후 `docker exec` 명령어로 쉘에 접속하여 state.py, schemas.py 등의 코드를 반복 수정하고 pytest를 호출해 독립적으로 검증할 수 있는 최적의 워크플로우를 제공합니다.
CMD ["sleep", "infinity"]
