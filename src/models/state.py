# FUNC-009: LangGraph 파이프라인 전체 노드가 공유하는 상태 객체
from pydantic import BaseModel, field_validator
from typing import TypedDict
from src.models.schemas import RewrittenQuery, RetrievedChunk, RerankingResult, EvaluationResult, FinalResponse

class ErrorLog(TypedDict):
    timestamp:  str   # ISO 8601 (UTC), 예: "2026-04-19T10:00:00Z"
    node:       str   # 노드명: "rewrite" | "search" | "rerank" | "evaluate" | "generate"
    error_type: str   # 예외 클래스명, 예: "TimeoutError"
    message:    str   # str(e)

class GraphState(BaseModel):
    """LangGraph StateGraph의 공유 상태"""
    # error_logs를 노드가 실행될 때마다 기존 로그에 추가하고 싶다면 Annotated를 활용할 수 있음
    query:                str
    is_accounting_query:  bool                   = True    # Intent Classification 결과
    query_strategy:       str                    = "hyde"  # "hyde" | "decompose" | "stepback"
    search_queries:       list[str]              = []      # search 노드에 전달할 쿼리 목록
    crag_count:           int                    = 0       # CRAG 반복 횟수 (최대 3)
    rewritten_query:      RewrittenQuery | None  = None
    retrieved_chunks: list[RetrievedChunk]   = []
    reranked_chunks:  list[RerankingResult]  = []
    evaluation:       EvaluationResult | None = None
    final_response:   FinalResponse | None   = None
    rewrite_count:    int                    = 0      # 초기값 0, 상한: MAX_REWRITE_COUNT
    error_logs:       list[ErrorLog]         = []
    metadata:         dict                   = {}     # 예: {"search_mode": "hybrid"}

    # Pseudo validator:
    # @field_validator("rewrite_count")
    # def count_non_negative(cls, v):
    #     assert v >= 0
    #     return v