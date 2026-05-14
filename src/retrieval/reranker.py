# FUNC-006: Cross-Encoder 기반 재정렬 모듈

from src.models.schemas import RetrievedChunk, RerankingResult
from src.utils.exception import RerankFailureError

def rerank(original_query: str, chunks: list[RetrievedChunk]) -> list[RerankingResult]:
    """
    Cross-Encoder로 질의-문서 쌍의 관련도를 재산출하여 정렬한다.
    유틸리티 수준에서는 threshold 기반 필터링을 수행하지 않는다.
    
    Args:
        original_query: 사용자 원문 또는 재작성된 쿼리
        chunks: 검색 엔진에서 반환된 후보 청크 리스트
        
    Returns:
        재정렬된 RerankingResult 리스트
    """
    # 빈 리스트 입력 시
    if not chunks:
        return []

    # 단일 청크 입력 시
    if len(chunks) == 1:
        # TODO: 단일 청크인 경우에도 리랭커 모델을 호출하여 실제 score를 할당하도록 변경 필요
        # 현재는 비교 대상이 없으므로 최상위 점수(1.0)를 부여하여 반환함
        return [RerankingResult(chunk=chunks[0], rerank_score=1.0)]

    try:
        # TODO: 실제 Reranker 알고리즘 도입하여 점수 계산
        scored_results = []
        for chunk in chunks:
            score = compute_relevance_score(original_query, chunk.content)
            scored_results.append(RerankingResult(chunk=chunk, rerank_score=score))

        # 점수 내림차순 정렬
        # TODO: Threshold 기반 필터링 추가 필요
        scored_results.sort(key=lambda x: x.rerank_score, reverse=True)
        
        # RerankingResult 반환
        return scored_results

    except Exception as e:
        # 재실행을 위해 상위 노드로 예외 전파
        # 만약 재시도 후에도 실패하여 Fallback 처리가 필요하다면 호출부에서 담당한다.
        if isinstance(e, RerankFailureError):
            # 상위 노드에서는 RerankFailureError: 리랭킹 과정 중 예상치 못한 오류 발생 : {오류 내용}으로 표시
            raise e
        raise RerankFailureError(f"리랭킹 과정 중 예상치 못한 오류 발생: {str(e)}")

def compute_relevance_score(query: str, content: str) -> float:
    """단일 질의-문서 쌍의 Cross-Encoder 관련도 점수를 반환한다."""
    # 모델마다 로짓의 분포가 다릅니다. 어떤 모델은 관련이 없어도 0.3을 내뱉고, 어떤 모델은 0.01을 내뱉음
    # 따라서 회계 기준서와 전혀 상관없는 질문을 테스트하며, RERANK_THRESHOLD의 적정값을 튜닝하는 과정이 반드시 필요
    # Pseudo:
    # input_pair = f"[CLS] {query} [SEP] {content} [SEP]"
    # logit      = cross_encoder_model.predict(input_pair)   # 단일 스칼라
    # return sigmoid(logit)   # [0, 1] 범위로 변환
    
    # TODO: 실제 Reranker 통합 전까지는 Retriever의 초기 성능 테스트를 위해 모든 청크에 1.0 반환
    return 1.0