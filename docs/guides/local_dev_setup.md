# 로컬 개발 셋업

> 작성일 2026-06-13. 패키지 매니저는 **uv** 고정.
> 루트의 `./install.sh`는 Docker Compose로 database + embedding + app을 모두 기동한다. app 컨테이너는 FastAPI API와 빌드된 React 프론트를 `:8000`에서 함께 서빙한다. 상태 점검은 `./check.sh`(무변경).
> 임베딩(KURE-v1)은 docker `embedding` 서비스(TEI 기성 이미지)로 분리 서빙되며, `EMBEDDING_SERVER_URL` 설정 시 `src/client`를 통해 위임하고 미설정 시 프로세스 내 로드(호스트 MPS)로 돈다.

## 1. 사전 요구
- Python 3.12+ (`.python-version` 참조)
- uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker / Docker Compose (pgvector PostgreSQL용)
- OpenAI API 키 (rewrite/evaluate/generate 노드용)

## 2. 의존성 설치
```bash
uv sync          # .venv 생성 + 의존성(dev 포함) 설치
```
> 모든 Python 실행은 `uv run ...`로 한다(예: `uv run pytest`, `uv run python -m src.main ...`).
> 기본 개발 경로는 Docker의 TEI 임베딩 서버를 사용한다. PDF 파싱 적재는 `uv sync --extra ingest`, `EMBEDDING_SERVER_URL` 없이 호스트 프로세스 안에서 KURE-v1을 직접 로드하는 경로는 `uv sync --extra local-embedding`으로 무거운 파서/모델 스택을 명시 설치한다.

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

> 기존 팀원 주의: 예전 `.env`에는 `POSTGRES_HOST=database`가 남아 있을 수 있다. `.env`는 개인 파일이라 템플릿(`.env.example`)이 `localhost`로 바뀌어도 자동 반영되지 않는다. 호스트에서 직접 실행한다면 `localhost`로 고쳐야 하며, 그대로 두면 `database` 호스트명 해석 실패로 DB 연결이 즉시 끊긴다.

> 모델·임계치의 기본값 정본은 `src/utils/config.py`다(EMBEDDING_MODEL, OPENAI_MODEL, RRF_K, TOP_K_RETRIEVAL ...). 리랭커(USE_RERANKER·RERANK_THRESHOLD·RERANK_MODEL)와 임베딩 실행 자원(EMBEDDING_DEVICE 등)은 `.env`로 override할 수 있다 — 키 목록은 `.env.example` 참조.

## 4. Docker 스택 기동
```bash
docker compose up -d --build
```
> DB 이미지(`db.Dockerfile`)는 pgvector 확장이 포함된 PostgreSQL을 빌드한다. `embedding`은 TEI로 KURE-v1을 서빙하고, `app`은 `http://localhost:8000`에서 API와 React를 함께 제공한다.

## 5. 실행 (진입점 `src/main.py`)
### 적재(ingest)
```bash
# 미리 빌드된 온톨로지 그래프(data/ontology/*.json) 전 챕터 적재
uv run python -m src.main ingest

# 컬렉션 비우고 재적재
uv run python -m src.main ingest --reset

# 단일 PDF: 파싱→온톨로지→청킹→적재 전체 경로
uv run python -m src.main ingest --pdf data/raw/제6장.pdf --standard-id gaap-ch6 --standard-type GAAP
```
> `docker-compose.yml`의 `./data/raw:/app/data/raw:ro` 마운트는 API PDF 서빙용이다. 문서 적재(`ingest`)는 `uv sync --extra ingest`를 설치한 쓰기 가능한 호스트 환경에서 실행하는 것을 전제로 한다.
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
```
> ⚠️ benchmark/통합 테스트는 `init_pool()` + 적재된 DB가 있어야 통과한다. DB 없이 `tests/integration` 직접 실행 시 검색 실패로 fail한다.

## 7. 컨테이너 안에서 실행
```bash
docker compose exec app uv run python -m src.main query "..."
```

---
관련 문서: [architecture_overview.md](../architecture/architecture_overview.md) · [func_interfaces.md](../architecture/func_interfaces.md) · `docs/guides/docker_setup_guide.md`
