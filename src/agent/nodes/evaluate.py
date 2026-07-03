# FUNC-007: 검색 맥락 평가 노드 (CRAG 패턴)
import re

import httpx
import pydantic
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from src.models.state import GraphState
from src.models.schemas import RerankingResult, EvaluationResult
from src.agent.prompts import EVALUATION_PROMPT
from src.utils import config
from src.utils.config import MAX_REWRITE_COUNT, OPENAI_MODEL
from src.utils.exception import (
    AccountingRAGError,
    EvaluationParsingError,
    LLMAPIConnectionError,
    InconsistentVerdictError,
    HallucinationDetectedError,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# !TODO: 기준서 참조 신호에 대해 더 정교한 방식이 필요함
# 외부 기준서 참조 지시를 나타내는 신호 문구.
# reasoning에 다음 중 하나라도 포함되면 standard_filter 값과 무관하게 외부 참조로 판단한다.
_EXTERNAL_REFERENCE_PHRASES: tuple[str, ...] = (
    "타 기준서 준용",
    "타 기준서를 준용",
    "타 기준서 참조",
    "타 기준서를 참조",
    "다른 기준서를 참조",
    "다른 기준서 참조",
    "외부 기준서",
    "준용한다",
)

# 외부 참조 문구가 부정 문맥("… 필요하지 않습니다")에서 등장하면 외부 참조로 보지 않기 위한
# 부정 종결 마커. 외부 참조 문구와 같은 문장에 이 마커가 있으면 그 신호는 무시한다.
# 단순 substring 매칭이 "외부 기준서 … 필요하지 않습니다"를 외부 참조로 오탐해 needs_external을 강제 True로 만들고 CRAG 루프를 3배 공회전 방지
_NEGATION_MARKERS: tuple[str, ...] = (
    "않",       # …하지 않다 / 않습니다 / 않으며
    "없",       # 필요 없다 / 없습니다
    "불필요",
    "아니",     # …가 아니라 …
)

# 부정 판정을 문장 단위로 한정해, 다른 문장의 부정이 외부 참조 신호를 잘못 무력화하지 않도록 한다.
_SENTENCE_SPLIT = re.compile(r"[.!?\n]+")

# NOTE:K-GAAP 같은 경우는 제 #### 호와 같은 형태가 아니라 제 ## 장인 것으로 알고 있음
# 조항 번호 패턴: K-IFRS/K-GAAP 기준서 번호, 3자리 이상 호수, 조항 번호
# 2자리 이하 단독 번호는 일반 수치와 구분이 불가하여 제외한다.
_CITATION_PATTERN = re.compile(
    r'(?:K-IFRS|K-GAAP)\s*제\s*\d+\s*호'   # 예: K-IFRS 제1116호
    r'|제\s*\d{3,}\s*호'                     # 예: 제1116호 (3자리 이상)
    r'|제\s*\d+\s*조(?:의\s*\d+)?'           # 예: 제15조, 제15조의2
)


def evaluate_context(state: GraphState) -> dict:
    """
    reranked_chunks를 EVALUATION_PROMPT + config.OPENAI_MODEL로 평가한다.
    - 결과를 state.evaluation에 저장
    - needs_external=True이면 workflow가 외부 검색 경로로 라우팅
    """
    # 빈 컨텍스트 조기 반환: 재검색이 무의미하므로 needs_external=False
    if not state.reranked_chunks:
        return {
            "evaluation": EvaluationResult(
                is_relevant=False,
                needs_external=False,
                confidence=0.0,
                reasoning="reranked_chunks가 비어 있어 평가 대상 컨텍스트가 없습니다."
            )
        }

    # 관련 청크만 필터링 (rerank_score 임계값 + content 비어있지 않음)
    relevant_chunks = [r for r in state.reranked_chunks if check_relevance(r, state.original_query)]

    if not relevant_chunks:
        return {
            "evaluation": EvaluationResult(
                is_relevant=False,
                needs_external=False,
                confidence=0.0,
                reasoning="rerank_score가 임계값 미만이거나 본문이 비어 있는 청크만 존재합니다."
            )
        }

    # 청크 인덱스 부여 후 프롬프트 컨텍스트 조립
    chunks_text = "\n\n".join(
        f"[{idx}] {r.chunk.content}" for idx, r in enumerate(relevant_chunks, start=1)
    )

    prompt = EVALUATION_PROMPT.format(
        query=state.original_query,
        standard_filter=state.standard_filter,
        chunks=chunks_text,
    )

    # PydanticAI Agent로 EvaluationResult 직접 파싱
    # 접두사를 "openai-chat:"으로 고정한다. pydantic-ai v2.0부터 "openai:"는 Responses API로
    # 해석되도록 바뀌어 DeprecationWarning이 발생하므로, 현행 Chat Completions 동작을 명시적으로 유지한다.
    evaluator_agent = Agent(f"openai-chat:{OPENAI_MODEL}", output_type=EvaluationResult)

    try:
        # PydanticAI 실행 — 파싱 실패(pydantic.ValidationError/UnexpectedModelBehavior)를 EV-301로 래핑한다.
        # (generate 노드와 동일 패턴) 래핑하지 않으면 아래 except Exception으로 떨어져 노드가 하드 크래시한다.
        try:
            result = evaluator_agent.run_sync(prompt)
            eval_result: EvaluationResult = result.output
        except (pydantic.ValidationError, UnexpectedModelBehavior) as e:
            raise EvaluationParsingError(f"LLM 평가 응답 파싱 실패: {e}")
        except httpx.RequestError as e:
            raise LLMAPIConnectionError(f"LLM API 연결 오류: {e}", node="evaluate")
    except EvaluationParsingError as e:
        # EV-301: 파싱 실패 → CRAG 루프 재진입 유도 (보수적 폴백)
        new_logs = state.error_logs + [e.to_error_log()]
        fallback = EvaluationResult(
            is_relevant=False,
            needs_external=True,
            confidence=0.0,
            reasoning="EV-301: LLM 응답 파싱 실패로 보수적 폴백 반환"
        )
        return {"evaluation": fallback, "error_logs": new_logs}

    except LLMAPIConnectionError as e:
        # CM-002: 네트워크 오류 → rewrite_count 기반 판단
        # 재시도 여지가 있으면 CRAG 루프로 재진입, 한계 도달 시 강제 종료
        new_logs = state.error_logs + [e.to_error_log()]
        needs_external = state.rewrite_count < MAX_REWRITE_COUNT
        fallback = EvaluationResult(
            is_relevant=False,
            needs_external=needs_external,
            confidence=0.0,
            reasoning=f"CM-002: API 연결 오류, {'재시도 가능' if needs_external else '최대 재시도 도달'}"
        )
        return {"evaluation": fallback, "error_logs": new_logs}

    except AccountingRAGError as e:
        # 기타 도메인 에러: 보수적 폴백으로 CRAG 루프 유지
        new_logs = state.error_logs + [e.to_error_log()]
        fallback = EvaluationResult(
            is_relevant=False,
            needs_external=True,
            confidence=0.0,
            reasoning=f"{type(e).__name__}: 도메인 에러 보수적 폴백"
        )
        return {"evaluation": fallback, "error_logs": new_logs}

    except Exception as e:
        # 시스템 에러: 원본 예외 그대로 전파 → LangGraph 파이프라인 중단
        logger.error(f"[{type(e).__name__}] evaluate_context 노드 시스템 에러: {e}", exc_info=True)
        raise

    # reasoning 후처리: 외부 참조 지시가 감지되면 needs_external을 True로 오버라이드
    if check_external_reference(eval_result, state.standard_filter):
        eval_result = eval_result.model_copy(update={"needs_external": True})

    # EV-302: 내부 일관성 검증
    try:
        validate_verdict(eval_result)
    except InconsistentVerdictError as e:
        new_logs = state.error_logs + [e.to_error_log()]
        fallback = EvaluationResult(
            is_relevant=False,
            needs_external=False,
            confidence=0.0,
            reasoning="EV-302: 평가 결과 내부 일관성 위반으로 보수적 폴백 반환"
        )
        return {"evaluation": fallback, "error_logs": new_logs}

    # EV-303: 환각 감지 검증
    try:
        detect_hallucination(eval_result, relevant_chunks)
    except HallucinationDetectedError as e:
        new_logs = state.error_logs + [e.to_error_log()]
        fallback = EvaluationResult(
            is_relevant=False,
            needs_external=False,
            confidence=0.0,
            reasoning="EV-303: 근거 없는 주장 감지로 is_relevant=False 반환"
        )
        return {"evaluation": fallback, "error_logs": new_logs}

    return {"evaluation": eval_result}


def check_relevance(chunk: RerankingResult, query: str) -> bool:
    """
    단일 청크가 질의에 관련성이 있는지 판단한다.

    조건:
        - rerank_score가 RERANK_THRESHOLD 이상
        - chunk.content가 공백 외 문자를 포함

    Args:
        chunk: 재정렬된 청크 결과
        query: 사용자 원본 질의 (현재 미사용, 추후 의미 기반 필터링 확장 여지)

    Returns:
        bool: 관련성 충족 여부
    """
    return chunk.rerank_score >= config.RERANK_THRESHOLD and len(chunk.chunk.content.strip()) > 0


def _is_negated(sentence: str) -> bool:
    """문장에 부정 종결 마커가 포함되어 있으면 True(외부 참조 신호를 무시해야 하는 문맥)."""
    return any(marker in sentence for marker in _NEGATION_MARKERS)


def _signals_external_reference(reasoning: str, standard_filter: str | None = None) -> bool:
    """reasoning을 문장 단위로 보고, 부정 문맥이 아닌 외부 참조 신호가 하나라도 있으면 True.

    - _EXTERNAL_REFERENCE_PHRASES(명시적 외부 참조 지시)는 standard_filter와 무관하게 신호로 본다.
    - standard_filter가 단일 기준서(GAAP/KIFRS)면 같은 문장에 반대 기준서가 등장해도 신호로 본다.
    - 외부 참조 문구가 부정 문맥("… 필요하지 않습니다")에 있는 문장은 신호에서 제외한다.
    """
    for sentence in _SENTENCE_SPLIT.split(reasoning):
        if _is_negated(sentence):
            continue
        if any(phrase in sentence for phrase in _EXTERNAL_REFERENCE_PHRASES):
            return True
        if standard_filter == "GAAP" and "K-IFRS" in sentence:
            return True
        if standard_filter == "KIFRS" and "K-GAAP" in sentence:
            return True
    return False


def check_external_reference(evaluation: EvaluationResult, standard_filter: str) -> bool:
    """
    평가 결과의 reasoning에서 외부 기준서 참조 필요 여부를 판단한다.

    판단 규칙:
        1. _EXTERNAL_REFERENCE_PHRASES 중 하나가 (부정 문맥이 아닌) 문장에 포함되면 True
           (명시적 외부 참조 지시는 standard_filter와 무관하게 외부 참조로 본다)
        2. standard_filter가 "ALL"이면 IFRS·GAAP 키워드 단독으로는 True를 반환하지 않음
           (양쪽 기준서가 모두 검색 대상이므로 단순 키워드 등장은 외부 참조가 아님)
        3. standard_filter가 단일 기준서(GAAP/KIFRS)일 때 반대 기준서가 (부정 문맥이 아닌)
           문장에 등장하면 True
        4. 외부 참조 문구가 부정 문맥("… 필요하지 않습니다")에서 등장하면 외부 참조로 보지 않는다.

    Args:
        evaluation: LLM이 산출한 평가 결과
        standard_filter: 사용자가 선택한 기준서 범위 ("GAAP" | "KIFRS" | "ALL")

    Returns:
        bool: 외부 참조 필요 여부
    """
    return _signals_external_reference(evaluation.reasoning, standard_filter)


def validate_verdict(eval_result: EvaluationResult) -> None:
    """
    EvaluationResult 내부 일관성 검증. 불일치 시 InconsistentVerdictError 발생.

    검증 규칙:
        1. is_relevant=True이고 confidence < 0.3이면 신뢰도 불일치
        2. needs_external=True이고 is_relevant=True인데 reasoning에 외부 참조 근거가 없으면 불일치
    """
    if eval_result.is_relevant and eval_result.confidence < 0.3:
        raise InconsistentVerdictError(
            f"is_relevant=True이지만 confidence={eval_result.confidence:.2f}로 신뢰도 불일치"
        )
    # needs_external=True이고 is_relevant=True이면 외부 참조가 필요하다.
    if eval_result.needs_external and eval_result.is_relevant:
        # 외부 참조 지시어가 있는지 확인.
        # check_external_reference와 동일한 부정-인지 판정을 공유해, 부정 문맥("… 필요하지 않습니다")의
        # 외부 참조 문구를 신호로 오인하던 문제를 일관되게 차단한다.
        has_external_signal = _signals_external_reference(eval_result.reasoning)
        # 외부 참조 지시어가 없으면 불일치
        if not has_external_signal:
            raise InconsistentVerdictError(
                "needs_external=True이지만 is_relevant=True이고 외부 참조 근거가 없어 불일치"
            )


def detect_hallucination(eval_result: EvaluationResult, chunks: list[RerankingResult]) -> None:
    """
    reasoning에 인용된 조항 번호가 컨텍스트 청크에 존재하는지 검증.
    청크에 없는 조항이 인용되면 HallucinationDetectedError 발생.
    """
    if not chunks:
        return

    context = " ".join(r.chunk.content for r in chunks)
    citations = _CITATION_PATTERN.findall(eval_result.reasoning)

    for citation in citations:
        # 공백 제거
        normalized_citation = re.sub(r'\s+', '', citation)
        normalized_context = re.sub(r'\s+', '', context)
        if normalized_citation not in normalized_context:
            raise HallucinationDetectedError(
                f"reasoning에 인용된 '{citation}'이 컨텍스트 청크에서 발견되지 않았습니다."
            )
