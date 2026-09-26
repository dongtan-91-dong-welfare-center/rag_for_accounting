"""검색된 조항을 UI 표시용 행으로 변환하는 순수 헬퍼.

streamlit·DB에 의존하지 않으므로 단위테스트가 가능하다(app.py는 import 시 DB 풀을초기화하므로 렌더 로직과 분리한다). 
NFR-002: 조항 검색이 1순위, LLM 답변은 참고용 — app.py는 이 모듈이 만든 행을 '검색된 조항' 섹션으로 답변보다 먼저 노출한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.models.schemas import RerankingResult
from src.utils.clause_paras import chunk_paras

DEFAULT_TOP_N = 5


@dataclass(frozen=True)
class ClauseRow:
    """UI에 노출할 조항 1건. 표시 전용 평면 구조."""

    rank: int        # 1-based 검색 순위
    chapter: str     # 장 번호(metadata.chapter), 결측 시 "?"
    node_id: str     # 온톨로지 노드 식별자(metadata.ontology_node_id), 결측 시 ""
    score: float     # 검색 점수 = chunk.score(RRF 하이브리드). USE_RERANKER=false일 때는 rerank_score가 전부 1.0이라 변별력이 없어 이 값을 대신 씀
    content: str     # 조항 본문 전문
    document_id: str = ""          # 원문 문서 식별자(chunk.document_id) — 뷰어의 PDF 서빙 경로에 사용(#196)
    page_start: int | None = None  # 원본 PDF 페이지 범위(#196 백필 metadata) — 미백필/미매칭이면 None
    page_end: int | None = None
    # 문단번호 목록
    # 공용 규칙이 content 헤더 ∪ chunk_id에서 원형 그대로(가지번호 유지) 뽑는다.
    # 용어 정의처럼 번호가 본래 없는 청크는 빈 목록.
    paras: list[str] = field(default_factory=list)


def build_clause_rows(
    reranked: list[RerankingResult] | None,
    top_n: int = DEFAULT_TOP_N,
) -> list[ClauseRow]:
    """reranked를 검색 순위 상위 top_n개의 ClauseRow 리스트로 변환한다.

    - 입력 순서를 검색 순위로 간주한다(rerank 노드가 점수 내림차순으로 정렬해 반환).
    - 점수는 chunk.score(RRF/하이브리드)를 노출한다.
    - USE_RERANKER=false에서는 rerank_score가 전부 1.0이라 변별력이 없기 때문이다.
    - 리랭커를 켜도 이 함수는 여전히 chunk.score만 노출한다.
      TODO: rerank_score로 점수 출처를 전환하는 로직은 아직 구현돼 있지 않다.
    - top_n<=0이거나 입력이 비면 빈 리스트를 반환한다.
    """
    if not reranked or top_n <= 0:
        return []
    rows: list[ClauseRow] = []
    for rank, item in enumerate(reranked[:top_n], start=1):
        chunk = item.chunk
        meta = chunk.metadata
        extra = meta.model_extra or {}  # page_start/page_end는 #196 백필이 채우는 비정형 키
        rows.append(
            ClauseRow(
                rank=rank,
                chapter=meta.chapter or "?",
                node_id=meta.ontology_node_id or "",
                score=chunk.score,
                content=chunk.content,
                document_id=chunk.document_id,
                page_start=extra.get("page_start"),
                page_end=extra.get("page_end"),
                paras=chunk_paras(chunk.content, chunk.chunk_id),
            )
        )
    return rows
