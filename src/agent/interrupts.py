"""
HIL interrupt 결과 판별·페이로드 정규화 공용 헬퍼.

run_workflow/resume_workflow의 invoke 결과에서 `__interrupt__`를 다루는 규약이 CLI(src/main.py)·Streamlit(app.py)에 2중 복제돼 있던 것을 단일화했다.
API 서버(src/api)도 동일 규약으로 interrupted 응답을 조립한다.

LangGraph 실계약: `__interrupt__`는 Interrupt 객체의 리스트이며 페이로드는 [0].value다.
(human_review 노드가 interrupt()에 넘긴 dict — src/agent/workflow.py 참고)
"""
from __future__ import annotations

from typing import Any


def is_interrupt(result: Any) -> bool:
    """워크플로 결과가 HIL interrupt로 중단되었는지 여부."""
    return isinstance(result, dict) and "__interrupt__" in result


def extract_interrupt_payload(result: dict) -> dict:
    """
    invoke 결과의 __interrupt__ 값을 dict 페이로드로 정규화한다.
    value가 dict가 아니거나 리스트가 비어 있으면 빈 dict를 반환해 호출부의 .get() 기반 렌더링이 항상 안전하도록 보장한다.
    """
    intr = result["__interrupt__"]
    item = intr[0] if isinstance(intr, (list, tuple)) and intr else intr
    payload = getattr(item, "value", item)
    return payload if isinstance(payload, dict) else {}
