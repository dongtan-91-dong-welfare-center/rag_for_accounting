# 백업 및 재해 복구(DR) 운영 가이드

> 비상장 중소기업 감사 지원 RAG 시스템의 데이터 유실을 방지하기 위한 정기 백업 설정과 시스템 장애 또는 서버 전소 시 신속한 복구를 위한 재해 복구(Disaster Recovery) 절차를 안내합니다.

---

## 1. 백업 및 재해 복구(DR) 정책 개요

시스템의 연속성을 보장하기 위해 다음과 같은 목표 지표 및 운영 정책을 적용합니다:

| 항목 | 정책 기준 | 상세 설명 및 근거 |
|---|---|---|
| **RTO (목표 복구 시간)** | **2시간 이내** | 장애 발생 시점부터 서비스가 정상 기동되어 사용자의 질의를 수락할 때까지 소요되는 최대 허용 시간입니다. 사전 인덱싱된 덤프 복원 방식을 사용하여 수 분 내 복원이 가능하므로 2시간 목표를 안정적으로 달성합니다. |
| **RPO (목표 복구 시점)** | **최대 24시간** | 일일 1회 정기 백업을 기준으로 하며, 재해 발생 시 최대 24시간 이전 데이터 상태로 복구됩니다. |
| **백업 주기 및 시점** | **매일 새벽 03:00 (KST)** | 감사인 및 회계사의 질의 트래픽이 발생하지 않는 새벽 시간대에 무인 자동 실행합니다. |
| **보관 주기 (Retention)** | **30일** | 디스크 용량 낭비를 방지하기 위해 생성일 기준 30일이 초과된 오래된 백업 파일(`*.dump`, `*.meta`, `*.tar.gz`)은 자동으로 삭제됩니다. |
| **저장 위치 및 비용** | **호스트 로컬 기본 보관 + 무비용 외부 복제** | 클라우드 스토리지 추가 비용 없이 서버 호스트 `backups/` 디렉터리에 1차 보관하며, 관리자 로컬 환경으로의 SCP/rsync 복제 가이드를 제공합니다. |
| **백업 대상 범위** | **운영 DB + 원문 PDF** | 벡터 임베딩이 포함된 PostgreSQL DB(`chunks`, `chunks_morph` 테이블)와 원문 열람을 위한 PDF 디렉터리(`data/raw_data`)를 포괄합니다. |

---

## 2. 정기 자동 백업 스케줄링 설정

`scripts/backup.sh` 스크립트를 사용하여 일일 덤프 생성 및 30일 초과 구형 백업본의 자동 정리를 스케줄링합니다.

### 방법 A: Linux Crontab 등록 (권장)

호스트 운영체제의 crontab에 백업 작업을 등록합니다:

```bash
# 크론탭 편집기 열기
crontab -e

# 매일 새벽 03:00에 실행되도록 등록 (프로젝트 절대 경로 사용)
0 3 * * * /path/to/rag_for_accounting/scripts/backup.sh >> /var/log/rag_backup.log 2>&1
```

- 원문 PDF 디렉터리(`data/raw_data`)까지 함께 정기 아카이빙하려면 환경변수를 지정합니다:
  ```bash
  0 3 * * * INCLUDE_PDF=1 /path/to/rag_for_accounting/scripts/backup.sh >> /var/log/rag_backup.log 2>&1
  ```

### 방법 B: Systemd Service 및 Timer 등록

Rocky Linux / RHEL 시스템에서 `systemd` 타이머로 관리할 경우:

1. **서비스 유닛 작성** (`/etc/systemd/system/rag-backup.service`):
   ```ini
   [Unit]
   Description=RAG for Accounting Daily Database Backup
   After=network.target

   [Service]
   Type=oneshot
   User=appuser
   WorkingDirectory=/path/to/rag_for_accounting
   ExecStart=/path/to/rag_for_accounting/scripts/backup.sh
   StandardOutput=journal
   StandardError=journal
   ```

2. **타이머 유닛 작성** (`/etc/systemd/system/rag-backup.timer`):
   ```ini
   [Unit]
   Description=Run RAG for Accounting Daily Backup at 03:00 AM

   [Timer]
   OnCalendar=*-*-* 03:00:00
   Persistent=true

   [Install]
   WantedBy=timers.target
   ```

