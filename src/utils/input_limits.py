# 진입점 공통 입력 길이 검증 — API는 pydantic max_length를, MCP·CLI는 이 함수를 사용한다(#445).
from src.utils.config import MAX_FEEDBACK_LENGTH, MAX_QUERY_LENGTH


def check_length(text: str, limit: int, label: str) -> None:
    """text가 limit자를 초과하면 안내 문구를 담은 ValueError를 던진다."""
    if len(text) > limit:
        raise ValueError(f"{label}은(는) {limit}자 이내로 입력해 주세요. (현재 {len(text)}자)")


def check_query_length(query: str) -> None:
    check_length(query, MAX_QUERY_LENGTH, "질의")


def check_feedback_length(feedback: str) -> None:
    check_length(feedback, MAX_FEEDBACK_LENGTH, "재작성 피드백")
