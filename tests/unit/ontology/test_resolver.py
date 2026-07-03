import pytest
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


@pytest.mark.unit
def test_lookup_chapter():
    lookup = build_lookup(_make_graph())
    assert lookup.get("제6장") == "gaap-ch6"


@pytest.mark.unit
def test_lookup_section():
    lookup = build_lookup(_make_graph())
    assert lookup.get("제2절") == "gaap-ch6-s2"


@pytest.mark.unit
def test_lookup_paragraph():
    lookup = build_lookup(_make_graph())
    assert lookup.get("6.4") == "gaap-ch6-s1-최초인식"
    assert lookup.get("문단6.4") == "gaap-ch6-s1-최초인식"


@pytest.mark.unit
def test_resolve_success():
    graph = _make_graph()
    graph.edges = [OntologyEdge(
        from_id="gaap-ch6-s1-최초인식", to_id="",
        edge_type="REFERENCES", unresolved_target="제2절",
    )]
    resolved = resolve_edges(graph)
    assert resolved.edges[0].to_id == "gaap-ch6-s2"
    assert resolved.edges[0].unresolved_target == ""


@pytest.mark.unit
def test_resolve_section_does_not_set_to_paragraph():
    """절로 해소된 엣지는 norm에 문단 패턴이 섞여 있어도 to_paragraph를 비워둔다.

    문단 9.9는 어떤 Subsection에도 없으므로 문단 우선(시도2) 매칭이 실패하고
    절 패턴(시도3)으로 폴백 해소된다. 이때 to_paragraph가 "9.9"로 잘못 채워지면 안 된다.
    """
    graph = _make_graph()
    graph.edges = [OntologyEdge(
        from_id="gaap-ch6-s1-최초인식", to_id="",
        edge_type="REFERENCES", unresolved_target="제2절 문단 9.9",
    )]
    resolved = resolve_edges(graph)
    assert resolved.edges[0].to_id == "gaap-ch6-s2"
    assert resolved.edges[0].to_paragraph == ""


@pytest.mark.unit
def test_resolve_subsection_sets_to_paragraph():
    """Subsection으로 해소된 엣지는 to_paragraph를 정상적으로 채운다."""
    graph = _make_graph()
    graph.edges = [OntologyEdge(
        from_id="gaap-ch6-s2", to_id="",
        edge_type="REFERENCES", unresolved_target="문단 6.4",
    )]
    resolved = resolve_edges(graph)
    assert resolved.edges[0].to_id == "gaap-ch6-s1-최초인식"
    assert resolved.edges[0].to_paragraph == "6.4"


@pytest.mark.unit
def test_resolve_failure_records_unresolved():
    # 문단·절·장 어느 패턴으로도 해소되지 않으면 원문을 그대로 남긴다.
    graph = _make_graph()
    graph.edges = [OntologyEdge(
        from_id="gaap-ch6-s1-최초인식", to_id="",
        edge_type="REFERENCES", unresolved_target="문단 9.9",
    )]
    resolved = resolve_edges(graph)
    assert resolved.edges[0].to_id == ""
    assert resolved.edges[0].unresolved_target == "문단 9.9"


@pytest.mark.unit
def test_resolve_cross_chapter_deterministic_id():
    """타 장 참조는 현재 장 Standard id의 prefix로 결정적 id를 만들어 연결한다.

    "제8장" 노드는 현재 장 그래프에 없지만 전 장을 합친 그래프에서 유효한 링크가 된다.
    타 장은 현재 그래프로 문단 소속 검증이 불가능하므로 to_paragraph는 원문 번호를 보존한다.
    """
    graph = _make_graph()
    graph.edges = [OntologyEdge(
        from_id="gaap-ch6-s1-최초인식", to_id="",
        edge_type="REFERENCES", unresolved_target="제8장 문단 8.2",
    )]
    resolved = resolve_edges(graph)
    assert resolved.edges[0].to_id == "gaap-ch8"
    assert resolved.edges[0].unresolved_target == ""
    assert resolved.edges[0].to_paragraph == "8.2"