3. **타이머 활성화**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now rag-backup.timer
   sudo systemctl status rag-backup.timer
   ```

---

## 3. 재해 복구(DR: Disaster Recovery) 절차

### 3-1. 복구 타임라인 분석 (RTO 2시간 충족 검증)

서버 전소로 인해 완전히 새로운 가상 머신(VM)에서 전체 스택을 재구축하는 최악의 시나리오에서도 총 소요 시간은 **약 25분 내외**로, 2시간(120분) RTO 목표를 충분히 충족합니다:

| 복구 단계 | 주요 작업 내용 | 예상 소요 시간 |
|---|---|---|
| **1단계: 인프라 준비** | 신규 VM 접속, Podman/Docker 등 패키지 설치 | 약 10분 |
| **2단계: 코드 및 백업본 전송** | 저장소 클론, 백업 덤프(`.dump`, `.meta`) 및 PDF 복사 | 약 5분 |
| **3단계: 컨테이너 스택 기동** | `docker compose up -d` 또는 `podman-compose up -d` | 약 3분 |
| **4단계: DB 복원 실행** | `./db_restore.sh <덤프파일>` 실행 및 청크 대조 | 약 3분 |
| **5단계: 정상성 검증** | 준비성 프로브 `GET /ready` 확인 및 UI 테스트 | 약 2분 |
| **총계** | **신규 서버 완전 복구 완료** | **약 23분 (목표 120분 이내)** |

---

### 3-2. 시나리오 1: 운영 데이터베이스 오염 또는 손상 시 로컬 복구

기존 서버의 컨테이너 환경이 유지된 상태에서 데이터만 이전 정상 시점으로 되돌리는 절차입니다.

1. **최신 정상 백업 파일 확인**:
   ```bash
   ls -ltr backups/*.dump
   # 최신 파일: backups/accounting_db_YYYYmmdd_HHMMSS.dump
   ```

2. **DB 복원 스크립트 실행**:
   `db_restore.sh`는 컨테이너 내부 `pg_restore`를 호출하며, 사이드카(`.meta`) 파일을 감지하여 복원된 청크 건수를 원본과 자동 대조 검증합니다:
   ```bash
   ./db_restore.sh backups/accounting_db_YYYYmmdd_HHMMSS.dump
   ```

3. **준비성 프로브 및 서비스 확인**:
   ```bash
   # 준비성 프로브 상태 점검 (HTTP 200 및 status: ready 확인)
   curl -s http://localhost:8000/ready | jq .

   # 전체 스택 헬스체크
   ./check.sh
   ```

---

### 3-3. 시나리오 2: 서버 전소 또는 신규 서버 재구축 복구

서버 하드웨어 장애나 클라우드 인스턴스 소실로 인해 새로운 서버에서 시스템을 복구하는 절차입니다.

1. **신규 서버 필수 패키지 설치 (Rocky Linux / Podman 기준)**:
   ```bash
   sudo dnf install -y epel-release
   sudo dnf install -y podman podman-compose curl git rsync
   ```

2. **프로젝트 저장소 클론 및 환경 설정**:
   ```bash
   git clone -b main <REPOSITORY_URL> rag_for_accounting
   cd rag_for_accounting

   cp .env.example .env
   # .env 파일 내의 OPENAI_API_KEY 등 필수 보안 변수 입력
   ```

3. **보관 중이던 백업 덤프 및 원문 PDF 파일 배치**:
   외부 저장소 또는 관리자 PC에 보관해 둔 백업 파일들을 신규 서버로 전송하여 배치합니다:
   ```bash
   mkdir -p backups data/raw_data

   # 덤프 파일과 .meta 사이드카 배치
   cp /path/to/saved/accounting_db_*.dump* backups/

   # 원문 PDF 파일 배치 (PDF 아카이브 압축 해제 또는 직접 복사)
   tar -xzf /path/to/saved/raw_data_*.tar.gz -C data/
   ```

4. **데이터베이스 컨테이너 선기동**:
   ```bash
   # Docker Compose 사용 시
   docker compose up -d database
   # Podman Compose 사용 시
   podman-compose up -d --build --force-recreate database
   ```

5. **고속 데이터베이스 복원 실행**:
   ```bash
   ./db_restore.sh backups/accounting_db_YYYYmmdd_HHMMSS.dump
   ```
   - 복원 완료 후 `chunks` 테이블 행 수가 원본 `.meta`와 일치하는지 자동으로 확인됩니다.

6. **전체 스택 기동 및 준비성 프로브 검증**:
   ```bash
   # 전체 스택 실행
   ./install.sh

   # 준비성 프로브 확인
   curl -s http://localhost:8000/ready
   ```

---

## 4. 무비용 외부 소산 (Off-site Replication) 안내

운영 서버 자체의 물리적 장애에 대비하여 추가 비용 없이 백업본을 외부로 안전하게 복제하는 방법입니다.

### 관리자 PC 또는 사내 NAS로의 복제 (선택 사항)

관리자 개인 PC나 사내 NAS의 터미널에서 다음 명령을 실행하여 서버의 백업 디렉터리를 동기화할 수 있습니다:

```bash
# 관리자 PC 터미널에서 실행 예시
rsync -avz --progress appuser@<서버IP>:/path/to/rag_for_accounting/backups/ ./my_local_backups/
```

- 개인 계정 정보나 이메일 등록이 필요 없으며, 사내 네트워크 또는 SSH 키 기반 인증을 통해 안전하게 백업 덤프를 수신할 수 있습니다.
- 백업 덤프(`*.dump`)는 PostgreSQL 커스텀 압축 포맷(-Fc)으로 생성되므로 텍스트 대비 네트워크 대역폭 소모가 적습니다.

---

## 5. 정기 모의 훈련 및 점검 지침

- **분기별 복원 훈련 권장**: 분기 1회 스테이징 또는 로컬 개발 환경에서 최신 백업본을 이용해 복원을 수행하여 스크립트 정합성을 검증합니다.
- **로그 모니터링**: Crontab 등록 시 지정한 로그 파일(`/var/log/rag_backup.log`)의 크기와 백업 완료 여부를 주기적으로 점검합니다.
