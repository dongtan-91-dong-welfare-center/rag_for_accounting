import json
import pytest
from unittest.mock import MagicMock, patch
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.agent.workflow import (
    build_workflow,
    human_review,
    route_after_human_review,
    run_workflow,
    resume_workflow,
)
from src.models.state import GraphState
from src.models.schemas import RetrievedChunk, RewrittenQuery
from src.utils.config import MAX_HIL_COUNT

# TODO: Fixture를 testconf.py에서 정의할 수 있는지 점검

def _mock_resp(content: dict) -> MagicMock:
    """OpenAI 응답 객체를 흉내 낸 가짜 객체 생성 (content를 JSON 문자열로 직렬화)"""
    resp = MagicMock()
    resp.choices[0].message.content = json.dumps(content)
    return resp


@pytest.fixture(autouse=True)
def mock_searcher():
    """외부 DB/API를 호출하는 searcher 모킹 (HIL 통과 후 search 노드 진입 대비)"""
    with patch("src.agent.workflow._search_impl") as mock_search:
        mock_search.return_value = [
            RetrievedChunk(
                chunk_id="1", document_id="DOC-001",
                content="유형자산의 감가상각은...", score=0.9, metadata={}
            ),
        ]
        yield mock_search


@pytest.fixture
def hil_app():
    """HIL(interrupt/resume)을 위해 MemorySaver 체크포인터로 컴파일한 워크플로우"""
    return build_workflow(checkpointer=MemorySaver())


def _decompose_state_query():
    """rewrite가 decompose 전략으로 분류되도록 강제하는 patch 컨텍스트 헬퍼용 질의"""
    return "유형자산과 무형자산의 감가상각 방법 차이는?"


# ── route_after_human_review 단위 ───────────────────────────────────────────────

@pytest.mark.unit
class TestRouteAfterHumanReview:
    def test_feedback_present_routes_to_rewrite(self):
        state = GraphState(original_query="q", human_feedback="리스를 강조해줘")
        assert route_after_human_review(state) == "rewrite" # 피드백이 있으면 rewrite 노드로 이동

    def test_no_feedback_routes_to_search(self):
        state = GraphState(original_query="q", human_feedback=None)
        assert route_after_human_review(state) == "search" # 피드백이 없으면 search 노드로 이동


# ── human_review 노드 단위 (interrupt 없이 통과하는 경로) ────────────────────────

@pytest.mark.unit
class TestHumanReviewPassThrough:
    def test_hyde_strategy_passes_through(self):
        """단순 hyde 전략은 interrupt 없이 빈 dict 반환(통과)"""
        state = GraphState(
            original_query="q",
            rewritten_query=RewrittenQuery(original_query="q", strategy="hyde", search_queries=["q"]),
        )
        assert human_review(state) == {}    # hyde 전략은 interrupt 없이 통과

    def test_already_approved_passes_through(self):
        """이미 승인된 경우 decompose라도 통과"""
        state = GraphState(
            original_query="q",
            rewritten_query=RewrittenQuery(original_query="q", strategy="decompose", search_queries=["q"]),
            human_approved=True,
        )
        assert human_review(state) == {}    # 이미 승인된 경우 decompose라도 통과

    def test_max_hil_count_reached_passes_through(self):
        """MAX_HIL_COUNT 도달 시 무한 루프 방지를 위해 통과"""
        state = GraphState(
            original_query="q",
            rewritten_query=RewrittenQuery(original_query="q", strategy="stepback", search_queries=["q"]),
            hil_count=MAX_HIL_COUNT,
        )
        assert human_review(state) == {}    # MAX_HIL_COUNT 도달 시 무한 루프 방지를 위해 통과


# ── E2E: 조건부 interrupt / resume ──────────────────────────────────────────────

