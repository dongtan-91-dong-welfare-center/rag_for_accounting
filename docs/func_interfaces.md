# FUNC 인터페이스 명세 (FUNC-001~009)

> v1.0 각 기능의 입출력 계약. 타입은 `src/models/schemas.py`, `src/models/state.py` 기준.
> 작성일 2026-06-13.

## 데이터 스키마 요약 (`src/models/schemas.py`)

| 스키마 | 필드 |
|---|---|
| `ParsedDocument` | title:str, text:str(markdown), tables:list[dict], metadata:dict |
| `RewrittenQuery` | original_query:str, strategy:str(`hyde`\|`decompose`\|`stepback`\|`bypass`), search_queries:list[str] |
| `RetrievedChunk` | chunk_id:str, document_id:str, content:str, score:float, metadata:`ChunkMetadata` |
| `ChunkMetadata` | ontology_node_id, node_type, standard_type, chapter (+extra="allow") |
| `RerankingResult` | chunk:`RetrievedChunk`, rerank_score:float |
| `EvaluationResult` | is_relevant:bool, needs_external:bool, confidence:float, reasoning:str |
| `Citation` | document_id:str, chunk_id:str, content:str, relevance_score:float |
| `FinalResponse` | answer:str, citations:list[`Citation`], is_answerable:bool, confidence_score:float |
| `IndexingResult` | document_id:str, chunk_count:int, status(`success`\|`partial`\|`failed`), skipped_chunks:list[`SkippedChunk`] |
| `SkippedChunk` | chunk_id:str, error_type:str, reason:str (적재 누락 청크 추적) |

---

## FUNC-001 — 문서 파싱 (`src/parse/`)
- **입력**: `file_path: str|Path` (PDF). 선택: overlap/containment_threshold(0.15), converter 주입
- **출력**: `ParsedDocument` (text는 마크다운, tables는 `{headers:[...], rows:[[...]]}`)
- **진입**: `DoclingParser().parse(path)`
- **비고**: ⚠️ `ParsedDocument`가 `parser_dtos.py`(dataclass, 실제 반환)와 `schemas.py`(Pydantic)에 이원 정의됨 — 통합 필요.

