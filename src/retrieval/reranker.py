# FUNC-006: Cross-Encoder 기반 재정렬 모듈

from src.models.schemas import RetrievedChunk, RerankingResult

def rerank(query: str, chunks: list[RetrievedChunk]) -> list[RerankingResult]:
    """
    Cross-Encoder로 질의-문서 쌍의 관련도를 재산출하고
    RERANK_THRESHOLD 이상인 항목만 반환한다.
    """
    # GPU 가속을 위해서 배치 처리를 고려할 수 있음
    # Pseudo:
    # [1단계: Cross-Encoder 점수 계산]
    # scored = [(chunk, compute_relevance_score(query, chunk.content))
    #           for chunk in chunks]
    #
    # [2단계: RERANK_THRESHOLD 미만 필터링]
    # filtered = [(chunk, score) for chunk, score in scored
    #             if score >= RERANK_THRESHOLD]
    #
    # [3단계: 점수 내림차순 정렬]
    # filtered.sort(key=lambda x: x[1], reverse=True)
    #
    # [4단계: RerankingResult 변환]
    # return [RerankingResult(chunk=chunk, rerank_score=score)
    #         for chunk, score in filtered]
    raise NotImplementedError

def compute_relevance_score(query: str, content: str) -> float:
    """단일 질의-문서 쌍의 Cross-Encoder 관련도 점수를 반환한다."""
    # 모델마다 로짓의 분포가 다릅니다. 어떤 모델은 관련이 없어도 0.3을 내뱉고, 어떤 모델은 0.01을 내뱉음
    # 따라서 회계 기준서와 전혀 상관없는 질문을 테스트하며, RERANK_THRESHOLD의 적정값을 튜닝하는 과정이 반드시 필요
    # Pseudo:
    # input_pair = f"[CLS] {query} [SEP] {content} [SEP]"
    # logit      = cross_encoder_model.predict(input_pair)   # 단일 스칼라
    # return sigmoid(logit)   # [0, 1] 범위로 변환
    raise NotImplementedError