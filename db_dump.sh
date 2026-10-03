#!/usr/bin/env bash
# accounting_db 컨테이너의 내용을 pg_dump 커스텀 포맷(-Fc)으로 로컬 파일에 백업한다.
# -Fc를 쓰는 이유: pg_restore로 병렬 복원·선택적 복원(-t 테이블명)이 가능하고, plain SQL보다 파일이 작다.
#
# [운영 방침]
# - chunks 및 chunks_morph(존재 시) 등 실제 서비스에 필요한 운영 데이터만 선별하여 덤프한다.
# - 실험용 테이블(chunks_2048, chunks_fine, bench_indexing 등) 및 질의 기록(interaction_log)은 제외한다.
# - 고아 확장 등록(ag_catalog) 스키마는 덤프에서 제외한다.
# - 덤프 완료 후 청크 수 등의 메타데이터를 담은 .meta 파일을 함께 생성하여 복원 시 자동 검증에 활용한다.
#
# 사용법: ./db_dump.sh [출력경로]  (생략 시 backups/<DB명>_YYYYmmdd_HHMMSS.dump)

# 엄격 모드 설정: 켜 두면 스크립트 내에서 오류가 발생했을 때 즉시 실행 중지
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

source "$ROOT/scripts/container_runtime.sh"
source "$ROOT/scripts/env_file.sh"

# -h 또는 --help 라는 인자를 사용하면 도움말 출력
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  echo "사용법: $0 [출력경로]"
  echo "  accounting_db 컨테이너의 운영 데이터(chunks 등)를 백업합니다."
  echo "  출력경로 생략 시 backups/<DB명>_YYYYmmdd_HHMMSS.dump 파일로 저장됩니다."
  exit 0
fi

# ${변수:-기본값}: 쉘의 매개변수 기본값 확장 문법
# 환경변수가 이미 설정되어 있고 비어있지 않다면 그 값을 사용
# 비어있거나 설정되어 있지 않다면 기본값을 사용
CONTAINER_NAME="${POSTGRES_CONTAINER:-accounting_db}"
DB="${POSTGRES_DB:-$(read_env POSTGRES_DB)}"
DB="${DB:-accounting_db}"
USER="${POSTGRES_USER:-$(read_env POSTGRES_USER)}"
USER="${USER:-accounting_user}"
PASSWORD="${POSTGRES_PASSWORD:-$(read_env POSTGRES_PASSWORD)}"
PASSWORD="${PASSWORD:-accounting_password}"
# OUT: 덤프 결과물이 저장될 파일 경로 (디렉터리가 아닌 최종 파일 경로를 가리키며, 향후 DUMP_FILE 또는 OUTPUT_FILE로 명명 표준화 검토)
OUT="${1:-backups/${DB}_$(date +%Y%m%d_%H%M%S).dump}"

# || (OR 연산자): 왼쪽 명령어가 실패(종료 코드 0이 아님)했을 때만 오른쪽 블록을 실행
detect_container_runtime || { container_runtime_hint; exit 1; }

# 실행 중인 대상 컨테이너가 실제로 떠 있는지 사전 검사하는 로직
"${CONTAINER[@]}" ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME" || {
  echo "[FAIL] $CONTAINER_NAME 컨테이너가 실행 중이 아닙니다. ${COMPOSE[*]} up -d 로 먼저 띄우세요." >&2
  exit 1
}

