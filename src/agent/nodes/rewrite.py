# FUNC-004: 질의 재작성 노드
#
# 처리 순서:
#   1. Intent Classification — 비회계 질의 조기 차단
#   2. Strategy Selection — 질의 특성에 따라 세 전략 중 선택
#      - stepback : 회사명·금액·연도가 모두 있는 과도하게 구체적인 질의
#      - decompose: 복수 주제를 포함한 복합 질의
#      - hyde     : 단순 질의 (기본값)
#   3. 전략별 LLM 호출 → search_queries 생성
#      - hyde     : [원문, 가상답변]
#      - decompose: [원문, 서브쿼리1, ...]
#      - stepback : [원문, 추상화쿼리]
#   4. LLM 실패 시 원문만 반환 (Bypass)

import json
import re

from src.agent.prompts import (
    DECOMPOSE_PROMPT,
    HYDE_PROMPT,
    INTENT_CLASSIFY_PROMPT,
    STEPBACK_PROMPT,
)
from src.models.schemas import RewrittenQuery
from src.models.state import GraphState
from src.utils.config import OPENAI_MODEL
from src.utils.llm_client import client

# 과도하게 구체적인 질의 감지: 회사명 + 금액 + 연도/올해 패턴
_SPECIFIC_RE = re.compile(
    r'(주식회사|㈜|\w+회사|\w+법인)'  # 회사명
    r'|(\d+억|\d+만원|\d+원)'         # 금액
    r'|(올해|작년|내년|\d{4}년)'       # 연도
)
# 복합 질의 감지: 두 주제를 연결하는 신호어
_COMPLEX_RE = re.compile(r'(와|과|및|그리고).{1,20}(는|은|인지|방법|기준|처리)')


def classify_intent(query: str) -> bool:
    """질의가 회계 관련인지 판별한다. LLM 실패 시 True(회계)로 폴백."""
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": INTENT_CLASSIFY_PROMPT.format(query=query)}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return json.loads(resp.choices[0].message.content).get("is_accounting", True)
    except Exception:
        return True


def select_strategy(query: str) -> str:
    """질의 특성에 따라 전략을 선택한다.

    우선순위:
      1. 회사명·금액·연도 패턴 2개 이상 매칭 → stepback
      2. 복합 주제 신호어 포함 → decompose
      3. 기본 → hyde
    """
    matches = _SPECIFIC_RE.findall(query)
    matched_groups = sum(1 for m in matches if any(m))
    if matched_groups >= 2:
        return "stepback"
    if _COMPLEX_RE.search(query):
        return "decompose"
    return "hyde"


def apply_hyde(query: str) -> list[str]:
    """원문 + 가상 답변을 반환한다. LLM 실패 시 원문만 반환."""
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": HYDE_PROMPT.format(query=query)}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        hypo = json.loads(resp.choices[0].message.content).get("hypothetical_answer", "")
        if hypo:
            return [query, hypo]
    except Exception:
        pass
    return [query]


def apply_decompose(query: str) -> list[str]:
    """원문 + 서브쿼리들을 반환한다. LLM 실패 시 원문만 반환."""
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": DECOMPOSE_PROMPT.format(query=query)}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        subs = json.loads(resp.choices[0].message.content).get("sub_queries", [])
        if subs:
            return [query] + subs
    except Exception:
        pass
    return [query]


def apply_stepback(query: str) -> list[str]:
    """원문 + 추상화된 원칙 쿼리를 반환한다. LLM 실패 시 원문만 반환."""
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": STEPBACK_PROMPT.format(query=query)}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        abstract = json.loads(resp.choices[0].message.content).get("abstract_query", "")
        if abstract:
            return [query, abstract]
    except Exception:
        pass
    return [query]


_STRATEGY_FN = {
    "hyde":      apply_hyde,
    "decompose": apply_decompose,
    "stepback":  apply_stepback,
}


def rewrite_query(state: GraphState) -> GraphState:
    """rewrite 노드 진입점. state를 받아 search_queries를 채운 뒤 반환한다."""
    try:
        is_accounting = classify_intent(state.query)
        state.is_accounting_query = is_accounting

        if not is_accounting:
            state.search_queries = [state.query]
            state.rewritten_query = RewrittenQuery(
                original=state.query,
                strategy="bypass",
                search_queries=[state.query],
            )
            return state

        strategy = select_strategy(state.query)
        state.query_strategy = strategy

        queries = _STRATEGY_FN[strategy](state.query)
        state.search_queries = queries
        state.rewritten_query = RewrittenQuery(
            original=state.query,
            strategy=strategy,
            search_queries=queries,
        )

    except Exception as e:
        state.search_queries = [state.query]
        state.rewritten_query = RewrittenQuery(
            original=state.query,
            strategy="bypass",
            search_queries=[state.query],
        )
        state.error_logs.append({
            "timestamp": "",
            "node": "rewrite",
            "error_type": type(e).__name__,
            "message": str(e),
        })

    return state
