"""review_auditor 순수함수 스모크 테스트.

feature/ontology에서 반입한 감사 도구의 특성화 테스트.
출력이 회계사의 데이터 수정 판단에 직결되므로 핵심 판정 함수의 계약을 고정한다.
"""
import pytest

from src.db.ontology.review_auditor import (
    CATEGORIES,
    _in_range,
    _justified,
    _ptuple,
    audit_chapter,
)


@pytest.mark.unit
def test_ptuple_parses_paragraph_variants():
    # (major, letter, minor, sub) 튜플로 정규화 — 접두어는 제거 후 비교된다.
    assert _ptuple("6.4") == (6, "", 4, 0)
    assert _ptuple("6.A13") == (6, "A", 13, 0)
    assert _ptuple("6.4의2") == (6, "", 4, 2)
    assert _ptuple("실6.142") == (6, "", 142, 0)
    assert _ptuple("제6장") is None


@pytest.mark.unit
def test_in_range_with_prefix_inheritance():
    # 범위 끝에 접두어가 없으면 시작의 접두어를 물려받아 비교한다.
    assert _in_range("실6.67", "실6.66", "6.68") is True
    # 접두어 종류가 다르면(본문 vs 실) 범위 밖으로 판정한다.
    assert _in_range("6.67", "실6.66", "6.68") is False
    # major가 다르면 범위 밖.
    assert _in_range("7.1", "6.66", "6.68") is False


@pytest.mark.unit
def test_justified_direct_and_range():
    # source_text에 직접 등장하거나 범위 내부이면 정당화된다.
    assert _justified("6.4", "문단 6.4에 따라 처리한다") is True
    assert _justified("6.10", "문단 6.9부터 6.11까지의 규정") is True
    assert _justified("6.10", "문단 6.9 내지 6.11") is True
    assert _justified("6.4", "문단 6.9에 따라 처리한다") is False


@pytest.mark.unit
def test_audit_chapter_buckets():
    """작은 그래프로 4개 카테고리 판정을 고정한다."""
    graph = {
        "nodes": [
            {"id": "gaap-ch6", "node_type": "Standard", "paragraphs": []},
            {"id": "gaap-ch6-s1-a", "node_type": "Subsection", "paragraphs": ["6.4"]},
        ],
        "edges": [
            # exact_duplicate: 동일 (from,to,문단,type,source) 2건
            {"from_id": "gaap-ch6-s1-a", "to_id": "gaap-ch6-s1-b", "to_paragraph": "6.9",
             "edge_type": "REFERENCES", "source_text": "문단 6.9에 따른다", "unresolved_target": ""},
            {"from_id": "gaap-ch6-s1-a", "to_id": "gaap-ch6-s1-b", "to_paragraph": "6.9",
             "edge_type": "REFERENCES", "source_text": "문단 6.9에 따른다", "unresolved_target": ""},
            # target_unjustified: source는 6.9를 가리키는데 to_paragraph가 6.4
            {"from_id": "gaap-ch6-s1-c", "to_id": "gaap-ch6-s1-a", "to_paragraph": "6.4",
             "edge_type": "REFERENCES", "source_text": "문단 6.9에 따라 처리한다", "unresolved_target": ""},
            # prefix_dropped: source엔 실6.4가 있는데 본문 6.4로 연결됨
            #  (직접 등장 "문단 6.4"도 있어 target_unjustified에는 걸리지 않는다)
            {"from_id": "gaap-ch6-s1-d", "to_id": "gaap-ch6-s1-a", "to_paragraph": "6.4",
             "edge_type": "REFERENCES", "source_text": "문단 6.4와 실6.4에서 설명한 명세서", "unresolved_target": ""},
            # cross_chapter_residual: 제N장 명시 없이 타 장 번호(8.2)만 남은 미해소 참조
            {"from_id": "gaap-ch6-s1-a", "to_id": "", "to_paragraph": "",
             "edge_type": "REFERENCES", "source_text": "문단 8.2를 준용한다", "unresolved_target": "문단 8.2"},
        ],
    }
    buckets = {c: [] for c in CATEGORIES}
    audit_chapter(graph, 6, buckets)

    assert len(buckets["exact_duplicate"]) == 1  # 엣지 2건이 중복으로 분류되었다.
    assert buckets["exact_duplicate"][0]["count"] == 2  # 이 테스트에서 6.9로 연결되는 엣지는 2건 존재한다.
    assert len(buckets["target_unjustified"]) == 1  # source는 6.9를 가리키는데 to_paragraph가 6.4인 엣지 1건
    assert buckets["target_unjustified"][0]["to_paragraph"] == "6.4"  # to_paragraph가 6.4로 잘못 연결됨
    assert "fix→6.9" in buckets["target_unjustified"][0]["suggested"]  # fix->6.9
    assert len(buckets["prefix_dropped"]) == 1  # source엔 실6.4가 있는데 본문 6.4로 연결됨
    assert len(buckets["cross_chapter_residual"]) == 1  # 제N장 명시 없이 타 장 번호(8.2)만 남은 미해소 참조
    assert "gaap-ch8" in buckets["cross_chapter_residual"][0]["suggested"]  # gaap-ch8
