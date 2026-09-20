#!/usr/bin/env bash
# db_dump.sh로 만든 백업 파일을 accounting_db 컨테이너에 복원한다.
#
# [복원 특징]
# - --clean --if-exists: 기존 테이블이 있으면 지우고 새로 만든다(멱등 복원).
# - --no-owner --no-privileges: 원본과 POSTGRES_USER가 달라도 소유권 불일치로 실패하지 않게 한다.
# - TOC 필터(-L): 개발 DB 카탈로그에 남아있는 Apache AGE 잔재(CREATE EXTENSION age 등) 및
#   실험용 테이블을 목록에서 걸러내어, 새 서버(AGE 미설치)에서도 오류 없이 종료 코드 0으로 복원된다.
# - 복원 후 검증: chunks 테이블 행 수를 조회하여 0건이거나 기대값과 다르면 실패로 보고한다.
#
# 사용법: ./db_restore.sh <덤프파일경로> [기대청크수]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

source "$ROOT/scripts/container_runtime.sh"
source "$ROOT/scripts/env_file.sh"

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ $# -lt 1 ]; then
  echo "사용법: $0 <덤프파일경로> [기대청크수]"
  echo "  덤프파일: 필수, pg_dump 커스텀 포맷(-Fc) 아카이브 파일"
  echo "  기대청크수: 선택, 미지정 시 .meta 파일 또는 EXPECTED_CHUNKS 환경변수를 확인합니다."
  exit $( [ $# -lt 1 ] && echo 1 || echo 0 )
fi

DUMP="$1"
EXPECTED_CHUNKS="${2:-${EXPECTED_CHUNKS:-}}"

# 사이드카 메타데이터 파일(.meta)이 있으면 기대 청크 수 자동 추출
if [ -z "$EXPECTED_CHUNKS" ] && [ -f "${DUMP}.meta" ]; then
  META_CHUNKS=$(sed -n 's/^CHUNKS_COUNT=//p' "${DUMP}.meta" | head -n 1 | tr -d '[:space:]')
  if [ -n "$META_CHUNKS" ]; then
    EXPECTED_CHUNKS="$META_CHUNKS"
    echo "[INFO] ${DUMP}.meta 파일에서 기대 청크 수(${EXPECTED_CHUNKS}건)를 읽었습니다."
  fi
fi

[ -f "$DUMP" ] || { echo "[FAIL] 파일 없음: $DUMP" >&2; exit 1; }
[ -s "$DUMP" ] || { echo "[FAIL] 덤프 파일이 비어 있습니다 (0 byte): $DUMP" >&2; exit 1; }

CONTAINER_NAME="${POSTGRES_CONTAINER:-accounting_db}"
DB="${POSTGRES_DB:-$(read_env POSTGRES_DB)}"
DB="${DB:-accounting_db}"
USER="${POSTGRES_USER:-$(read_env POSTGRES_USER)}"
USER="${USER:-accounting_user}"
PASSWORD="${POSTGRES_PASSWORD:-$(read_env POSTGRES_PASSWORD)}"
PASSWORD="${PASSWORD:-accounting_password}"

detect_container_runtime || { container_runtime_hint; exit 1; }

"${CONTAINER[@]}" ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME" || {
  echo "[FAIL] $CONTAINER_NAME 컨테이너가 실행 중이 아닙니다. ${COMPOSE[*]} up -d 로 먼저 띄우세요." >&2
  exit 1
}

echo "[INFO] pgvector 확장 확인/생성"
"${CONTAINER[@]}" exec -e PGPASSWORD="$PASSWORD" "$CONTAINER_NAME" \
  psql -U "$USER" -d "$DB" -c "CREATE EXTENSION IF NOT EXISTS vector;"

# TOC 필터링을 위한 임시 파일 설정 및 정리 트랩
TOC_HOST="$(mktemp)"
TOC_FILTERED=""
CONTAINER_TOC="/tmp/restore_toc_$$.list"

cleanup() {
  rm -f "$TOC_HOST" "$TOC_FILTERED"
  "${CONTAINER[@]}" exec "$CONTAINER_NAME" rm -f "$CONTAINER_TOC" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[INFO] 덤프 아카이브 목차(TOC) 추출 중..."
"${CONTAINER[@]}" exec -i "$CONTAINER_NAME" pg_restore -l < "$DUMP" > "$TOC_HOST"

echo "[INFO] TOC 필터링 적용 (Apache AGE 확장 및 불필요한 실험 테이블 배제)"
TOC_FILTERED="$(mktemp)"
if [ "${RESTORE_ALL_TABLES:-0}" = "1" ]; then
  grep -viE "EXTENSION - age|COMMENT - EXTENSION age|ag_catalog" "$TOC_HOST" > "$TOC_FILTERED" || true
else
  grep -viE "EXTENSION - age|COMMENT - EXTENSION age|ag_catalog|interaction_log|bench_indexing|chunks_2048|chunks_fine|chunks_smoke|chunks_test_" "$TOC_HOST" > "$TOC_FILTERED" || true
fi
mv "$TOC_FILTERED" "$TOC_HOST"
TOC_FILTERED=""

"${CONTAINER[@]}" cp "$TOC_HOST" "$CONTAINER_NAME:$CONTAINER_TOC"

echo "[INFO] $DUMP -> $CONTAINER_NAME:'$DB' 복원 중 (기존 테이블은 지우고 새로 만듦)"
"${CONTAINER[@]}" exec -i -e PGPASSWORD="$PASSWORD" "$CONTAINER_NAME" \
  pg_restore -U "$USER" -d "$DB" -L "$CONTAINER_TOC" --clean --if-exists --no-owner --no-privileges < "$DUMP"

echo "[INFO] 복원 데이터 무결성 검증 중..."
RESTORED_CHUNKS=$("${CONTAINER[@]}" exec -e PGPASSWORD="$PASSWORD" "$CONTAINER_NAME" \
  psql -U "$USER" -d "$DB" -tAc "SELECT COUNT(*) FROM chunks;" 2>/dev/null || echo "0")
RESTORED_CHUNKS=$(echo "$RESTORED_CHUNKS" | tr -d '[:space:]')
[ -z "$RESTORED_CHUNKS" ] && RESTORED_CHUNKS="0"

if [ "$RESTORED_CHUNKS" -le 0 ]; then
  echo "[FAIL] 복원 검증 실패: chunks 테이블이 비어 있습니다 (0건)." >&2
  exit 1
fi

if [ -n "$EXPECTED_CHUNKS" ]; then
  if [ "$RESTORED_CHUNKS" -ne "$EXPECTED_CHUNKS" ]; then
    echo "[FAIL] 복원 검증 실패: 청크 수 불일치 (기대: ${EXPECTED_CHUNKS}건, 실제 복원: ${RESTORED_CHUNKS}건)" >&2
    exit 1
  fi
  echo "[OK] 청크 수 일치 검증 통과: ${RESTORED_CHUNKS}건"
else
  echo "[INFO] 복원된 청크 수: ${RESTORED_CHUNKS}건 (기대값 미지정)"
fi

INDEX_COUNT=$("${CONTAINER[@]}" exec -e PGPASSWORD="$PASSWORD" "$CONTAINER_NAME" \
  psql -U "$USER" -d "$DB" -tAc "SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'chunks';" 2>/dev/null || echo "0")
INDEX_COUNT=$(echo "$INDEX_COUNT" | tr -d '[:space:]')
[ -z "$INDEX_COUNT" ] && INDEX_COUNT="0"

if [ "$INDEX_COUNT" -eq 0 ]; then
  echo "[WARN] chunks 테이블에 생성된 인덱스가 없습니다." >&2
fi

echo "[OK] 복원 완료: chunks ${RESTORED_CHUNKS}건, 인덱스 ${INDEX_COUNT}개 정상"
