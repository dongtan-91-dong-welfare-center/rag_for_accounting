#!/usr/bin/env bash
# Read-only stack check. Start services with ./install.sh first.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# compose를 어느 명령으로 부를지는 환경마다 다르므로(Docker Compose v2인지 podman-compose인지),
# 판정을 공유 파일에 맡기고 그 결과인 COMPOSE·CONTAINER 배열만 아래에서 씁니다.
source "$ROOT/scripts/container_runtime.sh"
source "$ROOT/scripts/env_file.sh"

# 아래 체크들이 스택이 실제로 오픈한 DB 계정과 호스트 포트를 사용하도록 .env 파일에서 값을 읽어옵니다.
# 이 과정이 없으면, 사용자가 POSTGRES_USER나 APP_HOST_PORT를 변경했을 때
# 스택은 정상인데 이 스크립트에서만 실패로 보고되는 상황이 발생합니다.
# 파일을 source하지 않고 필요한 값만 꺼내 오는 이유는 scripts/env_file.sh에 적어 두었습니다.
# 요약하면, 비밀번호에 `$`가 하나 들어 있으면 이 스크립트가 점검 결과를 한 줄도 못 내고 죽습니다.
APP_HOST_PORT="${APP_HOST_PORT:-$(read_env APP_HOST_PORT)}"
EMBEDDING_HOST_PORT="${EMBEDDING_HOST_PORT:-$(read_env EMBEDDING_HOST_PORT)}"
POSTGRES_USER="${POSTGRES_USER:-$(read_env POSTGRES_USER)}"
POSTGRES_DB="${POSTGRES_DB:-$(read_env POSTGRES_DB)}"
APP_URL="http://localhost:${APP_HOST_PORT:-8000}"
EMBEDDING_URL="http://localhost:${EMBEDDING_HOST_PORT:-8080}"

FAIL=0
pass() { printf "  [PASS] %s\n" "$1"; }
fail() { printf "  [FAIL] %s\n" "$1"; FAIL=1; }
warn() { printf "  [WARN] %s\n" "$1"; }

echo "-- 1. Required tools"
# command -v curl: 시스템에 curl 실행 파일이 존재하는지 확인합니다.
# >/dev/null 2>&1: 표준 출력과 에러 메시지를 모두 버려 화면을 깨끗하게 유지합니다.
# && pass ... || fail ...:
  # 성공하면(설치되어 있으면) pass "curl" 실행
  # 실패하면(없으면) fail "curl missing" 실행
command -v curl >/dev/null 2>&1 && pass "curl" || fail "curl missing"
if detect_container_runtime; then
  pass "compose command: ${COMPOSE[*]}"
else
  fail "compose가 지원하는 런타임이 설치되어 있지 않습니다. docker, podman, orbstack 설치 후 다시 시도하세요."
  container_runtime_hint
# fi: if 문이 종료되었음을 선언하는 명령어
fi
# "${CONTAINER[@]}" (실행할 때): 배열의 각 요소를 독립된 인자로 보존하여 안전하게 명령어로 실행합니다.
# "${CONTAINER[*]}" (출력할 때): 배열의 모든 요소를 하나의 문자열로 합쳐 화면에 깔끔하게 보여줄 때 씁니다.
"${CONTAINER[@]}" info >/dev/null 2>&1 \
  && pass "${CONTAINER[*]} 가 반응하고 있습니다." \
  || fail "${CONTAINER[*]} 가 반응하지 않습니다."

echo "-- 2. Environment"
if [ -f .env ]; then
  pass ".env 파일이 존재합니다."
  if grep -q "^OPENAI_API_KEY=sk-your-key-here" .env || ! grep -q "^OPENAI_API_KEY=" .env; then
    warn "OPENAI_API_KEY가 없거나 플레이스홀더 상태입니다."
  else
    pass "OPENAI_API_KEY가 설정되었습니다."
  fi
else
  fail ".env 파일이 존재하지 않습니다."
fi

