# FUNC 인터페이스 명세 (FUNC-001~009)

본 문서는 회계 기준서 RAG 시스템 v1.0 파이프라인을 구성하는 각 기능(FUNC-001부터 FUNC-009까지)의 세부 역할, 진입점 함수, 입출력 계약 및 에러 코드를 정의합니다.

데이터 타입과 상태 스키마의 단일 진실 공급원(SSoT)은 [src/models/schemas.py](../src/models/schemas.py)와 [src/models/state.py](../src/models/state.py)입니다.

> **주요 개념 및 약어**: HNSW(근사최근접 벡터 인덱스), tsvector(PostgreSQL 전문검색 토큰), upsert(충돌 시 갱신, 부재 시 삽입). 시스템 공통 용어(조항, RRF, HIL, CRAG) 및 파이프라인 전체 흐름은 [전체 아키텍처](ARCHITECTURE.md)를 참조합니다.

---

## FUNC-001: 문서 파싱 (`src/ingest/parse/`)
사용자가 제공한 PDF 파일 1개를 입력받아 Docling 엔진으로 텍스트와 표를 추출합니다. 페이지 내부의 읽기 순서를 사람이 읽는 자연스러운 순서(위에서 아래, 왼쪽에서 오른쪽)로 재정렬한 뒤 정형화된 마크다운 문서(`ParsedDocument`)로 반환합니다. `DoclingParser().parse(path)`를 진입점으로 사용합니다.

## FUNC-002: 청킹 및 온톨로지 빌드 (`src/ingest/ontology/`)
마크다운 문서를 장·절·소절(Standard/Section/Subsection) 계층 구조로 구조화하고, 조항 간의 상호 참조(REFERENCES 등) 관계를 정규식과 LLM을 결합하여 연결한 뒤, 해당 구조를 바탕으로 검색 가능한 청크 단위로 분할합니다.
`build_graph(md_path, standard_id, standard_type)`로 그래프 구조를 생성하고, `chunk_graph(graph, source_path)`로 청크를 추출합니다. 문서 구조를 파악하지 못하면 OT-103 에러를 발생시킵니다.

## FUNC-003: 인덱싱 (`src/db/vector_store.py`, `src/clients/embedding.py`)
온톨로지 청커가 분할한 청크 리스트(`list[RetrievedChunk]`)를 받아 KURE-v1(1024차원) 임베딩 벡터를 생성하고, PostgreSQL pgvector의 `chunks` 테이블에 upsert 방식으로 적재하여 `IndexingResult`를 반환합니다.
청크의 결정적 식별자(`chunk_id`)를 기준으로 중복 적재를 멱등하게 처리하며, 임베딩 토큰 한도를 초과하면 IX-201 에러를 기록하고 해당 청크를 건너뜁니다. 데이터베이스 연결이나 쿼리 실행에 실패하면 SE-102를 발생시킵니다. `index_documents(chunks, collection)` 함수로 진입합니다.

## FUNC-004: 질의 재구성 (`src/agent/nodes/rewrite.py`)
사용자 질의가 회계 관련 질문인지 먼저 판별하고, 비회계 질의인 경우 파이프라인을 조기 종료합니다.
회계 질문인 경우 질의 특성에 따라 hyde(가상 답변 생성), decompose(하위 질문 분해), stepback(일반 원칙 추상화) 중 가장 적절한 전략을 선택하여 검색용 쿼리를 생성합니다. LLM 호출이 실패하면 CM-002를 기록하고 사용자의 원문 쿼리로 폴백합니다. `rewrite_query(state)`를 진입점으로 사용합니다.

## FUNC-005: 하이브리드 검색 (`src/retrieval/searcher.py`)
pgvector 코사인 유사도 기반 Dense 검색과 PostgreSQL 전문검색(Full-text search) 기반 Sparse 검색을 각각 독립적으로 실행한 뒤, 상호 순위 융합(RRF, k=60) 알고리즘으로 병합합니다. 한쪽 검색 채널에 장애가 발생해도 다른 채널의 결과로 파이프라인을 지속하며, 검색 결과가 0건이면 top_k를 확장하여 재탐색을 시도합니다. 그럼에도 결과가 없으면 SE-103을 발생시킵니다. `search_chunks(...)`를 진입점으로 사용합니다.

## FUNC-006: 리랭킹 (`src/retrieval/reranker.py`)
검색된 청크들을 Cross-Encoder 모델을 사용하여 질의와의 정밀 관련도를 재계산하고 재정렬합니다.
설정값 `USE_RERANKER`가 비활성화(기본값)되어 있으면 이 단계를 건너뜁니다. 모델 호출이나 점수 계산이 실패하면 RR-201, 임계값을 초과하는 유효 청크가 없으면 RR-202를 발생시킵니다. `rerank_chunks(...)`를 진입점으로 사용합니다.

