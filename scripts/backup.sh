#!/usr/bin/env bash
# periodic backup runner & retention rotation script
#
# [운영 방침]
# - db_dump.sh를 실행하여 운영 데이터베이스(chunks, chunks_morph 등)의 최신 덤프와 .meta 사이드카를 생성합니다.
# - RETENTION_DAYS(기본값 30일)를 초과한 과거 덤프 및 메타데이터를 안전하게 자동 삭제(로테이션)합니다.
# - INCLUDE_PDF=1 설정 시 data/raw_data의 원문 PDF 디렉터리를 tar.gz로 함께 아카이빙합니다.
# - cron 및 systemd timer 등 무인 자동화 환경 친화적인 표준 로그 및 종료 코드를 제공합니다.
#
# 사용법:
#   ./scripts/backup.sh
#   RETENTION_DAYS=14 BACKUP_DIR=/custom/path ./scripts/backup.sh

set -euo pipefail

# 1. 프로젝트 루트 경로 산출
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 도움말 (-h / --help)
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  cat <<'EOF'
사용법: ./scripts/backup.sh [옵션]

환경 변수:
  BACKUP_DIR      백업 저장 디렉터리 (기본값: 프로젝트 루트/backups)
  RETENTION_DAYS  백업 파일 보관 일수 (기본값: 30)
  INCLUDE_PDF     원문 PDF(data/raw_data) 아카이빙 여부 (0: 제외, 1: 포함, 기본값: 0)
  DUMP_SCRIPT     실행할 db_dump.sh 경로 오버라이드 (기본값: 프로젝트 루트/db_dump.sh)

설명:
  운영 데이터베이스를 덤프하고, 보관 주기(RETENTION_DAYS)가 지난 오래된
  백업 파일(*.dump, *.meta, *.tar.gz)을 자동으로 정리합니다.
EOF
  exit 0
fi

# 2. 파라미터 및 환경 변수 기본값 설정
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
INCLUDE_PDF="${INCLUDE_PDF:-0}"
RAW_DATA_DIR="${RAW_DATA_DIR:-$ROOT/data/raw_data}"
DUMP_SCRIPT="${DUMP_SCRIPT:-$ROOT/db_dump.sh}"

# 3. 입력 검증 (엄격성 및 안전장치)
# RETENTION_DAYS 숫자 검증
case "$RETENTION_DAYS" in
  (*[!0-9]*|"")
    echo "[FAIL] RETENTION_DAYS는 0 이상의 정수여야 합니다: '$RETENTION_DAYS'" >&2
    exit 1
    ;;
esac

# BACKUP_DIR 위험 경로 거부 (루트 및 홈 디렉터리 삭제 참사 방지)
RESOLVED_BACKUP_DIR="$(mkdir -p "$BACKUP_DIR" && cd "$BACKUP_DIR" && pwd)"
RESOLVED_HOME="$(cd "$HOME" && pwd)"

if [ "$RESOLVED_BACKUP_DIR" = "/" ] || [ "$RESOLVED_BACKUP_DIR" = "$RESOLVED_HOME" ]; then
  echo "[FAIL] BACKUP_DIR을 시스템 루트(/) 또는 홈 디렉터리로 설정할 수 없습니다: '$RESOLVED_BACKUP_DIR'" >&2
  exit 1
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
echo "[BACKUP] [$(date '+%Y-%m-%d %H:%M:%S')] 백업 작업을 시작합니다."
echo "[BACKUP] 대상 디렉터리: $RESOLVED_BACKUP_DIR"
echo "[BACKUP] 보관 기간: $RETENTION_DAYS 일"

# 4. 데이터베이스 덤프 실행
if [ ! -f "$DUMP_SCRIPT" ]; then
  echo "[FAIL] 덤프 스크립트를 찾을 수 없습니다: $DUMP_SCRIPT" >&2
  exit 1
fi

DUMP_OUT="$RESOLVED_BACKUP_DIR/accounting_db_${TIMESTAMP}.dump"
echo "[BACKUP] 데이터베이스 덤프 생성 중 -> $DUMP_OUT"
bash "$DUMP_SCRIPT" "$DUMP_OUT"

# 5. 원문 PDF 선택적 아카이빙
if [ "$INCLUDE_PDF" = "1" ]; then
  if [ -d "$RAW_DATA_DIR" ]; then
    PDF_ARCHIVE="$RESOLVED_BACKUP_DIR/raw_data_${TIMESTAMP}.tar.gz"
    echo "[BACKUP] 원문 PDF 아카이브 생성 중 -> $PDF_ARCHIVE"
    tar -czf "$PDF_ARCHIVE" -C "$(dirname "$RAW_DATA_DIR")" "$(basename "$RAW_DATA_DIR")"
  else
    echo "[WARN] PDF 디렉터리가 존재하지 않아 아카이빙을 건너뜁니다: $RAW_DATA_DIR" >&2
  fi
fi

# 6. 보관 주기(Retention) 초과 파일 안전 로테이션
echo "[BACKUP] $RETENTION_DAYS 일 초과된 과거 백업 파일 정리 중..."

# -mindepth 1 -maxdepth 1 옵션으로 하위 디렉터리 순회 방지 및 직하위 파일만 정밀 타겟팅
CLEANUP_COUNT=0
for pattern in "*.dump" "*.meta" "*.tar.gz"; do
  while IFS= read -r -d '' file; do
    echo "[BACKUP] 보관 기간 초과 파일 삭제: $(basename "$file")"
    rm -f "$file"
    CLEANUP_COUNT=$((CLEANUP_COUNT + 1))
  done < <(find "$RESOLVED_BACKUP_DIR" -mindepth 1 -maxdepth 1 -name "$pattern" -type f -mtime +"$RETENTION_DAYS" -print0)
done

echo "[BACKUP] 정리 완료 (삭제된 파일 수: $CLEANUP_COUNT 개)"
echo "[BACKUP] [$(date '+%Y-%m-%d %H:%M:%S')] 백업 작업이 완료되었습니다."
exit 0
