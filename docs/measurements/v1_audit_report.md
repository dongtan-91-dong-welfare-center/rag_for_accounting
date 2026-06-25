# v1.0 전체 감사 보고서 (FUNC-001~009)

> 기준: `origin/dev` ≡ `test/chunking-search-integration`(동일선상) · 작성일 2026-06-13 (D-1)
> 방법: FUNC별·프로덕션 차원별 병렬 코드/테스트 감사 + 단위/시스템/통합 테스트 실측 + 적대적 완결성 비평

---

## 0. 종합 판정 — 조건부 병합 가능 (ready_with_minor_gaps)

9개 FUNC 코어 로직은 실제 구현되어 있고 단위 테스트 276 passed로 회귀가 없습니다. **컴파일/런타임을 차단하는 하드 블로커는 없습니다.** 병합 전에 처리할 릴리즈 게이트는 1건입니다.

| 게이트 | 내용 | 권고 |
|---|---|---|
| 🔴 라이브 E2E 미검증 | 단위/통합 테스트 전부 mock(임베딩·LLM·리랭커). 실 DB·실 LLM ingest→query 1회 관통 증거 없음. `OPENAI_MODEL='gpt-5.4-mini'` 유효성 미확인 | 병합 직전 1회 라이브 스모크(1개 챕터 ingest → query 1건). 모델 무효 시 즉시 Blocker 승격 |