echo "-- 3. Containers"
for name in accounting_db accounting_embedding accounting_app; do
  # inspect: 특정 컨테이너의 모든 세부 정보를 JSON 형태로 가져오는 명령어입니다.
  # -f '{{.State.Status}}': 세부 정보 전체를 다 보지 않고, 상태값(예: running, exited, paused 등) 딱 하나만 콕 집어서 뽑아내는 포맷 필터 옵션입니다.
  # "$name": 상태를 확인할 대상 컨테이너의 이름(또는 ID)입니다.
  # 2>/dev/null: 에러가 발생해도 화면에 출력하지 않습니다.
  # || echo missing: 만약 컨테이너를 찾지 못해 에러가 나면 missing 이라는 단어를 대신 출력합니다.
  # || (OR 연산자): 앞선 명령어가 실패했을 때만 뒤쪽 명령어를 실행합니다. 
  # 컨테이너가 없어서 inspect가 실패하면, 대신 echo missing을 실행해 문자열 "missing"을 뱉어냅니다.
  # status="$( ... )": 괄호 안의 전체 실행 결과를 변수 status에 저장합니다.
  status="$("${CONTAINER[@]}" inspect -f '{{.State.Status}}' "$name" 2>/dev/null || echo missing)"
  [ "$status" = "running" ] && pass "$name running" || fail "$name: $status"
done

echo "-- 4. Services"
# compose의 exec(서비스 이름 database)이 아니라 런타임의 exec(컨테이너 이름 accounting_db)을 쓴다.
# compose 쪽 exec은 구현체마다 옵션 지원이 갈리는 반면
# 컨테이너 이름은 compose 파일이 container_name으로 고정해 두었고 exec은 Docker와 Podman에서 같은 형태로 동작한다.
# 바로 위 3번 항목도 이미 같은 이름으로 컨테이너를 확인하고 있다.
# pg_isready: PostgreSQL 공식 유틸리티로, DB 서버가 연결 가능한 상태인지 가볍게 찔러보고 성공(0) 또는 실패(0 아님) 코드를 즉시 반환합니다.
# ${POSTGRES_USER:-accounting_user}: POSTGRES_USER 환경 변수가 설정되어 있으면 그 값을 사용하고, 비어 있거나 정의되지 않았다면 기본값으로 accounting_user를 대신 사용
if "${CONTAINER[@]}" exec accounting_db pg_isready -U "${POSTGRES_USER:-accounting_user}" >/dev/null 2>&1; then
  # exec은 컨테이너 안에서 유닉스 소켓으로 물어보므로, 호스트에 열린 포트를 확인한 것이 아니다.
  # 그래서 "localhost:5432가 응답한다"고 적으면 확인하지 않은 것을 확인했다고 말하는 셈이 된다.
  pass "PostgreSQL는 연결 가능한 상태입니다."
  # psql -U ... -d ... 실행은 "지정한 사용자 계정과 데이터베이스 이름으로 실제 SQL 쿼리를 날릴 수 있는 인증/권한 상태인지" 한 단계 더 깊게 검증
  if "${CONTAINER[@]}" exec accounting_db psql -U "${POSTGRES_USER:-accounting_user}" -d "${POSTGRES_DB:-accounting_db}" \
      -tAc "SELECT 1 FROM pg_available_extensions WHERE name='vector'" 2>/dev/null | grep -q 1; then
    pass "pgvector extension이 사용 가능합니다."
  else
    fail "pgvector extension이 사용 불가능합니다."
  fi
else
  fail "PostgreSQL는 연결 가능한 상태가 아닙니다."
fi

if curl -fsS "$EMBEDDING_URL/health" >/dev/null 2>&1; then
  pass "embedding server는 연결 가능한 상태입니다."
else
  warn "embedding server는 연결 가능한 상태가 아닙니다. 처음 KURE-v1 다운로드에는 몇 분 정도 걸릴 수 있습니다."
fi

if curl -fsS "$APP_URL/health" >/dev/null 2>&1; then
  pass "app health endpoint는 ${APP_URL#http://}에서 연결 가능한 상태입니다."
else
  fail "app health endpoint는 ${APP_URL#http://}에서 연결 가능한 상태가 아닙니다."
fi

if curl -fsS "$APP_URL/" >/dev/null 2>&1; then
  pass "React frontend는 app 컨테이너에서 제공됩니다."
else
  fail "React frontend는 app 컨테이너에서 제공되지 않습니다."
fi

echo
if [ "$FAIL" -eq 0 ]; then
  echo "확인 완료: 심각한 문제는 발견되지 않았습니다"
else
  echo "확인 완료: 심각한 문제가 발견되었습니다"
  exit 1
fi
