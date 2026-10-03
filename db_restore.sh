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

# -----------------------------------------------------------------------------
# 1. 실행 인자 검증 및 사용법 안내
# -----------------------------------------------------------------------------
# ${1:-}: set -u 미정의 변수 참조 에러 방지용 기본값 매개변수 확장 (파이썬 := 와 무관)
# $# -lt 1: 필수 인자인 덤프 파일 경로가 누락된 경우 즉시 사용법을 출력하고 조기 종료(exit 1)
# -h/--help 요청 시에는 사용법 안내 후 정상 종료(exit 0) 처리
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ $# -lt 1 ]; then
  echo "사용법: $0 <덤프파일경로> [기대청크수]"
  echo "  덤프파일: 필수, pg_dump 커스텀 포맷(-Fc) 아카이브 파일"
  echo "  기대청크수: 선택, 미지정 시 .meta 파일 또는 EXPECTED_CHUNKS 환경변수를 확인합니다."
  exit $( [ $# -lt 1 ] && echo 1 || echo 0 )
fi

DUMP="$1"
EXPECTED_CHUNKS="${2:-${EXPECTED_CHUNKS:-}}"

# -----------------------------------------------------------------------------
# 2. 사이드카 메타데이터(.meta) 파싱 및 파일 유효성 검사
# -----------------------------------------------------------------------------
# 기대 청크 수가 미지정되었고 동일 경로에 .meta 파일이 있을 경우 기대값 자동 추출
if [ -z "$EXPECTED_CHUNKS" ] && [ -f "${DUMP}.meta" ]; then
  # sed -n: 일치하지 않는 일반 행의 기본 출력 억제
  # s/^CHUNKS_COUNT=//: 키 접두사를 제거하고 순수 숫자 문자열만 추출
  # p: 패턴 치환에 성공한 행만 화면에 출력하는 플래그 (청크 수 표기가 아님)
  # head -n 1 및 tr -d '[:space:]': 중복 라인 방어 및 줄바꿈/공백 완전 제거로 정수 비교 에러 차단
  META_CHUNKS=$(sed -n 's/^CHUNKS_COUNT=//p' "${DUMP}.meta" | head -n 1 | tr -d '[:space:]')
  if [ -n "$META_CHUNKS" ]; then
    EXPECTED_CHUNKS="$META_CHUNKS"
    echo "[INFO] ${DUMP}.meta 파일에서 기대 청크 수(${EXPECTED_CHUNKS}건)를 읽었습니다."
  fi
fi

# -f: 일반 파일 존재 검사 / -s: 파일 크기 0바이트 초과 여부 검사 (0바이트 빈 파일 조기 차단)
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

# 대상 컨테이너가 정상 실행 중인지 사전 검사
"${CONTAINER[@]}" ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME" || {
  echo "[FAIL] $CONTAINER_NAME 컨테이너가 실행 중이 아닙니다. ${COMPOSE[*]} up -d 로 먼저 띄우세요." >&2
  exit 1
}

# -----------------------------------------------------------------------------
# 3. 임시 파일 정의 및 무결성 보장을 위한 종료 트랩
# -----------------------------------------------------------------------------
echo "[INFO] pgvector 확장 확인/생성"
"${CONTAINER[@]}" exec -e PGPASSWORD="$PASSWORD" "$CONTAINER_NAME" \
  psql -U "$USER" -d "$DB" -c "CREATE EXTENSION IF NOT EXISTS vector;"

# TOC: pg_dump -Fc 바이너리 아카이브 내부에 저장된 스키마/데이터/확장 명세 목록(목차)
# mktemp: 리눅스 표준 유틸리티로 /tmp 경로에 이름 충돌이 없는 고유한 임시 파일 생성
TOC_HOST="$(mktemp)"
TOC_FILTERED=""
# $$: 현재 셸 스크립트 프로세스 ID를 이용해 컨테이너 내부 임시 파일명 충돌 방지
CONTAINER_TOC="/tmp/restore_toc_$$.list"

# trap cleanup EXIT: 정상 종료, 에러 중단(exit 1), 강제 인터럽트 등 프로세스가 종료되는 모든 시점에 무조건 실행
cleanup() {
  # rm -f는 공백으로 나열된 복수 임시 파일을 일괄 강제 삭제하여 호스트/컨테이너 내부 자원 완전 회수
  rm -f "$TOC_HOST" "$TOC_FILTERED"
  "${CONTAINER[@]}" exec "$CONTAINER_NAME" rm -f "$CONTAINER_TOC" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# -----------------------------------------------------------------------------
# 4. 목차(TOC) 추출 및 필터링 (불필요한 확장 및 실험 테이블 제외)
# -----------------------------------------------------------------------------
echo "[INFO] 덤프 아카이브 목차(TOC) 추출 중..."
# pg_restore -l: 데이터를 복원하지 않고 아카이브 내부 목차(TOC)만 텍스트로 조회
# < "$DUMP": 호스트 바이너리 덤프를 컨테이너 표준 입력으로 전달
# > "$TOC_HOST": 컨테이너에서 추출된 텍스트 목차를 호스트 임시 파일로 저장
"${CONTAINER[@]}" exec -i "$CONTAINER_NAME" pg_restore -l < "$DUMP" > "$TOC_HOST"

echo "[INFO] TOC 필터링 적용 (Apache AGE 확장 및 불필요한 실험 테이블 배제)"
TOC_FILTERED="$(mktemp)"
# grep -viE: 제외(-v), 대소문자 무시(-i), 확장 정규식(-E)
# || true: 매칭 항목이 없을 때 grep 종료 코드 1로 인해 set -e가 발동되어 비정상 종료되는 현상 방지
if [ "${RESTORE_ALL_TABLES:-0}" = "1" ]; then
  # 전체 복원 모드: Apache AGE 확장 관련 구문만 제외
  grep -viE "EXTENSION - age|COMMENT - EXTENSION age|ag_catalog" "$TOC_HOST" > "$TOC_FILTERED" || true
else
  # 운영 복원 모드(기본): AGE 확장 및 개발/실험용 테이블(bench, smoke, test 등)을 목차에서 제외하여 불필요한 용량 점유 차단
  grep -viE "EXTENSION - age|COMMENT - EXTENSION age|ag_catalog|interaction_log|bench_indexing|chunks_2048|chunks_fine|chunks_smoke|chunks_test_" "$TOC_HOST" > "$TOC_FILTERED" || true
fi

# 셸 트렁케이션 방어: 동일 파일 직접 리다이렉션(> $TOC_HOST) 시 읽기 전에 0바이트로 초기화되는 현상을 막기 위해 mv로 덮어쓰기
mv "$TOC_FILTERED" "$TOC_HOST"
TOC_FILTERED=""

# 호스트의 정제된 목차 임시 파일을 컨테이너 내부 경로로 단일 전송 복사
"${CONTAINER[@]}" cp "$TOC_HOST" "$CONTAINER_NAME:$CONTAINER_TOC"

# -----------------------------------------------------------------------------
# 5. 선별적 복원 실행 (pg_restore)
# -----------------------------------------------------------------------------
echo "[INFO] $DUMP -> $CONTAINER_NAME:'$DB' 복원 중 (기존 테이블은 지우고 새로 만듦)"
# -L "$CONTAINER_TOC": 정제된 목차 파일 목록에 정의된 객체만 선별 복원 (미지원 확장 오류 원천 차단)
# --clean --if-exists: 멱등성 보장 (기존 테이블 존재 시 DROP 후 재생성)
# --no-owner --no-privileges: 환경 간 DB 사용자/권한 불일치 충돌 방지
"${CONTAINER[@]}" exec -i -e PGPASSWORD="$PASSWORD" "$CONTAINER_NAME" \
  pg_restore -U "$USER" -d "$DB" -L "$CONTAINER_TOC" --clean --if-exists --no-owner --no-privileges < "$DUMP"

# -----------------------------------------------------------------------------
# 6. 복원 데이터 무결성 및 인덱스 사후 검증 (3단계)
# -----------------------------------------------------------------------------
echo "[INFO] 복원 데이터 무결성 검증 중..."
# -tAc: Tuples-only(-t), Unaligned(-A), Command(-c) 조합으로 순수 카운트 값만 추출
RESTORED_CHUNKS=$("${CONTAINER[@]}" exec -e PGPASSWORD="$PASSWORD" "$CONTAINER_NAME" \
  psql -U "$USER" -d "$DB" -tAc "SELECT COUNT(*) FROM chunks;" 2>/dev/null || echo "0")
RESTORED_CHUNKS=$(echo "$RESTORED_CHUNKS" | tr -d '[:space:]')
# [ -z ... ]: 빈 문자열일 경우 숫자 비교 에러 방지를 위해 "0" 안전 대입
[ -z "$RESTORED_CHUNKS" ] && RESTORED_CHUNKS="0"

# [검증 1단계] 복원된 청크 건수가 0건 이하인지 확인
if [ "$RESTORED_CHUNKS" -le 0 ]; then
  echo "[FAIL] 복원 검증 실패: chunks 테이블이 비어 있습니다 (0건)." >&2
  exit 1
fi

# [검증 2단계] 기대 청크 수(인자 또는 .meta) 일치 여부 1:1 대조
# [ -n ... ]: 변수의 문자열 길이가 0이 아님(비어있지 않음)을 확인하는 문자열 검사식 (숫자 비교가 아님)
if [ -n "$EXPECTED_CHUNKS" ]; then
  if [ "$RESTORED_CHUNKS" -ne "$EXPECTED_CHUNKS" ]; then
    echo "[FAIL] 복원 검증 실패: 청크 수 불일치 (기대: ${EXPECTED_CHUNKS}건, 실제 복원: ${RESTORED_CHUNKS}건)" >&2
    exit 1
  fi
  echo "[OK] 청크 수 일치 검증 통과: ${RESTORED_CHUNKS}건"
else
  echo "[INFO] 복원된 청크 수: ${RESTORED_CHUNKS}건 (기대값 미지정)"
fi

# [검증 3단계] 테이블 복원 후 인덱스(벡터/기본키) 정상 생성 여부 점검
INDEX_COUNT=$("${CONTAINER[@]}" exec -e PGPASSWORD="$PASSWORD" "$CONTAINER_NAME" \
  psql -U "$USER" -d "$DB" -tAc "SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'chunks';" 2>/dev/null || echo "0")
INDEX_COUNT=$(echo "$INDEX_COUNT" | tr -d '[:space:]')
[ -z "$INDEX_COUNT" ] && INDEX_COUNT="0"

if [ "$INDEX_COUNT" -eq 0 ]; then
  echo "[WARN] chunks 테이블에 생성된 인덱스가 없습니다." >&2
fi

echo "[OK] 복원 완료: chunks ${RESTORED_CHUNKS}건, 인덱스 ${INDEX_COUNT}개 정상"
