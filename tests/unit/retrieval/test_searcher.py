"""
[FUNC-004/005] 하이브리드 검색 단위 테스트 Stub

대상 모듈: src/retrieval/searcher.py
검증 범위:
    - vector_search(): Dense 검색 반환 타입 규격
    - graph_search(): Sparse(그래프) 검색 반환 타입 규격
    - hybrid_search(): 가중 병합 로직 및 metadata_filter 적용

TODO: searcher.py 구현 완료 후 @pytest.mark.skip을 제거
"""
import pytest
from src.models.schemas import RetrievedChunk


@pytest.mark.unit
class TestVectorSearch:
    """FUNC-005a: Dense 검색(vector_search) 인터페이스 검증"""

    @pytest.mark.skip(reason="FUNC-005 searcher 구현 후 활성화 예정 — DB/임베딩 연동 필요")
    def test_vector_search_returns_chunks(self):
        """
        입력: query (str), top_k (int)
        출력: list[RetrievedChunk] — score 내림차순
        """
        from src.retrieval.searcher import vector_search

        results = vector_search("영업권 손상차손 인식 기준은?", top_k=5)
        assert isinstance(results, list)
        assert len(results) <= 5
        if results:
            assert isinstance(results[0], RetrievedChunk)
            # 내림차순 정렬 검증
            scores = [r.score for r in results]
            assert scores == sorted(scores, reverse=True)


@pytest.mark.unit
class TestGraphSearch:
    """FUNC-005b: Sparse 검색(graph_search) 인터페이스 검증"""

    @pytest.mark.skip(reason="FUNC-005 searcher 구현 후 활성화 예정 — Apache AGE 연동 필요")
    def test_graph_search_returns_chunks(self):
        """
        입력: query (str), top_k (int)
        출력: list[RetrievedChunk] — 그래프 탐색 결과
        """
        from src.retrieval.searcher import graph_search

        results = graph_search("영업권 손상차손 인식 기준은?", top_k=5)
        assert isinstance(results, list)
        assert len(results) <= 5
        if results:
            assert isinstance(results[0], RetrievedChunk)


@pytest.mark.unit
class TestHybridSearch:
    """FUNC-005c: 하이브리드 검색(hybrid_search) 인터페이스 검증"""

    @pytest.mark.skip(reason="FUNC-005 searcher 구현 후 활성화 예정 — 전체 검색 파이프라인 필요")
    def test_hybrid_search_returns_chunks(self):
        """
        입력: query (str), top_k (int), metadata_filter (dict | None)
        출력: list[RetrievedChunk] — Dense + Sparse 가중 병합 결과
        """
        from src.retrieval.searcher import hybrid_search

        results = hybrid_search("영업권 손상차손 인식 기준은?", top_k=5)
        assert isinstance(results, list)
        assert len(results) <= 5

    @pytest.mark.skip(reason="FUNC-005 searcher 구현 후 활성화 예정")
    def test_hybrid_search_with_metadata_filter(self):
        """metadata_filter 적용 시 필터 조건에 맞는 결과만 반환"""
        from src.retrieval.searcher import hybrid_search

        results = hybrid_search(
            "영업권 손상차손 인식 기준은?",
            top_k=5,
            metadata_filter={"standard_type": "K-GAAP"}
        )
        assert isinstance(results, list)
