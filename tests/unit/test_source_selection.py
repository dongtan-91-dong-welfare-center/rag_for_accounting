"""서비스 채팅 출처선별(select_cited_sources) 단위 테스트.

에이전트가 턴 중 검색한 근거 중 답변에 실제 인용된 [n]만 근거 패널에 남기는지 검증한다.
(재설계 문서 2.2 "답변 기반 출처 선별" 이식분 — src/app/chat/retrieval.py)
"""
import pytest

_retrieval = pytest.importorskip(
    "src.app.chat.retrieval",
    reason="src/app/chat은 feature/frontend 브랜치에만 존재 — 병합 전까지 스킵",
)
cited_indices = _retrieval.cited_indices
select_cited_sources = _retrieval.select_cited_sources


def _src(index: int) -> dict:
    return {"index": index, "content": f"근거{index} 본문", "locator": f"loc-{index}", "score": 0.9}


@pytest.mark.unit
class TestCitedIndices:
    def test_extracts_bracket_numbers(self):
        # Arrange
        answer = "리스는 이렇게 처리한다 [1]. 또한 조건부로는 [3]을 본다."

        # Act
        result = cited_indices(answer)

        # Assert
        assert result == {1, 3}

    def test_handles_multi_digit_and_dedup(self):
        assert cited_indices("[10] 그리고 다시 [10], [2]") == {10, 2}

    def test_returns_empty_set_for_no_citations(self):
        assert cited_indices("인용이 전혀 없는 답변") == set()

    def test_handles_none(self):
        assert cited_indices(None) == set()


@pytest.mark.unit
class TestSelectCitedSources:
    def test_keeps_only_cited_sources(self):
        # Arrange — 5건 검색됐지만 답변은 [1],[3]만 인용
        sources = [_src(i) for i in range(1, 6)]
        answer = "핵심은 이렇다 [1]. 예외는 [3]에서 다룬다."

        # Act
        selected = select_cited_sources(answer, sources)

        # Assert
        assert [s["index"] for s in selected] == [1, 3]

    def test_preserves_original_index_no_renumbering(self):
        # 답변 본문의 [n]과 프론트 매핑을 깨지 않도록 번호를 재부여하지 않는다.
        sources = [_src(i) for i in range(1, 6)]
        selected = select_cited_sources("근거는 [4]뿐이다.", sources)
        assert [s["index"] for s in selected] == [4]

    def test_returns_empty_when_no_citation(self):
        # 인용이 없으면 모델이 참조하지 않은 근거를 노출하지 않는다.
        sources = [_src(i) for i in range(1, 6)]
        assert select_cited_sources("인용 없는 답변", sources) == []

    def test_ignores_citation_index_absent_from_sources(self):
        # 모델이 [9]를 인용해도 검색된 근거에 없으면 버린다(허위 출처 방지).
        sources = [_src(1), _src(2)]
        selected = select_cited_sources("잘못된 인용 [9]와 올바른 [2]", sources)
        assert [s["index"] for s in selected] == [2]

    def test_empty_sources(self):
        assert select_cited_sources("아무거나 [1]", []) == []