@pytest.mark.unit
class TestHILInterruptResume:
    THREAD = {"configurable": {"thread_id": "hil-test-1"}}

    def _invoke_decompose(self, app, config):
        """decompose 전략으로 분류되도록 강제하여 워크플로우를 invoke"""
        with patch(
            "src.agent.nodes.rewrite.classify_and_select",
            return_value=(True, "decompose", 0.8),
        ), patch("src.agent.nodes.rewrite.client") as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"sub_queries": ["유형자산 감가상각은?", "무형자산 상각은?"]}
            )
            return app.invoke(GraphState(original_query=_decompose_state_query()), config=config)   # decompose 전략으로 강제 분기

    def test_decompose_strategy_interrupts(self, hil_app):
        """decompose 전략은 human_review에서 interrupt되어 search에 도달하지 않는다"""
        result = self._invoke_decompose(hil_app, self.THREAD)

        # interrupt 발생 확인
        assert "__interrupt__" in result    # human_review 노드에서 interrupt 발생
        payload = result["__interrupt__"][0].value
        assert payload["type"] == "human_review"    # human_review 타입 확인
        assert payload["strategy"] == "decompose"   # decompose 전략 확인
        # 구조화된 선택지가 페이로드에 포함되어 클라이언트가 렌더링할 수 있어야 함
        actions = {opt["action"] for opt in payload["options"]}
        assert actions == {"approve", "rewrite"}    # approve와 rewrite 액션 확인

        # search/generate 미도달 (조기 중단)
        assert result.get("final_response") is None # 최종 응답이 생성되지 않음

    def test_resume_approve_proceeds_to_search(self, hil_app, mock_searcher):
        """approve로 재개하면 search→generate까지 진행되어 최종 응답이 생성된다"""
        self._invoke_decompose(hil_app, self.THREAD)

        resumed = hil_app.invoke(Command(resume={"action": "approve"}), config=self.THREAD)

        assert "__interrupt__" not in resumed   # interrupt 발생하지 않음
        mock_searcher.assert_called()                 # search 노드 진입
        assert resumed["human_approved"] is True    # human_approved true
        assert resumed["final_response"] is not None  # 최종 응답 생성 확인

    def test_resume_rewrite_feedback_loops_back_and_reinterrupts(self, hil_app):
        """재작성 요청으로 재개하면 rewrite로 루프백 후 다시 interrupt되고 hil_count가 증가한다"""
        self._invoke_decompose(hil_app, self.THREAD)

        # 루프백 시 rewrite가 다시 호출되므로 classify/client를 동일하게 패치
        with patch(
            "src.agent.nodes.rewrite.classify_and_select",
            return_value=(True, "decompose", 0.8),
        ), patch("src.agent.nodes.rewrite.client") as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"sub_queries": ["유형자산 감가상각은?", "무형자산 상각은?"]}
            )
            resumed = hil_app.invoke(
                Command(resume={"action": "rewrite", "feedback": "감가상각 내용연수를 강조해줘"}),
                config=self.THREAD,
            )

        assert "__interrupt__" in resumed   # 재작성 후 다시 검토를 위해 interrupt가 발생해야 함
        assert resumed["hil_count"] == 1    # HIL 재작성 횟수가 1 증가
        assert resumed.get("human_feedback") is None    # 사용한 피드백은 rewrite에서 초기화됨
        assert resumed["rewrite_count"] == 1 # HIL 루프백은 CRAG 카운터(rewrite_count)를 소비하지 않는다 (최초 진입 시의 1 유지)

    def test_resume_rewrite_then_approve_completes(self, hil_app, mock_searcher):
        """재작성 1회 후 승인하면 최종적으로 search까지 진행된다"""
        self._invoke_decompose(hil_app, self.THREAD)

        with patch(
            "src.agent.nodes.rewrite.classify_and_select",
            return_value=(True, "decompose", 0.8),
        ), patch("src.agent.nodes.rewrite.client") as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"sub_queries": ["유형자산 감가상각은?", "무형자산 상각은?"]}
            )
            hil_app.invoke(
                Command(resume={"action": "rewrite", "feedback": "내용연수 강조"}),
                config=self.THREAD,
            )

        resumed = hil_app.invoke(Command(resume={"action": "approve"}), config=self.THREAD)
        assert "__interrupt__" not in resumed   # interrupt 발생하지 않음
        # search 노드 진입
        mock_searcher.assert_called()
        assert resumed["final_response"] is not None  # 최종 응답 생성 확인


# ── run_workflow / resume_workflow 진입점 ──────────────────────────────────────

@pytest.mark.unit
class TestRunResumeWorkflow:
    def test_run_workflow_issues_thread_id(self):
        """thread_id 미지정 시 UUID를 발급해 반환 dict에 포함한다"""
        mock_app = MagicMock()
        mock_app.invoke.return_value = {"original_query": "q", "final_response": "answer"}
        with patch("src.agent.workflow.build_workflow", return_value=mock_app):
            result = run_workflow("영업권 손상차손 인식 기준은?")
        assert "thread_id" in result    # thread_id 포함 확인
        assert isinstance(result["thread_id"], str) and result["thread_id"] # thread_id 유효성 확인
        assert mock_app.step_timeout == 30 # step_timeout 확인

    def test_run_workflow_reuses_given_thread_id(self):
        """thread_id를 명시하면 그대로 사용한다"""
        mock_app = MagicMock()
        mock_app.invoke.return_value = {"original_query": "q"}
        with patch("src.agent.workflow.build_workflow", return_value=mock_app):
            result = run_workflow("q", thread_id="fixed-id")
        assert result["thread_id"] == "fixed-id"    # thread_id 유지 확인

    def test_resume_workflow_invokes_with_command_and_thread(self):
        """resume_workflow가 Command(resume=...)와 thread_id config로 invoke한다"""
        mock_app = MagicMock()
        mock_app.invoke.return_value = {"final_response": "done"}
        with patch("src.agent.workflow.build_workflow", return_value=mock_app):
            result = resume_workflow("fixed-id", {"action": "approve"})

        assert result["thread_id"] == "fixed-id"  # thread_id 유지 확인
        call = mock_app.invoke.call_args
        sent_command = call.args[0]
        assert isinstance(sent_command, Command) # Command 객체 확인
        assert sent_command.resume == {"action": "approve"} # Command.resume 인자 확인
        assert call.kwargs["config"]["configurable"]["thread_id"] == "fixed-id" # thread_id config 확인

    def test_run_workflow_interrupt_returns_payload_with_thread_id(self, mock_searcher):
        """실제 그래프에서 decompose 질의가 interrupt되면 thread_id와 __interrupt__를 함께 반환한다"""
        with patch(
            "src.agent.nodes.rewrite.classify_and_select",
            return_value=(True, "decompose", 0.8),
        ), patch("src.agent.nodes.rewrite.client") as mock_client:
            mock_client.chat.completions.create.return_value = _mock_resp(
                {"sub_queries": ["a", "b"]}
            )
            result = run_workflow("유형자산과 무형자산 차이는?", thread_id="run-int-1")

        assert result["thread_id"] == "run-int-1"   # thread_id 유지 확인
        assert "__interrupt__" in result # interrupt 발생 확인

        # 같은 thread_id로 resume하여 완료
        resumed = resume_workflow("run-int-1", {"action": "approve"})
        assert resumed["thread_id"] == "run-int-1" # thread_id 유지 확인
        assert "__interrupt__" not in resumed   # interrupt 발생하지 않음
        assert resumed["final_response"] is not None # 최종 응답 생성 확인
