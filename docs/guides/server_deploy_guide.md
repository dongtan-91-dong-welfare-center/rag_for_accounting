# Rocky Linux 및 RHEL 서버 배포 가이드 (Podman 기준)

> Rocky Linux 8.8+ 및 RHEL 8+ 클라우드 가상 머신(VM) 환경에서 Podman 런타임을 기반으로 회계 RAG 시스템 컨테이너 스택을 안정적으로 구축하고 운영하는 절차를 설명합니다.

---

## 1. 개요 및 런타임 표준

### 1-1. 배경 및 목적
본 프로젝트는 개발 환경에서 Docker Desktop을 주로 활용하지만, Rocky Linux 및 RHEL 계열 클라우드 가상 머신은 배포판 표준 패키지 관리자를 통해 Podman을 기본 컨테이너 엔진으로 제공합니다. Docker를 별도로 설치할 경우 배포판 제공 패키지(`runc`, `podman` 등)와의 의존성 충돌이 발생할 수 있으므로, 서버 환경에서는 Podman 4.4+ 및 `podman-compose`를 기본 배포 경로로 규정합니다.

### 1-2. 배포 스택 구성
시스템은 세 가지 핵심 컨테이너로 구성됩니다:
1. `database`: pgvector 확장이 활성화된 PostgreSQL 16 벡터 데이터베이스.
2. `embedding`: KURE-v1(1024차원) 모델을 서빙하는 HuggingFace Text Embeddings Inference(TEI) CPU 컨테이너.
3. `app`: FastAPI 백엔드 API와 사전 빌드된 React 프론트엔드를 호스팅하는 애플리케이션 컨테이너.

---

## 2. 사전 요구사항 및 패키지 설치

### 2-1. EPEL 저장소 활성화 및 필수 패키지 설치
Rocky Linux 기본 AppStream 저장소에는 `podman-compose`가 포함되어 있지 않으므로 EPEL(Extra Packages for Enterprise Linux) 저장소를 먼저 활성화해야 합니다.

```bash
# EPEL 저장소 및 컨테이너 관리 도구 설치
sudo dnf install -y epel-release
sudo dnf install -y podman podman-compose curl git

# 설치 버전 및 정상 동작 확인
podman --version
podman-compose --version
```

### 2-2. Podman 루트리스(Rootless) 권한 및 비특권 포트 확인
Podman은 일반 사용자 권한으로 컨테이너를 구동하는 루트리스 모드를 기본 지원합니다.
루트리스 환경에서는 1024 미만의 특권 포트(예: 80, 443)를 기본적으로 컨테이너 호스트 포트로 직접 바인딩할 수 없습니다.

```bash
# 루트리스 동작 모드 확인 (true 반환 시 루트리스 구동 중)
podman info --format '{{.Host.Security.Rootless}}'

# 비특권 포트 시작 번호 확인 (기본값: 1024)
sysctl net.ipv4.ip_unprivileged_port_start
```

---

## 3. 포트 바인딩 및 방화벽 설계

### 3-1. 두 겹 방화벽 구조
클라우드 가상 머신 환경에서는 호스트 운영체제 내부 방화벽(`firewalld`)과 클라우드 플랫폼의 네트워크 접근 제어 그룹(ACG/Security Group)이 이중으로 트래픽을 통제합니다. 외부 접속을 정상화하려면 두 계층 모두에서 해당 포트가 개방되어 있어야 합니다.

### 3-2. 외부 공개 포트 전략
외부에서 웹 UI 및 API 서버에 접근할 수 있도록 다음 두 가지 포트 공개 전략 중 하나를 선택합니다:

1. **3000번 포트 권장 매핑 (`APP_HOST_PORT=3000`)**:
   - `근거:` 비특권 포트(>1024) 범위에 속하므로, 커널 파라미터 수정 없이 루트리스 Podman에서 즉시 기동할 수 있습니다. 또한 향후 앞단에 Nginx 리버스 프록시를 도입하여 80/443 포트로 전환할 때 포트 충돌이나 서비스 중단 없이 연계가 가능합니다.
2. **80번 특권 포트 직결 매핑 (`APP_HOST_PORT=80`)**:
   - 클라우드 방화벽 정책상 3000번이나 8000번을 열 수 없고 80번만 허용된 경우 적용합니다.
   - 단, 루트리스 환경에서 80번을 호스트 포트로 열기 위해서는 다음 커널 파라미터 설정이 선행되어야 합니다:
     ```bash
     sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80
     echo "net.ipv4.ip_unprivileged_port_start=80" | sudo tee -a /etc/sysctl.d/99-podman-ports.conf
     ```

