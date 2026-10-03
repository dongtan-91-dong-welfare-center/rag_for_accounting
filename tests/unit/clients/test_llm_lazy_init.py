"""지연 초기화 LLM 클라이언트 단위 테스트 (#361)."""
import sys

import pytest


@pytest.mark.unit
class TestLazyClientInit:
    """OPENAI_API_KEY 없이 import해도 예외가 발생하지 않아야 한다."""

    def test_import_without_api_key_does_not_raise(self, monkeypatch):
        """OPENAI_API_KEY 미설정 상태에서 모듈 import가 성공해야 한다."""
        monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        sys.modules.pop("src.clients.llm", None)
        import src.clients.llm  # noqa: F401

    def test_client_attribute_access_without_key_raises_runtime_error(self, monkeypatch):
        """OPENAI_API_KEY 미설정 상태에서 클라이언트 속성에 처음 접근하면 RuntimeError가 발생해야 한다."""
        monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        sys.modules.pop("src.clients.llm", None)
        import src.clients.llm as llm_module

        llm_module._client = None
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            _ = llm_module.client.chat

    def test_client_attribute_access_with_key_returns_openai_client(self, monkeypatch):
        """OPENAI_API_KEY가 설정된 상태에서 클라이언트 속성 접근이 성공해야 한다."""
        monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy-key")
        sys.modules.pop("src.clients.llm", None)
        import src.clients.llm as llm_module

        llm_module._client = None
        chat = llm_module.client.chat
        assert chat is not None

    def test_client_is_reused_across_calls(self, monkeypatch):
        """두 번 이상 접근해도 동일한 OpenAI 인스턴스를 재사용해야 한다."""
        monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy-key")
        sys.modules.pop("src.clients.llm", None)
        import src.clients.llm as llm_module

        llm_module._client = None
        _ = llm_module.client.chat
        first = llm_module._client
        _ = llm_module.client.models
        second = llm_module._client
        assert first is second

    def test_error_message_contains_env_var_name(self, monkeypatch):
        """오류 메시지에 OPENAI_API_KEY와 설정 안내가 포함되어야 한다."""
        monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        sys.modules.pop("src.clients.llm", None)
        import src.clients.llm as llm_module

        llm_module._client = None
        with pytest.raises(RuntimeError) as exc_info:
            _ = llm_module.client.chat
        assert "OPENAI_API_KEY" in str(exc_info.value)
        assert ".env" in str(exc_info.value)
