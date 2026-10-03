import math
import sys
import types

import pytest
from unittest.mock import patch, MagicMock
from src.retrieval import reranker as reranker_module
from src.retrieval.reranker import rerank_chunks, compute_relevance_scores
from src.agent.workflow import rerank
from src.models.schemas import RetrievedChunk, RerankingResult
from src.models.state import GraphState
from src.utils import config
from src.utils.exception import RerankFailureError, ScoreThresholdError


@pytest.mark.unit
class TestRerank:
    """rerank_chunks() 헬퍼 함수 단위 테스트"""

    @patch('src.retrieval.reranker.compute_relevance_scores')
    def test_multiple_chunks_returns_descending_order(self, mock_compute, sample_chunks):
        """다중 후보군을 입력받아 연관성 점수 내림차순으로 정렬되어 반환되는지 검증"""
        mock_compute.return_value = [0.2, 0.5, 0.9]

        results = rerank_chunks("영업권 손상차손 인식 기준은?", sample_chunks)

        assert len(results) == 3  # 길이가 3인지 확인
        assert results[0].chunk.chunk_id == "3" # 3번 청크가 가장 높음
        assert results[0].rerank_score == 0.9   # 0.9로 정렬 확인
        assert results[1].chunk.chunk_id == "2" # 2번 청크가 두 번째로 높음
        assert results[1].rerank_score == 0.5   # 0.5로 정렬 확인
        assert results[2].chunk.chunk_id == "1" # 1번 청크가 가장 낮음
        assert results[2].rerank_score == 0.2   # 0.2로 정렬 확인

    def test_empty_chunks_returns_empty_list(self):
        """빈 리스트가 전달되었을 때 ranked_chunks == [] 확인"""
        results = rerank_chunks("영업권 손상차손 인식 기준은?", [])
        assert results == []    # 빈 리스트인지 확인

    @patch('src.retrieval.reranker.compute_relevance_scores')
    def test_single_chunk_returns_max_score_without_model_call(self, mock_compute):
        """후보가 1개일 때 모델 추론 없이 즉시 1.0 점수로 반환하는지 검증"""
        single_chunk = [RetrievedChunk(chunk_id="1", document_id="doc1", content="content", score=0.5, metadata={})]
        results = rerank_chunks("영업권 손상차손 인식 기준은?", single_chunk)

        assert len(results) == 1    # 길이가 1인지 확인
        assert results[0].rerank_score == 1.0   # 점수가 1.0인지 확인
        mock_compute.assert_not_called()    # 모델 추론이 호출되지 않았는지 확인

    @patch('src.retrieval.reranker.compute_relevance_scores')
    def test_below_threshold_scores_returns_sorted_list(self, mock_compute, sample_chunks):
        """점수가 RERANK_THRESHOLD 미만이어도 필터링 없이 정렬된 리스트를 반환하는지 확인

        NOTE: rerank_chunks()는 임계값 필터링을 수행하지 않는다. 필터링은 rerank() 노드의 책임이다.
        """
        mock_compute.return_value = [0.1, 0.2, 0.3]

        results = rerank_chunks("영업권 손상차손 인식 기준은?", sample_chunks)

        assert len(results) == 3
        assert results[0].chunk.chunk_id == "3" # 3번 청크가 가장 높음
        assert results[0].rerank_score == 0.3   # 0.3으로 정렬 확인
        assert results[2].chunk.chunk_id == "1" # 1번 청크가 가장 낮음
        assert results[2].rerank_score == 0.1   # 0.1로 정렬 확인

    @patch('src.retrieval.reranker.compute_relevance_scores')
    def test_system_exception_propagates_without_wrapping(self, mock_compute, sample_chunks):
        """모델 장애 발생 시 원본 시스템 예외가 AccountingRAGError로 래핑되지 않고 그대로 전파되는지 확인

        NOTE: 시스템 예외는 rerank() 노드의 except Exception 블록에서 logger.critical 기록 후 파이프라인 중단.
        """
        mock_compute.side_effect = Exception("예상치 못한 에러 발생")

        with pytest.raises(Exception, match="예상치 못한 에러 발생"):
            rerank_chunks("영업권 손상차손 인식 기준은?", sample_chunks)


