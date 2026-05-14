import pytest
from unittest.mock import patch
from src.retrieval.reranker import rerank
from src.models.schemas import RetrievedChunk, RerankingResult

@pytest.fixture
# 추후 더미데이터를 위한 별도 json 파일 만들어서 관리하는 것을 고려해봐야 함
def sample_chunks():
    return [
        RetrievedChunk(chunk_id="1", document_id="doc1", content="First content", score=0.5, metadata={}),
        RetrievedChunk(chunk_id="2", document_id="doc2", content="Second content", score=0.6, metadata={}),
        RetrievedChunk(chunk_id="3", document_id="doc3", content="Third content", score=0.7, metadata={})
    ]

@patch('src.retrieval.reranker.compute_relevance_score')
def test_rerank_normal_behavior(mock_compute, sample_chunks):
    """정상 동작 테스트: 다중 후보군을 입력받아 정상적으로 연관성 점수에 따라 정렬되는지 검증"""
    # 점수 모킹: 3번 청크가 가장 높고, 1번 청크가 가장 낮음
    mock_compute.side_effect = [0.2, 0.5, 0.9]
    
    results = rerank("test query", sample_chunks)
    
    assert len(results) == 3
    # 정렬 확인 (내림차순)
    assert results[0].chunk.chunk_id == "3"
    assert results[0].rerank_score == 0.9
    assert results[1].chunk.chunk_id == "2"
    assert results[1].rerank_score == 0.5
    assert results[2].chunk.chunk_id == "1"
    assert results[2].rerank_score == 0.2

def test_rerank_empty_list():
    """빈 리스트 입력 테스트: 빈 리스트가 전달되었을 때 ranked_chunks == [] 확인"""
    results = rerank("test query", [])
    assert results == []

@patch('src.retrieval.reranker.compute_relevance_score')
def test_rerank_single_chunk(mock_compute):
    """단일 청크 입력 테스트: 후보가 1개일 때 모델 추론 없이 즉시 반환하는지 검증"""
    single_chunk = [RetrievedChunk(chunk_id="1", document_id="doc1", content="content", score=0.5, metadata={})]
    results = rerank("test query", single_chunk)
    
    assert len(results) == 1
    assert results[0].rerank_score == 1.0
    mock_compute.assert_not_called()

@patch('src.retrieval.reranker.compute_relevance_score')
def test_rerank_below_threshold(mock_compute, sample_chunks):
    """임계치 미달 테스트: 점수가 0.5 미만인 경우에도 리스트를 정상적으로 반환하는지 확인"""
    # 모든 점수를 0.5 미만으로 설정
    mock_compute.side_effect = [0.1, 0.2, 0.3]
    
    results = rerank("test query", sample_chunks)
    
    assert len(results) == 3
    # 정렬 확인 (내림차순)
    assert results[0].chunk.chunk_id == "3"
    assert results[0].rerank_score == 0.3
    assert results[2].chunk.chunk_id == "1"
    assert results[2].rerank_score == 0.1

@patch('src.retrieval.reranker.compute_relevance_score')
def test_rerank_exception_handling(mock_compute, sample_chunks):
    """예외 처리 테스트: 모델 장애 발생 시 RerankFailureError 예외가 상위 노드로 전파되는지 확인

    NOTE: 단위 테스트 수준에서는 예외 발생 검증만 수행합니다.
    예외가 전파된 후 error_logs 기록 및 Fallback 처리는 workflow 레벨의
    handle_node_errors 데코레이터와 route_after_evaluate에서 담당합니다.
    """
    from src.utils.exception import RerankFailureError

    mock_compute.side_effect = Exception("예상치 못한 에러 발생")

    # 예외가 발생하고 RerankFailureError로 래핑되어 전파됨
    with pytest.raises(RerankFailureError, match="리랭킹 과정 중 예상치 못한 오류 발생"):
        rerank("test query", sample_chunks)
