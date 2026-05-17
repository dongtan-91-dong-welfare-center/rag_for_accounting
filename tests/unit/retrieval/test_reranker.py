import pytest
from unittest.mock import patch
from src.retrieval.reranker import rerank, rerank_chunks
from src.models.schemas import RetrievedChunk, RerankingResult
from src.models.state import GraphState
from src.utils.exception import RerankFailureError, ScoreThresholdError


# 추후 더미데이터를 위한 별도 json 파일 만들어서 관리하는 것을 고려해봐야 함
@pytest.fixture
def sample_chunks():
    return [
        RetrievedChunk(chunk_id="1", document_id="doc1", content="First content", score=0.5, metadata={}),
        RetrievedChunk(chunk_id="2", document_id="doc2", content="Second content", score=0.6, metadata={}),
        RetrievedChunk(chunk_id="3", document_id="doc3", content="Third content", score=0.7, metadata={})
    ]


@pytest.mark.unit
class TestRerank:
    """rerank() 헬퍼 함수 단위 테스트"""

    @patch('src.retrieval.reranker.compute_relevance_score')
    def test_multiple_chunks_returns_descending_order(self, mock_compute, sample_chunks):
        """다중 후보군을 입력받아 연관성 점수 내림차순으로 정렬되어 반환되는지 검증"""
        mock_compute.side_effect = [0.2, 0.5, 0.9]

        results = rerank("영업권 손상차손 인식 기준은?", sample_chunks)

        assert len(results) == 3  # 길이가 3인지 확인
        assert results[0].chunk.chunk_id == "3" # 3번 청크가 가장 높음
        assert results[0].rerank_score == 0.9   # 0.9로 정렬 확인
        assert results[1].chunk.chunk_id == "2" # 2번 청크가 두 번째로 높음
        assert results[1].rerank_score == 0.5   # 0.5로 정렬 확인
        assert results[2].chunk.chunk_id == "1" # 1번 청크가 가장 낮음
        assert results[2].rerank_score == 0.2   # 0.2로 정렬 확인

    def test_empty_chunks_returns_empty_list(self):
        """빈 리스트가 전달되었을 때 ranked_chunks == [] 확인"""
        results = rerank("영업권 손상차손 인식 기준은?", [])
        assert results == []    # 빈 리스트인지 확인

    @patch('src.retrieval.reranker.compute_relevance_score')
    def test_single_chunk_returns_max_score_without_model_call(self, mock_compute):
        """후보가 1개일 때 모델 추론 없이 즉시 1.0 점수로 반환하는지 검증"""
        single_chunk = [RetrievedChunk(chunk_id="1", document_id="doc1", content="content", score=0.5, metadata={})]
        results = rerank("영업권 손상차손 인식 기준은?", single_chunk)

        assert len(results) == 1    # 길이가 1인지 확인
        assert results[0].rerank_score == 1.0   # 점수가 1.0인지 확인
        mock_compute.assert_not_called()    # 모델 추론이 호출되지 않았는지 확인

    @patch('src.retrieval.reranker.compute_relevance_score')
    def test_below_threshold_scores_returns_sorted_list(self, mock_compute, sample_chunks):
        """점수가 RERANK_THRESHOLD 미만이어도 필터링 없이 정렬된 리스트를 반환하는지 확인

        NOTE: rerank()는 임계값 필터링을 수행하지 않는다. 필터링은 rerank_chunks() 노드의 책임이다.
        """
        mock_compute.side_effect = [0.1, 0.2, 0.3]

        results = rerank("영업권 손상차손 인식 기준은?", sample_chunks)

        assert len(results) == 3
        assert results[0].chunk.chunk_id == "3" # 3번 청크가 가장 높음
        assert results[0].rerank_score == 0.3   # 0.3으로 정렬 확인
        assert results[2].chunk.chunk_id == "1" # 1번 청크가 가장 낮음
        assert results[2].rerank_score == 0.1   # 0.1로 정렬 확인

    @patch('src.retrieval.reranker.compute_relevance_score')
    def test_system_exception_propagates_without_wrapping(self, mock_compute, sample_chunks):
        """모델 장애 발생 시 원본 시스템 예외가 AccountingRAGError로 래핑되지 않고 그대로 전파되는지 확인

        NOTE: 시스템 예외는 rerank_chunks() 노드의 except Exception 블록에서 logger.critical 기록 후 파이프라인 중단.
        """
        mock_compute.side_effect = Exception("예상치 못한 에러 발생")

        with pytest.raises(Exception, match="예상치 못한 에러 발생"):
            rerank("영업권 손상차손 인식 기준은?", sample_chunks)