@pytest.mark.unit
class TestComputeRelevanceScores:
    """compute_relevance_scores() 배치 스코어링 단위 테스트"""

    def test_model_load_failure_raises_rerank_failure_error(self):
        """모델 로드 실패(_cross_encoder is None) 시 NameError가 아닌 RerankFailureError가 발생하는지 검증

        모듈 상단에서 _cross_encoder/_load_error를 None으로 선언하므로,
        로드 실패 상태에서도 NameError 없이 의도한 RerankFailureError로 분기되어야 한다.
        """
        with patch('src.retrieval.reranker._cross_encoder', None), \
             patch('src.retrieval.reranker._load_error', RuntimeError("모델 경로 오류")):
            with pytest.raises(RerankFailureError, match="Cross-Encoder 모델 로드 실패"):
                compute_relevance_scores("질의", ["문서1", "문서2"])

    def test_single_forward_pass_for_multiple_contents(self):
        """다수 문서 입력 시 predict가 쌍 리스트로 1회만 호출되는지(forward pass 1회) 검증"""
        mock_encoder = MagicMock()
        mock_encoder.predict.return_value = [0.0, 2.0, -2.0]

        with patch('src.retrieval.reranker._cross_encoder', mock_encoder):
            scores = compute_relevance_scores("질의", ["문서1", "문서2", "문서3"])

        # predict는 청크 수와 무관하게 단 1회 호출되어야 한다
        mock_encoder.predict.assert_called_once()
        called_pairs = mock_encoder.predict.call_args[0][0]
        assert called_pairs == [("질의", "문서1"), ("질의", "문서2"), ("질의", "문서3")]

        # raw score에 로지스틱(시그모이드)이 적용되었는지 확인
        expected = [1 / (1 + math.exp(-s)) for s in (0.0, 2.0, -2.0)]
        assert scores == pytest.approx(expected)    # 부동 소수점의 미세한 연산 오차를 허용


