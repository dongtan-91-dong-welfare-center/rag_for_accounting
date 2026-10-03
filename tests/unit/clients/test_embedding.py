"""
[FUNC-003/FUNC-005] 공유 임베딩 모듈 단위 테스트

대상 모듈: src/clients/embedding.py
검증 범위:
    - _resolve_device(): "auto" 시 cuda→mps→cpu 우선순위, 명시값 패스스루
    - _resolve_thread_count(): 명시값/자동(max(1, cpu-2)) 산정
    - embed_texts(): 빈 입력 처리, encode 호출 인자(batch_size/normalize), 실패 시 CM-002 변환
    - warmup_model(): preload 위해 임베딩 1회 호출, 실패 시 예외 전파

torch/SentenceTransformer는 mock으로 차단해 실제 모델 로드 없이 논리만 검증한다.
"""
import sys
import types
from contextlib import contextmanager

import pytest
from unittest.mock import patch, MagicMock

import numpy as np

from src.utils.config import EMBEDDING_DIM, EMBEDDING_ENCODE_BATCH_SIZE
from src.utils.exception import LLMAPIConnectionError


@contextmanager
def _fake_torch(*, cuda: bool, mps: bool):
    """
    torch 자리에, 가속기 가용성만 답하는 가짜 모듈을 끼워 넣는다.

    왜 필요한가:
        torch는 선택 의존성(optional dependency: `uv sync --extra local-embedding`으로만 설치되는 무거운 패키지)이다. 
        기본 개발 환경·운영 이미지에는 없다.
        그래서 실물 torch를 `patch("torch.cuda.is_available")`처럼 문자열 경로로 가리키면, patch가 대상을 찾으려 torch를 import하다 ModuleNotFoundError로 죽는다.
        검증하려는 것은 "가용성 → 디바이스" 우선순위 논리뿐이므로, 가짜 모듈로 충분하다.

    어떻게 동작하는가:
        _resolve_device()는 함수 안에서 `import torch`를 한다(지연 임포트). import 문은
        sys.modules를 먼저 보므로, 그 자리에 가짜를 넣어두면 실제 설치 여부와 무관하게
        가짜가 잡힌다.

    예: _fake_torch(cuda=False, mps=True) 안에서 _resolve_device("auto") → "mps"
    """
    fake = types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: cuda),
        backends=types.SimpleNamespace(
            mps=types.SimpleNamespace(is_available=lambda: mps),
        ),
    )
    with patch.dict(sys.modules, {"torch": fake}):
        yield


@pytest.mark.unit
class TestResolveDevice:
    """_resolve_device() — 디바이스 자동 선택/명시 패스스루"""

    def test_explicit_device_passthrough(self):
        """'auto'가 아닌 명시값은 가용성 검사 없이 그대로 반환한다"""
        from src.clients.embedding import _resolve_device

        assert _resolve_device("cpu") == "cpu"
        assert _resolve_device("mps") == "mps"
        assert _resolve_device("cuda") == "cuda"

    def test_auto_prefers_cuda(self):
        """auto: CUDA가 가용하면 cuda를 고른다 (최우선)"""
        from src.clients.embedding import _resolve_device

        with _fake_torch(cuda=True, mps=True):
            assert _resolve_device("auto") == "cuda"

    def test_auto_falls_back_to_mps(self):
        """auto: CUDA가 없고 MPS만 가용하면 mps를 고른다"""
        from src.clients.embedding import _resolve_device

        with _fake_torch(cuda=False, mps=True):
            assert _resolve_device("auto") == "mps"

    def test_auto_falls_back_to_cpu(self):
        """auto: 가속기가 없으면 cpu (Docker on Mac 컨테이너 경로)"""
        from src.clients.embedding import _resolve_device

        with _fake_torch(cuda=False, mps=False):
            assert _resolve_device("auto") == "cpu"


@pytest.mark.unit
class TestResolveThreadCount:
    """_resolve_thread_count() — torch intra-op 스레드 상한 산정"""

    def test_explicit_thread_count_used(self):
        """EMBEDDING_NUM_THREADS>0이면 그 값을 그대로 쓴다"""
        from src.clients import embedding

        with patch.object(embedding, "EMBEDDING_NUM_THREADS", 4):
            assert embedding._resolve_thread_count() == 4

    def test_auto_derives_from_cpu_count(self):
        """0(자동)이면 max(1, cpu_count-2)로 산정해 전 코어 점유를 막는다"""
        from src.clients import embedding

        with patch.object(embedding, "EMBEDDING_NUM_THREADS", 0), \
             patch("os.cpu_count", return_value=12):
            assert embedding._resolve_thread_count() == 10

    def test_auto_never_below_one(self):
        """코어 수가 적어도 최소 1스레드는 보장한다"""
        from src.clients import embedding

        with patch.object(embedding, "EMBEDDING_NUM_THREADS", 0), \
             patch("os.cpu_count", return_value=1):
            assert embedding._resolve_thread_count() == 1


@pytest.mark.unit
class TestEmbedTexts:
    """embed_texts() — 인코딩 인자 및 예외 변환"""

    def test_empty_input_returns_empty(self):
        """빈 입력은 모델 로드 없이 빈 리스트를 반환한다"""
        from src.clients.embedding import embed_texts

        with patch("src.clients.embedding._get_model") as mock_get:
            assert embed_texts([]) == []
            mock_get.assert_not_called()    # 빈 입력에 모델 로드 비용을 쓰지 않음

    def test_encode_called_with_batch_size_and_normalize(self):
        """encode가 정규화 옵션과 EMBEDDING_ENCODE_BATCH_SIZE로 호출되는지 검증"""
        from src.clients.embedding import embed_texts

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1] * EMBEDDING_DIM, [0.2] * EMBEDDING_DIM])

        with patch("src.clients.embedding._get_model", return_value=mock_model):
            result = embed_texts(["가", "나"])

        assert len(result) == 2 # 가, 나
        assert len(result[0]) == EMBEDDING_DIM
        _, kwargs = mock_model.encode.call_args
        assert kwargs["normalize_embeddings"] is True
        assert kwargs["batch_size"] == EMBEDDING_ENCODE_BATCH_SIZE

    def test_encode_failure_raises_cm002(self):
        """인코딩 실패는 DB 오류가 아니라 임베딩 모델 호출 실패(LLMAPIConnectionError, CM-002)로 변환한다"""
        from src.clients.embedding import embed_texts

        mock_model = MagicMock()
        mock_model.encode.side_effect = RuntimeError("OOM")

        with patch("src.clients.embedding._get_model", return_value=mock_model):
            with pytest.raises(LLMAPIConnectionError):
                embed_texts(["가"])


@pytest.mark.unit
class TestWarmupModel:
    """warmup_model() — 콜드 로드 분리용 모델 preload"""

    def test_warmup_triggers_single_embed(self):
        """모델 preload를 위해 임베딩 경로를 1회 태운다"""
        from src.clients import embedding

        with patch.object(embedding, "embed_texts", return_value=[[0.0]]) as mock_embed:
            embedding.warmup_model()
            mock_embed.assert_called_once()    # preload 1회

    def test_warmup_propagates_failure(self):
        """로드 실패는 LLMAPIConnectionError(CM-002)로 전파되어 호출측이 정책을 정한다"""
        from src.clients import embedding

        with patch.object(
            embedding, "embed_texts",
            side_effect=LLMAPIConnectionError("로드 실패", node="index"),
        ):
            with pytest.raises(LLMAPIConnectionError):
                embedding.warmup_model()