### 3-3. 포트 및 바인딩 설정 원칙
포트 공개 범위를 수정할 때는 `docker-compose.yml`을 직접 수정하지 않고 반드시 `.env` 파일의 변수를 변경합니다.
`근거:` `podman-compose` 1.0.6 환경에서는 `.env` 파일에 기록된 값이 셸 인라인 환경변수보다 우선순위가 높으므로, 터미널 인라인 선언(`APP_HOST_PORT=3000 podman-compose up`) 대신 `.env` 파일을 직접 편집해야 설정이 누락 없이 적용됩니다.

```ini
# .env 파일 내 포트 및 바인딩 주소 설정 예시
DB_BIND_ADDR=127.0.0.1
DB_HOST_PORT=5432
EMBEDDING_BIND_ADDR=127.0.0.1
EMBEDDING_HOST_PORT=8080
APP_BIND_ADDR=0.0.0.0
APP_HOST_PORT=3000
```

호스트 방화벽에서 애플리케이션 접근 포트를 영구 허용합니다:

```bash
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --reload
```

---

## 4. SELinux 보안 정책 선조치

Rocky Linux와 RHEL은 강제 모드(Enforcing)의 SELinux가 기본 활성화되어 있습니다. 컨테이너가 호스트의 파일 시스템에 접근하려면 적절한 라벨 권한을 부여해야 합니다.

### 4-1. 원문 PDF 볼륨 바인드 마운트 (`:ro,z`)
앱 컨테이너가 호스트의 원문 PDF 디렉터리(`data/raw_data`)를 읽을 수 있도록 볼륨 정의에 `:ro,z` 플래그가 지정되어 있습니다.
`근거:` `:z` 플래그를 부여하지 않으면 컨테이너 내부 프로세스가 파일 시스템에 접근할 때 SELinux에 의해 접근이 차단되어 원문 PDF 뷰어 호출 시 404 및 권한 거부 오류가 발생합니다.

호스트의 PDF 디렉터리 권한을 사전에 정비합니다:

```bash
mkdir -p data/raw_data
chmod 755 data/raw_data
```

### 4-2. Nginx 리버스 프록시 네트워크 연결 허용
향후 앞단에 Nginx 웹 서버를 배치하여 내부 포트(`http://127.0.0.1:3000` 또는 `8000`)로 트래픽을 프록시 전달하는 경우, SELinux 기본 정책에 의해 아웃바운드 소켓 연결이 차단되어 `502 Bad Gateway` 오류가 발생합니다. 아래 명령으로 Nginx의 네트워크 연결 권한을 영구 허용해야 합니다:

```bash
sudo setsebool -P httpd_can_network_connect 1
```

---

## 5. TEI 임베딩 컨테이너 기동 안정화

### 5-1. 저사양 CPU 호스트 웜업 OOM 방지
`nlpai-lab/KURE-v1` 모델을 구동하는 TEI 컨테이너는 기동 시 배치 상한 크기의 더미 텐서를 연속 메모리로 할당하여 웜업을 수행합니다. RAM 16GB 이하의 저사양 가상 머신에서는 기본값(16384 또는 8192) 적용 시 OOM Killer(exit 137)에 의해 프로세스가 강제 종료되는 현상이 발생합니다.

본 프로젝트는 안전 우선 기본값으로 `TEI_MAX_BATCH_TOKENS=4096`을 기본 적용하였습니다:
- `TEI_MAX_BATCH_TOKENS=4096`: 웜업 메모리 피크를 억제하여 16GB RAM 환경에서도 재시작 루프 없이 즉시 기동을 보장합니다.
- `TEI_MAX_INPUT_LENGTH=4096`: TEI 기동 검증 규칙(`max_batch_tokens >= max_input_length`)을 통과하도록 명시하였습니다.
- `TEI_MAX_CLIENT_BATCH_SIZE=8`: 동시 요청 폭주 시의 메모리 급증을 방지합니다.

### 5-2. `podman-compose` 1.0.6 헬스체크 의존성 한계 및 대기 가드
`docker-compose.yml`에는 `app` 서비스가 `embedding`의 헬스체크 통과(`service_healthy`)를 대기하도록 정의되어 있으나, EPEL 8 저장소에 고정된 `podman-compose` 1.0.6은 `condition: service_healthy` 속성을 지원하지 않고 조용히 무시합니다.
따라서 컨테이너 기동 후 TEI 서버의 웜업 완료(`http://localhost:8080/health` 200 OK)를 명시적으로 기다리는 절차가 필수적입니다.

