import pytest
from unittest.mock import patch, MagicMock
from src.models.schemas import LLMInternalResponse, EvaluationResult, RetrievedChunk

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
    generate_response()와 evaluate_context()는 호출 시점에 Agent를 생성하므로,
    workflow_app fixture가 그래프를 미리 컴파일한 후에도 이 patch가 적용된다.

    각 노드별 mock instance를 분리하는 이유:
        - generate 노드는 LLMInternalResponse를 반환해야 한다.
        - evaluate 노드는 EvaluationResult를 반환해야 한다.
        - 하나의 mock_instance를 공유하면 출력 타입이 섞여 다운스트림 검증이 깨진다.

    evaluate 기본 출력은 정상 경로 가정(is_relevant=True, needs_external=False)으로 설정한다.
    reasoning은 외부 참조 키워드(K-IFRS·K-GAAP·준용 등)를 포함하지 않아
    check_external_reference()의 오버라이드가 발동되지 않도록 한다.
    개별 테스트에서 다른 동작이 필요하면 src.agent.nodes.evaluate.Agent를 재패치하면 된다.
    """
    generate_response = LLMInternalResponse(
        answer="채권형 매도가능증권은 유효이자율법에 따라 처리됩니다.",
        is_answerable=True,
        llm_self_score=0.9
    )
    generate_mock_result = MagicMock()
    generate_mock_result.output = generate_response
    generate_mock_instance = MagicMock()
    generate_mock_instance.run_sync.return_value = generate_mock_result

    evaluate_response = EvaluationResult(
        is_relevant=True,
        needs_external=False,
        confidence=0.9,
        reasoning="검색된 청크에 질의 응답에 필요한 근거가 충분히 포함되어 있습니다."
    )
    evaluate_mock_result = MagicMock()
    evaluate_mock_result.output = evaluate_response
    evaluate_mock_instance = MagicMock()
    evaluate_mock_instance.run_sync.return_value = evaluate_mock_result

    with patch("src.agent.nodes.generate.Agent", return_value=generate_mock_instance), \
         patch("src.agent.nodes.evaluate.Agent", return_value=evaluate_mock_instance):
        yield   # 패치가 적용된 mock 객체를 yield 하여 다른 테스트에서 사용할 수 있도록 한다.


@pytest.fixture
def sample_chunks():
    return [
        RetrievedChunk(chunk_id="1", document_id="doc1", content="First content", score=0.5, metadata={}),
        RetrievedChunk(chunk_id="2", document_id="doc2", content="Second content", score=0.6, metadata={}),
        RetrievedChunk(chunk_id="3", document_id="doc3", content="Third content", score=0.7, metadata={})
    ]
