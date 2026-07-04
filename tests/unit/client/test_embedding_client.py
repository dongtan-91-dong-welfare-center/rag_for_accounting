# 임베딩 서빙 연결부(src/client/embedding_client.py)와
# 로컬/원격 디스패치(src/utils/embedding.py)의 단위 테스트.
# 실제 서버·모델 없이 httpx와 클라이언트 함수를 mock으로 대체한다.
import pytest
from unittest.mock import patch, MagicMock

from src.utils import config
from src.utils.exception import LLMAPIConnectionError


@pytest.mark.unit
class TestEmbeddingClientRequestShape:
    """클라이언트가 TEI API 규격(/embed, /tokenize)에 맞는 요청을 보내는지 검증"""

    def test_embed_texts_sends_tei_payload(self):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = [[0.1, 0.2], [0.3, 0.4]]
        with patch.object(config, "EMBEDDING_SERVER_URL", "http://tei:80"), \
             patch("src.client.embedding_client.httpx.post", return_value=mock_response) as mock_post:
            from src.client import embedding_client

            # Act
            vectors = embedding_client.embed_texts(["가", "나"])

        # Assert — normalize=True(pgvector 코사인 정합), truncate=False(silent truncation 방지)
        assert vectors == [[0.1, 0.2], [0.3, 0.4]]
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://tei:80/embed"
        assert kwargs["json"] == {"inputs": ["가", "나"], "normalize": True, "truncate": False}

    def test_count_tokens_uses_tokenize_endpoint(self):
        # Arrange — TEI /tokenize는 입력별 토큰 리스트를 반환한다
        mock_response = MagicMock()
        mock_response.json.return_value = [[{"id": 1}, {"id": 2}, {"id": 3}]]
        with patch.object(config, "EMBEDDING_SERVER_URL", "http://tei:80"), \
             patch("src.client.embedding_client.httpx.post", return_value=mock_response) as mock_post:
            from src.client import embedding_client

            # Act
            tokens = embedding_client.count_tokens("금융자산")

        # Assert
        assert tokens == 3
        assert mock_post.call_args[0][0] == "http://tei:80/tokenize"


@pytest.mark.unit
class TestEmbeddingDispatch:
    """EMBEDDING_SERVER_URL 설정 여부에 따른 embed_texts/count_tokens 분기 검증"""

    def test_embed_texts_delegates_to_client_when_url_set(self):
        # Arrange — 원격 경로에서는 로컬 모델(_get_model)이 호출되면 안 된다
        from src.utils import embedding

        with patch.object(config, "EMBEDDING_SERVER_URL", "http://tei:80"), \
             patch("src.client.embedding_client.embed_texts", return_value=[[0.5]]) as mock_remote, \
             patch("src.utils.embedding._get_model") as mock_local:
            # Act
            result = embedding.embed_texts(["질의"], node="search")

        # Assert
        assert result == [[0.5]]
        mock_remote.assert_called_once_with(["질의"])
        mock_local.assert_not_called()

    def test_embed_texts_uses_local_model_when_url_unset(self):
        # Arrange
        from src.utils import embedding

        mock_vector = MagicMock()
        mock_vector.tolist.return_value = [0.7]
        mock_model = MagicMock()
        mock_model.encode.return_value = [mock_vector]
        with patch.object(config, "EMBEDDING_SERVER_URL", ""), \
             patch("src.utils.embedding._get_model", return_value=mock_model):
            # Act
            result = embedding.embed_texts(["질의"])

        # Assert
        assert result == [[0.7]]

    def test_remote_failure_raises_llm_api_connection_error(self):
        # Arrange — 서버 호출 실패는 CM-002(LLMAPIConnectionError)로 변환돼야 한다
        from src.utils import embedding

        with patch.object(config, "EMBEDDING_SERVER_URL", "http://tei:80"), \
             patch("src.client.embedding_client.embed_texts", side_effect=ConnectionError("refused")):
            # Act & Assert
            with pytest.raises(LLMAPIConnectionError):
                embedding.embed_texts(["질의"], node="search")

    def test_count_tokens_delegates_to_client_when_url_set(self):
        # Arrange
        from src.utils import embedding

        with patch.object(config, "EMBEDDING_SERVER_URL", "http://tei:80"), \
             patch("src.client.embedding_client.count_tokens", return_value=42) as mock_remote, \
             patch("src.utils.embedding._get_model") as mock_local:
            # Act
            tokens = embedding.count_tokens("본문")

        # Assert
        assert tokens == 42
        mock_remote.assert_called_once_with("본문")
        mock_local.assert_not_called()