## FUNC-002 — 청킹/온톨로지 (`src/db/ontology/`)
- **입력**: 마크다운 경로 또는 `ParsedDocument`
- **출력**: `OntologyGraph`(노드 `Standard`/`Section`/`Subsection` + edges) → `RetrievedChunk[]`(score=0.0, metadata.ontology_node_id)
- **진입**: `build_graph(md_path, standard_id, standard_type)` → `chunk_graph(graph, source_path)`
- **에러**: OT-103(구조파싱실패). OT-101(순환참조)/OT-102(중복노드)는 검증 미구현으로 클래스 제거됨(#139) — 검증 로직 도입 시 재정의.

## FUNC-003 — 인덱싱 (`src/db/vector_store.py`, `src/utils/embedding.py`)
- **입력**: `list[RetrievedChunk]`, collection(기본 `chunks`)
- **출력**: `IndexingResult`
- **진입**: `index_documents(chunks, collection)`. 임베딩 KURE-v1(1024d) → pgvector HNSW upsert(멱등 chunk_id)
- **에러**: IX-201(토큰 한도 초과 → 부분 커밋), SE-102(DB)

## FUNC-004 — 질의 재구성 (`src/agent/nodes/rewrite.py`)
- **입력**: `GraphState`(original_query, standard_filter, human_feedback)
- **출력(상태 갱신)**: rewritten_query:`RewrittenQuery`, is_accounting_query:bool, classification_confidence:float
- **진입**: `rewrite_query(state)`. classify_and_select → hyde/decompose/stepback
- **에러**: CM-002(LLM). ⚠️ 현재 LLM 실패가 silent 폴백

## FUNC-005 — 하이브리드 검색 (`src/retrieval/searcher.py`)
- **입력**: `query:str`, `top_k:int=10`, `metadata_filter:dict|None`
- **출력**: `list[RetrievedChunk]`
- **진입**: `search_chunks(...)` = `dense_search`(pgvector cosine) + `sparse_search`(tsvector) → `reciprocal_rank_fusion(k=60)`
- **동작**: 한쪽 실패 시 단독 진행, 0건 시 top_k×2 재탐색, 최종 0건 시 SE-103
- **에러**: SE-101(타임아웃), SE-102(DB), SE-103(결과없음)

## FUNC-006 — 리랭킹 (`src/retrieval/reranker.py`)
- **입력**: `query:str`, `list[RetrievedChunk]`
- **출력**: `list[RerankingResult]` (rerank_score 내림차순, RERANK_THRESHOLD=0.5 필터)
- **진입**: `rerank_chunks(...)`. `USE_RERANKER=False`면 워크플로우가 호출 스킵
- **에러**: RR-201(모델/점수 실패), RR-202(임계 초과 청크 0건)

## FUNC-007 — 적합성 평가 / CRAG (`src/agent/nodes/evaluate.py`)
- **입력**: `GraphState`(reranked_chunks/retrieved_chunks)
- **출력**: evaluation:`EvaluationResult`. needs_external/needs_reretrieval 라우팅 신호
- **진입**: `evaluate_context(state)`
- **에러**: EV-301(평가 파싱), EV-302(일관성 위반), EV-303(할루시네이션 감지)

## FUNC-008 — 답변·인용 생성 (`src/agent/nodes/generate.py`)
- **입력**: `GraphState`(context chunks)
- **출력**: final_response:`FinalResponse`, retrieval_score, generation_score
- **진입**: `generate_response(state)`. [n] 인용 추출 + GN-401 인용 가드
- **에러**: GN-401(응답 포맷), GN-402(컨텍스트 길이 초과)

## FUNC-009 — 워크플로우 제어 (`src/agent/workflow.py`)
- **상태**: `GraphState`(Pydantic, 증분 merge)
- **노드/엣지**: rewrite → (early_exit | human_review) → search → rerank → evaluate →(CRAG 루프)→ generate → END
- **라우팅**: `route_after_rewrite`, `route_after_human_review`, `route_after_evaluate`(needs_reretrieval 최우선)
- **제어 상수**: MAX_REWRITE_COUNT=3, MAX_HIL_COUNT=5
- **진입**: `run_workflow(query, standard_filter)`, `resume_workflow(thread_id, decision)`
- **복원력**: `handle_node_errors` 데코레이터(예외→error_logs 기록 후 계속), GraphRecursionError 폴백. ⚠️ TimeoutError는 재전파, search의 CM-002 오분류

---

## 에러코드 카탈로그 (`src/utils/exception.py`)

| 코드 | 노드 | 의미 | retryable |
|---|---|---|---|
| CM-001 | * | 설정/환경변수 누락 | ✗ |
| CM-002 | * | LLM 호출 경로 실패(연결·인증·응답파싱) | ✓ |
| CM-003 | * | 문서 파싱 실패 (클래스 존재, 미배선 — 착지점 `DoclingParser.parse`) | ✗ |
| OT-103 | ontology | 구조파싱실패 | ✗ |
| SE-101/102/103 | search/index | 타임아웃 / DB / 결과없음 | ✓/✓/✗ |
| RR-201/202 | rerank | 모델실패 / 임계미달 | ✓/✗ |
| IX-201 | index | 임베딩 토큰 한도 초과 | ✗ |
| EV-301/302/303 | evaluate | 평가파싱 / 일관성 / 할루시네이션 | ✓/✗/✗ |
| GN-401/402 | generate | 응답포맷 / 컨텍스트길이 | ✓/✗ |

> `ErrorLog`(timestamp KST, node, error_type, message)로 `GraphState.error_logs`에 누적.
>
> #139에서 제거된 미사용 분류: PS-001(파일 없음)/PS-002(미지원 포맷), OT-101(순환참조)/OT-102(중복노드). 검증 로직을 실제 구현하는 시점에 raise 사이트와 함께 재도입한다.
