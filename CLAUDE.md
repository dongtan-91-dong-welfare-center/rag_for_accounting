# CLAUDE.md — 프로젝트 인덱스

> **한 줄 요약(BLUF):** 회계 기준서 RAG 시스템. 처음 왔다면 여기서 길을 잡고, 상세는 [docs/README.md](docs/README.md)의 결정트리로 간다.

## 이 프로젝트는

회계사가 질문하면 관련 회계기준 **조항**을 찾아 **근거(인용)와 함께** 답하는 RAG 시스템이다.
파이프라인: rewrite → search(하이브리드: dense+sparse를 RRF로 병합) → rerank → evaluate(CRAG 품질 게이트) → generate. LangGraph가 오케스트레이션한다.

## 길찾기

- **무엇을·어떻게** → [docs/README.md](docs/README.md) (결정트리·용어 사전)
- **현행 아키텍처(단일 진실)** → [docs/architecture/architecture_overview.md](docs/architecture/architecture_overview.md)
- **설치·실행** → 루트 [README.md](README.md) · [docs/guides/](docs/guides/)
- **왜 폐기됐나(GraphRAG/AGE)** → [docs/archive/README.md](docs/archive/README.md)

## 임계값·설정 SSoT

모델·임계값·상수는 **`src/utils/config.py`가 정본**이다. 문서에 수치를 복제하지 말고 이 파일을 가리킨다.
`근거:` 인덱싱(FUNC-003)과 검색(FUNC-005)이 `src/clients/embedding.py`를 공유하므로, 모델·차원을 한 곳에서 고정해야 불일치가 구조적으로 안 난다. 수치를 문서에 박으면 드리프트가 생긴다.
예: `OPENAI_MODEL` · `EMBEDDING_MODEL` · `EMBEDDING_DIM` · `RRF_K` · `TOP_K_RETRIEVAL` · `MAX_REWRITE_COUNT` · `USE_RERANKER`.

## 작성 규칙

새 문서는 BLUF · `근거:` · 용어 단일화를 지킨다 (상세: [docs/README.md](docs/README.md) "작성 규칙").
