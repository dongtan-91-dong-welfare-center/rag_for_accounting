from src.db.ontology.models import OntologyGraph, OntologyNode, OntologyEdge
from src.db.ontology.resolver import build_lookup, resolve_edges


def _make_graph() -> OntologyGraph:
    return OntologyGraph(nodes=[
        OntologyNode(id="gaap-ch6", node_type="Standard", chapter="6", name="제 6 장 금융자산·금융부채"),
        OntologyNode(id="gaap-ch6-s1", node_type="Section", title="제 1 절 공통사항", order=1),
        OntologyNode(id="gaap-ch6-s2", node_type="Section", title="제 2 절 유가증권", order=2),
        OntologyNode(id="gaap-ch6-s1-최초인식", node_type="Subsection",
                     title="금융상품의 최초인식", paragraphs=["6.4", "6.4의2"]),
    ])


def test_lookup_chapter():
    lookup = build_lookup(_make_graph())
    assert lookup.get("제6장") == "gaap-ch6"


def test_lookup_section():
    lookup = build_lookup(_make_graph())
    assert lookup.get("제2절") == "gaap-ch6-s2"


def test_lookup_paragraph():
    lookup = build_lookup(_make_graph())
    assert lookup.get("6.4") == "gaap-ch6-s1-최초인식"
    assert lookup.get("문단6.4") == "gaap-ch6-s1-최초인식"


def test_resolve_success():
    graph = _make_graph()
    graph.edges = [OntologyEdge(
        from_id="gaap-ch6-s1-최초인식", to_id="",
        edge_type="REFERENCES", unresolved_target="제2절",
    )]
    resolved = resolve_edges(graph)
    assert resolved.edges[0].to_id == "gaap-ch6-s2"
    assert resolved.edges[0].unresolved_target == ""


def test_resolve_failure_records_unresolved():
    graph = _make_graph()
    graph.edges = [OntologyEdge(
        from_id="gaap-ch6-s1-최초인식", to_id="",
        edge_type="REFERENCES", unresolved_target="제8장 문단 8.2",
    )]
    resolved = resolve_edges(graph)
    assert resolved.edges[0].to_id == ""
    assert resolved.edges[0].unresolved_target == "제8장 문단 8.2"
