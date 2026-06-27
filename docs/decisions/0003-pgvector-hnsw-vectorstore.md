# ADR-0003 — 벡터 스토어: PostgreSQL pgvector + HNSW

> **한 줄 요약(BLUF):** 벡터 저장·검색을 **PostgreSQL pgvector + HNSW 인덱스(`vector_cosine_ops`)**로 한다. 전용 벡터 DB(Milvus 등) 대신 단일 Postgres에 dense(pgvector)와 sparse(tsvector)를 함께 두어 인프라를 단순화한다.

- **Status:** Draft — freeze 조건: PR 리뷰 + 회고 정확성 확인
- **Date:** ADR 작성 2026-06-27
- **근거 이슈:** 코드 `src/db/vector_store.py`. Milvus·Apache AGE 폐기 경위 → [archive](../archive/README.md)

## 1. 왜 (Context)
- 초기 설계는 그래프 DB(Apache AGE)·전용 벡터 DB(Milvus)를 검토했으나 운영·의존 복잡도가 컸다.
- 문서를 장 단위로 계속 넣는 점진 적재에 맞는 인덱스가 필요하다.

## 2. 무엇을 골랐나 (Decision)
- **pgvector** 확장 + **HNSW** 인덱스 + `vector_cosine_ops`. sparse 검색(`to_tsvector`)도 같은 Postgres에 둔다.
- 컬렉션·HNSW 생성·upsert·검색은 `src/db/vector_store.py`. upsert는 `chunk_id` 기준 멱등.

## 3. 대가 (Consequences)
- (+) 단일 DB로 dense+sparse를 운영하고, 점진 적재(upsert)에 HNSW가 IVFFlat보다 적합하다(사전 학습 불필요).
- (+) Milvus·AGE 제거로 인프라가 단순해진다.
- (−) HNSW 삽입은 비선형 비용이라 대량 적재 시 지연이 늘 수 있다 — 인덱싱 벤치는 #98.
- (−) sparse는 `simple` 토크나이저라 한국어 형태소를 지원하지 않는다(별도 트랙).
