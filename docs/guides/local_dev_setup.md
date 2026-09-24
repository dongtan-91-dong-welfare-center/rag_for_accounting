# 로컬 개발 셋업 가이드

본 문서는 로컬 개발 환경 구축을 위한 의존성 설치, Docker 서비스 기동 및 ingest·query 파이프라인 실행 절차를 설명합니다.

## 1. 사전 요구
- Python 3.12+ (`.python-version` 참조)
- uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker 및 Docker Compose (PostgreSQL, 임베딩 서버, 통합 앱 실행용)
- OpenAI API 키 (rewrite, evaluate, generate 노드용)

### 권장 하드웨어

| 용도 | 최소/권장 |
|---|---|
| 기본 질의·API 개발 | CPU 4코어 이상, RAM 16GB 이상 |
| Docker 통합 실행 | Docker Desktop 메모리 8GB 이상 할당 권장 |
| 대량 적재 | RAM 24GB 이상 권장. 임베딩 배치와 Docling 파싱이 메모리를 많이 쓴다. |
| 로컬 임베딩 직접 실행 | Apple Silicon MPS 또는 CUDA GPU가 있으면 유리하다. 없으면 TEI CPU 컨테이너를 사용한다. |
| 리랭커 사용 | `BAAI/bge-reranker-v2-m3` 모델 캐시와 메모리 여유가 필요하다. 기본은 OFF다. |

처음 실행 시 KURE-v1 모델 다운로드 때문에 임베딩 서버 준비가 몇 분 걸릴 수 있습니다. `./check.sh` 스크립트는 이 상태를 감안하여 헬스체크를 수행합니다.

## 2. 의존성 설치
```bash
uv sync          # .venv 생성 및 기본 개발 의존성 설치
```
> 모든 Python 실행은 `uv run ...` 명령으로 수행합니다 (예: `uv run pytest`, `uv run python -m src.main ...`).
>
> 기본 설치는 가볍게 유지됩니다: 임베딩 연산은 Docker의 TEI 컨테이너에 위임하며, 무거운 PDF 파싱 라이브러리(Docling)나 로컬 임베딩 의존성은 제외되어 있습니다. 작업 목적에 따라 다음 추가 옵션을 설치합니다:
> - 원본 PDF를 직접 파싱하여 적재하는 경우: `uv sync --extra ingest`
> - Docker 임베딩 서버 없이 호스트 머신에서 KURE-v1을 직접 구동하는 경우: `uv sync --extra local-embedding`
>
> 전체 단위 테스트를 수행하려면 파싱 라이브러리가 필요하므로 `uv sync --extra ingest && uv run pytest` 순서로 실행합니다. 이 옵션 없이 기본 설치만으로 테스트를 실행하면 파싱 모듈 7건이 `ModuleNotFoundError: docling_core`로 실패합니다.

## 3. 환경 변수
```bash
cp .env.example .env
# .env 편집: OPENAI_API_KEY, POSTGRES_USER/PASSWORD/DB 등
```
주요 키:

| 키 | 용도 |
|---|---|
| `OPENAI_API_KEY` | LLM 노드 |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | DB 접속 |
| `POSTGRES_HOST` / `POSTGRES_PORT` | 연결 대상 |

> 모델명 및 임계값 기본값의 정본(SSoT)은 `src/utils/config.py`입니다 (`EMBEDDING_MODEL`, `OPENAI_MODEL`, `RRF_K`, `TOP_K_RETRIEVAL` 등). 리랭커 설정과 임베딩 실행 자원은 `.env`로 덮어쓸 수 있으며, 상세 키 목록은 `.env.example`을 참조합니다.

## 4. Docker 스택 기동
```bash
docker compose up -d --build
```
> DB 이미지(`db.Dockerfile`)는 pgvector 확장이 포함된 PostgreSQL을 빌드한다. `embedding`은 TEI로 KURE-v1을 서빙하고, `app`은 `http://localhost:8000`에서 API와 React를 함께 제공한다.
>
> 원문 PDF 조회를 Docker 앱에서 쓰려면 컨테이너의 `PDF_DIR`과 volume mount가 같은 위치를 봐야 한다. 현행 코드 기본값은 `data/raw_data`다. Compose에서 다른 경로를 마운트하면 `.env` 또는 compose 환경변수에 `PDF_DIR`을 맞춘다.