@pytest.mark.unit
class TestRerankNode:
    """rerank() 워크플로우 노드 단위 테스트"""

    @patch('src.agent.workflow.config.USE_RERANKER', True)
    @patch('src.agent.workflow._rerank_impl')
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

        result = rerank(state)

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

    @patch('src.agent.workflow.config.USE_RERANKER', True)
    @patch('src.agent.workflow._rerank_impl')
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

        result = rerank(state)

        assert "error_logs" in result   # error_logs가 존재하는지 확인
        assert len(result["error_logs"]) > 0   # error_logs가 비어있지 않은지 확인
        assert result["error_logs"][-1]["error_type"] == "RR-202"   # 에러 타입이 RR-202인지 확인

        # reranked_chunks는 빈 리스트, 재검색 신호 활성화
        assert result["reranked_chunks"] == []   # reranked_chunks가 빈 리스트인지 확인
        assert result["needs_reretrieval"] is True   # needs_reretrieval이 True인지 확인

    @patch('src.agent.workflow.config.USE_RERANKER', True)
    @patch('src.retrieval.reranker.compute_relevance_scores')
    def test_rerank_all_scores_below_threshold(self, mock_compute):
        """모든 rerank 점수가 임계값 미만: needs_reretrieval=True + reranked_chunks=[] + RR-202

        max_score < RERANK_THRESHOLD 조건 충족 시 ScoreThresholdError를 발생시키고
        to_error_log()를 통해 error_logs에 누적한다. 동시에 needs_reretrieval=True 신호를 발신하여
        라우팅이 rewrite 노드로 재진입하도록 한다.

        NOTE: rerank()는 청크가 1개면 compute_relevance_scores를 호출하지 않고 1.0을 반환한다.
        2개 이상의 청크가 있어야 compute_relevance_scores가 실제로 호출된다.
        """
        mock_compute.return_value = [0.1, 0.1]  # RERANK_THRESHOLD(0.5) 미만, 청크 2개
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            retrieved_chunks=[
                RetrievedChunk(chunk_id="1", document_id="doc1", content="content1", score=0.5, metadata={}),
                RetrievedChunk(chunk_id="2", document_id="doc2", content="content2", score=0.6, metadata={}),
            ],
            error_logs=[]
        )

        result = rerank(state)

        assert "error_logs" in result   # error_logs가 존재하는지 확안
        assert len(result["error_logs"]) > 0   # error_logs가 비어있지 않은지 확인
        assert result["error_logs"][-1]["error_type"] == "RR-202"   # 에러 타입이 RR-202인지 확인

        # 저점수 케이스 → 재검색 신호 활성화
        assert result["reranked_chunks"] == []   # reranked_chunks가 빈 리스트인지 확인
        assert result["needs_reretrieval"] is True   # needs_reretrieval이 True인지 확인

    @patch('src.retrieval.reranker.compute_relevance_scores')
    def test_success_path_sets_needs_reretrieval_false(self, mock_compute, sample_chunks):
        """정상 경로: 임계치 통과 시 needs_reretrieval=False가 반환 dict에 명시되는지 검증

        rerank()의 모든 반환 경로에서 needs_reretrieval이 명시되도록 한 설계를 고정한다.
        """
        mock_compute.return_value = [0.9] * len(sample_chunks)   # RERANK_THRESHOLD(0.5) 이상
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            retrieved_chunks=sample_chunks,
            error_logs=[]
        )

        result = rerank(state)

        assert "reranked_chunks" in result  # reranked_chunks가 존재하는지 확안
        assert len(result["reranked_chunks"]) == len(sample_chunks)  # reranked_chunks의 길이가 1차 검색 결과와 같은지 확인
        assert "needs_reretrieval" in result  # needs_reretrieval이 존재하는지 확안
        assert result["needs_reretrieval"] is False  # needs_reretrieval이 False인지 확안

    @patch('src.agent.workflow.config.USE_RERANKER', True)
    @patch('src.retrieval.reranker.compute_relevance_scores')
    def test_rerank_exact_threshold_boundary(self, mock_compute, sample_chunks):
        """
        최고점이 정확히 RERANK_THRESHOLD와 같을 때 ScoreThresholdError 없이
        needs_reretrieval=False 및 전체 청크가 반환되는지 경계값 불변식을 검증한다.
        """
        # 최고점은 정확히 RERANK_THRESHOLD, 나머지는 낮은 점수
        mock_compute.return_value = [config.RERANK_THRESHOLD, config.RERANK_THRESHOLD - 0.2, 0.1]
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            retrieved_chunks=sample_chunks,
            error_logs=[]
        )

        result = rerank(state)

        assert result["needs_reretrieval"] is False
        assert len(result["reranked_chunks"]) == len(sample_chunks)
        assert result["reranked_chunks"][0].rerank_score == pytest.approx(config.RERANK_THRESHOLD)
        assert len(result.get("error_logs", [])) == 0

    @patch('src.agent.workflow.config.USE_RERANKER', True)
    @patch('src.retrieval.reranker.compute_relevance_scores')
    def test_rerank_partial_pass_preserves_all_chunks(self, mock_compute, sample_chunks):
        """
        최고점만 RERANK_THRESHOLD 이상이고 나머지 하위 청크들의 점수가 임계값 미만일 때,
        rerank 노드는 청크를 임의로 탈락시키지 않고 입력 청크 전체를 내림차순 정렬하여 반환해야 한다.
        (개별 청크 필터링은 후속 evaluate 노드의 check_relevance 책임임을 검증)
        """
        mock_compute.return_value = [config.RERANK_THRESHOLD + 0.3, config.RERANK_THRESHOLD - 0.1, 0.05]
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            retrieved_chunks=sample_chunks,
            error_logs=[]
        )

        result = rerank(state)

        assert result["needs_reretrieval"] is False
        assert len(result["reranked_chunks"]) == len(sample_chunks)
        assert result["reranked_chunks"][0].rerank_score == pytest.approx(config.RERANK_THRESHOLD + 0.3)
        assert result["reranked_chunks"][1].rerank_score == pytest.approx(config.RERANK_THRESHOLD - 0.1)
        assert result["reranked_chunks"][2].rerank_score == pytest.approx(0.05)

    @patch('src.agent.workflow.config.USE_RERANKER', True)
    @patch('src.agent.workflow._rerank_impl', side_effect=RerankFailureError("리랭커 모델 서빙 응답 타임아웃"))
    def test_rerank_model_failure_fallback_preserves_input_order(self, mock_rerank_impl):
        """
        RerankFailureError 발생 시 fallback 경로가 1차 검색 청크들의 순서(정렬 순서 및 청크 ID)를
        하나도 왜곡하지 않고 그대로 RerankingResult 리스트로 보존하는지 검증한다.
        (단일 청크가 아닌 3개 이상의 다중 청크로 순서 불변식 검증)
        """
        ordered_chunks = [
            RetrievedChunk(chunk_id="c_top", document_id="doc1", content="내용1", score=0.85, metadata={}),
            RetrievedChunk(chunk_id="c_mid", document_id="doc2", content="내용2", score=0.65, metadata={}),
            RetrievedChunk(chunk_id="c_low", document_id="doc3", content="내용3", score=0.45, metadata={}),
        ]
        state = GraphState(
            original_query="퇴직급여 회계처리",
            retrieved_chunks=ordered_chunks,
            error_logs=[]
        )

        result = rerank(state)

        assert result["needs_reretrieval"] is False
        assert len(result["reranked_chunks"]) == 3
        # 순서 및 ID 보존 확인
        assert [r.chunk.chunk_id for r in result["reranked_chunks"]] == ["c_top", "c_mid", "c_low"]
        assert [r.rerank_score for r in result["reranked_chunks"]] == [0.85, 0.65, 0.45]
        # 에러 로그 누적 확인
        assert len(result["error_logs"]) == 1
        assert result["error_logs"][0]["error_type"] == "RR-201"