@pytest.mark.unit
class TestReranksChunksNode:
    """rerank_chunks() 워크플로우 노드 단위 테스트"""

    @patch('src.retrieval.reranker.rerank')
    def test_rerank_model_failure_records_error_log(self, mock_rerank):
        """RerankFailureError 발생 시: fallback chunks 반환 + needs_reretrieval=False + error_logs 기록

        [RR-201] RerankFailureError는 AccountingRAGError 계열이므로 to_error_log()를 통해
        구조화된 로그로 변환되어 error_logs에 누적된다. 동시에 1차 검색 결과의 score와 순서를 그대로
        유지한 fallback RerankingResult 리스트를 반환하여 후속 노드가 빈 컨텍스트로 강등되지 않도록
        견고성을 확보한다.
        """
        mock_rerank.side_effect = RerankFailureError("Rerank API 실패")
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            retrieved_chunks=[RetrievedChunk(chunk_id="1", document_id="doc1", content="content", score=0.5, metadata={})],
            error_logs=[]
        )

        result = rerank_chunks(state)

        # error_logs 검증
        assert "error_logs" in result   # error_logs가 존재하는지 확인
        assert len(result["error_logs"]) > 0   # error_logs가 비어있지 않은지 확인
        assert result["error_logs"][-1]["error_type"] == "RR-201"   # 에러 타입이 RR-201인지 확인

        # fallback chunks 검증: 1차 검색 결과 개수/순서/점수 유지
        assert "reranked_chunks" in result  # reranked_chunks가 존재하는지 확인
        assert len(result["reranked_chunks"]) == len(state.retrieved_chunks)  # reranked_chunks의 길이가 1차 검색 결과와 같은지 확인
        assert result["reranked_chunks"][0].chunk.chunk_id == "1"  # 1번 청크가 가장 높음
        assert result["reranked_chunks"][0].rerank_score == 0.5     # retrieved score 유지

        # needs_reretrieval 검증: fallback이 존재하므로 재검색은 불필요
        assert result["needs_reretrieval"] is False

    @patch('src.retrieval.reranker.rerank')
    def test_empty_results_after_rerank_records_error_log(self, mock_rerank):
        """rerank가 빈 결과를 반환 시: reranked_chunks=[] + needs_reretrieval=True + RR-202 기록

        빈 결과는 ScoreThresholdError로 처리되어 error_logs에 누적되고, needs_reretrieval=True 신호가
        발신되어 후속 라우팅(route_after_evaluate)이 CRAG 루프(rewrite)로 진입하도록 한다.
        """
        mock_rerank.return_value = []
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            retrieved_chunks=[RetrievedChunk(chunk_id="1", document_id="doc1", content="content", score=0.5, metadata={})],
            error_logs=[]
        )

        result = rerank_chunks(state)

        assert "error_logs" in result   # error_logs가 존재하는지 확인
        assert len(result["error_logs"]) > 0   # error_logs가 비어있지 않은지 확인
        assert result["error_logs"][-1]["error_type"] == "RR-202"   # 에러 타입이 RR-202인지 확인

        # reranked_chunks는 빈 리스트, 재검색 신호 활성화
        assert result["reranked_chunks"] == []   # reranked_chunks가 빈 리스트인지 확인
        assert result["needs_reretrieval"] is True   # needs_reretrieval이 True인지 확인

    @patch('src.retrieval.reranker.compute_relevance_score')
    def test_rerank_all_scores_below_threshold(self, mock_compute):
        """모든 rerank 점수가 임계값 미만: needs_reretrieval=True + reranked_chunks=[] + RR-202

        max_score < RERANK_THRESHOLD 조건 충족 시 ScoreThresholdError를 발생시키고
        to_error_log()를 통해 error_logs에 누적한다. 동시에 needs_reretrieval=True 신호를 발신하여
        라우팅이 rewrite 노드로 재진입하도록 한다.

        NOTE: rerank()는 청크가 1개면 compute_relevance_score를 호출하지 않고 1.0을 반환한다.
        2개 이상의 청크가 있어야 compute_relevance_score가 실제로 호출된다.
        """
        mock_compute.return_value = 0.1  # RERANK_THRESHOLD(0.5) 미만
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            retrieved_chunks=[
                RetrievedChunk(chunk_id="1", document_id="doc1", content="content1", score=0.5, metadata={}),
                RetrievedChunk(chunk_id="2", document_id="doc2", content="content2", score=0.6, metadata={}),
            ],
            error_logs=[]
        )

        result = rerank_chunks(state)

        assert "error_logs" in result   # error_logs가 존재하는지 확안
        assert len(result["error_logs"]) > 0   # error_logs가 비어있지 않은지 확인
        assert result["error_logs"][-1]["error_type"] == "RR-202"   # 에러 타입이 RR-202인지 확인

        # 저점수 케이스 → 재검색 신호 활성화
        assert result["reranked_chunks"] == []   # reranked_chunks가 빈 리스트인지 확인
        assert result["needs_reretrieval"] is True   # needs_reretrieval이 True인지 확인

    @patch('src.retrieval.reranker.compute_relevance_score')
    def test_success_path_sets_needs_reretrieval_false(self, mock_compute, sample_chunks):
        """정상 경로: 임계치 통과 시 needs_reretrieval=False가 반환 dict에 명시되는지 검증

        rerank_chunks의 모든 반환 경로에서 needs_reretrieval이 명시되도록 한 설계를 고정한다.
        """
        mock_compute.return_value = 0.9   # RERANK_THRESHOLD(0.5) 이상
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            retrieved_chunks=sample_chunks,
            error_logs=[]
        )

        result = rerank_chunks(state)

        assert "reranked_chunks" in result  # reranked_chunks가 존재하는지 확안
        assert len(result["reranked_chunks"]) == len(sample_chunks)  # reranked_chunks의 길이가 1차 검색 결과와 같은지 확인
        assert "needs_reretrieval" in result  # needs_reretrieval이 존재하는지 확안
        assert result["needs_reretrieval"] is False  # needs_reretrieval이 False인지 확안