---

## 6. 설치 및 자동 배포 실행

### 6-1. `./install.sh`를 통한 표준 기동
저장소의 `./install.sh` 스크립트는 `scripts/container_runtime.sh`를 통해 시스템에 설치된 `podman-compose`를 자동으로 감지하며, TEI 웜업 완료 시점까지 최대 15분간 `/health` 엔드포인트를 능동적으로 폴링 대기합니다.

```bash
# 1. 저장소 클론 및 이동
git clone https://github.com/dongtan-91-dong-welfare-center/rag_for_accounting.git
cd rag_for_accounting

# 2. 실행 권한 부여 및 최초 실행 (초기 .env 파일 생성)
chmod +x install.sh deploy.sh check.sh db_dump.sh db_restore.sh
./install.sh
```

최초 실행 시 `.env.example`로부터 `.env` 파일이 생성됩니다. 생성된 `.env` 파일에서 `OPENAI_API_KEY`와 필요 포트를 입력한 후 다시 실행합니다:

```bash
# .env 파일 편집
vi .env

# 스택 빌드 및 기동 실행
./install.sh
```

### 6-2. 기동 상태 점검 (`./check.sh`)
스택 구동 후 인프라 및 API 응답 상태를 점검합니다:

```bash
./check.sh
```

출력 결과에서 `1. Required tools`, `2. Container runtime & containers`, `3. Service health endpoints` 항목이 모두 통과되었는지 확인합니다.

---

## 7. 데이터베이스 적재 및 원문 PDF 배치

### 7-1. DB 덤프 복원 (1순위 권장 경로)
새 서버 구축 시 임베딩 연산 부하를 피하고 데이터 일치성을 보장하기 위해 기존 환경의 덤프 파일 복원을 기본 경로로 채택합니다.
`근거:` 앱 컨테이너 내부에는 PDF 파싱 라이브러리(Docling 등)가 설치되어 있지 않으므로, 컨테이너 내부에서 `--pdf` 명령을 통한 실시간 파싱 적재는 불가능합니다.

```bash
# 원본 서버에서 생성된 dump 파일을 대상 서버로 전송받은 후 복원 실행
./db_restore.sh backups/accounting_db_latest.dump
```

복원 스크립트는 `chunks` 및 `chunks_morph` 테이블의 행 수와 유효성을 자동으로 검증합니다.

### 7-2. 원문 PDF 파일 배치
원문 PDF는 저작권 및 BYO(Bring Your Own Data) 원칙에 따라 DB 덤프에 포함되지 않습니다.
원본 서버의 PDF 파일들을 대상 서버의 `data/raw_data/` 디렉터리에 복사해야 조항 카드에서 원문 보기가 동작합니다:

```bash
# 호스트 디렉터리에 PDF 파일 배치
ls -lh data/raw_data/
# 예: 제6장_금융자산(Ⅰ)_유가증권.pdf 또는 gaap-ch6.pdf
```

---

## 8. Nginx 리버스 프록시 구성 및 운영 관리

### 8-1. Nginx 설치 및 리버스 프록시 등록
외부 브라우저 요청을 표준 80번 포트로 수신하여 내부 애플리케이션 포트(`http://127.0.0.1:3000`)로 전달합니다.

```bash
sudo dnf install -y nginx
```

`/etc/nginx/conf.d/rag_accounting.conf` 파일을 생성하고 다음 설정을 반영합니다:

```nginx
server {
    listen 80;
    server_name _;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

설정 검증 및 서비스를 시작합니다:

```bash
# SELinux 아웃바운드 네트워크 연결 허용
sudo setsebool -P httpd_can_network_connect 1

# 문법 검증 및 서비스 구동
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx

# 80번 방화벽 개방
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --reload
```

### 8-2. 배포본 최신화 및 롤백 절차
운영 환경에서 신규 릴리즈를 반영하거나 롤백할 때는 변경 범위에 따라 다음 절차를 따릅니다:

#### 1) 일반 배포: 소스 코드 및 프론트엔드 변경 시 (약 10초 내외)
파이썬 백엔드(`src/`) 또는 프론트엔드(`frontend/`) 코드만 수정된 경우, `database` 및 `embedding` 컨테이너를 가동 상태로 유지한 채 `app` 컨테이너만 증분 재배포합니다. TEI 임베딩 모델 웜업(2~3분) 대기가 생략되어 무중단에 가까운 빠른 배포가 가능합니다:

```bash
# 1. 최신 코드 갱신
git pull origin main