@pytest.mark.unit
def test_lookup_section_direct_paragraph():
    # H3 없이 H2 바로 아래 놓인 문단(Section 직속)도 lookup에 등록돼야
    # "문단 3.16" 같은 같은-장 참조가 해소된다.
    graph = OntologyGraph(nodes=[
        OntologyNode(id="gaap-ch3", node_type="Standard", chapter="3", name="제 3 장 재고자산"),
        OntologyNode(id="gaap-ch3-s2", node_type="Section", title="제 2 절 평가",
                     order=2, paragraphs=["3.16"]),
    ])
    lookup = build_lookup(graph)
    assert lookup.get("3.16") == "gaap-ch3-s2"
    assert lookup.get("문단3.16") == "gaap-ch3-s2"


@pytest.mark.unit
def test_resolve_section_direct_paragraph_sets_to_paragraph():
    # Section 직속 문단으로 해소되면 그 문단이 실제 해당 Section 소속이므로 to_paragraph를 남긴다.
    graph = OntologyGraph(nodes=[
        OntologyNode(id="gaap-ch3", node_type="Standard", chapter="3", name="제 3 장 재고자산"),
        OntologyNode(id="gaap-ch3-s2", node_type="Section", title="제 2 절 평가",
                     order=2, paragraphs=["3.16"]),
        OntologyNode(id="gaap-ch3-s1-src", node_type="Subsection",
                     title="출처", paragraphs=["3.1"]),
    ])
    graph.edges = [OntologyEdge(
        from_id="gaap-ch3-s1-src", to_id="",
        edge_type="REFERENCES", unresolved_target="문단 3.16",
    )]
    resolved = resolve_edges(graph)
    assert resolved.edges[0].to_id == "gaap-ch3-s2"
    assert resolved.edges[0].to_paragraph == "3.16"


@pytest.mark.unit
def test_resolve_uiN_descriptor_falls_back_to_base_paragraph():
    # "28.5의1"처럼 '의N'이 하위문단이 아니라 설명어인 경우 본문단("28.5")으로 보정 해소한다.
    graph = OntologyGraph(nodes=[
        OntologyNode(id="gaap-ch28", node_type="Standard", chapter="28", name="제 28 장 테스트"),
        OntologyNode(id="gaap-ch28-s1-대상", node_type="Subsection",
                     title="대상", paragraphs=["28.5"]),
        OntologyNode(id="gaap-ch28-s1-src", node_type="Subsection",
                     title="출처", paragraphs=["28.1"]),
    ])
    graph.edges = [OntologyEdge(
        from_id="gaap-ch28-s1-src", to_id="",
        edge_type="REFERENCES", unresolved_target="문단 28.5의1",
    )]
    resolved = resolve_edges(graph)
    assert resolved.edges[0].to_id == "gaap-ch28-s1-대상"
    assert resolved.edges[0].to_paragraph == "28.5"


@pytest.mark.unit
def test_has_condition_without_target_becomes_selfloop():
    """외부 대상 없는 HAS_CONDITION은 to_id=from_id 자기루프로 보존된다.

    일반 자기참조(REFERENCES)는 여전히 제거된다.
    """
    graph = _make_graph()
    graph.edges = [
        OntologyEdge(from_id="gaap-ch6-s1-최초인식", to_id="",
                     edge_type="HAS_CONDITION", unresolved_target=""),
        # 자기 자신의 문단을 참조하는 REFERENCES — 해소 후 자기참조로 제거돼야 한다
        OntologyEdge(from_id="gaap-ch6-s1-최초인식", to_id="",
                     edge_type="REFERENCES", unresolved_target="문단 6.4"),
    ]
    resolved = resolve_edges(graph)
    assert len(resolved.edges) == 1
    assert resolved.edges[0].edge_type == "HAS_CONDITION"
    assert resolved.edges[0].to_id == "gaap-ch6-s1-최초인식"