@pytest.mark.unit
class TestLazyModelLoadFailure:
    """CrossEncoder 지연 로딩(_ensure_model_loaded)의 로드 실패 graceful 동작 검증.

    기존 TestComputeRelevanceScores.test_model_load_failure_raises_rerank_failure_error는
    '실패 상태(_cross_encoder=None, _load_error=설정)'를 직접 주입할 뿐, 
    로드 자체가 실패하는 경로(_ensure_model_loaded 내부에서 CrossEncoder 생성이 예외를 던지는 케이스)는 검증하지 않는다.
    여기서 그 경로를 모델 다운로드 실패로 시뮬레이션한다.
    """

    @staticmethod
    def _failing_sentence_transformers(message: str) -> types.ModuleType:
        """CrossEncoder() 생성이 예외를 던지는 가짜 sentence_transformers 모듈.

        실제 torch/모델 로드 없이, _ensure_model_loaded 내부의
        `from sentence_transformers import CrossEncoder`가 이 가짜를 집어가도록 한다.
        """
        fake = types.ModuleType("sentence_transformers")
        fake.CrossEncoder = MagicMock(side_effect=RuntimeError(message))
        return fake

    def test_load_failure_is_graceful_then_raises_on_use(self):
        """모델 로드(다운로드) 실패 시 _ensure_model_loaded는 예외를 삼켜 graceful하게 처리하고,
        이후 compute_relevance_scores 호출 시 NameError가 아닌 RerankFailureError로 분기되는지 검증.
        """
        fake_st = self._failing_sentence_transformers("모델 다운로드 실패(캐시 부재)")

        # 지연 로딩 상태를 초기화하여 _ensure_model_loaded가 실제 로드를 시도하도록 강제한다.
        with patch.object(reranker_module, "_cross_encoder", None), \
             patch.object(reranker_module, "_load_error", None), \
             patch.object(reranker_module, "_load_attempted", False), \
             patch.dict(sys.modules, {"sentence_transformers": fake_st}):
            # 로드 시도 자체는 예외를 전파하지 않는다.
            reranker_module._ensure_model_loaded()
            assert reranker_module._cross_encoder is None
            assert isinstance(reranker_module._load_error, RuntimeError)

            # 실제 사용 시점에 RerankFailureError로 분기.
            with pytest.raises(RerankFailureError, match="Cross-Encoder 모델 로드 실패"):
                compute_relevance_scores("질의", ["문서1", "문서2"])

    def test_load_attempted_once_no_retry_storm(self):
        """로드는 프로세스당 1회만 시도되고, 실패해도 매 호출마다 재시도하지 않는지 검증.

        _load_attempted 가드가 없으면 호출마다 모델 생성을 재시도해 다운로드/지연이 반복된다.
        """
        fake_st = self._failing_sentence_transformers("once")

        with patch.object(reranker_module, "_cross_encoder", None), \
             patch.object(reranker_module, "_load_error", None), \
             patch.object(reranker_module, "_load_attempted", False), \
             patch.dict(sys.modules, {"sentence_transformers": fake_st}):
            reranker_module._ensure_model_loaded()
            reranker_module._ensure_model_loaded()  # 두 번째 호출은 가드로 즉시 반환되어야 함

            fake_st.CrossEncoder.assert_called_once()  # 모델 생성 시도는 1회뿐

    def test_rerank_chunks_propagates_rerank_failure_on_load_failure(self, sample_chunks):
        """로드 실패 상태에서 rerank_chunks(청크 2개 이상)가 RerankFailureError를 전파하는지 검증.

        rerank() 노드는 이 RerankFailureError를 RR-201로 받아 1차 검색 결과 폴백으로 강등한다
        (TestRerankNode.test_rerank_model_failure_records_error_log). 
        즉 로드 실패가 파이프라인을 크래시시키지 않고 graceful 폴백으로 흡수되는 전체 경로의 진입점을 고정한다.
        """
        fake_st = self._failing_sentence_transformers("load fail")

        with patch.object(reranker_module, "_cross_encoder", None), \
             patch.object(reranker_module, "_load_error", None), \
             patch.object(reranker_module, "_load_attempted", False), \
             patch.dict(sys.modules, {"sentence_transformers": fake_st}):
            with pytest.raises(RerankFailureError, match="Cross-Encoder 모델 로드 실패"):
                rerank_chunks("질의", sample_chunks)


