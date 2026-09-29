#!/usr/bin/env bash
# ==============================================================================
# deploy.sh: app 서비스(FastAPI 백엔드 및 React 프론트엔드) 증분 빌드 및 무중단 교체 배포 스크립트
#
# [동작 배경 및 목적]
# - 본 스크립트는 소스 코드 수정 후 재배포 시 정적 인프라(PostgreSQL, TEI 임베딩)의 재기동을 방지합니다.
# - database 및 embedding 컨테이너를 재생성하지 않으므로, 수 분이 소요되는 TEI 모델 웜업 대기 시간을
#   완전히 제거하여 전체 배포 소요 시간을 10초 내외로 단축합니다.
# - 초기 전체 스택 기동 또는 인프라 설정 변경 시에는 반드시 ./install.sh를 실행해야 합니다.
# ==============================================================================

# 엄격한 오류 제어 모드를 설정합니다:
# -e: 명령어가 0이 아닌 종료 코드를 반환하면 즉각 스크립트를 중단합니다.
# -u: 초기화되지 않은 변수를 참조할 경우 오류를 발생시키고 중단합니다.
# -o pipefail: 파이프라인(|) 내 어느 한 명령어라도 실패하면 전체 명령어가 실패로 처리됩니다.
set -euo pipefail

# 배포 작업 도중 사용자 중단(Ctrl+C, SIGINT) 또는 종료 신호(SIGTERM) 수신 시 안내 메시지를 출력하는 안전 트랩을 등록합니다.
trap 'echo -e "\n경고: 사용자에 의해 배포 작업이 중단되었습니다. 현재 실행 상태를 점검하려면 ./check.sh를 실행하세요." >&2; exit 130' INT TERM

# 스크립트 파일이 위치한 디렉터리의 절대 경로를 계산하여 변수에 저장합니다.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 현재 작업 디렉터리를 프로젝트 루트로 변경하여 상대 경로 참조의 일관성을 보장합니다.
cd "$ROOT"

# 컨테이너 런타임 추상화 모듈(Docker/Podman 자동 감지)을 로드합니다.
source "$ROOT/scripts/container_runtime.sh"
# 안전한 환경 변수 파싱 모듈(source 대신 정규식 기반 키 추출)을 로드합니다.
source "$ROOT/scripts/env_file.sh"

# ==============================================================================
# [1] CLI 인자 파싱
# ==============================================================================
# docker build 명령어에 전달할 추가 플래그 배열을 초기화합니다.
build_args=()

# 명령줄로 전달된 모든 인자($@)를 순회하며 유효성을 검사합니다.
for arg in "$@"; do
  case "$arg" in
    # 도움말 플래그(-h, --help) 입력 시 사용법을 상세히 안내하고 정상 종료합니다.
    -h|--help)
      echo "사용법: $0 [--no-cache]"
      echo "  app 컨테이너(FastAPI 및 프론트엔드)만 단독으로 재빌드하고 교체 배포합니다."
      echo "  database 및 embedding 컨테이너를 재시작하지 않아 TEI 웜업 대기 없이 빠르게 배포됩니다."
      echo "  --no-cache: Docker 빌드 캐시를 사용하지 않고 app 이미지를 클린 재빌드합니다."
      echo "  초기 전체 설치 또는 인프라 설정 변경 시에는 ./install.sh를 사용하세요."
      exit 0
      ;;
    # --no-cache 플래그 전달 시 캐시 없이 클린 빌드하도록 빌드 인자 배열에 추가합니다.
    --no-cache)
      build_args+=(--no-cache)
      ;;
    # 정의되지 않은 미지원 인자가 들어올 경우 오류 메시지를 출력하고 비정상 종료(exit 1)합니다.
    *)
      echo "오류: 알 수 없는 인자 '$arg'" >&2
      echo "사용법: $0 [--no-cache]" >&2
      exit 1
      ;;
  esac
done

# ==============================================================================
# [2] 사전 요구사항 점검 (Pre-flight Checks)
# ==============================================================================
# 헬스체크 및 HTTP 통신을 수행할 curl 바이너리의 설치 여부를 검증합니다.
command -v curl >/dev/null 2>&1 || { echo "curl이 존재하지 않습니다. curl을 설치해주세요." >&2; exit 1; }

# 컨테이너 런타임(Docker Compose v2 또는 Podman Compose)을 감지하고 전역 배열(COMPOSE, CONTAINER)을 초기화합니다.
detect_container_runtime || { container_runtime_hint; exit 1; }

# 감지된 컨테이너 런타임 데몬이 실제로 동작 중인지 info 하위 명령으로 확인합니다.
"${CONTAINER[@]}" info >/dev/null 2>&1 \
  || { echo "${CONTAINER[*]}가 설치되었으나 응답하지 않습니다. 실행한 다음 ./deploy.sh를 다시 실행해주세요." >&2; exit 1; }

# .env 환경 설정 파일이 프로젝트 루트에 존재하는지 점검합니다.
if [ ! -f .env ]; then
  echo "오류: .env 파일이 존재하지 않습니다. ./install.sh를 먼저 실행하여 환경을 구성해주세요." >&2
  exit 1
fi

# ==============================================================================
# [3] 네트워크 포트 및 서비스 엔드포인트 URL 산출
# ==============================================================================
# 현재 환경 변수 또는 .env 파일에서 호스트 포트를 안전하게 읽어오며, 누락 시 기본값을 할당합니다.
APP_HOST_PORT="${APP_HOST_PORT:-$(read_env APP_HOST_PORT)}"
EMBEDDING_HOST_PORT="${EMBEDDING_HOST_PORT:-$(read_env EMBEDDING_HOST_PORT)}"

