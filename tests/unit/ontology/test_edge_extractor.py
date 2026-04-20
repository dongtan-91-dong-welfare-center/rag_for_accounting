import json
from unittest.mock import MagicMock, patch
from src.db.ontology.edge_extractor import extract_edges, EdgeCandidate


def _mock_response(edges: list[dict]):
    mock_msg = MagicMock()
    mock_msg.content = json.dumps({"edges": edges})
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


def test_empty_candidates_returns_without_llm_call():
    with patch("src.db.ontology.edge_extractor._client") as mc:
        result = extract_edges("gaap-ch6-s1-공통", "공통사항", "내용", [])
        assert result == []
        mc.chat.completions.create.assert_not_called()


def test_returns_list():
    with patch("src.db.ontology.edge_extractor._client") as mc:
        mc.chat.completions.create.return_value = _mock_response([])
        result = extract_edges("gaap-ch6-s1-적용범위", "적용범위", "내용", ["다만 리스는 제외한다."])
        assert isinstance(result, list)


def test_references_edge():
    data = {"edge_type": "REFERENCES", "paragraph": "6.3", "target_ref": "제2절",
            "source_text": "제2절에서 정하지 않은 사항은 이 절에서 적용한다.", "include": [], "condition_text": ""}
    with patch("src.db.ontology.edge_extractor._client") as mc:
        mc.chat.completions.create.return_value = _mock_response([data])
        result = extract_edges("gaap-ch6-s1-공통", "공통사항", "내용", ["제2절에서 정하지 않은"])
        assert result[0].edge_type == "REFERENCES"
        assert result[0].target_ref == "제2절"


def test_excludes_with_include():
    data = {"edge_type": "EXCLUDES", "paragraph": "6.2⑵", "target_ref": "리스 관련",
            "source_text": "리스. 다만, 리스채권은 적용한다.", "include": ["리스채권의 제거와 손상"], "condition_text": ""}
    with patch("src.db.ontology.edge_extractor._client") as mc:
        mc.chat.completions.create.return_value = _mock_response([data])
        result = extract_edges("gaap-ch6-적용범위", "적용범위", "내용", ["리스. 다만, 리스채권은 적용한다."])
        assert "리스채권의 제거와 손상" in result[0].include


def test_is_default_for_edge():
    data = {"edge_type": "IS_DEFAULT_FOR", "paragraph": "6.3", "target_ref": "제2절",
            "source_text": "제2절~제4절에서 정하지 않은 사항은 이 절에서 적용한다.", "include": [], "condition_text": ""}
    with patch("src.db.ontology.edge_extractor._client") as mc:
        mc.chat.completions.create.return_value = _mock_response([data])
        result = extract_edges("gaap-ch6-s1-공통", "공통사항", "내용", ["제2절~제4절에서 정하지 않은"])
        assert result[0].edge_type == "IS_DEFAULT_FOR"
        assert result[0].target_ref == "제2절"


def test_none_filtered():
    data = {"edge_type": "NONE", "paragraph": "", "target_ref": "",
            "source_text": "단순 서술", "include": [], "condition_text": ""}
    with patch("src.db.ontology.edge_extractor._client") as mc:
        mc.chat.completions.create.return_value = _mock_response([data])
        result = extract_edges("gaap-ch6-s1", "제목", "내용", ["단순 서술"])
        assert result == []
