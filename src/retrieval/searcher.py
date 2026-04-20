# FUNC-005: 하이브리드 검색 (Dense + Sparse) 매니저

from src.models.schemas import RetrievedChunk
from src.utils.config import DENSE_WEIGHT, SPARSE_WEIGHT, VECTOR_COLLECTION_NAME

def vector_search(query: str, top_k: int) -> list[RetrievedChunk]:
    """Bi-Encoder 임베딩 기반 Dense 검색 (pgvector ANN)"""
    # Pseudo:
    # [1단계: 질의 임베딩]
    # query_embedding = bi_encoder.encode(query)
    #
    # [2단계: pgvector ANN 검색 (코사인 유사도)]
    # results = db.execute(
    #     f"SELECT chunk_id, content, score FROM {VECTOR_COLLECTION_NAME} "
    #     "ORDER BY embedding <=> %s LIMIT %s",
    #     [query_embedding, top_k])
    #
    # [3단계: RetrievedChunk 변환]
    # return [RetrievedChunk(chunk_id=r[0], content=r[1], score=r[2], ...) for r in results]
    raise NotImplementedError

def graph_search(query: str, top_k: int) -> list[RetrievedChunk]:
    """Apache AGE openCypher 쿼리 기반 온톨로지 그래프 탐색"""
    # Pseudo:
    # [1단계: 개체명 인식 및 쿼리 생성]
    # entities = extract_entities(query)
    # cypher_query = f"MATCH (n:Chunk)-[r:RELATED_TO]->(m) WHERE n.content CONTAINS '{entities[0]}' RETURN n, r, m LIMIT {top_k}"
    #
    # [2단계: Apache AGE 실행]
    # graph_results = db.execute(f"SELECT * FROM cypher('ontology_graph', $$ {cypher_query} $$) as (n agtype, r agtype, m agtype)")
    #
    # [3단계: RetrievedChunk 변환]
    # return [RetrievedChunk(chunk_id=res['n']['id'], content=res['n']['content'], score=1.0) for res in graph_results]
    raise NotImplementedError

def hybrid_search(query: str, top_k: int = 5, metadata_filter: dict | None = None) -> list[RetrievedChunk]:
    """
    - FUNC-005: 하이브리드 검색 (Dense + Sparse)
    - metadata_filter: 회계기준(K-IFRS/K-GAAP) 필터링 포함
    """
    # Pseudo:
    # [1단계: 각 검색 실행 — 각각 top_k // 2개 후보 수집]
    # dense_results  = vector_search(query, top_k=top_k // 2)
    # sparse_results = graph_search(query, top_k=top_k // 2)
    #
    # [2단계: 스코어 정규화 — 각 결과를 [0, 1] 범위로 Min-Max 정규화]
    # dense_scores  = normalize([r.score for r in dense_results])
    # sparse_scores = normalize([r.score for r in sparse_results])
    #
    # [3단계: 가중 평균 병합 (config.py 상수 사용)]
    # merged = {}
    # for chunk, score in zip(dense_results, dense_scores):
    #     merged[chunk.chunk_id] = (chunk, score * DENSE_WEIGHT)
    # for chunk, score in zip(sparse_results, sparse_scores):
    #     if chunk.chunk_id in merged:
    #         merged[chunk.chunk_id] = (chunk, merged[chunk.chunk_id][1]
    #                                          + score * SPARSE_WEIGHT)
    #     else:
    #         merged[chunk.chunk_id] = (chunk, score * SPARSE_WEIGHT)
    #
    # [4단계: 상위 top_k 재선택]
    # return [chunk for chunk, _ in
    #         sorted(merged.values(), key=lambda x: x[1], reverse=True)[:top_k]]
    raise NotImplementedError