# 2. app 컨테이너 단독 증분 빌드 및 교체 배포
./deploy.sh

# 3. 헬스체크 및 무결성 검증
./check.sh
```

패키지 캐시 오염 등으로 클린 재빌드가 필요한 경우에는 `--no-cache` 옵션을 사용할 수 있습니다:

```bash
./deploy.sh --no-cache
```

#### 2) 인프라 변경 배포: DB 스키마·인프라 설정 변경 시
`docker-compose.yml`, TEI 파라미터, PostgreSQL 설정 또는 DDL 마이그레이션이 포함된 경우 전체 스택을 재기동합니다:

```bash
# 1. 최신 코드 갱신
git pull origin main

# 2. 전체 스택 재빌드 및 기동
./install.sh

# 3. 헬스체크 및 무결성 검증
./check.sh
```

#### 3) 장애 발생 시 롤백 절차
```bash
# 직전 안정 커밋 또는 릴리즈 태그로 체크아웃
git checkout <PREVIOUS_STABLE_TAG_OR_COMMIT>

# 소스 코드 변경에 대한 롤백 시
./deploy.sh

# 인프라 변경이 포함된 롤백 시
./install.sh

# 롤백 후 상태 검증
./check.sh
```

---

## 9. 자주 발생하는 결함 및 문제 해결 (Troubleshooting)

| 증상 | 발생 원인 | 해결 방법 |
|---|---|---|
| 브라우저에서 사이트 연결 거부 또는 타임아웃 | 호스트 `firewalld` 또는 클라우드 ACG 방화벽 차단 | `sudo firewall-cmd --list-ports`와 클라우드 콘솔의 인바운드 보안 규칙에서 포트(3000 또는 80)를 개방합니다. |
| `embedding` 컨테이너가 exit 137로 계속 재시작함 | TEI 기동 웜업 중 메모리 부족(OOM) | `.env` 파일의 `TEI_MAX_BATCH_TOKENS=4096` 설정을 확인하고 재기동합니다. |
| 소스 코드 수정 후 재배포 시 3~5분의 긴 웜업 대기 발생 | 전체 스택을 재기동하는 `./install.sh` 실행 | `embedding` 컨테이너를 재시작하지 않고 `app`만 증분 교체하는 `./deploy.sh`를 사용합니다. |
| 검색 및 답변은 정상이나 PDF 보기 클릭 시 404 오류 | 원문 PDF 미배치 또는 SELinux 마운트 차단 | `data/raw_data/` 디렉터리에 해당 PDF 파일이 존재하는지 확인하고, 볼륨 마운트 옵션의 `:ro,z` 설정을 확인합니다. |
| Nginx 연결 시 `502 Bad Gateway` 오류 | SELinux가 Nginx의 내부 포트 접근 차단 | `sudo setsebool -P httpd_can_network_connect 1` 명령을 실행합니다. |
| 컨테이너 기동 직후 앱에서 `Connection refused` 발생 | TEI 웜업 완료 전 app 조기 기동 | `./install.sh`를 통해 기동하거나 `curl http://localhost:8080/health`가 200 OK를 반환할 때까지 대기합니다. |
| 인라인 환경변수로 지정한 포트가 반영되지 않음 | `podman-compose` 1.0.6의 우선순위 동작 특성 | 셸 환경변수 대신 `.env` 파일의 `APP_HOST_PORT` 값을 직접 수정합니다. |

---

## 10. 부록: Docker 환경에서의 배포

호스트 서버가 이미 Docker Engine 및 Docker Compose v2를 운용 중인 경우, 본 가이드의 Podman 명령어는 동일하게 Docker로 대체할 수 있습니다.
저장소의 `./install.sh`, `./deploy.sh` 및 `./check.sh` 스크립트는 `docker compose`를 우선적으로 자동 판별하므로 수동 명령어 변경 없이 동일한 배포 인터페이스를 제공합니다:

```bash
# Docker 환경에서의 전체 스택 초기 기동
./install.sh

# Docker 환경에서의 앱 코드 증분 재배포
./deploy.sh

# 상태 점검
./check.sh
```