## FUNC-007: 적합성 평가 및 CRAG (`src/agent/nodes/evaluate.py`)
검색된 컨텍스트가 질의에 답변하기에 충분하고 정확한지 LLM으로 평가합니다. 근거가 불충분할 경우 `needs_external` 또는 `needs_reretrieval` 플래그를 설정하여 워크플로가 질의 재작성(rewrite) 단계로 되돌아가는 CRAG 루프를 실행하도록 유도합니다.
평가 응답 파싱에 실패하면 EV-301, 평가 결과가 내부적으로 모순되면 EV-302, 근거 없는 환각 주장이 감지되면 EV-303을 발생시킵니다. `evaluate_context(state)`를 진입점으로 사용합니다.

## FUNC-008: 답변 및 인용 생성 (`src/agent/nodes/generate.py`)
검색 및 검증된 컨텍스트를 근거로 최종 답변을 생성하고, 답변 본문 내의 `[n]` 인용 표기를 실제 출처 청크와 연결합니다.
인용 근거 없이 답변이 가능하다고 판단하면 GN-401, 컨텍스트 길이가 모델의 최대 토큰 한도를 초과하면 GN-402를 발생시킵니다. `generate_response(state)`를 진입점으로 사용합니다.

## FUNC-009: 워크플로우 제어 (`src/agent/workflow.py`)
rewrite → search → rerank → evaluate → generate 노드를 LangGraph StateGraph로 오케스트레이션합니다. 평가 기준 미달 시 rewrite로 되돌아가는 CRAG 루프(최대 `MAX_REWRITE_COUNT=3`회)와 사용자 확인이 필요한 Human-in-the-Loop(HIL) 중단 및 재개(최대 `MAX_HIL_COUNT=5`회)를 라우팅합니다.
노드 실행 중 예외가 발생하면 `handle_node_errors` 데코레이터가 error_logs에 기록하고 안전하게 진행하며, 반복 한도 초과(`GraphRecursionError`)나 타임아웃(`TimeoutError`) 발생 시 예외를 다시 던지지 않고 사전 정의된 폴백 응답을 반환합니다. `run_workflow(query, standard_filter)` 및 `resume_workflow(thread_id, decision)`를 진입점으로 사용합니다.

---

## 에러코드 카탈로그 (`src/utils/exception.py`)

| 코드 | 노드 | 발생 시점 |
|---|---|---|
| CM-001 | * | 필수 설정 또는 환경변수가 누락되었을 때 |
| CM-002 | * | LLM API 호출이 실패했을 때 (네트워크 연결, 인증, 응답 파싱) |
| CM-003 | * | 문서 파싱 실패용 예외 (향후 `DoclingParser.parse`에 연결 예정) |
| OT-103 | ontology | 문서 계층 구조를 파악하지 못했을 때 |
| SE-101 | search | pgvector 검색 쿼리 실행 시간이 타임아웃을 초과했을 때 |
| SE-102 | search 또는 index | DB 연결이 끊기거나 쿼리 실행이 실패했을 때 |
| SE-103 | search | 검색 결과가 없거나 임계값을 만족하는 결과가 하나도 없을 때 |
| RR-201 | rerank | 리랭킹 모델 호출 또는 점수 계산이 실패했을 때 |
| RR-202 | rerank | 리랭킹 후 임계값을 넘는 청크가 하나도 없을 때 |
| IX-201 | index | 임베딩 토큰 한도를 초과하여 해당 청크를 건너뛸 때 |
| EV-301 | evaluate | 평가 응답을 정해진 스키마 형식으로 읽지 못했을 때 |
| EV-302 | evaluate | 평가 결과가 논리적으로 모순될 때 |
| EV-303 | evaluate | 검색 근거가 없는 환각 주장이 감지되었을 때 |
| GN-401 | generate | 답변 생성 시 필수 인용 근거가 누락되었을 때 |
| GN-402 | generate | 컨텍스트 길이가 모델의 최대 토큰 한도를 초과했을 때 |
| TIMEOUT | workflow | 노드 단일 실행이 타임아웃을 초과했을 때 (워크플로 폴백이 기록) |
| RECURSION_LIMIT | workflow | 그래프 최대 재귀 반복 한도를 소진했을 때 (워크플로 폴백이 기록) |

> 상세 예외 로그는 `ErrorLog`(timestamp KST, node, error_type, message) 구조체로 `GraphState.error_logs`에 누적 관리됩니다.

