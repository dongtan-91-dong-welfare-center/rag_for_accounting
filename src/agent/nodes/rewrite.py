# FUNC-004: 질의 재작성 노드
#
# 처리 순서:
#   1. Classify & Select — 회계 여부 + 전략을 단일 LLM 호출로 판단
#      - bypass  : 비회계 질의 조기 차단
#      - stepback: 회사명·금액·날짜가 포함된 과도하게 구체적인 질의
#      - decompose: 두 가지 이상의 독립적인 주제를 포함한 복합 질의
#      - hyde    : 그 외 일반 질의 (기본값)
#   2. 전략별 LLM 호출 → search_queries 생성
#      - hyde     : [원문, 가상답변]
#      - decompose: [원문, 서브쿼리1, ...]
#      - stepback : [원문, 추상화쿼리]
#   3. LLM 실패 시 원문만 반환 (Bypass)

import json
import re

from src.agent.prompts import (
    CLASSIFY_STRATEGY_PROMPT,
    DECOMPOSE_PROMPT,
    HYDE_PROMPT,
    STEPBACK_PROMPT,
)
from src.models.schemas import RewrittenQuery
from src.models.state import GraphState
from src.utils.config import OPENAI_MODEL
from src.utils.llm_client import client


_STANDARD_LABEL: dict[str, str] = {
    "GAAP":  "일반기업회계기준(K-GAAP)만 적용",
    "KIFRS": "한국채택국제회계기준(K-IFRS)만 적용",
    "ALL":   "K-GAAP 및 K-IFRS 모두 적용",
}


def _standard_context(standard_filter: str) -> str:
    return _STANDARD_LABEL.get(standard_filter, _STANDARD_LABEL["ALL"])


def _strip_markdown(content: str) -> str:
    # LLM이 JSON을 마크다운 코드 블록(```json ... ```)으로 감싸 반환하는 경우 래퍼 제거
    # (?:json)? — "json" 언어 태그가 있어도 없어도 매칭 (```json / ``` 둘 다 처리)
    # (?:...) 는 비캡처 그룹으로, re.sub이 매칭된 전체(```json 포함)를 빈 문자열로 교체
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())


def classify_and_select(query: str) -> tuple[bool, str]:
    """회계 여부와 검색 전략을 단일 LLM 호출로 판단한다. 실패 시 (True, 'hyde')로 폴백."""
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": CLASSIFY_STRATEGY_PROMPT.format(query=query)}],  # {query} 플레이스홀더에 실제 질의 주입
            response_format={"type": "json_object"},
            temperature=0,
        )
        data = json.loads(_strip_markdown(resp.choices[0].message.content))
        raw = data.get("is_accounting", True)
        # LLM이 boolean 대신 문자열 "True"/"False"를 반환하는 경우 명시적 변환
        # str(raw).lower() == "true" → "true"면 True, 아니면 False 반환
        is_accounting = raw if isinstance(raw, bool) else str(raw).lower() == "true"
        strategy = data.get("strategy", "hyde")
        return is_accounting, strategy
    except Exception:
        # !TODO: logger 구현 후 LLM 호출 실패 경고 로그 기록 (예: logger.warning("classify_and_select failed: %s", e))
        return True, "hyde"


def apply_hyde(query: str, standard_filter: str) -> list[str]:
    """원문 + 가상 답변을 반환한다. LLM 실패 시 원문만 반환."""
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": HYDE_PROMPT.format(
                query=query, standard_context=_standard_context(standard_filter)
            )}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        hypo = json.loads(_strip_markdown(resp.choices[0].message.content)).get("hypothetical_answer", "")
        if hypo:
            return [query, hypo]
    except Exception:
        # !TODO: logger 구현 후 LLM 호출 실패 경고 로그 기록 (예: logger.warning("apply_hyde failed: %s", e))
        pass
    return [query]


def apply_decompose(query: str, standard_filter: str) -> list[str]:
    """원문 + 서브쿼리들을 반환한다. LLM 실패 시 원문만 반환."""
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": DECOMPOSE_PROMPT.format(
                query=query, standard_context=_standard_context(standard_filter)
            )}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        subs = json.loads(_strip_markdown(resp.choices[0].message.content)).get("sub_queries", [])
        if subs:
            return [query] + subs
    except Exception:
        # !TODO: logger 구현 후 LLM 호출 실패 경고 로그 기록 (예: logger.warning("apply_decompose failed: %s", e))
        pass
    return [query]


def apply_stepback(query: str, standard_filter: str) -> list[str]:
    """원문 + 추상화된 원칙 쿼리를 반환한다. LLM 실패 시 원문만 반환."""
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": STEPBACK_PROMPT.format(
                query=query, standard_context=_standard_context(standard_filter)
            )}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        abstract = json.loads(_strip_markdown(resp.choices[0].message.content)).get("abstract_query", "")
        if abstract:
            return [query, abstract]
    except Exception:
        # !TODO: logger 구현 후 LLM 호출 실패 경고 로그 기록 (예: logger.warning("apply_stepback failed: %s", e))
        pass
    return [query]


_STRATEGY_FN = {
    "hyde":      apply_hyde,
    "decompose": apply_decompose,
    "stepback":  apply_stepback,
}


def rewrite_query(state: GraphState) -> GraphState:
    """rewrite 노드 진입점. state를 받아 search_queries를 채운 뒤 반환한다."""
    # !TODO: 평가 임계치 미달로 CRAG 루프를 통해 재진입할 때의 처리 방식 결정 필요.
    #        - classify_and_select는 재호출 불필요 (질의·is_accounting 불변) → state 값 재사용
    #        - 전략 교체 여부: 동일 전략 재시도 vs. hyde→decompose→stepback 순 에스컬레이션
    #        - rewrite_count 증가 시점: 이 함수 진입 직후 state.rewrite_count += 1
    try:
        is_accounting, strategy = classify_and_select(state.original_query)
        state.is_accounting_query = is_accounting

        if not is_accounting:
            state.rewritten_query = RewrittenQuery(
                original_query=state.original_query,
                strategy="bypass",
                search_queries=[state.original_query],
            )
            return state

        queries = _STRATEGY_FN[strategy](state.original_query, state.standard_filter)
        state.rewritten_query = RewrittenQuery(
            original_query=state.original_query,
            strategy=strategy,
            search_queries=queries,
        )

    except Exception as e:
        state.rewritten_query = RewrittenQuery(
            original_query=state.original_query,
            strategy="bypass",
            search_queries=[state.original_query],
        )
        state.error_logs.append({
            "timestamp": "",
            "node": "rewrite",
            "error_type": type(e).__name__,
            "message": str(e),
        })

    return state
