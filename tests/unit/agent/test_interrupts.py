"""src/agent/interrupts.py — HIL interrupt 페이로드 정규화 공용 헬퍼 테스트.

main.py·app.py에 2중 복제돼 있던 정규화 규약을 단일 모듈로 옮기며,
LangGraph invoke 결과의 `__interrupt__` 실계약(Interrupt 객체 리스트)을 그대로 검증한다.
"""
from langgraph.types import Interrupt

from src.agent.interrupts import extract_interrupt_payload, is_interrupt

PAYLOAD = {
    "type": "human_review",
    "strategy": "decompose",
    "original_query": "리스 회계처리",
    "search_queries": ["리스 인식", "리스 측정"],
}


class TestIsInterrupt:
    def test_true_when_interrupt_key_present(self):
        """__interrupt__ 키가 있으면 True 반환"""
        assert is_interrupt({"__interrupt__": [Interrupt(value=PAYLOAD)]}) is True

    def test_false_for_completed_result(self):
        """완료된 결과는 False 반환"""
        assert is_interrupt({"thread_id": "t1", "final_response": None}) is False

    def test_false_for_non_dict(self):
        """dict가 아니면 False 반환"""
        assert is_interrupt(None) is False
        assert is_interrupt([]) is False


class TestExtractInterruptPayload:
    def test_extracts_value_from_interrupt_list(self):
        """LangGraph 실계약: __interrupt__는 Interrupt 객체의 리스트 — [0].value가 페이로드다."""
        result = {"__interrupt__": [Interrupt(value=PAYLOAD)]}
        assert extract_interrupt_payload(result) == PAYLOAD

    def test_extracts_value_from_bare_interrupt(self):
        """리스트로 감싸이지 않은 단일 Interrupt도 동일하게 정규화한다."""
        result = {"__interrupt__": Interrupt(value=PAYLOAD)}
        assert extract_interrupt_payload(result) == PAYLOAD

    def test_returns_empty_dict_for_non_dict_value(self):
        """value가 dict가 아니면 빈 dict — 호출부의 .get() 렌더링이 안전하도록."""
        result = {"__interrupt__": [Interrupt(value="approve?")]}
        assert extract_interrupt_payload(result) == {}

    def test_returns_empty_dict_for_empty_interrupt_list(self):
        """빈 Interrupt 리스트면 빈 dict 반환"""
        assert extract_interrupt_payload({"__interrupt__": []}) == {}
