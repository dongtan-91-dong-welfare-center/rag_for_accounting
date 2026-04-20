# FUNC-003: pgvector를 이용한 문서 임베딩 저장 및 조회

from src.models.schemas import RetrievedChunk, IndexingResult
from src.utils.config import BATCH_SIZE

def index_documents(chunks: list[RetrievedChunk], collection: str) -> IndexingResult:
    """
    청크 리스트를 pgvector에 저장한다.
    - 각 청크의 content를 Bi-Encoder로 임베딩하여 벡터 컬럼에 저장
    - 중복 chunk_id는 upsert 처리
    """
    # Pseudo:
    # try:
    #   success_count = 0
    #
    #   for batch in chunks_to_batches(chunks, BATCH_SIZE):
    #       embeddings = embed_model.encode([c.content for c in batch])
    #       for chunk, vector in zip(batch, embeddings):
    #           [upsert: chunk_id 존재 여부로 INSERT/UPDATE 분기]
    #           # 데이터량이 많아지면 매번 SELECT를 날리는 것은 오버헤드가 크기 때문에 ON CONFLICT 구문 사용 고려
    #           existing = db.execute(
    #               "SELECT 1 FROM {collection} WHERE chunk_id = %s", [chunk.chunk_id])
    #           if existing:
    #               db.execute("UPDATE ... SET embedding = %s WHERE chunk_id = %s",
    #                          [vector, chunk.chunk_id])
    #           else:
    #               db.execute("INSERT INTO {collection} VALUES (%s, %s, %s)",
    #                          [chunk.chunk_id, chunk.content, vector])
    #           success_count += 1
    #
    #   return IndexingResult(
    #       document_id=chunks[0].document_id,
    #       chunk_count=success_count,
    #       status="success",
    #   )
    #
    # except Exception as e:
    #   # 만약 1,000개의 청크 중 500개만 성공하고 에러가 났을 때, "절반만 저장된 상태"를 허용할 것인지 아니면 전체를 롤백할 것인지에 대한 결정이 필요
    #   return IndexingResult(document_id=chunks[0].document_id, chunk_count=0, status="failed")
    raise NotImplementedError

def similarity_search(query_vector: list[float], top_k: int, collection: str) -> list[RetrievedChunk]:
    """코사인 유사도 기반 근사 최근접 이웃(ANN) 검색. pgvector의 <=> 연산자 사용."""
    # Pseudo:
    # results = db.execute(
    #     f"SELECT chunk_id, document_id, content, (1 - (embedding <=> %s)) as score "
    #     f"FROM {collection} ORDER BY embedding <=> %s LIMIT %s",
    #     [query_vector, query_vector, top_k])
    #
    # return [RetrievedChunk(chunk_id=r[0], document_id=r[1], content=r[2], score=r[3]) for r in results]
    raise NotImplementedError

def delete_collection(collection: str) -> bool:
    """지정한 컬렉션의 모든 벡터를 삭제한다."""
    # Pseudo:
    # try:
    #     db.execute(f"DELETE FROM {collection}")
    #     return True
    # except Exception:
    #     return False
    raise NotImplementedError