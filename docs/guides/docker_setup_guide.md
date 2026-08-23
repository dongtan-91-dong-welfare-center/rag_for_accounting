# 프로젝트 Docker 환경 구성 및 검증 가이드

> Docker Compose는 `database`(pgvector), `embedding`(KURE-v1 TEI), `app`(FastAPI + React)을 한 번에 띄운다. 일반 사용자는 `./install.sh`로 설치·기동하고 `./check.sh`로 상태를 확인하면 된다.

## 1. 개요 및 목적

- **환경 격리**: 개발자별 호스트 환경 차이에 따른 Python·모델 의존성 충돌을 줄인다.
- **벡터 검색 데이터베이스**: pgvector 확장이 포함된 PostgreSQL 컨테이너를 구동한다.
- **임베딩 분리**: KURE-v1을 TEI 컨테이너로 서빙해 앱 컨테이너의 모델 로드를 줄인다.
- **통합 앱**: FastAPI API와 빌드된 React 프론트를 `http://localhost:8000`에서 함께 제공한다.

## 2. Docker 환경 실행 지침

일반 사용자는 아래 두 명령으로 충분하다.

```bash
./install.sh
./check.sh
```

수동으로 실행하려면 아래 단계를 따른다.

### 1단계: 컨테이너 빌드 및 백그라운드 실행
기존과 변경된 `pyproject.toml`과 `Dockerfile` 사항을 반영해야 하므로 반드시 갱신 빌드가 필요합니다.
```bash
docker compose up --build -d
```

서비스 구성은 다음과 같다.

| 서비스 | 컨테이너 | 역할 | 포트 |
|---|---|---|---|
| `database` | `accounting_db` | PostgreSQL + pgvector | `5432` |
| `embedding` | `accounting_embedding` | KURE-v1 TEI 임베딩 서버 | `8080` |
| `app` | `accounting_app` | FastAPI API + React 정적 파일 | `8000` |

### 2단계: 자동화된 인프라 환경 검증 테스트
인프라 검증은 `tests/utils/infra_check.py`의 `check_docker_infrastructure()`에 위임되어 있습니다. `tests/integration/conftest.py`의 세션 픽스처가 **통합 테스트 진입 전 자동으로 실행**하여 Docker 데몬·컨테이너 구동·`pgvector` 확장 로드를 점검하고, 문제가 있으면 통합 테스트를 건너뜁니다.

따라서 인프라 준비 상태는 `./check.sh` 또는 통합 테스트로 검증한다:
```bash
./check.sh
uv run python tests/run_tests.py --phase1-only
```

첫 실행에서는 `embedding` 서비스가 KURE-v1 모델을 다운로드한다. 이 단계는 몇 분 걸릴 수 있으며, 다운로드 후에는 `tei_cache` 볼륨을 재사용한다.

### 3단계: 컨테이너 쉘 접근 및 개발자 수동 활용 가이드
자동화된 테스트 이외에 직접 컨테이너에 접근하여 데이터베이스를 조회하거나 단위 작업을 수행해야 하는 경우,
아래와 같이 각 컨테이너 쉘에 접속하여 자유로운 개발 및 디버깅 작업을 진행할 수 있습니다.

#### App 컨테이너 (`accounting_app`) 내부 활동 
앱 환경에 진입하여 패키지를 조사하거나 코드를 디버깅할 때 사용합니다.
```bash
docker exec -it accounting_app bash

# 쉘 내부에서 가능한 개발자 작업 예시:
# 1. 컨테이너에 최종적으로 설치된 패키지 확인
uv pip list
# 2. 내부에서 별도로 파이썬 단위 테스트 직접 통과 여부 수행
pytest src/ingest/ontology/models.py
```

#### DB 컨테이너 (`accounting_db`) 조회
`psql` 도구를 사용하여 데이터베이스 쿼리를 직접 테스트하거나 데이터가 어떻게 적재되었는지 확인할 때 사용합니다.
```bash
# DB 마스터 계정으로 직통 쉘(psql) 열기
docker exec -it accounting_db psql -U accounting_user -d accounting_db

# psql 내부에서 가능한 작업 예시:
# 1. 적재된 청크/임베딩 테이블의 구조 및 행 수 점검
# 2. 단일 텍스트 청크나 임베딩 데이터를 대상으로 한 vector 쿼리 디버깅
```

---

## 4. 원문 PDF와 `PDF_DIR`

원문 PDF는 저장소에 포함하지 않는다. API의 `GET /documents/{document_id}/pdf`는 `PDF_DIR`에서 파일을 찾는다.

| 위치 | 의미 |
|---|---|
| 호스트 `data/raw_data` | 기본 개발 경로. 사용자가 직접 PDF를 둔다. |
| 컨테이너 `PDF_DIR` | 앱 컨테이너 내부에서 PDF를 찾는 경로다. |

Compose에서 PDF volume을 다른 위치로 마운트하면 `PDF_DIR`도 같은 위치로 맞춘다. 경로가 맞지 않으면 질의와 조항 표시는 되지만 PDF 보기 버튼은 404가 난다.

## 5. 트러블슈팅 — 의존성을 바꿨는데 컨테이너가 옛 버전을 쓸 때

**증상**: `pyproject.toml`에 패키지를 추가했거나 원격에서 받은 `uv.lock`이 바뀌었는데, 컨테이너 안에서는 여전히 이전 패키지 상태로 동작한다.

**원인**: 컨테이너의 가상환경(`/app/.venv`)은 빌드 시점에 고정된다. 로컬에서 `pyproject.toml`·`uv.lock`만 바꿔도 컨테이너 안까지는 자동으로 반영되지 않는다.

**대응**:
1. 로컬(호스트)에서 의존성을 갱신한다.
   ```bash
   uv add <새로운-패키지명>    # 신규 패키지가 필요할 때
   uv lock                   # 원격에서 pyproject.toml 변동사항만 받았을 때 동기화 목적
   ```
2. 컨테이너를 재빌드한다(필수) — 위 변경을 이미지 안 가상환경에 반영한다.
   ```bash
   docker compose up --build -d
   ```
