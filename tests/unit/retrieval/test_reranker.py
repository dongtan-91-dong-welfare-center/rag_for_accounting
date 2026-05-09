"""
[FUNC-006] 리랭킹 단위 테스트 Stub

대상 모듈: src/retrieval/reranker.py
검증 범위:
    - rerank(): Cross-Encoder 재정렬 및 threshold 필터링
    - compute_relevance_score(): 단일 쌍의 관련도 점수 계산

TODO: reranker.py 구현 완료 후 @pytest.mark.skip을 제거
"""
import pytest
from src.models.schemas import RetrievedChunk, RerankingResult
from src.utils.config import RERANK_THRESHOLD


@pytest.mark.unit
class TestRerank:
    """rerank() 함수 인터페이스 검증"""

    @pytest.mark.skip(reason="FUNC-006 reranker 구현 후 활성화 예정 — Cross-Encoder 모델 필요")
    def test_rerank_returns_reranking_results(self):
        """
        입력: query (str), chunks (list[RetrievedChunk])
        출력: list[RerankingResult] — rerank_score 내림차순, threshold 이상만 포함
        """
        from src.retrieval.reranker import rerank

        chunks = [
            RetrievedChunk(chunk_id="c1", document_id="D1", content="영업권 정의", score=0.8, metadata={}),
            RetrievedChunk(chunk_id="c2", document_id="D1", content="오늘 날씨", score=0.3, metadata={}),
        ]
        results = rerank("영업권 손상차손 인식 기준은?", chunks)
        assert isinstance(results, list)
        if results:
            assert isinstance(results[0], RerankingResult)
            # 내림차순 정렬 검증
            scores = [r.rerank_score for r in results]
            assert scores == sorted(scores, reverse=True)
            # threshold 이상만 포함
            assert all(r.rerank_score >= RERANK_THRESHOLD for r in results)

    @pytest.mark.skip(reason="FUNC-006 reranker 구현 후 활성화 예정")
    def test_rerank_empty_chunks(self):
        """빈 청크 리스트 → 빈 리스트 반환"""
        from src.retrieval.reranker import rerank

        results = rerank("영업권", [])
        assert results == []


@pytest.mark.unit
class TestComputeRelevanceScore:
    """compute_relevance_score() 함수 인터페이스 검증"""

    @pytest.mark.skip(reason="FUNC-006 reranker 구현 후 활성화 예정 — Cross-Encoder 모델 필요")
    def test_score_in_zero_one_range(self):
        """
        입력: query (str), content (str)
        출력: float ∈ [0, 1]
        """
        from src.retrieval.reranker import compute_relevance_score

        score = compute_relevance_score("영업권 손상차손", "영업권은 사업결합에서 발생하는 자산입니다.")
        assert 0.0 <= score <= 1.0
