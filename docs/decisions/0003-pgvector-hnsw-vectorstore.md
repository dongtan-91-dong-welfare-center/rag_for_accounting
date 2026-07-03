# ADR-0003 — 벡터 스토어: PostgreSQL pgvector + HNSW

> **한 줄 요약(BLUF):** 벡터 저장·검색을 **PostgreSQL pgvector + HNSW**(`vector_cosine_ops`)로 한다. 별도 벡터 DB(Qdrant 등) 대신 단일 Postgres에 dense(pgvector)와 sparse(tsvector)를 함께 두어 서비스·비용을 줄인다.

- **Status:** Accepted
- **Date:** 2026-06-27 (소급)
- **근거 코드:** `src/db/vector_store.py` · **관련:** [archive](../archive/README.md)(그래프 DB 기반 초기 설계 폐기) · 결정: 5/25 회의

## 1. 왜 (Context)
- 별도 전용 벡터 DB(Qdrant 등)를 두면 상시 구동 서비스가 하나 더 늘고, 클라우드 상시 운영은 시간제 과금이라 부담이 크다(5/25 회의 — 자체 서버 1대로 운영하려면 서비스 수를 줄이는 게 유리).
- 이미 쓰는 PostgreSQL에 dense·sparse를 함께 얹으면 추가 서비스 없이 단일 DB로 운영된다.
- 문서를 장 단위로 계속 넣는 점진 적재에 맞는 인덱스가 필요하다.
- 그래프 DB 기반 초기 설계(Apache AGE 등)는 폐기됨 → [archive](../archive/README.md).

## 2. 무엇을 골랐나 (Decision)
- **pgvector** 확장 + **HNSW** 인덱스 + `vector_cosine_ops`. sparse 검색(`to_tsvector`)도 같은 Postgres에 둔다.
- 컬렉션·HNSW 생성·upsert·검색은 `src/db/vector_store.py`. upsert는 `chunk_id` 기준 멱등.

**선정 근거 (대안 대비)** — 별도 벡터 DB(Qdrant 등) 대비:
- **단일 DB**: dense(pgvector)+sparse(tsvector)를 한 Postgres에 둬 운영할 서비스가 하나뿐이다.
- **비용·운영**: 자체 서버 1대 상시 구동으로 클라우드 시간제 과금을 피한다(5/25 회의).
- **점진 적재**: 계속 추가되는 조각에 HNSW가 IVFFlat보다 적합하다(사전 학습 불필요).

## 3. 결과(영향) (Consequences)
- (+) 단일 DB로 dense+sparse를 운영하고, 점진 적재(upsert)에 HNSW가 IVFFlat보다 적합하다(사전 학습 불필요).
- (+) 별도 벡터 DB 서비스가 없어 인프라·비용이 단순하다.
- (−) HNSW 삽입은 비선형 비용이라 대량 적재 시 지연이 늘 수 있다 — 인덱싱 벤치는 #98.
- (−) sparse는 `simple` 토크나이저라 한국어 형태소를 지원하지 않는다(별도 트랙).