## 5. 실행 (진입점 `src/main.py`)
### 적재(ingest)
```bash
# 미리 빌드된 온톨로지 그래프(data/ontology/*.json) 전 챕터 적재
uv run python -m src.main ingest

# 컬렉션 비우고 재적재
uv run python -m src.main ingest --reset

# 단일 PDF: 파싱→온톨로지→청킹→적재 전체 경로
uv run python -m src.main ingest --pdf data/raw_data/제6장.pdf --standard-id gaap-ch6 --standard-type GAAP
```
> `docker-compose.yml`의 PDF 마운트는 API PDF 서빙용이다. 현행 `PDF_DIR` 기본값은 `data/raw_data`이며, 문서 적재(`ingest`)는 `uv sync --extra ingest`를 설치한 쓰기 가능한 호스트 환경에서 실행하는 것을 전제로 한다.
### 질의(query)
```bash
uv run python -m src.main query "금융자산의 최초 인식 시점은?"
uv run python -m src.main query "리스 회계처리" --standard GAAP
```
> HIL interrupt 발생 시 대화형으로 승인/재작성 입력. 비대화형(파이프) 환경은 자동 승인.

### API 서버(FastAPI)
컨테이너 기본 경로에서는 `app` 서비스가 이미 `http://localhost:8000`에서 API와 React를 함께 서빙한다.

호스트에서 API만 직접 실행하려면 아래처럼 띄운다.
```bash
uv run uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```
> ⚠️ **단일 워커 전제.** HIL 체크포인터가 프로세스-로컬 MemorySaver라서 `--workers N`으로 늘리면 `/resume`이 다른 워커로 라우팅돼 세션을 찾지 못한다(404). 서버 재시작 시 진행 중 HIL 세션도 소실된다. 영속 체크포인터(PostgresSaver) 전환은 #209.
>
> OpenAPI 문서는 http://localhost:8000/docs — 응답 계약의 정본은 `src/api/schemas.py`. CORS 허용 origin은 `API_CORS_ORIGINS`(`.env.example` 참조)로 override.

### React 개발 서버
컨테이너 통합 앱이 아닌 Vite dev 서버로 프론트를 개발할 때만 실행한다. `frontend/vite.config.ts`가 `/query`, `/resume`, `/documents`를 `localhost:8000`으로 프록시한다.
```bash
cd frontend
npm install
npm run dev
```

## 6. 테스트
마커 3단계 (`pyproject.toml`):

| 마커 | 의미 | 실행 |
|---|---|---|
| `unit` | 외부 의존성 없는 함수 논리 (Phase 0) | `uv run pytest -m unit` |
| `system` | 가짜 데이터 기반 예외/규격 (Phase 1, Fast Fail) | `uv run pytest -m system` |
| `benchmark` | 정답셋 기반 답변 품질 (Phase 2, **라이브 DB·LLM 필요**) | `uv run pytest -m benchmark` |

```bash
uv run pytest tests/unit -q          # 단위 전체 (현재 276 passed)
uv run pytest -m system -q           # 시스템 (현재 34 passed)
uv run python tests/run_tests.py     # 통합 러너
./check.sh                           # Docker 통합 앱/DB/임베딩 상태 점검
```
> ⚠️ benchmark/통합 테스트는 `init_pool()` + 적재된 DB가 있어야 통과한다. DB 없이 `tests/integration` 직접 실행 시 검색 실패로 fail한다.

## 7. 컨테이너 안에서 실행
```bash
docker compose exec app uv run python -m src.main query "..."
```

---
관련 문서: [ARCHITECTURE.md](../ARCHITECTURE.md) · [func_interfaces.md](../func_interfaces.md) · [docker_setup_guide.md](docker_setup_guide.md)
