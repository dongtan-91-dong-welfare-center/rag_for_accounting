# 문서 파싱부터 답변 생성까지 파이프라인 전 단계(파싱·인덱싱·재작성·검색·재정렬·평가·생성)가 공유하는 데이터 스키마 모음
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal

QueryScopeCategory = Literal["accounting", "out_of_scope_adjacent", "completely_unrelated"]

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

    parser는 src/ingest/parse/parser_dtos.py를 통해 이 클래스를 재노출받아 사용한다.
    """
    title: str
    text: str
    tables: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

class SkippedChunk(BaseModel):
    """index_documents에서 적재되지 못한 청크와 사유 (FUNC-003 부분실패 추적)

    재시도 가능 여부는 error_type에서 파생한다(IX-201 토큰초과=재적재 불가, SE-102 DB·CM-002 임베딩 일시장애=재적재 가능)
    """
    chunk_id: str
    error_type: str   # "IX-201" | "SE-102" | "CM-002" ... (docs/func_interfaces.md 카탈로그)
    reason: str       # 로그 문구와 동일한 상세 메시지

    @property
    def is_retryable(self) -> bool:
        """일시적 장애(DB 통신 오류, 임베딩 API 장애 등)로 인한 누락인 경우 재시도 가능으로 판별한다.

        IX-201(토큰 초과)은 텍스트 분할 없이는 단순 재시도해도 동일하게 실패하므로 False이다.
        """
        return self.error_type in {"SE-102", "CM-002"}

class IndexingResult(BaseModel):
    """인덱싱 결과 — pgvector 저장 완료 여부 (FUNC-003 출력)"""
    document_id: str
    chunk_count: int                                                 # 성공 적재 건수
    status: Literal["success", "partial", "failed"]
    skipped_chunks: list[SkippedChunk] = Field(default_factory=list)  # 누락 청크 추적

    def get_retryable_chunks(self) -> list[SkippedChunk]:
        """부분 실패 중 재적재(재시도)가 가능한 dead-letter 청크 목록을 반환한다."""
        return [chunk for chunk in self.skipped_chunks if chunk.is_retryable]

class ClassifyResult(BaseModel):
    """질의 분류 및 전략 선정 결과 — rewrite 노드의 classify 단계 출력"""
    is_accounting: bool = True
    query_scope: QueryScopeCategory = "accounting"
    strategy: Literal["hyde", "decompose", "stepback", "bypass"] = "hyde"
    confidence: float = 0.0


class HydeResult(BaseModel):
    """HyDE 가상 답변 생성 결과"""
    hypothetical_answer: str = ""


class DecomposeResult(BaseModel):
    """복합 질의 분해 결과"""
    sub_queries: list[str] = Field(default_factory=list)


class StepbackResult(BaseModel):
    """구체적 질의의 일반 원칙 추상화 결과"""
    abstract_query: str = ""


class RewrittenQuery(BaseModel):
    """재작성 질의 — rewrite 노드 출력. search_queries를 search 노드에 전달한다."""
    original_query:       str       # 사용자 원문 쿼리
    strategy:       str       # "hyde" | "decompose" | "stepback" | "bypass"
    search_queries: list[str] # 검색에 사용할 쿼리 목록 (원문 항상 포함)

class ChunkMetadata(BaseModel):
    """검색 청크의 메타데이터 — 온톨로지 노드 식별자 등 핵심 속성을 타입-세이프하게 보장한다.

    명시 필드는 `src/ingest/ontology/models.py`의 `OntologyNode`와 정합을 맞춘다:
      - ontology_node_id ↔ OntologyNode.id   (예: "gaap-ch6-s1-최초인식")
        ※ OntologyNode 쪽 필드명은 `id`이며, 청크 메타데이터에서는 룩업 의미를
          분명히 하기 위해 `ontology_node_id`로 부른다.
      - node_type        ↔ OntologyNode.node_type      ("Standard"|"Section"|"Subsection")
      - standard_type    ↔ OntologyNode.standard_type  ("GAAP"|"KIFRS")
      - chapter          ↔ OntologyNode.chapter         (예: "6")

    extra="allow"로 DB JSONB의 비정형 키(예: 원본 파일 경로를 담는 "source_path")도 수용하며,
    이들은 `model_extra`를 통해 접근한다.
    """
    model_config = ConfigDict(extra="allow")

    ontology_node_id: str | None = None
    node_type: str | None = None
    standard_type: str | None = None
    chapter: str | None = None

class RetrievedChunk(BaseModel):
    """청크 단위 데이터 — 검색 시에는 Dense/Sparse/Hybrid 검색 결과를 담고, 인덱싱 시에는 온톨로지 청커가 문서를 분할한 조각을 담는다(분할 단계에서는 score가 0.0으로 채워진다)"""
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


class ContextCheckResult(BaseModel):
    """
    청크 문맥 보존 여부 점검 결과: context_harness 하나의 검사 케이스 출력

    chunk_id     : 검사 대상 청크 식별자
    check_type   : 검사 종류: "sentence_boundary" 또는 "clause_number_gap"
    passed       : True이면 문맥이 온전히 보존됨, False이면 단절 또는 이상 감지
    detail       : 판정 근거 텍스트 (docs/benchmark/ 형식과 동일하게 케이스별 근거 포함)
    """

    chunk_id: str
    check_type: Literal["sentence_boundary", "clause_number_gap"]
    passed: bool
    detail: str
