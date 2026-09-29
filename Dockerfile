# syntax 지시어는 Dockerfile 구문 해석기를 최신 BuildKit 사양(버전 1)으로 고정하여 고급 기능(캐시 마운트 등)을 활성화합니다.
# syntax=docker/dockerfile:1

# ==============================================================================
# 1단계: 프론트엔드 빌드 스테이지 (frontend-builder)
# React 기반 사용자 인터페이스 소스 코드를 컴파일하고 정적 파일 번들을 생성합니다.
# ==============================================================================
# Node.js 22 경량(slim) 이미지를 프론트엔드 전용 빌드 환경으로 지정합니다.
FROM node:22-slim AS frontend-builder

# 컨테이너 내부의 작업 디렉터리를 /frontend로 지정하고 이동합니다.
WORKDIR /frontend

# 의존성 명세 파일만 먼저 복사하여 소스 코드 변경 시 npm 설치 단계의 레이어 캐시를 최대한 활용합니다.
COPY frontend/package.json frontend/package-lock.json ./

# --mount=type=cache 옵션을 지정하여 npm 다운로드 캐시 디렉터리(/root/.npm)를 호스트 레벨에서 재사용합니다.
# npm ci 명령은 package-lock.json에 명시된 종속성을 정확하게 설치하여 재현 가능한 빌드를 보장합니다.
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# 프론트엔드 전체 소스 코드를 컨테이너 작업 디렉터리로 복사합니다.
COPY frontend/ ./

# Vite 또는 웹팩 기반의 프로덕션 번들 빌드를 실행하여 dist 디렉터리에 정적 결과물을 생성합니다.
RUN npm run build


# ==============================================================================
# 2단계: 백엔드 및 통합 프로덕션 애플리케이션 스테이지 (app)
# FastAPI 애플리케이션 및 정적 프론트엔드 서빙을 위한 최종 실행 환경을 구성합니다.
# ==============================================================================
# 파이썬 3.12 경량(slim) 공식 이미지를 기반으로 하여 컨테이너의 전체 용량을 최소화합니다.
FROM python:3.12-slim AS app

# 애플리케이션 런타임 환경 변수를 선언합니다:
# - PYTHONUNBUFFERED=1: 파이썬 표준 입출력 버퍼링을 비활성화하여 로그 출력이 지연 없이 즉각 수집되도록 설정합니다.
# - PYTHONDONTWRITEBYTECODE=1: 불필요한 .pyc 바이트코드 파일 생성을 방지하여 이미지 크기를 줄입니다.
# - UV_COMPILE_BYTECODE=1: uv 패키지 동기화 시 바이트코드를 사전에 컴파일하여 첫 실행 속도를 최적화합니다.
# - UV_LINK_MODE=copy: 가상 캐시 마운트 간 hardlink 생성 시 발생할 수 있는 크로스 디바이스 링크(EXDEV) 오류를 방지하기 위해 파일 복사 방식을 강제합니다.
# - PATH: 생성될 가상환경의 실행 파일 디렉터리(/app/.venv/bin)를 최우선 검색 경로로 등록합니다.
# - FRONTEND_DIST_DIR: FastAPI 정적 파일 마운트 지점으로 사용할 프론트엔드 번들 경로를 지정합니다.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    FRONTEND_DIST_DIR="/app/frontend/dist"

# 공식 uv 배포 이미지로부터 고속 파이썬 패키지 관리자 바이너리(uv, uvx)를 컨테이너의 /bin 경로로 직접 복사합니다.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 애플리케이션 실행 기준 디렉터리를 /app으로 설정합니다.
WORKDIR /app

# 패키지 명세 및 잠금 파일만 먼저 복사하여 소스 코드 수정 시 종속성 재설치를 방지하는 레이어 캐시를 구성합니다.
COPY pyproject.toml uv.lock ./

# --mount=type=cache 옵션으로 uv 패키지 캐시 디렉터리(/root/.cache/uv)를 마운트하여 의존성 재다운로드 비용을 절감합니다.
# --frozen 플래그로 uv.lock과의 일치성을 강제하고, --no-dev 옵션으로 프로덕션에 불필요한 개발 종속성을 배제합니다.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# 애플리케이션 백엔드 소스 코드를 /app/src 디렉터리로 복사합니다.
COPY src/ ./src/

# 원문 문서 인덱싱 및 로컬 파싱 작업에 사용될 필수 데이터 디렉터리를 미리 생성합니다.
RUN mkdir -p ./data/raw

# 1단계(frontend-builder)에서 빌드된 프론트엔드 정적 산출물을 /app/frontend/dist 경로로 복사합니다.
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# 애플리케이션 서버가 수신 대기할 네트워크 포트(8000)를 문서화하고 컨테이너 외부로 노출합니다.
EXPOSE 8000

# 컨테이너 시작 시 실행할 기본 프로세스로 uvicorn ASGI 웹 서버를 지정하고, 모든 네트워크 인터페이스(0.0.0.0)에서 8000번 포트로 대기하도록 설정합니다.
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]

