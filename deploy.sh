#!/usr/bin/env bash
# app 컨테이너(FastAPI 및 빌드된 React 프론트엔드) 증분 빌드 및 교체 배포:
# - database(PostgreSQL) 및 embedding(TEI KURE-v1) 컨테이너는 가동 상태를 유지합니다.
# - 정적 인프라가 재기동되지 않으므로 TEI 웜업(2~3분) 대기가 생략되어 10초 내외로 배포됩니다.
# - 초기 설치 및 인프라 변경 시에는 ./install.sh를 사용하세요.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

source "$ROOT/scripts/container_runtime.sh"
source "$ROOT/scripts/env_file.sh"

# CLI 인자 파싱
build_args=()
for arg in "$@"; do
  case "$arg" in
    -h|--help)
      echo "사용법: $0 [--no-cache]"
      echo "  app 컨테이너(FastAPI 및 프론트엔드)만 단독으로 재빌드하고 교체 배포합니다."
      echo "  database 및 embedding 컨테이너를 재시작하지 않아 TEI 웜업 대기 없이 빠르게 배포됩니다."
      echo "  --no-cache: Docker 빌드 캐시를 사용하지 않고 app 이미지를 클린 재빌드합니다."
      echo "  초기 전체 설치 또는 인프라 설정 변경 시에는 ./install.sh를 사용하세요."
      exit 0
      ;;
    --no-cache)
      build_args+=(--no-cache)
      ;;
    *)
      echo "오류: 알 수 없는 인자 '$arg'" >&2
      echo "사용법: $0 [--no-cache]" >&2
      exit 1
      ;;
  esac
done

command -v curl >/dev/null 2>&1 || { echo "curl이 존재하지 않습니다. curl을 설치해주세요." >&2; exit 1; }
detect_container_runtime || { container_runtime_hint; exit 1; }
"${CONTAINER[@]}" info >/dev/null 2>&1 \
  || { echo "${CONTAINER[*]}가 설치되었으나 응답하지 않습니다. 실행한 다음 ./deploy.sh를 다시 실행해주세요." >&2; exit 1; }

if [ ! -f .env ]; then
  echo "오류: .env 파일이 존재하지 않습니다. ./install.sh를 먼저 실행하여 환경을 구성해주세요." >&2
  exit 1
fi

APP_HOST_PORT="${APP_HOST_PORT:-$(read_env APP_HOST_PORT)}"
EMBEDDING_HOST_PORT="${EMBEDDING_HOST_PORT:-$(read_env EMBEDDING_HOST_PORT)}"
APP_URL="http://localhost:${APP_HOST_PORT:-8000}"
EMBEDDING_URL="http://localhost:${EMBEDDING_HOST_PORT:-8080}"

# 정적 인프라 사전 검증: database 및 embedding 상태 확인
DB_CONTAINER="${POSTGRES_CONTAINER:-accounting_db}"
EMBEDDING_CONTAINER="accounting_embedding"

for dep in "$DB_CONTAINER" "$EMBEDDING_CONTAINER"; do
  status="$("${CONTAINER[@]}" inspect -f '{{.State.Status}}' "$dep" 2>/dev/null || echo missing)"
  if [ "$status" != "running" ]; then
    echo "오류: 필수 인프라 컨테이너($dep)가 실행 중이지 않습니다 (상태: $status)." >&2
    echo "초기 기동 또는 인프라 재기동을 위해 ./install.sh를 먼저 실행해주세요." >&2
    exit 1
  fi
done

if ! curl -fsS "$EMBEDDING_URL/health" >/dev/null 2>&1; then
  echo "오류: 임베딩 서버($EMBEDDING_URL)가 정상 응답하지 않습니다." >&2
  echo "TEI 웜업이 완료될 때까지 대기하거나 ./install.sh를 통해 스택 상태를 확인해주세요." >&2
  exit 1
fi

echo "[1/3] Building app container"
"${COMPOSE[@]}" build ${build_args[@]+"${build_args[@]}"} app

echo "[2/3] Recreating app container"
"${COMPOSE[@]}" up "${COMPOSE_DEPLOY_FLAGS[@]}" app

echo "[3/3] Waiting for app server to be ready"
APP_READY=0
for _ in $(seq 1 60); do
  if curl -fsS "$APP_URL/health" >/dev/null 2>&1; then
    APP_READY=1
    break
  fi
  sleep 2
done

if [ "$APP_READY" -ne 1 ]; then
  echo "오류: 앱 서버가 준비되지 않았습니다." >&2
  echo "--- 최근 app 컨테이너 로그 (최대 50줄) ---" >&2
  "${COMPOSE[@]}" logs --tail=50 app >&2 || true
  echo "----------------------------------------" >&2
  echo "확인: ${COMPOSE[*]} logs app" >&2
  exit 1
fi

echo "배포 완료: app 컨테이너가 성공적으로 갱신되었습니다."
echo "  App/API   : $APP_URL"
echo "  API docs  : $APP_URL/docs"
echo
echo "Useful commands:"
echo "  ./check.sh"
echo "  ${COMPOSE[*]} logs -f app"
