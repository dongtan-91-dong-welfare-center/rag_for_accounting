import json
import pytest
from unittest.mock import patch, MagicMock
from src.models.schemas import LLMInternalResponse
from src.agent.workflow import build_workflow


@pytest.fixture(autouse=True)
def mock_rewrite_llm(request):
    """
    system 마커 테스트에서 rewrite 노드(classify_and_select 등)의 LLM 호출을 차단한다.

    Phase 1 시스템 테스트는 "가짜 데이터 기반, 외부 의존성 없음"이 계약이다(pyproject markers).
    그러나 rewrite 노드는 실제 OpenAI(src.agent.nodes.rewrite.client)를 호출해 회계/비회계를 분류하므로
    search/rerank/evaluate를 모킹한 시나리오 테스트라도 "에러 복구 테스트" 같은 placeholder 질의가 비회계로 분류되어 route_after_rewrite가 early_exit로 이탈한다.
    그 결과 검색·평가 파이프라인이 통째로 스킵되고 error_logs/rewrite_count 검증이 깨진다

    여기서 client를 모킹해 항상 (is_accounting=True, strategy="hyde")로 분류시켜
    파이프라인이 정상적으로 진행되도록 보장한다. 모든 전략 함수가 동일 응답을 안전하게 파싱할 수
    있도록 hypothetical_answer/sub_queries/abstract_query를 함께 포함한다.

    단, 실제 LLM 분류를 검증하는 test_rewrite_all_queries(system 미표시)에는 적용하지 않는다.
    """
    if request.node.get_closest_marker("system") is None:
        yield
        return

    content = json.dumps({
        "is_accounting": True,
        "strategy": "hyde",
        "confidence": 0.95,
        "hypothetical_answer": "테스트용 가상 답변",
        "sub_queries": ["테스트용 서브쿼리"],
        "abstract_query": "테스트용 추상 질의",
    })
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = content

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("src.agent.nodes.rewrite.client", mock_client):
        yield

@pytest.fixture(autouse=True)
def mock_llm_agent():
    """
    추론 통합 테스트에서 실제 OpenAI API 호출을 차단한다.

    generate_response()는 실행 시점에 Agent를 생성하므로,
    LazyAppProxy로 지연 빌드하는 워크플로우에도 이 patch가 적용된다.
    generate_response 자체를 workflow 레벨에서 통째로 대체하는 테스트(happy_path 등)에는 문제가 없다

    answer에 "[1]" 인용 마크업을 포함시키는 이유:
        generate 노드의 GN-401 가드(generate.py)는 is_answerable=True인데 인용 근거가 하나도 없으면 LLMResponseFormatError를 발생시킨다.
        chunk_map은 항상 인덱스 1부터 시작하므로 "[1]"이 있으면 최소 1건의 citation이 추출되어 GN-401 계약을 만족한다.
    """
    llm_response = LLMInternalResponse(
        answer="테스트 답변입니다. [1]",
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
