"""LLM 호출을 모킹하여 파이프라인 구조를 검증한다."""
from unittest.mock import patch
from src.db.ontology.builder import build_graph
from src.db.ontology.edge_extractor import EdgeCandidate

MD_PATH = "data/llm_parsed/회계_sample.md"


def _mock_extract(subsection_id, title, content, candidates):
    if any("절" in c for c in candidates):
        return [EdgeCandidate(
            edge_type="REFERENCES", paragraph="mock",
            target_ref="제1절", source_text=candidates[0],
        )]
    return []


def test_graph_has_all_node_types():
    with patch("src.db.ontology.builder.extract_edges", side_effect=_mock_extract):
        graph = build_graph(MD_PATH, "gaap-ch6", "GAAP")
    types = {n.node_type for n in graph.nodes}
    assert "Standard" in types
    assert "Section" in types
    assert "Subsection" in types


def test_graph_has_contains_edges():
    with patch("src.db.ontology.builder.extract_edges", side_effect=_mock_extract):
        graph = build_graph(MD_PATH, "gaap-ch6", "GAAP")
    assert any(e.edge_type == "CONTAINS" for e in graph.edges)


def test_save_reload(tmp_path):
    from src.db.ontology.builder import save_graph
    from src.db.ontology.models import OntologyGraph

    with patch("src.db.ontology.builder.extract_edges", side_effect=_mock_extract):
        graph = build_graph(MD_PATH, "gaap-ch6", "GAAP")
    out = tmp_path / "test.json"
    save_graph(graph, out)
    loaded = OntologyGraph.model_validate_json(out.read_text(encoding="utf-8"))
    assert len(loaded.nodes) == len(graph.nodes)
    assert len(loaded.edges) == len(graph.edges)
