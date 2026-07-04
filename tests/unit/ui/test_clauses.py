"""src.ui.clauses.build_clause_rows 단위테스트 (순수 — DB·streamlit 불필요)."""
from src.models.schemas import ChunkMetadata, RerankingResult, RetrievedChunk
from src.ui.clauses import DEFAULT_TOP_N, ClauseRow, build_clause_rows


def _rr(chunk_id, score, chapter="6", node_id="gaap-ch6-s1", rerank_score=1.0, content="조항 본문"):
    """reranked chunk 생성 헬퍼 함수 """
    return RerankingResult(
        chunk=RetrievedChunk(
            chunk_id=chunk_id,
            document_id="doc",
            content=content,
            score=score,
            metadata=ChunkMetadata(chapter=chapter, ontology_node_id=node_id),
        ),
        rerank_score=rerank_score,
    )


def test_assigns_1based_rank_in_input_order():
    """입력 순서에 따라 1부터 시작하는 순위를 할당한다"""
    rows = build_clause_rows([_rr("a", 0.9), _rr("b", 0.8), _rr("c", 0.7)])
    assert [r.rank for r in rows] == [1, 2, 3]
    assert all(isinstance(r, ClauseRow) for r in rows)


def test_caps_at_top_n():
    """top_n개수만큼만 반환한다"""
    reranked = [_rr(str(i), 1.0 - i / 100) for i in range(10)]
    rows = build_clause_rows(reranked, top_n=5)
    assert len(rows) == 5
    assert rows[-1].rank == 5


def test_default_top_n_is_5():
    """기본 top_n은 5이다"""
    reranked = [_rr(str(i), 1.0) for i in range(10)]
    assert len(build_clause_rows(reranked)) == DEFAULT_TOP_N == 5


def test_score_uses_chunk_score_not_rerank_score():
    # rerank_score(no-op 1.0)가 아니라 chunk.score(RRF)를 노출해야 한다
    rows = build_clause_rows([_rr("a", 0.42, rerank_score=1.0)])
    assert rows[0].score == 0.42


def test_missing_metadata_falls_back():
    """메타데이터가 누락된 경우 기본값을 반환한다"""
    rr = RerankingResult(
        chunk=RetrievedChunk(
            chunk_id="a", document_id="d", content="x", score=0.5, metadata=ChunkMetadata()
        ),
        rerank_score=1.0,
    )
    row = build_clause_rows([rr])[0]
    assert row.chapter == "?"
    assert row.node_id == ""


def test_empty_and_nonpositive_top_n():
    """입력이 비었거나 top_n이 0 이하일 때 빈 리스트를 반환한다"""
    assert build_clause_rows([]) == []
    assert build_clause_rows(None) == []
    assert build_clause_rows([_rr("a", 1.0)], top_n=0) == []


def test_page_range_and_document_id_from_metadata():
    """metadata extra의 page_start/page_end와 chunk.document_id를 노출한다 — #196 뷰어가 소비."""
    rr = RerankingResult(
        chunk=RetrievedChunk(
            chunk_id="a",
            document_id="gaap-ch10",
            content="x",
            score=0.5,
            metadata=ChunkMetadata(chapter="10", page_start=3, page_end=4),
        ),
        rerank_score=1.0,
    )
    row = build_clause_rows([rr])[0]
    assert (row.page_start, row.page_end) == (3, 4)
    assert row.document_id == "gaap-ch10"


def test_page_range_defaults_to_none_when_absent():
    """백필 전(또는 미매칭) 청크는 페이지가 None — 뷰어 버튼 미표시로 강등된다."""
    row = build_clause_rows([_rr("a", 0.5)])[0]
    assert (row.page_start, row.page_end) == (None, None)
