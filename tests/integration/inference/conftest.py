import pytest
from unittest.mock import patch, MagicMock
from src.models.schemas import LLMInternalResponse
from src.agent.workflow import build_workflow

@pytest.fixture(autouse=True)
def mock_llm_agent():
    """
    추론 통합 테스트에서 실제 OpenAI API 호출을 차단한다.

    generate_response()는 실행 시점에 Agent를 생성하므로,
    LazyAppProxy로 지연 빌드하는 워크플로우에도 이 patch가 적용된다.
    generate_response 자체를 workflow 레벨에서 통째로 대체하는 테스트(happy_path 등)에는 문제가 없다
    """
    llm_response = LLMInternalResponse(
        answer="테스트 답변입니다.",
        is_answerable=True,
        llm_self_score=0.9
    )
    mock_result = MagicMock()
    mock_result.output = llm_response

    mock_instance = MagicMock()
    mock_instance.run_sync.return_value = mock_result

    with patch("src.agent.nodes.generate.Agent", return_value=mock_instance):
        yield   # 테스트가 실행되는 동안에만 패치 상태를 유지하고 테스트가 끝나면 자동으로 원상복구


@pytest.fixture
def mocked_app():
    """
    테스트마다 새로운 그래프 객체를 생성하는 Fixture
    각 테스트 함수의 patch가 적용된 상태에서 build_workflow가 호출되도록 보장하기 위해
    호출 시점에 지연 빌드를 수행하는 프록시 객체를 반환합니다.
    """
    class LazyAppProxy:
        def __getattr__(self, name):
            app = build_workflow()
            return getattr(app, name)
    return LazyAppProxy()
