from src.db.ontology.models import OntologyGraph, OntologyNode, OntologyEdge
from src.db.ontology.resolver import build_lookup, resolve_edges, _expand_range_target


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


# --- 범위 표기 확장 ---------------------------------------------------
# start/end의 prefix(실·결·사례)가 다르면 확장하지 않고 None을 반환해
# 존재하지 않는 문단 번호(예: "실6.67")가 만들어지는 것을 막는다.

def test_expand_range_same_prefix_expands_inclusive():
    # 같은 종류(본문)의 연속 범위는 끝 번호까지 포함해 확장한다.
    paras = ["6.8의2", "6.9", "6.10", "6.11"]
    assert _expand_range_target("문단 6.8의2~6.11", paras) == paras


def test_expand_range_practice_prefix_expands():
    # 실무지침(실) prefix가 양쪽 모두 일치하면 정상 확장한다.
    paras = ["실6.66", "실6.67"]
    assert _expand_range_target("문단 실6.66~실6.67", paras) == paras


def test_expand_range_prefix_mismatch_returns_none():
    # 시작은 "실6.66", 끝은 prefix 없는 "6.67"인 경우.
    # start prefix를 그대로 끌어다 "실6.67"을 만들면 안 되므로 None을 반환한다.
    paras = ["실6.66", "6.67"]
    assert _expand_range_target("문단 실6.66~6.67", paras) is None


def test_resolve_range_prefix_mismatch_keeps_unresolved():
    # _expand_range_target가 None이면 resolver는 원문을 그대로 남겨 수동 확인이 가능하게 하고
    # 잘못된 부분의 매핑 엣지를 만들지 않는다.
    graph = OntologyGraph(nodes=[
        OntologyNode(id="gaap-ch6-s1-실무지침", node_type="Subsection",
                     title="실무지침", paragraphs=["실6.66"]),
        OntologyNode(id="gaap-ch6-s1-본문", node_type="Subsection",
                     title="본문", paragraphs=["6.67"]),
    ])
    graph.edges = [OntologyEdge(
        from_id="gaap-ch6-s1-실무지침", to_id="",
        edge_type="REFERENCES", unresolved_target="문단 실6.66~6.67",
    )]
    resolved = resolve_edges(graph)
    assert len(resolved.edges) == 1
    assert resolved.edges[0].to_id == ""
    assert resolved.edges[0].unresolved_target == "문단 실6.66~6.67"


def test_resolve_range_splits_into_multiple_edges():
    # 동일 prefix 범위는 paragraph마다 개별 REFERENCES 엣지로 분리된다.
    graph = OntologyGraph(nodes=[
        OntologyNode(id="gaap-ch6-s1-src", node_type="Subsection",
                     title="출처", paragraphs=["6.8"]),
        OntologyNode(id="gaap-ch6-s1-a", node_type="Subsection",
                     title="a", paragraphs=["6.9"]),
        OntologyNode(id="gaap-ch6-s1-b", node_type="Subsection",
                     title="b", paragraphs=["6.10"]),
    ])
    graph.edges = [OntologyEdge(
        from_id="gaap-ch6-s1-src", to_id="",
        edge_type="REFERENCES", unresolved_target="문단 6.9~6.10",
    )]
    resolved = resolve_edges(graph)
    to_ids = sorted(e.to_id for e in resolved.edges)
    assert to_ids == ["gaap-ch6-s1-a", "gaap-ch6-s1-b"]
    assert all(e.unresolved_target == "" for e in resolved.edges)
    assert {e.to_paragraph for e in resolved.edges} == {"6.9", "6.10"}
