"""
통합 테스트 공용 헬퍼

Human-in-the-Loop 도입으로 decompose/stepback 전략 질의는 search 이전에 human_review 노드에서 interrupt()로 중단된다.
단발성 실행을 가정하는 벤치마크/통합 테스트가 이 중단으로 final_response=None을 받는 문제를 막기 위해,
중단을 자동 승인하여 끝까지 진행시키는 헬퍼를 제공한다.
"""
from typing import Any, Literal

from src.agent.workflow import run_workflow, resume_workflow

# 그래프 내부 MAX_HIL_COUNT(=5, #79 결정)보다 1 큰 안전 상한.
# 그래프가 정상이라면 결코 도달하지 않으며, 무한 루프 회귀 시 즉시 실패하도록 가드한다.
_MAX_AUTO_APPROVE = 6


def run_workflow_to_completion(
    query: str,
    *,
    standard_filter: Literal["GAAP", "KIFRS", "ALL"] = "ALL",
    **kwargs: Any,
) -> dict[str, Any]:
    """HIL 중단을 자동 승인하여 단발성 완료를 보장한다.

    decompose/stepback로 분류되어 human_review에서 interrupt 되더라도 사람 개입 없이 끝까지 진행한 뒤 최종 상태를 반환한다.
    approve 액션은 사람 피드백을 주입하지 않는 중립 통과이므로, 재작성된 질의를 그대로 search로 넘겨 검색·grounding 측정값을 왜곡하지 않는다.

    Args:
        query: 사용자 질의.
        standard_filter: 기준서 범위 필터. run_workflow와 동일 계약.
        **kwargs: run_workflow로 그대로 전달되는 추가 인자(thread_id 등).

    Returns:
        interrupt가 모두 소거된 최종 상태 dict (final_response 포함).

    Raises:
        RuntimeError: auto-approve 횟수가 _MAX_AUTO_APPROVE를 초과한 경우
            (HIL 루프가 종료되지 않는 회귀를 테스트에서 즉시 검출).
    """
    result = run_workflow(query, standard_filter=standard_filter, **kwargs)
    guard = 0
    while "__interrupt__" in result:
        guard += 1
        if guard > _MAX_AUTO_APPROVE:
            raise RuntimeError(
                f"auto-approve 루프 상한({_MAX_AUTO_APPROVE}) 초과 — "
                f"HIL 루프가 종료되지 않음 (query={query!r})"
            )
        thread_id = result.get("thread_id")
        assert thread_id, "interrupt 상태에 thread_id 가 없음 (#79 계약 위반)"
        result = resume_workflow(thread_id, {"action": "approve"})
    return result
