# 서버 간 데이터베이스(DB) 이관 가이드

> 운영 환경에서 이미 청크 분할 및 KURE-v1 임베딩 벡터 적재가 완료된 데이터베이스를 다른 독립 서버(개발/운영/스테이징)로 빠르고 안전하게 복사·이관하는 절차를 설명합니다.

---

## 1. 적재 경로 우선순위

새 서버를 구축할 때 데이터를 공급하는 경로는 다음과 같으며, **덤프 복원**을 1순위 기본 경로로 채택합니다.

| 순위 | 경로 | 판단 및 장단점 |
|---|---|---|
| **1순위 (기본)** | **기존 임베딩이 포함된 덤프 복원 (`db_dump.sh` / `db_restore.sh`)** | **가장 빠르고 안정적임.** 수천 건의 임베딩 연산과 인덱스 생성을 다시 수행할 필요가 없으며, 원본과 복원 결과의 데이터 건수를 즉시 대조 검증할 수 있습니다. |
| **2순위 (보조)** | 정제된 마크다운 적재 (`src.main ingest --markdown-dir`) | 무거운 PDF 파싱 단계가 없어 앱 컨테이너 내부에서도 실행 가능하나, 임베딩 연산 시간이 소요됩니다. |
| **비권장** | 새 서버에서 원문 PDF 실시간 파싱 | vCPU 2 등의 저사양 환경에서 파싱 부하가 매우 크고, 앱 컨테이너 기본 이미지에는 PDF 파싱 의존성(`--extra ingest`)이 포함되지 않습니다. |

---

## 2. 필수 제약 사항

### ① 임베딩 모델 및 차원 일치 필수
복원되는 벡터는 **`nlpai-lab/KURE-v1` (1024차원)** 모델로 생성된 값입니다.
새 서버가 다른 임베딩 모델을 사용하면 코사인 유사도 연산이 왜곡되어 오류 없이 검색 품질만 붕괴됩니다.
따라서 새 서버의 `.env` 환경 변수는 원본 서버와 동일해야 합니다:

```bash
EMBEDDING_MODEL=nlpai-lab/KURE-v1
EMBEDDING_DIM=1024
```

### ② 원문 PDF 파일 동반 복사 (BYO 데이터)
`db_dump.sh`로 생성하는 DB 덤프에는 텍스트 청크와 벡터만 포함되며, **원문 PDF 바이너리는 저장되지 않습니다.**
원문 PDF는 저작권 문제로 저장소에 포함하지 않는 BYO(Bring Your Own) 방식이므로, DB만 복원하면 검색 질의 및 조항 보기는 동작하지만 웹 UI의 **원문 PDF 보기**가 404 오류를 냅니다.
따라서 이관 시 반드시 **덤프 파일과 `data/raw_data/` 내의 PDF 파일들을 함께 전송**해야 합니다.

---

## 3. 단계별 이관 절차

### 1단계: 원본 서버에서 DB 덤프 생성

원본 서버의 저장소 루트에서 `db_dump.sh`를 실행합니다.

```bash
./db_dump.sh
# 특정 경로 지정 시: ./db_dump.sh backups/accounting_db_latest.dump
```

- 운영 필수 테이블인 `chunks` 및 `chunks_morph`(존재 시)만 선별하여 덤프합니다.
- 실험용 임시 테이블(`chunks_2048`, `chunks_fine`, `bench_indexing` 등) 및 개발 질의 기록(`interaction_log`)은 덤프에서 제외됩니다.
- 덤프 완료 후 청크 수 등의 메타데이터가 담긴 `.meta` 파일이 함께 생성됩니다.

### 2단계: 덤프 파일과 원문 PDF를 대상 서버로 전송

SCP, rsync, 또는 사내 안전한 파일 전송 수단을 사용하여 대상 서버로 복사합니다.

```bash
# 덤프 및 메타데이터 전송
scp backups/accounting_db_*.dump* user@target-server:/path/to/rag/backups/

# 원문 PDF 디렉터리 동반 전송
rsync -avzP data/raw_data/ user@target-server:/path/to/rag/data/raw_data/
```

### 3단계: 대상 서버에서 컨테이너 스택 준비

대상 서버에서 컨테이너 런타임(Docker 또는 Podman)을 확인하고 스택을 기동합니다.

```bash
# 최초 환경 설정 (.env 준비)
cp .env.example .env
# 필요 시 .env의 OPENAI_API_KEY, HOST_PORT 등 수정

# 스택 기동 (install.sh가 런타임을 자동 감지하여 실행)
./install.sh

# 또는 데이터베이스 컨테이너만 선기동할 경우
# (Docker Compose 환경)
docker compose up -d database
# (Podman 환경)
podman-compose up -d --build --force-recreate database
```

### 4단계: 대상 서버에서 DB 복원 실행

데이터베이스 컨테이너(`accounting_db`)가 기동된 상태에서 `db_restore.sh`를 실행합니다.

```bash
./db_restore.sh backups/accounting_db_latest.dump
# 또는 기대 청크 수를 명시할 경우:
./db_restore.sh backups/accounting_db_latest.dump 1507
```

- **TOC(Table of Contents) 필터 자동 적용**:
  개발 DB 카탈로그에 남아 있던 Apache AGE 고아 확장 등록(`CREATE EXTENSION age` 등)을 복원 목록에서 자동으로 걸러냅니다. 
  따라서 신규 서버 이미지에 AGE가 설치되어 있지 않아도 `pg_restore`가 실패하지 않고 **종료 코드 0**으로 깨끗하게 복원됩니다.
- **사이드카 메타데이터 연동**:
  덤프 파일과 같은 위치에 `.meta` 파일이 있으면 원본 서버의 청크 수를 자동으로 읽어 일치 여부를 대조합니다.
- **복원 후 자동 검증**:
  복원 직후 `chunks` 테이블 행 수를 직접 조회하여 0건이거나 기대 수치와 다르면 즉시 에러를 반환합니다.

### 5단계: 스택 점검 및 서비스 확인

복원이 끝나면 전체 스택 상태를 최종 점검합니다.

```bash
./check.sh
```

웹 브라우저(`http://localhost:8000`)에 접속하여 질의 검색 및 조항 카드에서 **원문 PDF 보기**가 정상 출력되는지 확인합니다.

---

## 4. 컨테이너 런타임별 참고사항 (Docker / Podman)

- `db_dump.sh`와 `db_restore.sh`는 `scripts/container_runtime.sh`의 감지 로직을 공유합니다.
- Docker Compose v2뿐만 아니라 Rocky Linux, RHEL 계열의 Podman 및 `podman-compose` 환경에서도 추가 래퍼 설치 없이 바로 동작합니다.
- 복원 시 사용되는 `pg_restore` 및 임시 목차(TOC) 조작은 호스트에 PostgreSQL 클라이언트 툴이 설치되어 있지 않아도 `accounting_db` 컨테이너 내부 바이너리와 표준 입출력 파이프를 통해 완전히 격리되어 수행됩니다.
