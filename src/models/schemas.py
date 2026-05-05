# FUNC-002~009 전반에서 사용하는 공용 데이터 스키마
from pydantic import BaseModel, field_validator
from typing import Literal

class Citation(BaseModel):
    """인용 근거 — 답변 생성 시 참조한 문서 출처 정보"""
    document_id: str
    chunk_id: str
    content: str
    relevance_score: float
    # Pseudo validator:
    # @field_validator("relevance_score")
    # def score_in_range(cls, v):
    #     assert 0.0 <= v <= 1.0, "relevance_score must be in [0, 1]"
    #     return v

class FinalResponse(BaseModel):
    """최종 답변 — 사용자에게 반환되는 응답 구조체"""
    answer: str
    citations: list[Citation]
    is_answerable: bool
    confidence_score: float

class ParsedDocument(BaseModel):
    """파싱된 문서 — Docling 처리 결과 (FUNC-001 출력)"""
    title: str
    text: str
    tables: list[dict]
    metadata: dict

class IndexingResult(BaseModel):
    """인덱싱 결과 — pgvector 저장 완료 여부 (FUNC-003 출력)"""
    document_id: str
    chunk_count: int
    status: Literal["success", "partial", "failed"]
    # @field_validator("chunk_count")
    # def count_positive(cls, v):
    #     assert v >= 0
    #     return v

class RewrittenQuery(BaseModel):
    """재작성 질의 — rewrite 노드 출력. search_queries를 search 노드에 전달한다."""
    original_query:       str       # 사용자 원문 쿼리
    strategy:       str       # "hyde" | "decompose" | "stepback" | "bypass"
    search_queries: list[str] # 검색에 사용할 쿼리 목록 (원문 항상 포함)

class RetrievedChunk(BaseModel):
    """검색된 청크 — Dense/Sparse/Hybrid 검색 결과 단위 (FUNC-005 출력)"""
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict

class RerankingResult(BaseModel):
    """재정렬 결과 — Cross-Encoder 재정렬 후 청크 (FUNC-006 출력)"""
    chunk: RetrievedChunk
    rerank_score: float
    # Pseudo validator:
    # 동일한 validator 적용: rerank_score ∈ [0, 1]

class EvaluationResult(BaseModel):
    """평가 결과 — 검색 맥락의 품질 판단 (FUNC-007 출력)"""
    is_relevant: bool
    needs_external: bool
    confidence: float
    reasoning: str
    # Pseudo validator:
    # 동일한 validator 적용: confidence ∈ [0, 1]