# -----------------------------------------------------------------------------
# 1. 백업 대상 운영 테이블 선별
# -----------------------------------------------------------------------------
TARGET_TABLES=()
# ${ALL_TABLES:-0}: set -u 환경에서 미정의 변수 참조 에러를 방지하고 기본값 0을 적용
# ALL_TABLES=1로 명시하지 않는 한 실험용 테이블/로그를 배제하고 서비스 운영 테이블만 선별 덤프
if [ "${ALL_TABLES:-0}" != "1" ]; then
  for tbl in chunks chunks_morph; do
    # "${CONTAINER[@]}": docker compose 등 다중 단어로 구성된 런타임 배열 인자를 공백 분리 없이 보존
    # table_schema='public': 시스템/확장 카탈로그 스키마를 제외하고 순수 서비스 운영 테이블 존재 여부만 검사
    if "${CONTAINER[@]}" exec -e PGPASSWORD="$PASSWORD" "$CONTAINER_NAME" \
         psql -U "$USER" -d "$DB" -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='$tbl';" 2>/dev/null | grep -q 1; then
      TARGET_TABLES+=("-t" "$tbl")
    fi
  done
  # ${#TARGET_TABLES[@]} -eq 0: 백업 대상 핵심 테이블이 전혀 없으면 비정상 상태로 판단하여 조기 종료
  if [ ${#TARGET_TABLES[@]} -eq 0 ]; then
    echo "[FAIL] 운영 테이블(chunks)을 DB에서 찾을 수 없습니다. DB 초기화 여부를 확인하거나 ALL_TABLES=1을 사용하세요." >&2
    exit 1
  fi
fi

# -----------------------------------------------------------------------------
# 2. 출력 디렉터리 준비 및 덤프 전 행 수(청크 수) 집계
# -----------------------------------------------------------------------------
# dirname 명령어로 파일명을 제외한 부모 디렉터리 경로만 추출하고, 없으면 자동 생성하여 파일 쓰기 오류 방지
mkdir -p "$(dirname "$OUT")"

# tr -d '[:space:]': 결과 텍스트의 모든 공백/개행을 완전히 제거하여 이후 숫자 비교 시 셸 문법 에러 차단
CHUNK_COUNT=$("${CONTAINER[@]}" exec -e PGPASSWORD="$PASSWORD" "$CONTAINER_NAME" \
  psql -U "$USER" -d "$DB" -tAc "SELECT COUNT(*) FROM chunks;" 2>/dev/null || echo "0")
CHUNK_COUNT=$(echo "$CHUNK_COUNT" | tr -d '[:space:]')
# [ -z ... ] && ...: 문자열 길이가 0인 경우 기본값 "0"을 안전하게 대입하는 단축 평가식
[ -z "$CHUNK_COUNT" ] && CHUNK_COUNT="0"

echo "[INFO] $CONTAINER_NAME 에서 '$DB' 덤프 중 -> $OUT"
if [ ${#TARGET_TABLES[@]} -gt 0 ]; then
  echo "[INFO] 선별된 운영 테이블: ${TARGET_TABLES[*]}"
else
  echo "[INFO] 전체 테이블 대상 덤프 진행"
fi

# -----------------------------------------------------------------------------
# 3. 무결성 보장을 위한 트랩 핸들러 (비정상 종료 시 잔재 파일 정리)
# -----------------------------------------------------------------------------
# trap cleanup EXIT: 정상 종료, 에러 중단(exit 1), 강제 인터럽트 등 프로세스가 종료되는 모든 시점에 무조건 실행
cleanup() {
  # [ -f ]: 일반 파일 존재 검사 / [ ! -s ]: 파일 크기가 0바이트인지 검사
  # 덤프 도중 중단되어 남겨진 0바이트 빈 파일이 디스크에 방치되지 않도록 삭제 (rm -f 플래그와 별개로 크기 조건 검사)
  if [ -f "$OUT" ] && [ ! -s "$OUT" ]; then
    rm -f "$OUT"
  fi
}
trap cleanup EXIT

# -----------------------------------------------------------------------------
# 4. pg_dump 실행 및 결과 무결성 검증
# -----------------------------------------------------------------------------
# if ! ...; then: pg_dump 실행 결과가 실패(Non-zero)인 경우 실패 분기로 진입
# -Fc: PostgreSQL Custom Format(압축 바이너리)으로 추출하여 사후 TOC 필터링 및 선택 복원 지원
# --no-owner --no-privileges: 타 환경 복원 시 사용자 및 권한 불일치 충돌 방지
# --exclude-schema=ag_catalog: 타 환경 복원 실패를 유발하는 Apache AGE 확장 스키마 잔재 원천 차단
if ! "${CONTAINER[@]}" exec -e PGPASSWORD="$PASSWORD" "$CONTAINER_NAME" \
       pg_dump -U "$USER" -d "$DB" -Fc --no-owner --no-privileges --exclude-schema=ag_catalog "${TARGET_TABLES[@]}" > "$OUT"; then
  rm -f "$OUT"
  echo "[FAIL] pg_dump 실행에 실패했습니다: $OUT" >&2
  exit 1
fi

# 덤프 파일이 정상 크기를 가졌는지 최종 확인
[ -s "$OUT" ] || {
  rm -f "$OUT"
  echo "[FAIL] 덤프 파일이 비어있거나 생성되지 않았습니다: $OUT" >&2
  exit 1
}

# -----------------------------------------------------------------------------
# 5. 복원 자동 검증용 사이드카 메타데이터(.meta) 생성
# -----------------------------------------------------------------------------
# cat <<EOF > ...: Here Document 입력을 메타 파일에 리다이렉션하여 여러 줄 텍스트를 파일에 기록
# 바이너리 덤프의 불투명성을 해소하고 db_restore.sh가 사후 청크 수 일치 검증 시 활용
META_FILE="${OUT}.meta"
cat <<EOF > "$META_FILE"
DUMP_FILE=$(basename "$OUT")
DUMP_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DATABASE=$DB
CHUNKS_COUNT=$CHUNK_COUNT
TABLES=${TARGET_TABLES[*]}
EOF

# $(du -h ... | cut -f1): du 결과 중 탭으로 구분된 첫 번째 필드(용량 문자열)만 파싱
echo "[OK] 완료: $OUT ($(du -h "$OUT" | cut -f1), 청크: ${CHUNK_COUNT}건)"
echo "[OK] 메타데이터 저장: $META_FILE"
