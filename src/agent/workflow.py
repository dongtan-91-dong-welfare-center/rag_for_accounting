# FUNC-009: LangGraph StateGraph 파이프라인 정의

import uuid
from datetime import datetime
from functools import wraps, partial
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from src.agent.nodes.generate import generate_response as generate
from src.agent.nodes.evaluate import evaluate_context as evaluate
from src.retrieval.searcher import search_chunks as _search_impl
from src.retrieval.reranker import rerank_chunks as _rerank_impl
from src.utils import config
from src.utils.config import MAX_REWRITE_COUNT, MAX_HIL_COUNT, KST, TOP_K_RETRIEVAL
from src.utils.exception import (
    AccountingRAGError,
    RerankFailureError,
    ScoreThresholdError,
    SearchTimeoutError,
    DatabaseQueryError,
    NoContextFoundError,
    LLMAPIConnectionError,
)
from src.utils.logger import get_logger
from src.models.state import GraphState, ErrorLog
from src.models.schemas import (
    RetrievedChunk, FinalResponse, RerankingResult
)

logger = get_logger(__name__)


def handle_node_errors(node_name: str):
    """
    각 노드에서 발생하는 예외를 캐치하여 state.error_logs에 기록하고,
    워크플로우가 중단되지 않도록 상태를 반환하는 데코레이터입니다.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(state: GraphState) -> dict:
            try:
                return func(state)
            except AccountingRAGError as e:
                # 커스텀 예외 처리(Exception.py에서 정의)
                new_logs = state.error_logs + [e.to_error_log()]
                return {"error_logs": new_logs}
            except Exception as e:
                # 예상치 못한 예외 처리
                error_log = {
                    # src.utils.config에 정의된 KST(+09:00) 타임존을 사용하여 ISO 8601 형식으로 변환
                    "timestamp": datetime.now(KST).isoformat(),
                    "node": node_name,
                    "error_type": "UNKNOWN",
                    "message": str(e)
                }
                new_logs = state.error_logs + [error_log]
                return {"error_logs": new_logs}
        return wrapper
    return decorator

from src.agent.nodes.rewrite import rewrite_query as _rewrite_impl

@handle_node_errors("rewrite")
def rewrite(state: GraphState) -> dict:
    """
    질의 재작성 노드 연결
    """
    # 주의: 래퍼에서 rewrite_count를 증가시키므로, _rewrite_impl 내부에서는 카운트를 증가시키지 않아야 한다는 계약을 유지합니다.
    # 단, HIL 피드백으로 인한 재진입(human_feedback 존재)은 CRAG 재시도가 아니므로
    # rewrite_count를 증가시키지 않는다. (CRAG 루프=rewrite_count, HIL 루프=hil_count로 분리)
    if not state.human_feedback:
        state.rewrite_count += 1

    # 실제 모듈을 통해 상태 변화 수행 (in-place mutation)
    # updated_state는 사실상 state와 동일한 객체입니다.
    updated_state = _rewrite_impl(state)
    
    # TODO: _rewrite_impl과 handle_node_errors 간의 이중 예외 처리 중복 해결 필요
    return {
        "rewrite_count": updated_state.rewrite_count,
        "rewritten_query": updated_state.rewritten_query,
        "is_accounting_query": updated_state.is_accounting_query,
        "classification_confidence": updated_state.classification_confidence,
        # rewrite_query가 사용 후 None으로 초기화한 값을 반드시 채널에 반영해야
        # route_after_human_review가 다음 루프에서 잘못 rewrite로 분기하지 않는다.
        "human_feedback": updated_state.human_feedback,
        "error_logs": updated_state.error_logs,
    }


def early_exit(state: GraphState) -> dict:
    """
    비회계 질문 조기 종료 노드.

    route_after_rewrite가 비회계 질의로 분기시킨 경우 검색·재정렬·평가·생성 파이프라인을
    건너뛰고 안내 메시지를 담은 FinalResponse를 생성한 뒤 END로 종료한다.
    confidence_score에는 rewrite 노드가 기록한 LLM 분류 신뢰도를 그대로 전달하여,
    운영 단계에서 분류 경계가 모호한 케이스를 추출·분석할 수 있도록 한다.
    """
    return {
        "final_response": FinalResponse(
            answer="죄송합니다. 회계 관련 질문을 해 주세요.",
            citations=[],
            is_answerable=False,
            confidence_score=state.classification_confidence,
        )
    }


def route_after_rewrite(state: GraphState) -> Literal["early_exit", "human_review"]:
    """
    rewrite 노드 직후 분기 결정.

    - 비회계 질의(is_accounting_query=False): early_exit 노드로 분기하여 안내 응답 후 종료.
    - 회계 질의: human_review 노드로 진행한다. (HIL 적용 여부는 human_review 노드가 전략 기반으로 결정)
    """
    if not state.is_accounting_query:
        return "early_exit"
    return "human_review"


# 조건부 HIL 트리거 전략: 복잡하거나 추상화가 필요해 사용자 확인 가치가 큰 전략만 중단한다.
# 단순 hyde 전략은 중단 없이 search로 통과시킨다. (운영 데이터 축적 후 confidence 기반 조건 추가 검토)
HIL_STRATEGIES: set[str] = {"decompose", "stepback"}


def human_review(state: GraphState, *, hil_enabled: bool = True) -> dict:
    """
    조건부 Human-in-the-Loop 노드.

    재작성 전략이 HIL_STRATEGIES(decompose/stepback)에 해당하고, 아직 승인되지 않았으며,
    HIL 재작성 횟수가 MAX_HIL_COUNT 미만일 때에만 interrupt()로 워크플로우를 중단하여
    사용자 확인을 받는다. 그 외(단순 hyde 전략·이미 승인·최대 횟수 도달)는 중단 없이 통과한다.

    interrupt() 페이로드에는 구조화된 선택지(options)를 포함해 클라이언트가 UI로 렌더링하도록 한다.
    재개 시 주입되는 값의 action에 따라 분기한다.
      - action="rewrite": human_feedback 저장 + hil_count 증가 → route_after_human_review가 rewrite로 루프백
      - 그 외(approve 등): human_approved=True 설정 → search로 진행

    hil_enabled=False이면 어떤 전략이든 interrupt 없이 통과한다(단위 테스트용 HIL 비활성화 경로)
    build_workflow가 checkpointer 부재 시 이 값을 False로 바인딩한다. interrupt()는 checkpointer 없이는
    호출할 수 없으므로, checkpointer가 없는 단발성 그래프에서 decompose/stepback 질의가 런타임 에러를
    일으키지 않고 search로 통과하도록 보장한다. (프로덕션 기본값은 True로 동작 불변)
    """
    strategy = state.rewritten_query.strategy if state.rewritten_query else "hyde"

    should_review = (
        hil_enabled
        and strategy in HIL_STRATEGIES
        and not state.human_approved
        and state.hil_count < MAX_HIL_COUNT
    )
    if not should_review:
        # 통과: 상태 변경 없음
        return {}

    # interrupt: 워크플로우를 중단하고 사용자 확인을 받음
    decision = interrupt({
        "type": "human_review",
        "strategy": strategy,
        "original_query": state.original_query,
        "search_queries": state.rewritten_query.search_queries if state.rewritten_query else [],
        "hil_count": state.hil_count,
        "max_hil_count": MAX_HIL_COUNT,
        "options": [
            {"action": "approve", "label": "이대로 검색을 진행합니다"},
            {"action": "rewrite", "label": "재작성을 요청합니다 (피드백 입력)"},
        ],
    })

    decision = decision or {}   # decision이 None이면 빈 딕셔너리로 초기화
    if decision.get("action") == "rewrite":
        return {
            "human_feedback": decision.get("feedback", ""),
            "hil_count": state.hil_count + 1,
        }
    # approve(기본): 현재 재작성 결과를 승인 처리
    return {"human_approved": True}


def route_after_human_review(state: GraphState) -> Literal["rewrite", "search"]:
    """
    human_review 노드 직후 분기 결정.

    - human_feedback이 존재하면 사용자가 재작성을 요청한 것 → rewrite로 루프백.
    - 그 외(승인 또는 통과)는 search로 진행.
    """
    if state.human_feedback:
        return "rewrite"
    return "search"

def search(state: GraphState) -> dict:
    """하이브리드 검색 노드 — searcher.search_chunks() 호출"""

    # rewrite 노드 결과에서 검색 쿼리 추출
    search_queries = [state.original_query]
    if state.rewritten_query and state.rewritten_query.search_queries:
        search_queries = state.rewritten_query.search_queries

    # standard_filter → metadata_filter 변환
    metadata_filter = None
    if state.standard_filter != "ALL":
        metadata_filter = {"standard_type": state.standard_filter}

    try:
        # 복수 쿼리에 대해 검색 후 병합·중복 제거
        all_chunks: dict[str, RetrievedChunk] = {}
        for q in search_queries:
            results = _search_impl(q, top_k=TOP_K_RETRIEVAL, metadata_filter=metadata_filter)
            for chunk in results:
                if chunk.chunk_id not in all_chunks or chunk.score > all_chunks[chunk.chunk_id].score:
                    all_chunks[chunk.chunk_id] = chunk

        # score 내림차순 정렬 후 상위 TOP_K 반환
        merged = sorted(all_chunks.values(), key=lambda c: c.score, reverse=True)[:TOP_K_RETRIEVAL]
        return {"retrieved_chunks": merged}

    except (SearchTimeoutError, DatabaseQueryError, LLMAPIConnectionError) as e:
        # SE-101/SE-102/CM-002: 재시도 가능한 타임아웃·DB 오류·임베딩 일시 장애 → CRAG 루프 재진입
        new_logs = state.error_logs + [e.to_error_log()]
        return {
            "retrieved_chunks": [],
            "needs_reretrieval": True,
            "error_logs": new_logs,
        }
    except NoContextFoundError as e:
        # SE-103: 검색 결과 없음 → 재시도 무의미, 빈 결과로 진행
        new_logs = state.error_logs + [e.to_error_log()]
        return {
            "retrieved_chunks": [],
            "needs_reretrieval": False,
            "error_logs": new_logs,
        }
    except AccountingRAGError as e:
        # 그 외 예기치 못한 도메인 에러: 크래시 대신 graceful 강등.
        # 재진입이 유의미한 일시 장애(SE-101/102/CM-002)는 위에서 타입으로 분기하므로,
        # 여기 도달하는 에러는 재시도 무의미로 보고 SE-103처럼 빈 결과로 진행한다.
        new_logs = state.error_logs + [e.to_error_log()]
        return {
            "retrieved_chunks": [],
            "needs_reretrieval": False,
            "error_logs": new_logs,
        }
    except Exception as e:
        # 시스템 에러: 원본 예외 그대로 전파 → LangGraph 파이프라인 중단
        logger.error(f"[{type(e).__name__}] search 노드 시스템 에러: {e}", exc_info=True)
        raise


def rerank(state: GraphState) -> dict:
    """
    워크플로우 노드: USE_RERANKER 활성화 여부에 따라 재정렬 모델 호출 여부를 결정한다.

    동작:
        - USE_RERANKER=false: 모델 호출 없이 retrieved_chunks를 score=1.0으로 래핑하여 반환
        - USE_RERANKER=true: rerank() 유틸리티 호출 → 임계값 필터링 → 예외 처리
          - ScoreThresholdError: needs_reretrieval=True + reranked_chunks=[]
          - RerankFailureError: needs_reretrieval=False + fallback(1차 검색 결과 순서 유지)
    """
    # 활성화 여부 확인 (조기 반환 - 모델 호출 없음)
    if not config.USE_RERANKER:
        logger.info("USE_RERANKER=false: 모델 호출 스킵, 1차 검색 결과 반환")
        fallback = [RerankingResult(chunk=c, rerank_score=1.0)
                    for c in state.retrieved_chunks]
        return {
            "reranked_chunks": fallback,
            "needs_reretrieval": False,
            "error_logs": state.error_logs,
        }

    logger.info(
        f"재정렬 수행: {len(state.retrieved_chunks)}개 청크, "
        f"질의: {state.original_query[:50]}..."
    )

    # TODO: search 노드 구현 후 search-rerank 간 관계 재정의 후에 처리 방식을 명확하게 결정해야 함
    # 현재는 retrieved_chunks가 비어있을 때 조기 반환하여 ScoreThresholdError를 발생시키지 않는다.
    # 이는 search 노드 실패(빈 결과)와 리랭킹 자체 실패를 구분하기 위함이다.
    if not state.retrieved_chunks:
        return {"reranked_chunks": []}

    # rerank() 유틸리티 함수 호출 (실제 모델 추론)
    try:
        results = _rerank_impl(state.original_query, state.retrieved_chunks)

        if not results:
            logger.warning("재정렬 후 유효한 청크가 없습니다.")
            raise ScoreThresholdError("재정렬 후 유효한 청크가 없습니다.")

        # rerank()가 내림차순 정렬을 보장하므로 0번째가 최고 점수
        max_score = results[0].rerank_score
        if max_score < config.RERANK_THRESHOLD:
            logger.warning(
                f"재정렬 점수 임계값 미달: 최고점={max_score}, "
                f"임계값={config.RERANK_THRESHOLD}"
            )
            raise ScoreThresholdError(
                f"최고 관련도({max_score})가 임계값({config.RERANK_THRESHOLD})에 미달합니다."
            )

        logger.info(f"재정렬 완료: {len(results)}개 청크 반환")
        return {"reranked_chunks": results, "needs_reretrieval": False}

    except AccountingRAGError as e:
        new_logs = state.error_logs + [e.to_error_log()]
        if isinstance(e, RerankFailureError):
            # 모델 실패 → 1차 검색 결과 순서 유지하여 fallback 반환, 재검색 신호 없음
            fallback = [
                RerankingResult(chunk=c, rerank_score=c.score)
                for c in state.retrieved_chunks
            ]
            return {
                "reranked_chunks": fallback,
                "needs_reretrieval": False,
                "error_logs": new_logs,
            }
        # ScoreThresholdError 등: 점수 임계치 미달 → 재검색 신호
        return {
            "reranked_chunks": [],
            "needs_reretrieval": True,
            "error_logs": new_logs,
        }
    except Exception as e:
        # 시스템 예외는 AccountingRAGError로 래핑하지 않고 원본 타입 그대로 전파한다.
        logger.critical(f"[{type(e).__name__}] rerank 노드 치명적 오류: {e}", exc_info=True)
        raise


def route_after_evaluate(state: GraphState) -> str:
    """
    TODO: FUNC-009 (평가 후 라우팅 결정)
    평가 결과 또는 에러 상태에 따라 다음 노드를 결정한다.

    [IF문 우선순위]
    1순위: needs_reretrieval (어느 노드에서든 재검색이 확정된 상태)
    2순위: evaluate 노드 자체 에러 안전장치 (무한 루프 방지)
    3순위: evaluation.needs_external 기반 CRAG 루프

    needs_reretrieval을 최상단에 두는 이유:
    rerank가 reranked_chunks=[]를 evaluate에 넘기면 evaluate가 자체 실패할 가능성이 높아
    error_logs[-1]["node"] == "evaluate" 조건이 먼저 트리거되고, 결과적으로 needs_reretrieval=True 신호가
    무시된 채 잘못된 답변 생성으로 직행하는 버그가 발생한다.
    """
    # TODO: evaluation이 None일 경우의 예외 처리에 대해 재검토 요망.
    # 현재 단계에서는 유닛 테스트와의 충돌 방지 및 파이프라인의 안전한 종료를 위해 
    # ValueError 발생 대신 generate로 안전하게 우회하도록 유지합니다.

    # 1순위: 어느 노드에서든 재검색이 확정된 상태라면, 다른 안전장치보다 먼저 rewrite를 고려한다.
    if state.needs_reretrieval and state.rewrite_count < MAX_REWRITE_COUNT:
        return "rewrite"

    # 2순위: evaluate 노드 자체에서 에러가 발생했다면, 무한 루프 방지를 위해 강제로 generate로 우회한다.
    if state.error_logs and state.error_logs[-1]["node"] == "evaluate":
        return "generate"

    # 3순위: CRAG (Corrective RAG) 루프 진입 조건 판단
    # 아래 3가지 조건이 모두 만족될 때만 rewrite 노드로 돌아가서 쿼리 재작성 및 검색을 다시 시도합니다.
    #   (1) state.evaluation 존재: 정상적으로 평가 결과 객체가 반환되었는가?
    #   (2) needs_external == True: LLM이 기존 컨텍스트만으로는 부족하여 외부 정보가 더 필요하다고 판단했는가?
    #   (3) rewrite_count < MAX_REWRITE_COUNT: 무한 루프를 막기 위한 최대 재시도 횟수 제한(예: 3회)을 넘지 않았는가?
    if (state.evaluation and
        state.evaluation.needs_external and
        state.rewrite_count < MAX_REWRITE_COUNT):
        return "rewrite"

    # 답변 생성 단계로 진행
    # 검색된 컨텍스트가 충분히 유효하거나(needs_external=False), 이미 최대 재시도 횟수를 소진했다면 답변을 생성합니다.
    return "generate"

def build_workflow(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """
    LangGraph StateGraph를 구성하고 컴파일하여 반환합니다.

    노드 등록 및 조건부 엣지를 정의하여 StateGraph를 반환한다.
    실행 순서: rewrite → (회계 질의) human_review → search → rerank → evaluate → generate
                       → (비회계 질의) early_exit → END
    rewrite 이후 route_after_rewrite, human_review 이후 route_after_human_review,
    evaluate 이후 route_after_evaluate로 분기 처리.

    Args:
        checkpointer: HIL(interrupt/resume)을 위한 상태 저장소.
        None이면 체크포인트 없이 컴파일되며 interrupt()를 호출할 수 없다(단순 단방향 실행 전용).
        이때 human_review 노드는 HIL 비활성화(hil_enabled=False)로 바인딩되어 decompose/stepback
        질의도 interrupt 없이 search로 통과한다.
        HIL을 사용하는 run_workflow/resume_workflow는 MemorySaver 싱글턴(_CHECKPOINTER)을 주입한다.

    return CompiledStateGraph : LangGraph로 빌드된 상태 그래프
    왜 CompiledGraph를 사용하는가? -> StateGraph보다 성능이 좋다. (동작 방식은 동일하지만 내부적으로 최적화됨)
    동작 방식이 어떠한데? -> LangGraph의 build_workflow를 통해 StateGraph를 컴파일하면 CompiledStateGraph 객체가 반환된다.
    이 객체는 내부적으로 최적화되어 StateGraph보다 빠른 실행 속도를 제공한다. 
    """
    workflow = StateGraph(GraphState)

    # checkpointer가 없으면 interrupt()를 호출할 수 없으므로 HIL을 비활성화한다.
    # human_review 노드는 state만 받으므로 partial로 hil_enabled를 바인딩해 주입한다.
    hil_enabled = checkpointer is not None

    # 노드 추가
    workflow.add_node("rewrite", rewrite)
    workflow.add_node("early_exit", early_exit)
    workflow.add_node("human_review", partial(human_review, hil_enabled=hil_enabled))
    workflow.add_node("search", search)
    workflow.add_node("rerank", rerank)
    workflow.add_node("evaluate", evaluate)
    workflow.add_node("generate", generate)

    # 엣지 연결 (고정 흐름)
    workflow.add_edge(START, "rewrite")

    # rewrite 직후 조건부 분기: 비회계 질의는 early_exit로 조기 종료, 회계 질의는 human_review로 진행
    workflow.add_conditional_edges(
        "rewrite",
        route_after_rewrite,
        {
            "early_exit": "early_exit",
            "human_review": "human_review",
        }
    )
    workflow.add_edge("early_exit", END)

    # human_review 직후 조건부 분기: 사용자가 재작성 요청 시 rewrite로 루프백, 아니면 search로 진행
    workflow.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "rewrite": "rewrite",
            "search": "search",
        }
    )

    workflow.add_edge("search", "rerank")
    workflow.add_edge("rerank", "evaluate")

    # 조건부 엣지 연결 (평가 결과에 따른 분기)
    workflow.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {
            "rewrite": "rewrite",
            "generate": "generate"
        }
    )

    workflow.add_edge("generate", END)

    # 그래프 컴파일 (checkpointer가 주어지면 HIL interrupt/resume 지원)
    return workflow.compile(checkpointer=checkpointer)


# HIL(interrupt/resume) 상태를 run_workflow와 resume_workflow 호출 간 공유하기 위한 인메모리 체크포인터 싱글턴
# MemorySaver는 체크포인트를 자신의 내부 저장소에 thread_id로 보관하므로
# 매 호출마다 build_workflow로 그래프를 새로 컴파일하더라도 동일 인스턴스를 주입하면 중단된 세션을 정상적으로 재개할 수 있다.
# !TODO: 실서비스 전환 시 AsyncPostgresSaver로 교체 (checkpointer 인터페이스 통일됨)
_CHECKPOINTER: BaseCheckpointSaver = MemorySaver()


def _run_config(thread_id: str, metadata: dict[str, Any] | None = None) -> RunnableConfig:
    """LangGraph invoke에 전달할 실행 설정. thread_id로 HIL 세션을 식별한다.

    metadata가 주어지면 RunnableConfig.metadata로 전달한다.
    LangSmith 트레이싱이 활성(LANGCHAIN_TRACING_V2=true)일 때 케이스 ID·gold 조항 등이 트레이스에 부착되어 분석 시 필터 키로 쓰인다.
    트레이싱 비활성 시에는 무해하게 무시되므로(LangGraph가 config.metadata를 항상 허용)
    키 부재 환경에서도 동일하게 정상 동작한다.
    """
    run_config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": MAX_REWRITE_COUNT * 5 + 5,
    }
    if metadata:
        run_config["metadata"] = metadata
    return run_config


def _recursion_fallback_response() -> FinalResponse:
    return FinalResponse(
        answer="너무 많은 재시도가 발생하여 답변을 생성하지 못했습니다. 질문을 구체화하여 다시 시도해주세요.",
        citations=[],
        is_answerable=False,
        confidence_score=0.0,
    )


def _timeout_fallback_response() -> FinalResponse:
    return FinalResponse(
        answer="처리 시간이 초과되어 답변을 생성하지 못했습니다. 잠시 후 다시 시도해주세요.",
        citations=[],
        is_answerable=False,
        confidence_score=0.0,
    )


def _timeout_error_log(e: TimeoutError) -> ErrorLog:
    # step_timeout은 그래프 러너가 던지므로 어느 노드에서 초과됐는지 특정할 수 없다 → node="workflow"
    return {
        "timestamp": datetime.now(KST).isoformat(),
        "node": "workflow",
        "error_type": "TIMEOUT",
        "message": str(e) or "노드 실행이 step_timeout을 초과했습니다.",
    }


def thread_exists(thread_id: str) -> bool:
    """체크포인터에 thread_id의 체크포인트가 존재하는지 여부.

    resume_workflow는 미존재 thread_id에 대한 동작이 정의돼 있지 않으므로(체크포인트 없이
    Command(resume=...) 주입), API 계층(#195)이 재개 전에 이 함수로 404를 판정한다.
    """
    return _CHECKPOINTER.get(_run_config(thread_id)) is not None


def run_workflow(
    query: str,
    standard_filter: Literal["GAAP", "KIFRS", "ALL"] = "ALL",
    thread_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    외부에서 워크플로우를 실행하기 위한 진입점 함수.

    HIL을 지원하기 위해 MemorySaver 체크포인터를 주입하고 thread_id로 세션을 식별한다.
    thread_id가 주어지지 않으면 새 UUID를 발급한다. 반환 dict에는 항상 thread_id가 포함되어,
    워크플로우가 human_review에서 중단(`__interrupt__` 키 존재)된 경우 클라이언트가 이 값을
    resume_workflow에 전달하여 재개할 수 있다.

    metadata는 LangSmith 트레이스에 부착할 케이스 식별 정보(예: {"case_id", "gold"})로,
    _run_config를 통해 RunnableConfig.metadata로 전달된다. 
    트레이싱 비활성 시 무시된다.
    """
    app = build_workflow(checkpointer=_CHECKPOINTER)

    # 노드별 30초 타임아웃 설정 (LangGraph CompiledStateGraph 속성)
    app.step_timeout = 30

    if thread_id is None:
        thread_id = str(uuid.uuid4())

    initial_state = GraphState(original_query=query, standard_filter=standard_filter)

    try:
        # 정상/중단 반환 시 LangGraph의 invoke()는 dict를 반환하며 값들은 Pydantic 객체를 유지합니다.
        # human_review에서 interrupt가 발생하면 반환 dict에 "__interrupt__" 키가 포함됩니다.
        result = app.invoke(initial_state, config=_run_config(thread_id, metadata))
        result["thread_id"] = thread_id
        return result
    except GraphRecursionError:
        # GraphRecursionError 발생 시 최선 답변 혹은 답변 불가 상태 반환
        initial_state.final_response = _recursion_fallback_response()
        # TODO: 예외 발생 시 error_logs 기록 및 상태 반환 로직 정교화
        # invoke() 결과와 동일한 직렬화 구조 유지를 위해, model_dump() 대신
        # Pydantic 인스턴스를 값으로 유지하는 dict comprehension 방식을 사용합니다.
        fallback = {k: getattr(initial_state, k) for k in GraphState.model_fields}  # 예시: {'original_query': '....', ...}
        fallback["thread_id"] = thread_id
        return fallback
    except TimeoutError as e:
        # 노드 실행이 step_timeout을 초과 — 구조화 반환 계약(#131)에 따라
        # GraphRecursionError와 동일하게 폴백 GraphState + error_logs를 반환한다.
        initial_state.final_response = _timeout_fallback_response()
        initial_state.error_logs = initial_state.error_logs + [_timeout_error_log(e)]
        fallback = {k: getattr(initial_state, k) for k in GraphState.model_fields}
        fallback["thread_id"] = thread_id
        return fallback


def resume_workflow(
    thread_id: str,
    resume_value: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    human_review에서 interrupt로 중단된 워크플로우를 재개한다.

    thread_id로 체크포인터에 보관된 중간 상태를 복원하고, resume_value를 human_review 노드의 interrupt() 반환값으로 주입하여 실행을 이어간다.
    resume_value는 구조화된 결정 dict이며, 예: {"action": "approve"} 또는 {"action": "rewrite", "feedback": "리스 회계처리를 강조해줘"}.

    반환 dict에는 thread_id가 포함된다. 사용자가 다시 재작성을 요청하여 또 한 번 중단되면
    반환 dict에 "__interrupt__" 키가 존재하므로, 동일 thread_id로 재차 resume_workflow를 호출한다.

    metadata는 run_workflow와 동일한 케이스 식별 정보를 재개 실행 트레이스에도 부착하기 위한 것으로,
    호출자가 run_workflow에 넘긴 값을 그대로 전달하면 한 케이스의 run/resume 트레이스가 동일 메타데이터를 공유한다.
    """
    app = build_workflow(checkpointer=_CHECKPOINTER)
    app.step_timeout = 30

    try:
        result = app.invoke(Command(resume=resume_value), config=_run_config(thread_id, metadata))
        result["thread_id"] = thread_id
        return result
    except GraphRecursionError:
        # 재개 시점에는 initial_state가 없으므로 체크포인트에 보관된 현재 상태를 복원해 폴백을 구성한다.
        snapshot = app.get_state(_run_config(thread_id))
        fallback = dict(snapshot.values)
        fallback["final_response"] = _recursion_fallback_response()
        fallback["thread_id"] = thread_id
        return fallback
    except TimeoutError as e:
        # 재개 중 타임아웃도 재전파 대신 체크포인트 상태 기반 폴백을 반환한다(#131).
        snapshot = app.get_state(_run_config(thread_id))
        fallback = dict(snapshot.values)
        fallback["final_response"] = _timeout_fallback_response()
        fallback["error_logs"] = list(fallback.get("error_logs", [])) + [_timeout_error_log(e)]
        fallback["thread_id"] = thread_id
        return fallback
