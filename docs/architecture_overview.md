# 아키텍처 개요 (v1.0)

> 회계기준서 RAG 시스템. **pgvector + BM25(tsvector) 하이브리드 검색** 기반.
> Apache AGE / EdgeQuake / GraphRAG는 v1.0에서 제거됨(초기 설계 문서 `ARCHITECTURE.md`는 superseded).
> 작성일 2026-06-13 · 코드 실태 기준.

## 1. 한눈에 보기

두 경로를 단일 CLI(`src/main.py`)로 제공한다.

```
[적재 ingest]
 PDF/HWP ──(FUNC-001 Docling 파싱)──▶ ParsedDocument(markdown)
   └▶(FUNC-002 온톨로지 빌드)──▶ OntologyGraph(Standard/Section/Subsection + edges)
        └▶(FUNC-002 청킹)──▶ RetrievedChunk[]  (metadata.ontology_node_id)
             └▶(FUNC-003 임베딩 KURE-v1 → pgvector HNSW upsert)──▶ chunks 테이블

[질의 query — LangGraph StateGraph]
 original_query
   ─▶ rewrite(FUNC-004) ──┬─(비회계)─▶ early_exit ─▶ END
                          └─(회계)──▶ human_review(HIL, interrupt)
   ─▶ search(FUNC-005, dense+sparse RRF)
   ─▶ rerank(FUNC-006, CrossEncoder · USE_RERANKER 게이트)
   ─▶ evaluate(FUNC-007, CRAG 자가검증) ──(부족)──▶ rewrite (CRAG 루프, 최대 3회)
   ─▶ generate(FUNC-008, 답변+인용) ─▶ FinalResponse ─▶ END
```

## 2. 핵심 결정

| 영역 | 결정 | 근거 |
|---|---|---|
| 임베딩 | `nlpai-lab/KURE-v1` (자체호스팅, MIT, 1024차원) | 인덱싱·검색이 `embed_texts()` 공유 → 차원 정합 구조적 보장 |
| 벡터 인덱스 | pgvector HNSW + `vector_cosine_ops` | 점진 적재(upsert)에 IVFFlat보다 적합 |
| Sparse 검색 | PostgreSQL `to_tsvector('simple')` + `ts_rank_cd` | ※ 한국어 형태소 미지원·GIN 인덱스 미설정 |
| 하이브리드 병합 | RRF(Reciprocal Rank Fusion), k=60 | 점수 분포 차이에 강건, 가중치 튜닝 불필요 |
| LLM | `OPENAI_MODEL`(config) · PydanticAI/OpenAI | rewrite/evaluate/generate 공통 (라이브 검증 필요) |
| 오케스트레이션 | LangGraph StateGraph + MemorySaver 체크포인터 | HIL interrupt/resume, CRAG 루프 |
| 상태 공유 | `GraphState`(Pydantic) 증분 merge | 노드는 변경 필드 dict만 반환 |

## 3. 모듈 지도 (실제 구조)

```
src/
├── parse/            FUNC-001 — Docling 파싱(parser, layout_config, cluster_merge, reading_order, parser_dtos)
├── db/
│   ├── ontology/     FUNC-002 — builder, chunker, md_parser, edge_detector/extractor, resolver, models
│   ├── vector_store.py  FUNC-003 — pgvector 테이블/HNSW 생성, upsert, 검색
│   └── connection.py    psycopg 연결풀(init_pool/get_pool/close_pool)
├── utils/
│   ├── embedding.py  FUNC-003/005 — KURE-v1 embed_texts (인덱싱·검색 공유)
│   ├── config.py     전역 상수(모델·임계치·RRF_K·TOP_K 등)
│   ├── exception.py  커스텀 예외 18종 + 에러코드
│   └── logger.py     KST 로깅
├── retrieval/
│   ├── searcher.py   FUNC-005 — dense_search/sparse_search/RRF/search_chunks
│   ├── reranker.py   FUNC-006 — CrossEncoder rerank_chunks
│   └── ontology_bridge.py  검색 청크 → 온톨로지 노드 룩업
├── agent/
│   ├── nodes/        FUNC-004/007/008 — rewrite, evaluate, generate
│   ├── prompts.py    LLM 프롬프트
│   └── workflow.py   FUNC-009 — StateGraph 정의, 라우팅, HIL, 폴백
├── models/           schemas.py(공용 Pydantic), state.py(GraphState)
└── main.py           ingest/query CLI 진입점
```

> 인터페이스(입출력 타입)·에러코드 카탈로그는 [func_interfaces.md](func_interfaces.md) 참조.
> 데이터 흐름 다이어그램: `docs/assets/arch-ingest.svg`, `docs/assets/arch-query.svg`.

## 4. 알려진 한계 (v1.0)
- 전 파이프라인 테스트가 mock — 실데이터 E2E 미검증 (병합 전 스모크 권고)
- DB 인프라(db.Dockerfile/docker-compose/.env)에 Apache AGE 빌드·로드 잔재
- Sparse 검색 한국어 형태소 미지원, GIN 인덱스 미설정
- 크로스챕터 참조는 단일 문서 빌드 한계로 미해소 엣지로 남음

상세 갭·로드맵: [v1_audit_report.md](v1_audit_report.md).
