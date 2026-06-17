"""검색된 조항을 UI 표시용 행으로 변환하는 순수 헬퍼.

streamlit·DB에 의존하지 않으므로 단위테스트가 가능하다(app.py는 import 시 DB 풀을초기화하므로 렌더 로직과 분리한다). 
NFR-002: 조항 검색이 1순위, LLM 답변은 참고용 — app.py는 이 모듈이 만든 행을 '검색된 조항' 섹션으로 답변보다 먼저 노출한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.models.schemas import RerankingResult

DEFAULT_TOP_N = 5


@dataclass(frozen=True)
class ClauseRow:
    """UI에 노출할 조항 1건. 표시 전용 평면 구조."""

    rank: int        # 1-based 검색 순위
    chapter: str     # 장 번호(metadata.chapter), 결측 시 "?"
    node_id: str     # 온톨로지 노드 식별자(metadata.ontology_node_id), 결측 시 ""
    score: float     # 검색 점수 = chunk.score(RRF 하이브리드). rerank_score는 no-op(1.0)라 쓰지 않음
    content: str     # 조항 본문 전문


def build_clause_rows(
    reranked: list[RerankingResult] | None,
    top_n: int = DEFAULT_TOP_N,
) -> list[ClauseRow]:
    """reranked_chunks를 검색 순위 상위 top_n개의 ClauseRow로 변환한다.

    - 입력 순서를 검색 순위로 간주한다(rerank 노드가 점수 내림차순으로 정렬해 반환).
    - 점수는 chunk.score(RRF/하이브리드)를 노출한다.
    - USE_RERANKER=false에서는 rerank_score가 전부 1.0이라 변별력이 없기 때문이다.
    - 리랭커를 켜면 이 점수 출처/라벨을 rerank_score로 전환한다.
    - top_n<=0이거나 입력이 비면 빈 리스트를 반환한다.
    """
    if not reranked or top_n <= 0:
        return []
    rows: list[ClauseRow] = []
    for rank, item in enumerate(reranked[:top_n], start=1):
        chunk = item.chunk
        meta = chunk.metadata
        rows.append(
            ClauseRow(
                rank=rank,
                chapter=meta.chapter or "?",
                node_id=meta.ontology_node_id or "",
                score=chunk.score,
                content=chunk.content,
            )
        )
    return rows
