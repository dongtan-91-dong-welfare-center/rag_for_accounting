# FUNC-002~009 전반에서 사용하는 공용 데이터 스키마
from pydantic import BaseModel, ConfigDict, Field, field_validator
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

class LLMInternalResponse(BaseModel):
    """LLM 내부 응답 — PydanticAI에서 생성하는 원시 응답"""
    answer: str
    is_answerable: bool
    llm_self_score: float

class FinalResponse(BaseModel):
    """최종 답변 — 사용자에게 반환되는 응답 구조체"""
    answer: str
    citations: list[Citation]
    is_answerable: bool
    confidence_score: float

class ParsedDocument(BaseModel):
    """파싱된 문서 — Docling 처리 결과 (FUNC-001 출력)

    parser는 src/parse/parser_dtos.py를 통해 이 클래스를 재노출받아 사용한다.
    """
    title: str
    text: str
    tables: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

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

class ChunkMetadata(BaseModel):
    """검색 청크의 메타데이터 — 온톨로지 노드 식별자 등 핵심 속성을 타입-세이프하게 보장한다.

    명시 필드는 `src/db/ontology/models.py`의 `OntologyNode`와 정합을 맞춘다:
      - ontology_node_id ↔ OntologyNode.id   (예: "gaap-ch6-s1-최초인식")
        ※ OntologyNode 쪽 필드명은 `id`이며, 청크 메타데이터에서는 룩업 의미를
          분명히 하기 위해 `ontology_node_id`로 부른다.
      - node_type        ↔ OntologyNode.node_type      ("Standard"|"Section"|"Subsection")
      - standard_type    ↔ OntologyNode.standard_type  ("GAAP"|"KIFRS")
      - chapter          ↔ OntologyNode.chapter         (예: "6")

    extra="allow"로 DB JSONB의 비정형 키(예: "source")도 수용하며,
    이들은 `model_extra`를 통해 접근한다.
    """
    model_config = ConfigDict(extra="allow")

    ontology_node_id: str | None = None
    node_type: str | None = None
    standard_type: str | None = None
    chapter: str | None = None

class RetrievedChunk(BaseModel):
    """검색된 청크 — Dense/Sparse/Hybrid 검색 결과 단위 (FUNC-005 출력)"""
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata)

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