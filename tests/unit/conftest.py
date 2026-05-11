import pytest
from unittest.mock import patch, MagicMock
from src.models.schemas import LLMInternalResponse

# 단위 테스트 전용 환경 및 Mock 설정
# DB 연결, 외부 API(OpenAI 등) 호출 없이 빠르고 독립적으로 실행되도록 구성

@pytest.fixture(autouse=True)
def mock_external_dependencies(monkeypatch):
    """단위 테스트 실행 시 실수로 외부 의존성을 호출하는 것을 방지하기 위해 환경 변수를 가짜 값으로 설정"""
    monkeypatch.setenv("OPENAI_API_KEY", "mock-openai-key-for-unit-test")
    monkeypatch.setenv("POSTGRES_USER", "mock_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "mock_pass")
    monkeypatch.setenv("POSTGRES_DB", "mock_db")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")

@pytest.fixture(autouse=True)
def mock_llm_agent():
    """
    단위 테스트에서 실제 OpenAI API 호출을 차단한다.
    generate_response()는 호출 시점에 Agent를 생성하므로,
    workflow_app fixture가 그래프를 미리 컴파일한 후에도 이 patch가 적용된다.
    """
    llm_response = LLMInternalResponse(
        answer="채권형 매도가능증권은 유효이자율법에 따라 처리됩니다.",
        is_answerable=True,
        llm_self_score=0.9
    )
    mock_result = MagicMock()
    mock_result.output = llm_response

    mock_instance = MagicMock()
    mock_instance.run_sync.return_value = mock_result

    with patch("src.agent.nodes.generate.Agent", return_value=mock_instance):
        yield   # 패치가 적용된 mock 객체를 yield 하여 다른 테스트에서 사용할 수 있도록 한다.
