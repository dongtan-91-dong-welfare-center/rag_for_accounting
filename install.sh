#!/usr/bin/env bash
# 컨테이너화된 스택 빌드 및 실행:
# - database: PostgreSQL + pgvector
# - embedding: nlpai-lab/KURE-v1을 서빙하는 TEI
# - app: FastAPI API + 빌드된 React 프론트엔드 (8000번 포트)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# compose를 어느 명령으로 부를지는 환경마다 다르므로(Docker Compose v2인지 podman-compose인지),
# 판정을 공유 파일에 맡기고 그 결과인 COMPOSE·CONTAINER 배열만 아래에서 쓴다.
source "$ROOT/scripts/container_runtime.sh"
source "$ROOT/scripts/env_file.sh"

# command -v curl: 시스템의 $PATH 경로에서 curl 실행 파일이 존재하는지 확인하는 표준 셸 명령어
command -v curl >/dev/null 2>&1 || { echo "curl이 존재하지 않습니다. curl을 설치해주세요." >&2; exit 1; }
detect_container_runtime || { container_runtime_hint; exit 1; }
"${CONTAINER[@]}" info >/dev/null 2>&1 \
  || { echo "${CONTAINER[*]}가 설치되었으나 응답하지 않습니다. 실행한 다음 ./install.sh를 다시 실행해주세요." >&2; exit 1; }

if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env가 .env.example으로부터 생성되었습니다. OPENAI_API_KEY를 설정한 후 ./install.sh를 다시 실행해주세요." >&2
  exit 1
fi

# 아래의 헬스 체크가 스택이 실제로 오픈한 주소를 바라보도록 .env에서 호스트 포트를 읽어옵니다.
# 이 작업이 없으면, APP_HOST_PORT를 변경할 때 스택은 정상 동작하더라도 이 스크립트에서 실패로 보고하게 됩니다.
# 파일을 source하지 않고 필요한 값만 꺼내 오는 이유는 scripts/env_file.sh에 적어 두었습니다.
# 요약하면, 비밀번호에 흔히 들어가는 `$` 하나 때문에 컨테이너를 띄우기도 전에 이 스크립트가 죽습니다.
APP_HOST_PORT="${APP_HOST_PORT:-$(read_env APP_HOST_PORT)}"
EMBEDDING_HOST_PORT="${EMBEDDING_HOST_PORT:-$(read_env EMBEDDING_HOST_PORT)}"
DB_HOST_PORT="${DB_HOST_PORT:-$(read_env DB_HOST_PORT)}"
APP_URL="http://localhost:${APP_HOST_PORT:-8000}"
EMBEDDING_URL="http://localhost:${EMBEDDING_HOST_PORT:-8080}"

echo "[1/3] Building and starting containers"
# 런타임별 Compose 옵션 설정
# Docker: 기본 백그라운드 실행 및 재빌드
# Podman: podman-compose는 빌드 후 기존 컨테이너를 재사용하는 문제가 있어 --force-recreate를 필수로 추가
"${COMPOSE[@]}" up "${COMPOSE_UP_FLAGS[@]}"

echo "[2/3] Waiting for embedding and app servers"
echo "Waiting for embedding server. First KURE-v1 download can take several minutes."
for _ in $(seq 1 180); do
  if curl -fsS "$EMBEDDING_URL/health" >/dev/null 2>&1; then
    break
  fi
  sleep 5
done
curl -fsS "$EMBEDDING_URL/health" >/dev/null 2>&1 \
  || { echo "임베딩 서버가 준비되지 않았습니다. 확인: ${COMPOSE[*]} logs embedding" >&2; exit 1; }

for _ in $(seq 1 60); do
  if curl -fsS "$APP_URL/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS "$APP_URL/health" >/dev/null 2>&1 \
  || { echo "앱 서버가 준비되지 않았습니다. 확인: ${COMPOSE[*]} logs app" >&2; exit 1; }

echo "[3/3] Stack is running"
echo "  App/API   : $APP_URL"
echo "  API docs  : $APP_URL/docs"
echo "  Embedding : $EMBEDDING_URL"
echo "  DB        : localhost:${DB_HOST_PORT:-5432}"
echo
echo "Useful commands:"
echo "  ./check.sh"
echo "  ${COMPOSE[*]} logs -f app"
echo "  ${COMPOSE[*]} down"