# 점검 대상 서비스 엔드포인트 URL을 구성합니다.
# 주의(Minor 3): .env에서 APP_BIND_ADDR을 127.0.0.1 이외의 특정 사설 IP로 엄격히 제한한 경우,
# localhost를 통한 헬스체크가 인터페이스 정책에 따라 제한될 수 있으므로 기본 루프백 주소를 사용합니다.
APP_URL="http://localhost:${APP_HOST_PORT:-8000}"
EMBEDDING_URL="http://localhost:${EMBEDDING_HOST_PORT:-8080}"

# ==============================================================================
# [4] 정적 인프라 컨테이너 사전 가동 상태 검증
# ==============================================================================
# 데이터베이스 및 임베딩 컨테이너의 이름을 결정합니다 (환경 변수 오버라이드 지원 대칭화).
DB_CONTAINER="${POSTGRES_CONTAINER:-accounting_db}"
EMBEDDING_CONTAINER="${EMBEDDING_CONTAINER:-accounting_embedding}"

# 필수 인프라 컨테이너가 running 상태인지 inspect 명령어로 하나씩 검사합니다.
for dep in "$DB_CONTAINER" "$EMBEDDING_CONTAINER"; do
  status="$("${CONTAINER[@]}" inspect -f '{{.State.Status}}' "$dep" 2>/dev/null || echo missing)"
  if [ "$status" != "running" ]; then
    echo "오류: 필수 인프라 컨테이너($dep)가 실행 중이지 않습니다 (상태: $status)." >&2
    echo "초기 기동 또는 인프라 재기동을 위해 ./install.sh를 먼저 실행해주세요." >&2
    exit 1
  fi
done

# 임베딩 서버(TEI)의 모델 웜업이 완료되었는지 헬스체크 엔드포인트를 호출하여 검증합니다.
# 소켓 블로킹 및 무한 대기를 방지하기 위해 연결 타임아웃 2초, 최대 전송 시간 5초를 지정합니다.
if ! curl -fsS --connect-timeout 2 --max-time 5 "$EMBEDDING_URL/health" >/dev/null 2>&1; then
  echo "오류: 임베딩 서버($EMBEDDING_URL)가 정상 응답하지 않습니다." >&2
  echo "TEI 웜업이 완료될 때까지 대기하거나 ./install.sh를 통해 스택 상태를 확인해주세요." >&2
  exit 1
fi

# ==============================================================================
# [5] app 서비스 증분 빌드 및 컨테이너 교체
# ==============================================================================
# 1단계: app 컨테이너 이미지만 단독으로 빌드합니다.
# Bash 3.2 호환성: build_args 배열이 비어있을 때 발생하는 unbound variable 오류를 방지하기 위해 ${build_args[@]+"${build_args[@]}"} 구문을 사용합니다.
echo "[1/3] Building app container"
"${COMPOSE[@]}" build ${build_args[@]+"${build_args[@]}"} app

# 2단계: 기존 app 컨테이너를 새로운 이미지로 교체 기동합니다.
# COMPOSE_DEPLOY_FLAGS는 런타임에 따라 Docker는 (-d --no-deps), Podman은 (-d --force-recreate --no-deps)가 전달됩니다.
# --no-deps 옵션을 통해 연관 서비스(database, embedding)의 불필요한 재기동을 차단합니다.
echo "[2/3] Recreating app container"
"${COMPOSE[@]}" up "${COMPOSE_DEPLOY_FLAGS[@]}" app

# ==============================================================================
# [6] 앱 서버 가동 준비 상태 대기 (Health Check Polling)
# ==============================================================================
echo "[3/3] Waiting for app server to be ready"
APP_READY=0

# 최대 120초(60회 x 2초) 동안 앱 서버의 /health 엔드포인트를 주기적으로 호출하여 응답을 확인합니다.
# curl 호출 시 교착 상태를 예방하기 위해 연결 타임아웃 2초, 최대 응답 시간 5초를 명시합니다.
for _ in $(seq 1 60); do
  if curl -fsS --connect-timeout 2 --max-time 5 "$APP_URL/health" >/dev/null 2>&1; then
    APP_READY=1
    break
  fi
  sleep 2
done

# 지정된 제한 시간 내에 앱 서버가 정상 응답하지 않으면 최근 로그를 출력하고 비정상 종료합니다.
if [ "$APP_READY" -ne 1 ]; then
  echo "오류: 앱 서버가 준비되지 않았습니다." >&2
  echo "--- 최근 app 컨테이너 로그 (최대 50줄) ---" >&2
  # 최근 50줄의 로그를 표준 에러로 출력하여 실패 원인을 즉시 파악할 수 있도록 돕습니다.
  "${COMPOSE[@]}" logs --tail=50 app >&2 || true
  echo "----------------------------------------" >&2
  echo "확인: ${COMPOSE[*]} logs app" >&2
  exit 1
fi

# ==============================================================================
# [7] 배포 완료 안내
# ==============================================================================
echo "배포 완료: app 컨테이너가 성공적으로 갱신되었습니다."
echo "  App/API   : $APP_URL"
echo "  API docs  : $APP_URL/docs"
echo
echo "Useful commands:"
echo "  ./check.sh"
echo "  ${COMPOSE[*]} logs -f app"

