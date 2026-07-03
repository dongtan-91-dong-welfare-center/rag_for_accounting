import pytest
from src.db.ontology.md_parser import parse_markdown
from src.db.ontology.models import OntologyGraph

SAMPLE_MD = """# 제 6 장 금융자산 · 금융부채

한국회계기준원 회계기준위원회 의결 2017. 9. 22.

### 적용범위

#### 6.2 이 장은 다음을 제외한 모든 유형의 금융상품에 적용한다 .
- ⑴ 종속기업 , 관계기업 및 조인트벤처 투자지분
- ⑵ 리스에 따른 권리와 의무 . 다만 , ㈎ 리스채권의 제거와 손상에 대하여는 이 장을 적용한다 .

## 제 1 절 공통사항

#### 6.3 제 2 절 ~ 제 4 절 에서 정하지 않은 사항은 이 절에서 제시하는 원칙을 적용한다 .

### 금융상품의 최초인식

#### 6.4 금융자산이나 금융부채는 계약당사자가 되는 때에만 재무상태표에 인식한다 .
#### 6.4 의 2 정형화된 거래의 경우 매매일에 해당 거래를 인식한다 .
"""


@pytest.mark.unit
def test_parse_returns_graph():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    assert isinstance(graph, OntologyGraph)


@pytest.mark.unit
def test_standard_node_created():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    standards = [n for n in graph.nodes if n.node_type == "Standard"]
    assert len(standards) == 1
    assert standards[0].id == "gaap-ch6"
    assert "금융자산" in standards[0].name


@pytest.mark.unit
def test_standard_chapter_extracted_from_markdown():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    standard = next(n for n in graph.nodes if n.node_type == "Standard")
    assert standard.chapter == "6"


@pytest.mark.unit
def test_section_node_created():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    sections = [n for n in graph.nodes if n.node_type == "Section"]
    assert len(sections) == 1
    assert "공통사항" in sections[0].title


@pytest.mark.unit
def test_subsection_nodes_created():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    subsections = [n for n in graph.nodes if n.node_type == "Subsection"]
    titles = [s.title for s in subsections]
    assert "적용범위" in titles
    assert "금융상품의 최초인식" in titles


@pytest.mark.unit
def test_subsection_paragraphs():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    sub = next(n for n in graph.nodes if n.node_type == "Subsection" and n.title == "적용범위")
    assert "6.2" in sub.paragraphs


@pytest.mark.unit
def test_subsection_content_not_empty():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    sub = next(n for n in graph.nodes if n.node_type == "Subsection" and n.title == "금융상품의 최초인식")
    assert "6.4" in sub.content


@pytest.mark.unit
def test_contains_edges_exist():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    contains = [e for e in graph.edges if e.edge_type == "CONTAINS"]
    from_ids = [e.from_id for e in contains]
    assert "gaap-ch6" in from_ids


EMPTY_PARA_MD = """# 제 6 장 테스트

## 제 1 절 공통사항

### 6.5

### 6.6

#### 6.6 이 문단은 내용이 있다 .
"""


@pytest.mark.unit
def test_empty_paragraph_number_subsection_preserved():
    """title 자체가 문단 번호인 빈 소절(삭제됐거나 내용이 하위문단으로 옮겨간 문단)도 노드로 남긴다.

    문단 번호의 존재를 기록해 번호 연속성(범위 확장)과 참조 해소(build_lookup)를 보장한다.
    """
    graph = parse_markdown(EMPTY_PARA_MD, standard_id="gaap-ch6", standard_type="GAAP")
    titles = [n.title for n in graph.nodes if n.node_type == "Subsection"]
    assert "6.5" in titles


SLUG_CONFLICT_MD = """# 제 6 장 테스트

### 용어의 정의

이 소절은 절(H2) 없이 등장해 Standard 직속 Subsection이 된다 .

## 용어의 정의

본문이 이어진다 .

### 하위 소절

내용 .
"""


@pytest.mark.unit
def test_section_slug_id_conflict_with_subsection_gets_suffix():
    """절번호 없는 Section 슬러그 id가 동명 Subsection id와 충돌하면 suffix로 구분한다.

    동명 Subsection을 Section으로 잘못 재사용하면 타입이 섞여 CONTAINS 구조가 깨진다.
    """
    graph = parse_markdown(SLUG_CONFLICT_MD, standard_id="gaap-ch6", standard_type="GAAP")
    subsections = [n for n in graph.nodes if n.node_type == "Subsection" and n.title == "용어의 정의"]
    sections = [n for n in graph.nodes if n.node_type == "Section" and n.title == "용어의 정의"]
    assert len(subsections) == 1
    assert len(sections) == 1
    assert sections[0].id != subsections[0].id
