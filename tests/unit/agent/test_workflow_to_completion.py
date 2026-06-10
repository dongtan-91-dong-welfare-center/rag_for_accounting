"""
run_workflow_to_completion 헬퍼(#90) 단위 테스트

라이브 LLM/Docker 없이 run_workflow/resume_workflow를 모킹하여 auto-approve 루프와
상한 가드 동작을 검증한다.
"""
import pytest
from unittest.mock import patch

from tests.integration.helpers import (
    run_workflow_to_completion,
    _MAX_AUTO_APPROVE,
)


@pytest.mark.unit
class TestRunWorkflowToCompletion:
    def test_passthrough_when_no_interrupt(self):
        """interrupt가 없으면 run_workflow 결과를 그대로 반환하고 resume을 호출하지 않는다."""
        completed = {"thread_id": "t1", "final_response": "answer"}
        with patch(
            "tests.integration.helpers.run_workflow", return_value=completed
        ) as mock_run, patch(
            "tests.integration.helpers.resume_workflow"
        ) as mock_resume:
            result = run_workflow_to_completion("회계 질의", standard_filter="KIFRS")

        assert result is completed
        mock_run.assert_called_once_with("회계 질의", standard_filter="KIFRS")
        mock_resume.assert_not_called()

    def test_auto_approves_until_completion(self):
        """interrupt 상태면 approve로 재개하여 __interrupt__가 소거될 때까지 진행한다."""
        interrupted = {"thread_id": "t1", "__interrupt__": [{"value": {}}]}
        completed = {"thread_id": "t1", "final_response": "answer"}
        with patch(
            "tests.integration.helpers.run_workflow", return_value=interrupted
        ), patch(
            "tests.integration.helpers.resume_workflow", return_value=completed
        ) as mock_resume:
            result = run_workflow_to_completion("복잡한 회계 질의")

        assert result is completed
        assert "__interrupt__" not in result
        mock_resume.assert_called_once_with("t1", {"action": "approve"})

    def test_raises_when_loop_never_terminates(self):
        """resume이 계속 interrupt를 반환하면 _MAX_AUTO_APPROVE 초과 시 RuntimeError."""
        interrupted = {"thread_id": "t1", "__interrupt__": [{"value": {}}]}
        with patch(
            "tests.integration.helpers.run_workflow", return_value=interrupted
        ), patch(
            "tests.integration.helpers.resume_workflow", return_value=interrupted
        ) as mock_resume:
            with pytest.raises(RuntimeError, match="auto-approve 루프 상한"):
                run_workflow_to_completion("종료되지 않는 질의")

        # 초기 run 1회 + resume을 상한 횟수만큼 호출한 뒤 다음 시도에서 가드 발동
        assert mock_resume.call_count == _MAX_AUTO_APPROVE

    def test_asserts_thread_id_present_on_interrupt(self):
        """interrupt 상태에 thread_id가 없으면 #79 계약 위반으로 AssertionError."""
        bad = {"__interrupt__": [{"value": {}}]}
        with patch(
            "tests.integration.helpers.run_workflow", return_value=bad
        ), patch("tests.integration.helpers.resume_workflow"):
            with pytest.raises(AssertionError, match="thread_id"):
                run_workflow_to_completion("질의")
