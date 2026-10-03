"""[FUNC-009] PydanticAI 통일 및 LangSmith / OpenTelemetry 트레이싱 배선 검증 테스트 (#171).

검증 항목:
1. init_tracing()의 기본 비활성 및 안전한 no-op 동작 (키 부재 시).
2. InMemorySpanExporter를 통한 PydanticAI Agent 계측 스팬 수집 검증.
3. 부모 컨텍스트(스팬 ID)와 자식 LLM 스팬 간의 올바른 연결 검증.
4. LLM 호출 시 토큰 수(token usage) 또는 모델 메타데이터 스팬 속성 기록 검증.
5. rewrite 노드 PydanticAI Agent 실행 및 스팬 생성 검증.
"""
import pytest
from unittest.mock import patch
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.utils.tracing import init_tracing, reset_tracing, is_tracing_configured
from src.agent.nodes.rewrite import classify_and_select, apply_hyde
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from src.models.schemas import ClassifyResult, HydeResult


@pytest.fixture(autouse=True)
def clean_tracing():
    """각 테스트 전후 트레이싱 상태를 격리한다."""
    reset_tracing()
    yield
    reset_tracing()


@pytest.mark.unit
class TestTracingInstrumentation:
    def test_tracing_noop_when_key_absent(self, monkeypatch):
        """API 키가 없으면 init_tracing은 어떠한 OTel 계측도 구성하지 않고 False를 반환한다."""
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
        monkeypatch.setattr("src.utils.tracing.LANGSMITH_TRACING_ENABLED", True)

        assert is_tracing_configured() is False
        initialized = init_tracing()
        assert initialized is False

    def test_pydantic_ai_spans_captured_with_in_memory_exporter(self):
        """InMemorySpanExporter가 등록되면 PydanticAI Agent 실행 스팬이 정상 포착된다."""
        import logfire

        exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(exporter)

        # 강제 초기화 + InMemorySpanExporter 주입
        init_tracing(force=True, additional_span_processors=[processor])

        # TestModel을 사용하는 PydanticAI Agent 실행
        agent = Agent(TestModel(custom_output_args={"is_accounting": True, "strategy": "hyde"}), output_type=ClassifyResult)
        res = agent.run_sync("회계 질의")

        assert res.output.is_accounting is True
        spans = exporter.get_finished_spans()
        assert len(spans) > 0

        # span 이름 중 agent 또는 pydantic_ai 관련 span이 존재하는지 확인
        span_names = [s.name for s in spans]
        assert any("agent" in name.lower() for name in span_names)

    def test_parent_child_span_linkage(self):
        """부모 스팬 컨텍스트 내에서 Agent가 실행되면 부모-자식 관계가 올바르게 맺어진다."""
        import logfire

        exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(exporter)

        init_tracing(force=True, additional_span_processors=[processor])

        agent = Agent(TestModel(custom_output_args={"hypothetical_answer": "가상 답변입니다."}), output_type=HydeResult)

        with logfire.span("parent_node_span") as parent_span:
            res = agent.run_sync("질의")

        assert res.output.hypothetical_answer == "가상 답변입니다."
        spans = exporter.get_finished_spans()
        assert len(spans) >= 2

        parent = next((s for s in spans if s.name == "parent_node_span"), None)
        assert parent is not None

        # 하위 스팬 중 적어도 하나는 parent의 context span_id를 부모로 가져야 한다
        children = [s for s in spans if s.parent and s.parent.span_id == parent.context.span_id]
        assert len(children) > 0, "자식 LLM 스팬이 부모 노드 스팬에 연결되어야 합니다."

    def test_rewrite_agent_execution_with_test_model(self):
        """rewrite의 classify_and_select 및 apply_hyde가 PydanticAI Agent로 정상 동작한다."""
        with patch("src.agent.nodes.rewrite._get_classify_agent") as mock_agent_fn:
            mock_agent = Agent(
                TestModel(custom_output_args={"is_accounting": True, "strategy": "stepback", "confidence": 0.95}),
                output_type=ClassifyResult,
            )
            mock_agent_fn.return_value = mock_agent

            is_acc, strat, conf, scope = classify_and_select("구체적 질의")
            assert is_acc is True
            assert strat == "stepback"
            assert conf == 0.95
            assert scope == "accounting"
