"""청크 문맥 보존 점검 하네스 단위 테스트 (#298)."""
import pytest

from src.ingest.ontology.context_harness import (
    detect_broken_sentences,
    detect_clause_number_gaps,
    render_report_markdown,
    run_context_harness,
)
from src.models.schemas import RetrievedChunk

pytestmark = pytest.mark.unit


def _chunk(cid: str, content: str) -> RetrievedChunk:
    return RetrievedChunk(chunk_id=cid, document_id="doc", content=content, score=0.0)


def test_complete_sentences_pass():
    chunks = [_chunk("a", "재고자산은 원가로 측정한다."), _chunk("b", "다음 문장.")]
    results = detect_broken_sentences(chunks)
    assert len(results) == 1
    assert results[0].passed is True


def test_unfinished_sentence_detected():
    chunks = [_chunk("a", "재고자산은 취득원가와 순실현가능가치 중"), _chunk("b", "작은 금액으로 한다.")]
    results = detect_broken_sentences(chunks)
    assert results[0].passed is False
    assert results[0].chunk_id == "a"
    assert "순실현가능가치" in results[0].detail


def test_last_chunk_and_single_chunk_not_checked():
    assert detect_broken_sentences([_chunk("a", "끝나지 않은")]) == []


def test_consecutive_clause_numbers_pass():
    chunks = [_chunk("a", "#### 21.8 가\n본문."), _chunk("b", "#### 21.9 나\n본문.")]
    results = detect_clause_number_gaps(chunks)
    assert len(results) == 1 and results[0].passed is True


def test_clause_number_gap_detected():
    chunks = [_chunk("a", "#### 21.8 가\n본문."), _chunk("b", "#### 21.11 나\n본문.")]
    results = detect_clause_number_gaps(chunks)
    assert results[0].passed is False
    assert results[0].chunk_id == "b"
    assert "2개" in results[0].detail


def test_branch_numbers():
    chunks = [
        _chunk("a", "#### 21.5 가"),
        _chunk("b", "#### 21.5의2 나"),
        _chunk("c", "#### 21.6 다"),
    ]
    assert all(r.passed for r in detect_clause_number_gaps(chunks))


def test_chapter_change_is_skipped():
    chunks = [_chunk("a", "#### 21.8 가"), _chunk("b", "#### 22.1 나")]
    assert detect_clause_number_gaps(chunks) == []


def test_run_harness_and_report_format():
    chunks = [
        _chunk("a", "#### 21.8 가\n끊긴 문장"),
        _chunk("b", "#### 21.10 나\n완결."),
    ]
    results = run_context_harness(chunks)
    assert {r.check_type for r in results} == {"sentence_boundary", "clause_number_gap"}
    assert all(not r.passed for r in results)
    report = render_report_markdown(results)
    assert "# 청크 문맥 보존 점검 리포트" in report
    assert "단절 의심: 2건" in report
    assert "| a | sentence_boundary | 단절 의심 |" in report
