#!/usr/bin/env bash
# Read-only stack check. Start services with ./install.sh or docker compose up -d.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# 아래 체크들이 스택이 실제로 오픈한 DB 계정과 호스트 포트를 사용하도록 .env 파일을 읽어옵니다.
# 이 과정이 없으면, 사용자가 POSTGRES_USER나 APP_HOST_PORT를 변경했을 때
# 스택은 정상인데 이 스크립트에서만 실패로 보고되는 상황이 발생합니다.
[ -f .env ] && { set -a && source .env && set +a; }
APP_URL="http://localhost:${APP_HOST_PORT:-8000}"
EMBEDDING_URL="http://localhost:${EMBEDDING_HOST_PORT:-8080}"

FAIL=0
pass() { printf "  [PASS] %s\n" "$1"; }
fail() { printf "  [FAIL] %s\n" "$1"; FAIL=1; }
warn() { printf "  [WARN] %s\n" "$1"; }

echo "-- 1. Required tools"
for tool in docker curl; do
  command -v "$tool" >/dev/null 2>&1 && pass "$tool" || fail "$tool missing"
done
docker info >/dev/null 2>&1 && pass "Docker daemon" || fail "Docker daemon is not running"

echo "-- 2. Environment"
if [ -f .env ]; then
  pass ".env exists"
  if grep -q "^OPENAI_API_KEY=sk-your-key-here" .env || ! grep -q "^OPENAI_API_KEY=" .env; then
    warn "OPENAI_API_KEY is missing or still a placeholder"
  else
    pass "OPENAI_API_KEY is set"
  fi
else
  fail ".env missing"
fi

echo "-- 3. Containers"
for name in accounting_db accounting_embedding accounting_app; do
  status="$(docker inspect -f '{{.State.Status}}' "$name" 2>/dev/null || echo missing)"
  [ "$status" = "running" ] && pass "$name running" || fail "$name: $status"
done

echo "-- 4. Services"
if docker compose exec -T database pg_isready -U "${POSTGRES_USER:-accounting_user}" >/dev/null 2>&1; then
  pass "PostgreSQL responds on localhost:${DB_HOST_PORT:-5432}"
  if docker compose exec -T database psql -U "${POSTGRES_USER:-accounting_user}" -d "${POSTGRES_DB:-accounting_db}" \
      -tAc "SELECT 1 FROM pg_available_extensions WHERE name='vector'" 2>/dev/null | grep -q 1; then
    pass "pgvector extension is available"
  else
    fail "pgvector extension is not available"
  fi
else
  fail "PostgreSQL is not ready"
fi

if curl -fsS "$EMBEDDING_URL/health" >/dev/null 2>&1; then
  pass "embedding server responds on ${EMBEDDING_URL#http://}"
else
  warn "embedding server is not healthy yet; first KURE-v1 download can take several minutes"
fi

if curl -fsS "$APP_URL/health" >/dev/null 2>&1; then
  pass "app health endpoint responds on ${APP_URL#http://}"
else
  fail "app health endpoint is not responding"
fi

if curl -fsS "$APP_URL/" >/dev/null 2>&1; then
  pass "React frontend is served by app container"
else
  fail "React frontend is not served by app container"
fi

echo
if [ "$FAIL" -eq 0 ]; then
  echo "Check complete: no blocking failures"
else
  echo "Check complete: failures found"
  exit 1
fi
