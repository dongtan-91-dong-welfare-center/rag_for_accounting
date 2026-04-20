from src.db.ontology.models import OntologyNode, OntologyEdge, OntologyGraph


def test_standard_node():
    node = OntologyNode(
        id="gaap-ch6",
        node_type="Standard",
        name="제6장 금융자산·금융부채",
        standard_type="GAAP",
        chapter="6",
    )
    assert node.node_type == "Standard"
    assert node.chapter == "6"


def test_subsection_node_defaults():
    node = OntologyNode(
        id="gaap-ch6-s1-최초인식",
        node_type="Subsection",
        title="금융상품의 최초인식",
        content="6.4 금융자산이나...",
    )
    assert node.paragraphs == []
    assert node.unresolved_refs == []


def test_references_edge():
    edge = OntologyEdge(
        from_id="gaap-ch6-s1-후속측정",
        to_id="gaap-ch6-s2",
        edge_type="REFERENCES",
        paragraph="6.14⑵㈏",
        source_text="제8장 '지분법' 문단 8.2 참조",
    )
    assert edge.edge_type == "REFERENCES"
    assert edge.include == []


def test_excludes_edge_with_include():
    edge = OntologyEdge(
        from_id="gaap-ch6-적용범위",
        to_id="gaap-ch6-리스",
        edge_type="EXCLUDES",
        paragraph="6.2⑵",
        include=["리스채권의 제거와 손상", "금융리스부채의 제거"],
    )
    assert len(edge.include) == 2


def test_unresolved_edge():
    edge = OntologyEdge(
        from_id="gaap-ch6-s1-최초인식",
        to_id="",
        edge_type="REFERENCES",
        unresolved_target="제8장 문단 8.2",
    )
    assert edge.to_id == ""
    assert edge.unresolved_target == "제8장 문단 8.2"


def test_is_default_for_edge():
    edge = OntologyEdge(
        from_id="gaap-ch6-s1-공통원칙",
        to_id="gaap-ch6-s2",
        edge_type="IS_DEFAULT_FOR",
        source_text="제2절~제4절에서 정하지 않은 사항은 이 절에서 적용한다.",
    )
    assert edge.edge_type == "IS_DEFAULT_FOR"


def test_ontology_graph_defaults():
    graph = OntologyGraph()
    assert graph.nodes == []
    assert graph.edges == []