> **저작권 데이터(과거 #102)**: 기준서 원문·파생 데이터가 PUBLIC git에 추적 중이나, **회계기준원(KASB) 사용 허가 확보** → 게이트 아님(#102 closed가 정상, 재오픈 불필요).

### FUNC 상태 요약

| FUNC | 영역 | 구현 | 테스트 | 판정 |
|---|---|---|---|---|
| 001 | 파싱(Docling) | 핵심 완성(레이아웃 후처리·마커병합·표 페이지걸침) | 단위 6/8, 2건 @skip(실 PDF) | 🟡 |
| 002 | 청킹/온톨로지 | 4단계 파이프라인 완성, 33개 챕터 그래프 | 단위 58 + 통합 4 (고아·dangling 0) | 🟢 |
| 003 | 인덱싱(임베딩·pgvector) | KURE-v1→HNSW, dense+sparse | 단위 23 + 통합 4 | 🟢 |
| 004 | 질의 재구성 | classify + hyde/decompose/stepback + HIL | 단위 44 + 계약 2 | 🟡 |
| 005 | 하이브리드 검색 | dense/sparse 독립장애 + RRF(k=60) | 단위 19 + bridge 6 | 🟡 |
| 006 | 리랭킹 | CrossEncoder 배치 + USE_RERANKER 게이트 | 단위 14 + 통합 6 (전부 mock) | 🟡 |
| 007 | 적합성 평가(CRAG) | EV-301/302/303 자가검증 | 단위 27 + 라우팅 통합 | 🟢 |
| 008 | 답변·인용 생성 | PydanticAI + [n] 인용 추출 | 단위 15 | 🟢 |
| 009 | 워크플로우 제어 | StateGraph + 조건부 라우팅 3종 + CRAG/HIL | 단위 70+ | 🟡 |

🟡 사유: 001=실 PDF 검증 부재, 004=silent LLM 실패, 005=한국어 형태소 미지원·GIN 없음, 006=실모델 미검증, 009=CM-002 오분류/TimeoutError 미처리.

### 테스트 실측 (2026-06-13)

| 계층 | 결과 | 비고 |
|---|---|---|
| 단위(unit) | **276 passed, 5 skipped** | 견고. 단 전부 mock |
| 시스템(system, fast-fail) | **34 passed, 323 deselected** | 가짜 데이터 예외/규격 검증 |
| 통합(integration) | **28 failed, 48 passed** | 라이브 DB·적재 부재로 benchmark_compliance 전패(`init_pool` 미호출). NFR-002 정확도 **미측정** |

---

## 1. Phase 2 — v1.0 갭 분석 (심각도/공수)

공수: S(≤0.5d) / M(0.5~1.5d) / L(1.5~3d) / XL(3d+)

### 🔴 릴리즈 게이트 (병합 전 결정)

| # | 항목 | FUNC | 공수 | 근거 |
|---|---|---|---|---|
| G2 | 실데이터 E2E + OPENAI_MODEL 라이브 미검증 | 001·003·005·006·007·008·009 | M | 전 테스트 mock, `config.py:13` gpt-5.4-mini |

> ~~G1 저작권 데이터~~ — 회계기준원(KASB) 허가 확보로 해소. data/ 추적은 의도된 상태.

### 🟠 Major (병합 후 fast-follow — 운영 신뢰도 직결)

| # | 항목 | FUNC | 공수 | 근거 |
|---|---|---|---|---|
| M1 | search()가 CM-002(임베딩 일시장애)를 SE-103처럼 처리 → CRAG 재시도 누락 | 005·009 | M | `searcher.py:190` embed_query가 try 밖, `workflow.py:232` AccountingRAGError 포획→needs_reretrieval=False |
| M2 | rewrite LLM 실패 silent (4개 호출부, error_log·로깅 부재) | 004 | M | `rewrite.py:69,106,126,146` bare except + `!TODO` |
| M3 | DB 인프라 AGE 잔재 (db.Dockerfile/compose/.env/infra_check) — 결정과 모순 + 통합테스트 부당 skip(#126) | infra | M | `db.Dockerfile:30` git clone age, `docker-compose.yml:30` shared_preload_libraries=age |
| M4 | run_workflow/resume_workflow TimeoutError 미처리 재전파(구조화 반환 계약 위반) | 009 | M | `workflow.py:502-507,534` except TimeoutError: raise (main.py 핸들러 없음→CLI 크래시) |
| M5 | ParsedDocument 이원 정의(parser_dtos dataclass ↔ schemas Pydantic) | 001 | M | `parser_dtos.py:67` vs `schemas.py:30` |
| M6 | CI/자동화 파이프라인 부재(.github/workflows 없음) | infra | L | `.github/` 디렉터리 없음 |
| M7 | index_documents 부분실패 시 손실 청크 복구 신호 부재 | 003 | M | IX-201 스킵 시 부분 커밋, 재적재 훅 없음 |
| M8 | 리랭커 import-time 모델 로드 실패 graceful fallback 미검증 | 006 | M | CrossEncoder 모듈 로드 시점 의존 |

### 🟡 Minor (정리/개선)

| # | 항목 | FUNC | 공수 |
|---|---|---|---|
| m1 | skip 스텁 테스트 6건 정리 | 001·002 | S |
| m2 | rewrite 이중 예외처리 + error_logs timestamp 공백 | 004·009 | S |
| m3 | rerank()/evaluate() needs_reretrieval 명시 + reranker.py:55 TODO 정리 | 006·007 | S |
| m4 | handle_node_errors 전 노드 일관 적용 + evaluation=None 라우팅 명시 | 009 | M |
| m5 | metadata_filter SQL 안전성 문서화(현행 psycopg 파라미터 바인딩으로 주입 위험 낮음 — 검토/명문화 수준) | 003·005 | S |

### 정정 (감사 과정의 과장 시정)
- **AGE 제거**: src/ Python 코드는 클린(✅). 단 DB 인프라(db.Dockerfile/docker-compose/.env.example/infra_check.py)는 여전히 AGE 빌드·로드 → M3로 분류.
- **Dense 인덱스**: HNSW 인덱스 생성 코드 존재(`vector_store.py:62`) ✅ — 누락 아님.
- **SQL injection**: 파라미터 바인딩 사용으로 실제 위험 낮음 → m5(문서화)로 강등.

---

## 2. Phase 3 — 프로덕션 로드맵 (v1.0 이후)

### 관찰성 (Observability)
- [high] 구조화 로깅(JSON Lines) 도입 — 현재 text formatter만
- [high] 요청 단위 trace_id 전파 — thread_id는 HIL 전용, 전 경로 단일 trace 부재
- [high] 메트릭 수집 — `logger.py`의 log_execution_time 스텁 완성
- [med] LLM 토큰/비용 추적 — OpenAI usage 미기록
- [low] LangSmith 트레이싱 연동 — 의존성 선언만 있고 import 0건

### 에러 핸들링·복구
- [med] `is_retryable` 메타데이터 활성화 — 현재 dead code, 재시도 라우팅에 연결
- [med] error_logs 무한 증가 가드 — TTL/상한/회전 없이 MemorySaver 누적
- [med] index_documents 부분실패 dead-letter/재시도 훅(M7)
- [low] CRAG rewrite_count 재진입 전략 확정(동일 재시도 vs hyde→decompose→stepback 에스컬레이션)

### 성능·부하
- [high] pgvector HNSW 인덱싱 성능 벤치마크 (#98)
- [high] 대량 적재 OOM 완화 검증 (#117, KURE-v1 CPU 프로파일)
- [med] 한국어 형태소 sparse 검색 (#81, pg_bigm/사전 토큰화) — 현재 `to_tsvector('simple')` + GIN 인덱스 없음(매 질의 풀스캔)
- [med] RRF k 튜닝 벤치마크 (#99)
- [med] 연결풀 고갈 가드 — getconn 타임아웃 없음(max_size=10)
- [med] OpenAI 클라이언트 timeout/retry — step_timeout(30s) < API 기본(60s) 불일치

### 배포 인프라
- [med] DB 스키마 마이그레이션 도구(Alembic 등) — 현재 _ensure_collection 동적 생성만
- [med] DB 백업·복구·DR 절차
- [med] Docker 멀티스테이지 빌드 — 프로덕션 이미지에 dev 의존성(pytest) 포함
- [med] 헬스체크/준비성 프로브 (docker-compose)
- [low] 이미지 태그 버전 고정
- [low] v1.1 패키지화 + 로컬 MCP 서버 BYO-corpus (#103)

---

## 3. 기존 이슈와의 연계

이미 추적 중(open): #38(NFR-001), #81(한국어 sparse), #96(NFR-002), #98(인덱싱 벤치), #99(RRF k), #101(온톨로지 6/20), #103(v1.1 패키지), #104(HIL 벤치), #117(OOM), #126(AGE infra_check).

신규 발행 후보(net-new): G2·M1·M2·M4·M5·M6·M7·M8. (M3는 #126 확장 코멘트로 보강)
저작권(구 G1)은 회계기준원 허가 확보로 제외.
