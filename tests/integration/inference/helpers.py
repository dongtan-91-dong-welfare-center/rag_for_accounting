from src.models.schemas import RetrievedChunk, RerankingResult, EvaluationResult


def make_retrieved_chunks(scores: list[float] | None = None) -> list[RetrievedChunk]:
    """주어진 점수 목록으로 검색 결과 청크를 생성. 미지정 시 기본 2개([0.9, 0.85]) 생성"""
    if scores is None:
        scores = [0.9, 0.85]
    return [
        RetrievedChunk(
            chunk_id=f"chunk-{i}",
            document_id=f"DOC-{i:03d}",
            content=f"기준서 내용 {i}",
            score=score,
            metadata={}
        )
        for i, score in enumerate(scores)
    ]


def make_reranked_results(
    chunks: list[RetrievedChunk],
    rerank_scores: list[float] | None = None,
) -> list[RerankingResult]:
    """검색 청크를 리랭킹 결과로 변환. 점수 미지정 시 0.95부터 0.05씩 감소하는 기본값 사용"""
    if rerank_scores is None:
        rerank_scores = [round(0.95 - i * 0.05, 2) for i in range(len(chunks))]
    return [
        RerankingResult(chunk=chunk, rerank_score=score)
        for chunk, score in zip(chunks, rerank_scores)
    ]


def make_eval_result(*, needs_external: bool, confidence: float = 0.9) -> dict:
    """evaluate 노드의 Mock 반환값 생성"""
    return {
        "evaluation": EvaluationResult(
            is_relevant=not needs_external,
            needs_external=needs_external,
            confidence=confidence,
            reasoning="추가 검색 필요" if needs_external else "검색 결과 충분"
        )
    }
