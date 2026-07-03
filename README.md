# 회계 기준서 RAG 시스템

이 프로젝트는 회계 기준서에 대한 질의응답을 위해 설계된 RAG(Retrieval-Augmented Generation) 시스템입니다. LangGraph를 활용한 에이전트 워크플로우를 통해 질문 분석, 문서 검색, 답변 생성 과정을 자동화합니다.

> **목적**: 본 프로젝트는 비영리·공익 목적으로 개발되었으며, 상업적 용도로 사용할 수 없습니다.

## 🚀 주요 기능

- **에이전트 워크플로우**: 질문 재작성 → 문서 검색 → 품질 평가 → 답변 생성의 4단계 파이프라인
- **하이브리드 검색**: Dense(의미) 및 Sparse(키워드) 벡터를 결합한 고성능 검색
- **고급 RAG 기법**: 컨텍스트얼 리트리벌, 리랭킹 등 적용
- **구조화된 답변**: Pydantic을 활용한 정제된 답변 출력

## 🛠️ 설치 및 실행

### 1. 환경 설정 및 의존성 설정

프로젝트 루트 디렉토리에서 가상 환경을 생성하고 활성화합니다.
uv 사용을 권장합니다.

```bash
uv sync
```

### 2. 데이터베이스 기동

pgvector 확장이 포함된 PostgreSQL을 docker compose로 기동합니다.
접속 정보는 `.env`(템플릿: `.env.example`)에서 읽습니다.

```bash
docker compose up -d database
```

### 3. 실행

진입점 `src/main.py`는 적재(`ingest`)와 질의(`query`) 두 경로를 제공합니다.

#### 문서 적재 (ingest)

미리 빌드된 온톨로지 그래프(`data/ontology/*.json`)를 청킹·임베딩하여 pgvector에 적재합니다.

> 📌 데이터 정책: `data/`(회계기준 원문·파생)는 **BYO(Bring Your Own)** 방향으로 전환 중입니다 — 배경·근거는 [docs/decisions/0001](docs/decisions/0001-byo-corpus-kgaap.md) 참조.

```bash
# data/ontology 전체 장을 적재 (검색기와 동일한 chunks 테이블에 저장)
uv run python -m src.main ingest

# 컬렉션을 비우고 새로 적재
uv run python -m src.main ingest --reset

# 단일 PDF에서 파싱 → 온톨로지 빌드 → 청킹·적재까지 전체 경로
uv run python -m src.main ingest --pdf data/raw/제6장.pdf --standard-id gaap-ch6 --standard-type GAAP
```

#### 질의 (query)

적재된 데이터를 기반으로 워크플로(rewrite → search → rerank → evaluate → generate)를 실행해 답변과 인용을 출력합니다.

```bash
uv run python -m src.main query "금융자산의 최초 인식 시점은?"
uv run python -m src.main query "리스 회계처리" --standard GAAP
```

> 컨테이너(`app`) 안에서 실행하려면 `docker compose exec app uv run python -m src.main ...` 형태로 호출합니다.

### 4. (선택) LangSmith 트레이싱

케이스별로 파이프라인 노드 흐름·입출력·지연을 추적하려면 LangSmith 트레이싱을 켤 수 있습니다(개발자 디버깅용, 기본 OFF). `.env`에 아래 환경변수를 설정합니다.

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-your-key-here   # 시크릿 — 레포에 커밋 금지
LANGCHAIN_PROJECT=rag-for-accounting # 트레이스가 모일 프로젝트명(선택)
```

- 활성화하면 LangGraph 노드(rewrite→search→rerank→evaluate→generate)와 CRAG 루프·HIL interrupt 분기가 노드 단위 트레이스로 기록됩니다.
- 벤치마크 측정 경로는 각 트레이스에 케이스 식별 메타데이터(`case_id`, `gold`)를 부착하므로, LangSmith UI에서 케이스별 필터링이 가능합니다.
- 키가 없거나 `LANGCHAIN_TRACING_V2`가 `true`가 아니면 트레이싱은 비활성이며 파이프라인은 동일하게 동작합니다.
- ⚠️ 활성화 시 질의·LLM 답변·검색 컨텍스트가 외부 SaaS(LangSmith)로 전송됩니다.

## 📂 프로젝트 구조

전체 문서 인덱스는 [docs/README.md](docs/README.md)에서 시작하세요. **현행 코드 모듈맵**은 [docs/architecture/architecture_overview.md](docs/architecture/architecture_overview.md)의 "모듈 지도(실제 구조)"를 참조합니다 — 단일 출처(SSoT)를 위해 구조를 여기서 중복 기재하지 않습니다.

## 📖 문서 학습

RAG 기술에 대한 자세한 학습 자료는 `docs/reference/rag_study.md` 파일에 정리되어 있습니다.

## 📝 TODO

현재 진행 중인 작업은 `task-board.html` 파일에 정리되어 있습니다.


## 📚 데이터 출처

본 프로젝트에서 사용하는 회계기준 원문은 한국회계기준원이 공개한 자료입니다.

> 출처: 한국회계기준원 http://www.kasb.or.kr Copyright ©KAI all rights reserved.

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.