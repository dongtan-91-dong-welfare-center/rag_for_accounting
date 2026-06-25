# archive/ — 폐기 격리소

> **한 줄 요약(BLUF):** 여기 문서는 **내용이 폐기됐다**(현행과 불일치). 첫인상에서 현행 문서와 섞이지 않도록 격리했다. 현행 아키텍처는 [architecture_overview.md](../architecture/architecture_overview.md)를 보라.

`근거:` 격리 기준은 "lint가 깨지나"가 아니라 **"내용이 폐기됐나"**다. 아래 4종은 모두 Apache AGE/EdgeQuake/Milvus/GraphRAG 전제로 설계됐으나, v1.0은 **pgvector + BM25 하이브리드**로 구현됐다(코드엔 AGE 잔재 0건 — 문서만 옛것이라 신뢰를 잃을 위험 → 격리).

## SUPERSEDED 목록

| 문서 | 전제(폐기) | 대체 흐름 |
|---|---|---|
| `회계기준서_RAG_Architecture.md` | 초기 검색 아키텍처 분석(에이전틱·하이브리드 프레임워크 고찰) | → graphrag-docling-design → 현행 |
| `graphrag-docling-design.md` | Docling + EdgeQuake(AGE) + LangGraph GraphRAG 설계 | → 현행 pgvector+BM25 |
| `graphrag-docling-implementation.md` | 위 설계의 구현 계획(EdgeQuake 그래프+벡터) | → 현행 |
| `ARCHITECTURE.md` | GraphRAG 전제 아키텍처 | → 현행 |

> 이 폴더는 **경로 lint 스코프에서 제외**된다(작성 당시를 가리키는 깨진 인용을 의도적으로 보존). 단 이 README의 현행 리다이렉트 링크만은 유효를 유지한다.
