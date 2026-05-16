# FUNC-007: 검색 맥락 평가 노드 (CRAG 패턴)

from pydantic_ai import Agent
from src.models.state import GraphState
from src.models.schemas import RerankingResult, EvaluationResult
from src.agent.prompts import EVALUATION_PROMPT
from src.utils.config import RERANK_THRESHOLD
from src.utils.exception import AccountingRAGError, EvaluationParsingError
from src.utils.logger import get_logger

logger = get_logger(__name__)

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


def evaluate_context(state: GraphState) -> dict:
    """
    reranked_chunks를 EVALUATION_PROMPT + GPT-4o-mini로 평가한다.
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
    evaluator_agent = Agent("openai:gpt-4o-mini", output_type=EvaluationResult)

    try:
        result = evaluator_agent.run_sync(prompt)
        eval_result: EvaluationResult = result.output
    except AccountingRAGError as e:
        # 도메인 에러: error_logs 기록 + CRAG 루프 유지용 폴백 반환
        # TODO: pydantic_ai 파싱 실패(Exception)와 네트워크 오류(CM-002)를 구분하여
        # 네트워크 오류 시에는 needs_external=True 대신 재시도 횟수 기반 판단 필요
        new_logs = state.error_logs + [e.to_error_log()]
        fallback = EvaluationResult(
            is_relevant=False,
            needs_external=True,
            confidence=0.0,
            reasoning="EV-301: LLM 응답 파싱 실패로 보수적 폴백 반환"
        )
        return {"evaluation": fallback, "error_logs": new_logs}
    except Exception as e:
        # 시스템 에러: 원본 예외 그대로 전파 → LangGraph 파이프라인 중단
        logger.error(f"[{type(e).__name__}] evaluate_context 노드 시스템 에러: {e}", exc_info=True)
        raise

    # reasoning 후처리: 외부 참조 지시가 감지되면 needs_external을 True로 오버라이드
    if check_external_reference(eval_result, state.standard_filter):
        eval_result = eval_result.model_copy(update={"needs_external": True})

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
    return chunk.rerank_score >= RERANK_THRESHOLD and len(chunk.chunk.content.strip()) > 0


def check_external_reference(evaluation: EvaluationResult, standard_filter: str) -> bool:
    """
    평가 결과의 reasoning에서 외부 기준서 참조 필요 여부를 판단한다.

    판단 규칙:
        1. _EXTERNAL_REFERENCE_PHRASES 중 하나라도 reasoning에 포함되면 True
           (명시적 외부 참조 지시는 standard_filter와 무관하게 외부 참조로 본다)
        2. standard_filter가 "ALL"이면 IFRS·GAAP 키워드 단독으로는 True를 반환하지 않음
           (양쪽 기준서가 모두 검색 대상이므로 단순 키워드 등장은 외부 참조가 아님)
        3. standard_filter가 단일 기준서(GAAP/KIFRS)일 때 반대 기준서가 reasoning에 등장하면 True

    Args:
        evaluation: LLM이 산출한 평가 결과
        standard_filter: 사용자가 선택한 기준서 범위 ("GAAP" | "KIFRS" | "ALL")

    Returns:
        bool: 외부 참조 필요 여부
    """
    reasoning = evaluation.reasoning

    if any(phrase in reasoning for phrase in _EXTERNAL_REFERENCE_PHRASES):
        return True

    if standard_filter == "ALL":
        return False

    if standard_filter == "GAAP" and "K-IFRS" in reasoning:
        return True
    if standard_filter == "KIFRS" and "K-GAAP" in reasoning:
        return True

    return False
