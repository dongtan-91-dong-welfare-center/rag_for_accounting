# FUNC-009: LangGraph 파이프라인 전체 노드가 공유하는 상태 객체
from pydantic import BaseModel, field_validator
from typing import TypedDict
from src.models.schemas import RewrittenQuery, RetrievedChunk, RerankingResult, EvaluationResult, FinalResponse

class ErrorLog(TypedDict):
    """
    각 노드 실행 중 발생한 예외 정보를 기록하는 타입 딕셔너리.
    """
    timestamp:  str   # ISO 8601 형식의 한국 표준시(KST, +09:00). 예: "2026-04-19T10:00:00+09:00" (src.utils.config KST 활용)
    node:       str   # 예외가 발생한 노드명: "rewrite" | "search" | "rerank" | "evaluate" | "generate" | "parse" | "ontology" | "index"
    error_type: str   # 커스텀 에러 코드 (예: "CM-002", "SE-101") 또는 일반 예외 시 "UNKNOWN"
    message:    str   # 에러 상세 메시지

class GraphState(BaseModel):
    """
    LangGraph StateGraph의 공유 상태 (State) 객체.
    모든 노드는 이 상태를 입력받아 작업을 수행하고, 변경할 필드만 담은 dict를 반환하여 증분 업데이트(Merge) 합니다.
    전체 흐름은 [상태 다이어그램](docs/assets/arch-state.svg)을 참고하세요.
    """
    # 사용자 초기 입력값
    query:                str                    # 워크플로우 시작 시 주입됨. 불변에 가깝게 유지

    # 의도 분류 (향후 구현 예정)
    is_accounting_query:  bool                   = True   # 회계 질의 여부. 비회계면 rewrite 노드에서 Bypass

    # 질의 재작성 및 검색 관련
    rewrite_count:        int                    = 0      # [rewrite 노드] CRAG 루프 진입 횟수 기록 (최대 MAX_REWRITE_COUNT)
    rewritten_query:      RewrittenQuery | None  = None   # [rewrite 노드] 검색에 최적화된 새로운 쿼리
    
    # 문서 검색 및 재정렬 관련
    retrieved_chunks:     list[RetrievedChunk]   = []     # [search 노드] DB/벡터 검색된 원본 문서 청크 리스트
    reranked_chunks:      list[RerankingResult]  = []     # [rerank 노드] 쿼리와의 유사도를 기준으로 재정렬 및 필터링된 결과
    
    # 평가 및 답변 생성 관련
    evaluation:           EvaluationResult | None = None  # [evaluate 노드] 검색된 컨텍스트가 질의에 답하기 충분한지에 대한 LLM 판단
    final_response:       FinalResponse | None   = None   # [generate 노드] 최종 사용자 답변 및 참조 문서 메타데이터

    # 에러 추적 및 부가 정보 (선택적 병합)
    # 참고: error_logs를 노드가 실행될 때마다 기존 로그에 누적 추가하기 위해 데코레이터에서 직접 list.append()를 수행하거나, 
    # LangGraph의 Annotated[list, add_messages] 패턴을 도입할 수 있습니다.
    error_logs:           list[ErrorLog]         = []     # 예외 발생 시 누적
    metadata:             dict                   = {}     # 예: {"search_mode": "hybrid"}

    # Pseudo validator:
    # @field_validator("rewrite_count")
    # def count_non_negative(cls, v):
    #     assert v >= 0
    #     return v