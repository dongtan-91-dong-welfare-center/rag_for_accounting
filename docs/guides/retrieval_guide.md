# 하이브리드 검색·Sparse 검색 가이드

본 문서는 Dense 벡터 검색과 PostgreSQL 전문검색 기반 Sparse 검색을 결합한 하이브리드 검색 파이프라인의 동작 원리 및 병합 규약을 설명합니다.

## 1. 현행 검색 흐름

`src/retrieval/searcher.py`의 `search_chunks()`가 검색 단일 진입점이다.

```text
query
  → embed_query(KURE-v1)
  → dense_search(pgvector cosine)
  → sparse_search(PostgreSQL full-text search)
  → reciprocal_rank_fusion(RRF_K=60, SPARSE_FUSION_WEIGHT=0.1)
  → top_k 반환
```

워크플로에서는 `src/agent/workflow.py`의 `search()` 노드가 rewrite 결과의 `search_queries`를 순회한다. 쿼리가 여러 개면 각 쿼리의 결과를 합치고, 같은 `chunk_id`는 더 높은 점수만 남긴다.

## 2. Dense 검색

Dense 검색은 질의를 KURE-v1로 임베딩하고 `chunks.embedding vector(1024)`와 cosine distance를 계산한다.

| 항목 | 값 |
|---|---|
| 모델 | `nlpai-lab/KURE-v1` |
| 차원 | `1024` |
| DB 연산 | `embedding <=> %s::vector` |
| 점수 | `1 - cosine_distance` |
| 인덱스 | HNSW `vector_cosine_ops` |

인덱싱과 검색은 모두 `src/clients/embedding.embed_texts()`를 공유한다. 따라서 모델·차원 불일치가 구조적으로 발생하지 않는다.

## 3. Sparse 검색

Sparse 검색은 PostgreSQL 내장 전문검색을 쓴다.

```sql
to_tsvector('simple', content) @@ plainto_tsquery('simple', query)
```

순위 점수는 `ts_rank_cd`로 계산한다. 이 방식은 키워드 일치를 보강하지만, 다음 한계가 있다.

| 한계 | 의미 |
|---|---|
| 한국어 형태소 분석 없음 | `simple` 설정은 띄어쓰기·기호 중심으로 토큰화한다. |
| IDF 없음 | 흔한 단어를 자동으로 덜 세는 BM25식 가중치가 없다. |
| 동의어 사전 없음 | 회의에서 언급된 동의어 확장은 아직 구현되지 않았다. |
| 조항 번호 검색 보강 제한 | 조항 번호·정확한 용어에는 유리하지만 의미 기반 확장에는 약하다. |

따라서 현행 sparse는 “BM25”가 아니라 “PostgreSQL full-text sparse”라고 부르는 것이 정확하다. 외부 문서에서 BM25라고 표현할 때는 이 차이를 명시한다.

## 4. RRF 병합 및 가중치 설정

Dense와 Sparse 결과는 점수 체계가 다르므로 직접 합산하지 않고, 각 검색 채널의 순위를 기반으로 RRF(Reciprocal Rank Fusion) 점수를 계산합니다:

```text
score(doc) = Σ wᵢ / (RRF_K + rankᵢ(doc))
```

`RRF_K=60`은 `src/utils/config.py`의 기본값이며 순위 간 점수 격차를 완만하게 조절합니다. 채널별 가중치 $w_i$는 Dense 검색이 1.0(고정)이며, Sparse 검색에는 `SPARSE_FUSION_WEIGHT=0.1`이 적용됩니다. 이는 Sparse 채널의 결과가 의미 기반 Dense 상위 후보를 부적절하게 밀어내는 역전 현상을 방지하면서, 키워드가 일치하는 후보를 상위로 재정렬하는 보조 신호로 기능하도록 설계된 결과입니다.

## 5. 장애 처리와 재탐색

검색은 Dense와 Sparse를 독립적으로 실행한다.

| 상황 | 동작 |
|---|---|
| Dense 실패, Sparse 성공 | Sparse 단독 결과로 진행 |
| Sparse 실패, Dense 성공 | Dense 단독 결과로 진행 |
| 둘 다 실패 | `DatabaseQueryError` |
| 결과 0건 | `top_k * 2`로 1회 재탐색 |
| 재탐색도 0건 | `NoContextFoundError` |

워크플로 검색 노드는 일시 장애(`SearchTimeoutError`, `DatabaseQueryError`, `LLMAPIConnectionError`)를 CRAG 재검색 신호로 바꾸고, 결과 없음(`NoContextFoundError`)은 빈 컨텍스트로 답변 생성 단계까지 보낸다.

## 6. 필터링

`standard_filter`가 `GAAP` 또는 `KIFRS`이면 metadata 필터로 변환한다.

```python
{"standard_type": "GAAP"}
```

필터는 Dense/Sparse SQL 모두에서 `metadata->>%s = %s` 조건으로 적용된다. `ALL`이면 필터가 없다.

## 7. 개선 작업을 할 때 지켜야 할 점

2026-07-11 회의에서 언급된 형태소 분석기 기반 검색, 동의어 사전, 앙상블 검색은 현행 구현과 구분한다.

| 개선 후보 | 문서화 기준 |
|---|---|
| 한국어 형태소 분석 | PostgreSQL `simple` 대체 여부와 tokenizer 재현성을 기록한다. |
| BM25 | 실제 BM25 구현인지, `ts_rank_cd` 보강인지 명확히 쓴다. |
| 동의어 사전 | 질의 확장 시 원문 조항 번호와 회계 용어가 깨지지 않는지 테스트한다. |
| 4-way 앙상블 | Dense/Sparse/형태소/GPT 기반 검색 각각의 실패·중복 제거 규칙을 먼저 정의한다. |

성능 수치는 검수된 벤치마크 데이터셋과 함께만 기록합니다. 실측 리포트는 `docs/benchmark/`에 보관하며, 초기 측정 이력은 `docs/measurements/`에서 관리합니다.
