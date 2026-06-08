"""
[FUNC-002] 온톨로지 구축 단위 테스트 Stub

대상 모듈: src/db/ontology/builder.py
검증 범위:
    - 마크다운 문서에서 회계 개념 노드/엣지 추출
    - Apache AGE 그래프에 온톨로지 적재

TODO: builder.py 구현 완료 후 @pytest.mark.skip을 제거하고 실제 로직 검증
"""
import pytest


@pytest.mark.unit
class TestOntologyNodeExtraction:
    """마크다운 → 온톨로지 노드 추출 검증"""

    @pytest.mark.skip(reason="FUNC-002 온톨로지 builder 구현 후 활성화 예정")
    def test_extract_entities_from_markdown(self):
        """
        입력: 마크다운 텍스트 (ParsedDocument.text)
        출력: 회계 개념 엔티티 리스트 (노드 후보)
        """
        # from src.db.ontology.builder import extract_entities
        # entities = extract_entities("## 영업권\n영업권은 사업결합에서 발생하는 ...")
        # assert len(entities) > 0
        # assert any("영업권" in e for e in entities)
        pass

    @pytest.mark.skip(reason="FUNC-002 온톨로지 builder 구현 후 활성화 예정")
    def test_extract_relationships(self):
        """
        입력: 회계 개념 엔티티 리스트
        출력: 엣지(관계) 리스트 — (subject, predicate, object) 형태
        """
        # from src.db.ontology.edge_extractor import extract_edges
        # edges = extract_edges(["영업권", "손상차손", "사업결합"])
        # assert len(edges) > 0
        pass


@pytest.mark.unit
class TestOntologyGraphWrite:
    """Apache AGE 그래프 적재 검증"""

    @pytest.mark.skip(reason="FUNC-002 온톨로지 builder 구현 후 활성화 예정 — DB 연동 필요")
    def test_build_graph_from_entities(self):
        """
        입력: 엔티티 리스트 + 엣지 리스트
        출력: 그래프 적재 결과 (노드 수, 엣지 수)
        """
        # from src.db.ontology.builder import build_graph
        # result = build_graph(entities, edges)
        # assert result["node_count"] > 0
        # assert result["edge_count"] > 0
        pass