@pytest.mark.unit
def test_complete_ranges_supplements_missing_members():
    """LLM이 범위를 끝점 2개로 쪼개 반환해도 source_text의 범위 표현을 재파싱해
    그래프에 존재하는 누락 구간 멤버(6.10)를 템플릿 엣지 복제로 보충한다."""
    src_text = "문단 6.9부터 6.11까지의 규정에 따라 처리한다."
    graph = OntologyGraph(nodes=[
        OntologyNode(id="gaap-ch6", node_type="Standard", chapter="6", name="제 6 장 테스트"),
        OntologyNode(id="gaap-ch6-s1-src", node_type="Subsection", title="출처", paragraphs=["6.8"]),
        OntologyNode(id="gaap-ch6-s1-a", node_type="Subsection", title="a", paragraphs=["6.9"]),
        OntologyNode(id="gaap-ch6-s1-b", node_type="Subsection", title="b", paragraphs=["6.10"]),
        OntologyNode(id="gaap-ch6-s1-c", node_type="Subsection", title="c", paragraphs=["6.11"]),
    ])
    graph.edges = [
        OntologyEdge(from_id="gaap-ch6-s1-src", to_id="", edge_type="REFERENCES",
                     unresolved_target="문단 6.9", source_text=src_text),
        OntologyEdge(from_id="gaap-ch6-s1-src", to_id="", edge_type="REFERENCES",
                     unresolved_target="문단 6.11", source_text=src_text),
    ]
    resolved = resolve_edges(graph)
    assert {e.to_paragraph for e in resolved.edges} == {"6.9", "6.10", "6.11"}
    assert all(e.to_id for e in resolved.edges)
    # 보충 엣지는 템플릿(기존 엣지)의 타입·출처를 보존한다
    added = [e for e in resolved.edges if e.to_paragraph == "6.10"]
    assert added[0].edge_type == "REFERENCES"
    assert added[0].source_text == src_text


# --- 범위 표기 확장 ---------------------------------------------------
# start/end의 prefix(실·결·사례)가 다르면 확장하지 않고 None을 반환해
# 존재하지 않는 문단 번호(예: "실6.67")가 만들어지는 것을 막는다.

@pytest.mark.unit
def test_expand_range_same_prefix_expands_inclusive():
    # 같은 종류(본문)의 연속 범위는 끝 번호까지 포함해 확장한다.
    paras = ["6.8의2", "6.9", "6.10", "6.11"]
    assert _expand_range_target("문단 6.8의2~6.11", paras) == paras


@pytest.mark.unit
def test_expand_range_practice_prefix_expands():
    # 실무지침(실) prefix가 양쪽 모두 일치하면 정상 확장한다.
    paras = ["실6.66", "실6.67"]
    assert _expand_range_target("문단 실6.66~실6.67", paras) == paras


@pytest.mark.unit
def test_expand_range_prefix_mismatch_returns_none():
    # 시작은 "실6.66", 끝은 prefix 없는 "6.67"인 경우.
    # 끝 번호는 시작의 접두어를 물려받아 "실6.67"로 해석되는데,
    # 그래프에 "실6.67"이 없으므로 확장하지 않고 None을 반환한다(부분 매핑 노이즈 방지).
    paras = ["실6.66", "6.67"]
    assert _expand_range_target("문단 실6.66~6.67", paras) is None


@pytest.mark.unit
def test_expand_range_prefix_inheritance():
    # 원문은 보통 접두어를 범위 시작에만 적는다("실6.66~6.67").
    # 끝 번호가 시작의 접두어를 물려받아 그래프에 존재하면 정상 확장한다.
    paras = ["실6.66", "실6.67"]
    assert _expand_range_target("문단 실6.66~6.67", paras) == paras


@pytest.mark.unit
def test_expand_range_conflicting_prefixes_returns_none():
    # 양 끝 접두어가 서로 다르면(실 vs 결) 확장 불가.
    paras = ["실6.66", "결6.67"]
    assert _expand_range_target("문단 실6.66~결6.67", paras) is None


@pytest.mark.unit
def test_expand_range_naeji_keyword():
    # "내지" 범위 문법 지원: "문단 X 내지 문단 Y"는 X~Y 연속 구간이다.
    paras = ["22.37", "22.38", "22.44"]
    assert _expand_range_target("문단 22.37 내지 문단 22.44", paras) == paras


@pytest.mark.unit
def test_expand_range_eseo_kkaji_keyword():
    # "에서 ~ 까지" 범위 문법 지원.
    paras = ["6.87", "6.88", "6.89"]
    assert _expand_range_target("6.87에서 6.89까지", paras) == paras


@pytest.mark.unit
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


@pytest.mark.unit
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