@pytest.mark.unit
class TestWarmupReranker:
    """
    warmup_reranker() — 기동 시 리랭커 모델을 미리 로드해 첫 질의의 콜드 로드를 요청 경로 밖으로 뺀다.

    rerank 노드는 그래프 러너의 step_timeout(노드당 30초) 안에서 도는데,
    bge-reranker-v2-m3(~2.2GB)를 첫 질의 때 지연 로딩하면 최초 다운로드가 30초를 넘겨 타임아웃 폴백이 나간다.
    기동 시 미리 데워 이를 막는다.
    """

    def test_loads_model_when_enabled(self):
        """USE_RERANKER=True면 모델 로드(_ensure_model_loaded)를 호출한다."""
        with patch("src.retrieval.reranker._ensure_model_loaded") as mock_load, \
             patch("src.utils.config.USE_RERANKER", True):
            reranker_module.warmup_reranker()
            mock_load.assert_called_once()

    def test_skips_when_disabled(self):
        """USE_RERANKER=False면 리랭커를 쓰지 않으므로 모델을 로드하지 않는다(불필요한 ~2.2GB 로드 회피)."""
        with patch("src.retrieval.reranker._ensure_model_loaded") as mock_load, \
             patch("src.utils.config.USE_RERANKER", False):
            reranker_module.warmup_reranker()
            mock_load.assert_not_called()
