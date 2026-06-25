# 로컬 개발 셋업

> 작성일 2026-06-13. 패키지 매니저는 **uv** 고정.

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

> ⚠️ `.env.example`에 남아있는 `AGE_GRAPH_NAME` 등 AGE 레거시 키는 v1.0에서 불필요(#126, 정리 예정).
> 모델·임계치 등은 `.env`가 아니라 `src/utils/config.py` 상수로 관리(EMBEDDING_MODEL, OPENAI_MODEL, RRF_K, TOP_K_RETRIEVAL, USE_RERANKER ...).

## 4. 데이터베이스 기동
```bash
docker compose up -d database
```
> 현재 DB 이미지(`db.Dockerfile`)는 pgvector + (레거시) Apache AGE를 빌드한다. AGE 잔재 제거는 #126 진행 중.

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
### 질의(query)
```bash
uv run python -m src.main query "금융자산의 최초 인식 시점은?"
uv run python -m src.main query "리스 회계처리" --standard GAAP
```
> HIL interrupt 발생 시 대화형으로 승인/재작성 입력. 비대화형(파이프) 환경은 자동 승인.

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
