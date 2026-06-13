"""
[FUNC-003/FUNC-005] 공유 임베딩 모듈 단위 테스트

대상 모듈: src/utils/embedding.py
검증 범위:
    - _resolve_device(): "auto" 시 cuda→mps→cpu 우선순위, 명시값 패스스루
    - _resolve_thread_count(): 명시값/자동(max(1, cpu-2)) 산정
    - embed_texts(): 빈 입력 처리, encode 호출 인자(batch_size/normalize), 실패 시 CM-002 변환

torch/SentenceTransformer는 mock으로 차단해 실제 모델 로드 없이 논리만 검증한다.
"""
import pytest
from unittest.mock import patch, MagicMock

import numpy as np

from src.utils.config import EMBEDDING_DIM, EMBEDDING_ENCODE_BATCH_SIZE
from src.utils.exception import LLMAPIConnectionError


@pytest.mark.unit
class TestResolveDevice:
    """_resolve_device() — 디바이스 자동 선택/명시 패스스루"""

    def test_explicit_device_passthrough(self):
        """'auto'가 아닌 명시값은 가용성 검사 없이 그대로 반환한다"""
        from src.utils.embedding import _resolve_device

        assert _resolve_device("cpu") == "cpu"
        assert _resolve_device("mps") == "mps"
        assert _resolve_device("cuda") == "cuda"

    def test_auto_prefers_cuda(self):
        """auto: CUDA가 가용하면 cuda를 고른다 (최우선)"""
        from src.utils.embedding import _resolve_device

        with patch("torch.cuda.is_available", return_value=True), \
             patch("torch.backends.mps.is_available", return_value=True):
            assert _resolve_device("auto") == "cuda"

    def test_auto_falls_back_to_mps(self):
        """auto: CUDA가 없고 MPS만 가용하면 mps를 고른다"""
        from src.utils.embedding import _resolve_device

        with patch("torch.cuda.is_available", return_value=False), \
             patch("torch.backends.mps.is_available", return_value=True):
            assert _resolve_device("auto") == "mps"

    def test_auto_falls_back_to_cpu(self):
        """auto: 가속기가 없으면 cpu (Docker on Mac 컨테이너 경로)"""
        from src.utils.embedding import _resolve_device

        with patch("torch.cuda.is_available", return_value=False), \
             patch("torch.backends.mps.is_available", return_value=False):
            assert _resolve_device("auto") == "cpu"


@pytest.mark.unit
class TestResolveThreadCount:
    """_resolve_thread_count() — torch intra-op 스레드 상한 산정"""

    def test_explicit_thread_count_used(self):
        """EMBEDDING_NUM_THREADS>0이면 그 값을 그대로 쓴다"""
        from src.utils import embedding

        with patch.object(embedding, "EMBEDDING_NUM_THREADS", 4):
            assert embedding._resolve_thread_count() == 4

    def test_auto_derives_from_cpu_count(self):
        """0(자동)이면 max(1, cpu_count-2)로 산정해 전 코어 점유를 막는다"""
        from src.utils import embedding

        with patch.object(embedding, "EMBEDDING_NUM_THREADS", 0), \
             patch("os.cpu_count", return_value=12):
            assert embedding._resolve_thread_count() == 10

    def test_auto_never_below_one(self):
        """코어 수가 적어도 최소 1스레드는 보장한다"""
        from src.utils import embedding

        with patch.object(embedding, "EMBEDDING_NUM_THREADS", 0), \
             patch("os.cpu_count", return_value=1):
            assert embedding._resolve_thread_count() == 1


@pytest.mark.unit
class TestEmbedTexts:
    """embed_texts() — 인코딩 인자 및 예외 변환"""

    def test_empty_input_returns_empty(self):
        """빈 입력은 모델 로드 없이 빈 리스트를 반환한다"""
        from src.utils.embedding import embed_texts

        with patch("src.utils.embedding._get_model") as mock_get:
            assert embed_texts([]) == []
            mock_get.assert_not_called()    # 빈 입력에 모델 로드 비용을 쓰지 않음

    def test_encode_called_with_batch_size_and_normalize(self):
        """encode가 정규화 옵션과 EMBEDDING_ENCODE_BATCH_SIZE로 호출되는지 검증"""
        from src.utils.embedding import embed_texts

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1] * EMBEDDING_DIM, [0.2] * EMBEDDING_DIM])

        with patch("src.utils.embedding._get_model", return_value=mock_model):
            result = embed_texts(["가", "나"])

        assert len(result) == 2 # 가, 나
        assert len(result[0]) == EMBEDDING_DIM
        _, kwargs = mock_model.encode.call_args
        assert kwargs["normalize_embeddings"] is True
        assert kwargs["batch_size"] == EMBEDDING_ENCODE_BATCH_SIZE

    def test_encode_failure_raises_cm002(self):
        """인코딩 실패는 DB 오류가 아니라 임베딩 모델 호출 실패(LLMAPIConnectionError, CM-002)로 변환한다"""
        from src.utils.embedding import embed_texts

        mock_model = MagicMock()
        mock_model.encode.side_effect = RuntimeError("OOM")

        with patch("src.utils.embedding._get_model", return_value=mock_model):
            with pytest.raises(LLMAPIConnectionError):
                embed_texts(["가"])
