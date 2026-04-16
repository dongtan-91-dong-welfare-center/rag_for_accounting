# 온톨로지 구축 파이프라인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 파싱된 회계기준서 마크다운 파일에서 Standard/Section/Subsection 노드와 CONTAINS/REFERENCES/EXCLUDES/HAS_CONDITION 엣지를 추출하여 프레임워크 독립적인 JSON 그래프로 저장한다.

**Architecture:** 마크다운 파서가 `##` 헤딩 계층으로 Standard→Section→Subsection 노드를 구성하고, 정규식 탐지기가 엣지 후보 문장을 필터링한다. LLM(GPT-4o-mini)이 후보 문장에서 엣지 타입·대상·속성을 자유 판별하며, 리졸버가 텍스트 참조를 노드 ID로 변환한다. 미연결 참조는 `unresolved_refs`/`unresolved_target`에 기록한다. 빌더가 파이프라인 조율 + CLI를 모두 담당한다.

**Tech Stack:** Python 3.12, uv, Pydantic v2, openai, re, json, pytest

**Spec:** `docs/superpowers/specs/2026-04-10-ontology-schema-design.md`

**입력 형식 (`data/회계_sample.md` 기준):**
```
## 제 6 장 금융자산 · 금융부채   ← Standard 헤딩
## 제 1 절 공통사항              ← Section 헤딩 (제N절 패턴)
## 금융상품의 최초인식            ← Subsection 헤딩
- 6.4 ...내용...               ← 문단
- ⑴ ...                       ← 하위 항목
```

---

## File Structure

```
src/db/ontology/
  __init__.py
  models.py          # OntologyNode, OntologyEdge, OntologyGraph (Pydantic)
  md_parser.py       # 마크다운 → Standard/Section/Subsection 노드 + CONTAINS 엣지
  edge_detector.py   # 정규식 탐지: 엣지 후보 문장 필터링
  edge_extractor.py  # LLM: 후보 문장 → EdgeCandidate 목록
  resolver.py        # target_ref 텍스트 → 노드 ID 변환
  builder.py         # 파이프라인 조율 + argparse CLI (main 포함)

tests/unit/ontology/
  __init__.py
  test_models.py
  test_md_parser.py
  test_edge_detector.py
  test_edge_extractor.py
  test_resolver.py

tests/integration/
  test_ontology_builder.py

data/ontology/           # 출력 디렉토리 (빌더가 생성)
  gaap-ch6.json
```

---

## Task 1: 의존성 추가

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: pyproject.toml 수정**

```toml
[project]
name = "rag-for-accounting"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "docling>=2.85.0",
    "streamlit>=1.56.0",
    "pydantic>=2.0.0",
    "openai>=1.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.25.0",
]
```

- [ ] **Step 2: 설치**

Run: `uv sync --all-extras`
Expected: `pydantic`, `openai`, `python-dotenv` 포함 설치 성공

- [ ] **Step 3: .env.example 생성**

`.env.example`:
```
OPENAI_API_KEY=sk-your-key-here
```

- [ ] **Step 4: 커밋**

```bash
git add pyproject.toml uv.lock .env.example
git commit -m "chore: pydantic, openai, python-dotenv 의존성 추가"
```

---

## Task 2: 데이터 모델

**Files:**
- Create: `src/db/ontology/__init__.py`
- Create: `src/db/ontology/models.py`
- Create: `tests/unit/ontology/__init__.py`
- Test: `tests/unit/ontology/test_models.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/ontology/test_models.py`:
```python
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


def test_ontology_graph_defaults():
    graph = OntologyGraph()
    assert graph.nodes == []
    assert graph.edges == []
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `uv run pytest tests/unit/ontology/test_models.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: 모델 구현**

`src/db/ontology/__init__.py`: (빈 파일)

`src/db/ontology/models.py`:
```python
from pydantic import BaseModel, Field
from typing import Literal


class OntologyNode(BaseModel):
    id: str
    node_type: Literal["Standard", "Section", "Subsection"]
    # Standard
    name: str = ""
    standard_type: str = ""   # "GAAP" | "KIFRS"
    chapter: str = ""
    effective_date: str = ""
    # Section / Subsection
    title: str = ""
    order: int = 0
    # Subsection
    content: str = ""
    paragraphs: list[str] = Field(default_factory=list)
    unresolved_refs: list[str] = Field(default_factory=list)


class OntologyEdge(BaseModel):
    from_id: str
    to_id: str = ""
    edge_type: Literal["CONTAINS", "REFERENCES", "EXCLUDES", "HAS_CONDITION"]
    order: int = 0              # CONTAINS
    paragraph: str = ""         # REFERENCES, EXCLUDES, HAS_CONDITION
    source_text: str = ""
    include: list[str] = Field(default_factory=list)  # EXCLUDES
    condition_text: str = ""    # HAS_CONDITION
    unresolved_target: str = "" # to_id 빈 경우 원문 참조 텍스트


class OntologyGraph(BaseModel):
    nodes: list[OntologyNode] = Field(default_factory=list)
    edges: list[OntologyEdge] = Field(default_factory=list)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/ontology/test_models.py -v`
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add src/db/ontology/ tests/unit/ontology/
git commit -m "feat: 온톨로지 Pydantic 모델 정의"
```

---

## Task 3: 마크다운 파서

**Files:**
- Create: `src/db/ontology/md_parser.py`
- Test: `tests/unit/ontology/test_md_parser.py`

파싱 규칙:
- `## 제\s*\d+\s*장` → Standard 노드 이름 확정
- `## 제\s*\d+\s*절` → Section 노드
- 그 외 `##` (문서 제목 제외) → Subsection 노드
- `- 6.X`, `- 실6.X` 등 마커 → 현재 Subsection의 `paragraphs` + `content`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/ontology/test_md_parser.py`:
```python
from src.db.ontology.md_parser import parse_markdown
from src.db.ontology.models import OntologyGraph

SAMPLE_MD = """## 일반기업회계기준

제 6 장 금융자산 · 금융부채

한국회계기준원 회계기준위원회 의결 2017. 9. 22.

## 제 6 장 금융자산 · 금융부채

## 적용범위

- 6.2 이 장은 다음을 제외한 모든 유형의 금융상품에 적용한다 .
- ⑴ 종속기업 , 관계기업 및 조인트벤처 투자지분
- ⑵ 리스에 따른 권리와 의무 . 다만 , ㈎ 리스채권의 제거와 손상에 대하여는 이 장을 적용한다 .

## 제 1 절 공통사항

- 6.3 제 2 절 ~ 제 4 절 에서 정하지 않은 사항은 이 절에서 제시하는 원칙을 적용한다 .

## 금융상품의 최초인식

- 6.4 금융자산이나 금융부채는 계약당사자가 되는 때에만 재무상태표에 인식한다 .
- 6.4 의 2 정형화된 거래의 경우 매매일에 해당 거래를 인식한다 .
"""


def test_parse_returns_graph():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    assert isinstance(graph, OntologyGraph)


def test_standard_node_created():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    standards = [n for n in graph.nodes if n.node_type == "Standard"]
    assert len(standards) == 1
    assert standards[0].id == "gaap-ch6"
    assert "금융자산" in standards[0].name


def test_standard_chapter_extracted_from_markdown():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    standard = next(n for n in graph.nodes if n.node_type == "Standard")
    assert standard.chapter == "6"


def test_section_node_created():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    sections = [n for n in graph.nodes if n.node_type == "Section"]
    assert len(sections) == 1
    assert "공통사항" in sections[0].title


def test_subsection_nodes_created():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    subsections = [n for n in graph.nodes if n.node_type == "Subsection"]
    titles = [s.title for s in subsections]
    assert "적용범위" in titles
    assert "금융상품의 최초인식" in titles


def test_subsection_paragraphs():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    sub = next(n for n in graph.nodes if n.node_type == "Subsection" and n.title == "적용범위")
    assert "6.2" in sub.paragraphs


def test_subsection_content_not_empty():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    sub = next(n for n in graph.nodes if n.node_type == "Subsection" and n.title == "금융상품의 최초인식")
    assert "6.4" in sub.content


def test_contains_edges_exist():
    graph = parse_markdown(SAMPLE_MD, standard_id="gaap-ch6", standard_type="GAAP")
    contains = [e for e in graph.edges if e.edge_type == "CONTAINS"]
    from_ids = [e.from_id for e in contains]
    assert "gaap-ch6" in from_ids
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `uv run pytest tests/unit/ontology/test_md_parser.py -v`
Expected: `ImportError`

- [ ] **Step 3: 파서 구현**

`src/db/ontology/md_parser.py`:
```python
import re
from src.db.ontology.models import OntologyGraph, OntologyNode, OntologyEdge
from src.parse.parser_dtos import _MARKER_RE

_CHAPTER_RE = re.compile(r'제\s*(\d+)\s*장')
_SECTION_RE = re.compile(r'제\s*(\d+)\s*절')


def _slugify(text: str) -> str:
    return re.sub(r'\s+', '_', text.strip())[:40]


def _extract_paragraph_id(line: str) -> str | None:
    """'- 6.4 ...' 또는 '- 실6.1 ...' 형태에서 문단 번호를 추출한다."""
    content = re.sub(r'^-\s+', '', line).strip()
    tokens = content.split()
    first_token = tokens[0] if tokens else ''
    if _MARKER_RE.match(first_token) and re.search(r'\d+\.\d+', first_token):
        return first_token
    return None


def parse_markdown(
    text: str,
    standard_id: str,
    standard_type: str,
    effective_date: str = "",
) -> OntologyGraph:
    graph = OntologyGraph()
    standard = OntologyNode(
        id=standard_id,
        node_type="Standard",
        standard_type=standard_type,
        effective_date=effective_date,
    )
    graph.nodes.append(standard)

    current_section: OntologyNode | None = None
    current_subsection: OntologyNode | None = None
    section_order = 0
    subsection_order = 0
    content_lines: list[str] = []

    def flush_subsection() -> None:
        nonlocal current_subsection, content_lines
        if current_subsection is None:
            return
        current_subsection.content = '\n'.join(content_lines).strip()
        graph.nodes.append(current_subsection)
        parent_id = current_section.id if current_section else standard_id
        graph.edges.append(OntologyEdge(
            from_id=parent_id,
            to_id=current_subsection.id,
            edge_type="CONTAINS",
            order=current_subsection.order,
        ))
        content_lines.clear()

    for line in text.split('\n'):
        stripped = line.strip()

        if not stripped.startswith('## '):
            if current_subsection is not None:
                content_lines.append(line)
                para_id = _extract_paragraph_id(stripped)
                if para_id and para_id not in current_subsection.paragraphs:
                    current_subsection.paragraphs.append(para_id)
            continue

        heading = stripped[3:].strip()
        chapter_match = _CHAPTER_RE.search(heading)
        section_match = _SECTION_RE.search(heading)

        if chapter_match:
            standard.name = heading
            standard.chapter = chapter_match.group(1)
            continue

        if section_match:
            flush_subsection()
            current_subsection = None
            section_order += 1
            subsection_order = 0
            sec_id = f"{standard_id}-s{section_match.group(1)}"
            current_section = OntologyNode(
                id=sec_id,
                node_type="Section",
                title=heading,
                order=section_order,
            )
            graph.nodes.append(current_section)
            graph.edges.append(OntologyEdge(
                from_id=standard_id,
                to_id=sec_id,
                edge_type="CONTAINS",
                order=section_order,
            ))
            continue

        # Subsection
        flush_subsection()
        subsection_order += 1
        parent_id = current_section.id if current_section else standard_id
        sub_id = f"{parent_id}-{_slugify(heading)}"
        current_subsection = OntologyNode(
            id=sub_id,
            node_type="Subsection",
            title=heading,
            order=subsection_order,
        )

    flush_subsection()
    return graph
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/ontology/test_md_parser.py -v`
Expected: 8 passed

- [ ] **Step 5: 커밋**

```bash
git add src/db/ontology/md_parser.py tests/unit/ontology/test_md_parser.py
git commit -m "feat: 마크다운 → 온톨로지 노드 파서 구현"
```

---

## Task 4: 엣지 탐지기

**Files:**
- Create: `src/db/ontology/edge_detector.py`
- Test: `tests/unit/ontology/test_edge_detector.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/ontology/test_edge_detector.py`:
```python
from src.db.ontology.edge_detector import detect_candidates


def test_detects_다만():
    content = "- ⑵ 리스에 따른 권리와 의무 . 다만 , ㈎ 리스채권에 대하여는 이 장을 적용한다 ."
    assert any("다만" in c for c in detect_candidates(content))


def test_detects_제외():
    content = "- 6.5 금융자산 ( 제 2 절 유가증권의 적용대상 금융자산은 제외 ) 의 양도의 경우에"
    assert any("제외" in c for c in detect_candidates(content))


def test_detects_section_ref():
    content = "- 6.3 제 2 절 ~ 제 4 절 에서 정하지 않은 사항은 이 절에서 제시하는 원칙을 적용한다 ."
    assert len(detect_candidates(content)) >= 1


def test_detects_문단_ref():
    content = "- 6.21 유가증권의 최초 인식에 관한 규정은 이 장의 제 1 절 공통사항 문단 6.4 를 따른다 ."
    assert any("문단" in c for c in detect_candidates(content))


def test_detects_불구하고():
    content = "- 6.89 위의 규정에 불구하고 다음의 경우에는 별도의 처리를 한다 ."
    assert any("불구하고" in c for c in detect_candidates(content))


def test_no_false_positive():
    content = "- 6.7 매각거래와 관련하여 취득하거나 부담하는 자산 및 부채의 예로는 위탁수수료를 들 수 있다 ."
    assert detect_candidates(content) == []
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `uv run pytest tests/unit/ontology/test_edge_detector.py -v`
Expected: `ImportError`

- [ ] **Step 3: 탐지기 구현**

`src/db/ontology/edge_detector.py`:
```python
import re

_PATTERNS = [
    re.compile(r'다만'),
    re.compile(r'제외'),
    re.compile(r'제\s*\d+\s*절'),
    re.compile(r'제\s*\d+\s*장'),
    re.compile(r'문단\s*\d+'),
    re.compile(r'불구하고'),
    re.compile(r'한하여'),
]


def detect_candidates(content: str) -> list[str]:
    """
    Subsection content에서 엣지 탐지 패턴과 매칭되는 줄을 반환한다.
    정규식은 후보를 좁히는 트리거이며, 엣지 타입 판별은 LLM이 수행한다.
    """
    return [
        line.strip()
        for line in content.split('\n')
        if line.strip() and any(p.search(line) for p in _PATTERNS)
    ]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/ontology/test_edge_detector.py -v`
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add src/db/ontology/edge_detector.py tests/unit/ontology/test_edge_detector.py
git commit -m "feat: 정규식 기반 엣지 후보 탐지기 구현"
```

---

## Task 5: LLM 엣지 추출기

**Files:**
- Create: `src/db/ontology/edge_extractor.py`
- Test: `tests/unit/ontology/test_edge_extractor.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/ontology/test_edge_extractor.py`:
```python
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


def test_none_filtered():
    data = {"edge_type": "NONE", "paragraph": "", "target_ref": "",
            "source_text": "단순 서술", "include": [], "condition_text": ""}
    with patch("src.db.ontology.edge_extractor._client") as mc:
        mc.chat.completions.create.return_value = _mock_response([data])
        result = extract_edges("gaap-ch6-s1", "제목", "내용", ["단순 서술"])
        assert result == []
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `uv run pytest tests/unit/ontology/test_edge_extractor.py -v`
Expected: `ImportError`

- [ ] **Step 3: 추출기 구현**

`src/db/ontology/edge_extractor.py`:
```python
import json
import os
from pydantic import BaseModel, Field
from typing import Literal
from openai import OpenAI

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

_SYSTEM_PROMPT = """당신은 한국 회계기준서 텍스트에서 조항 간 관계(엣지)를 추출하는 전문가입니다.
주어진 후보 문장 각각에 대해 엣지를 판별하고 JSON으로 반환합니다.

엣지 타입:
- REFERENCES: 다른 장·절·문단을 참조 (제N절, 제N장, 문단 X.X 등)
- EXCLUDES: 적용범위에서 제외. include 배열에 제외 후 재포함되는 항목 기입
- HAS_CONDITION: 원칙은 A이나 특정 조건 충족 시 다른 처리(B)로 전환하며 B가 외부 조항인 경우
- NONE: 엣지 없음 (자기 소절 내 단순 언급, 일반 서술, 조건 목록 나열)

반환 형식:
{
  "edges": [
    {
      "edge_type": "REFERENCES|EXCLUDES|HAS_CONDITION|NONE",
      "paragraph": "출처 하위 항목 번호 (예: 6.14⑵㈏, 빈 문자열 가능)",
      "target_ref": "참조 대상 원문 (예: 제2절, 문단 6.4, 제8장 문단 8.2)",
      "source_text": "해당 원문 문장",
      "include": ["재포함 항목1"],
      "condition_text": "조건 원문 (HAS_CONDITION일 때만)"
    }
  ]
}"""


class EdgeCandidate(BaseModel):
    edge_type: Literal["REFERENCES", "EXCLUDES", "HAS_CONDITION", "NONE"]
    paragraph: str = ""
    target_ref: str = ""
    source_text: str = ""
    include: list[str] = Field(default_factory=list)
    condition_text: str = ""


def extract_edges(
    subsection_id: str,
    title: str,
    content: str,
    candidates: list[str],
) -> list[EdgeCandidate]:
    """후보 문장을 LLM에 보내 엣지를 추출한다. NONE은 제외하고 반환."""
    if not candidates:
        return []

    user_prompt = (
        f"소절 ID: {subsection_id}\n소절 제목: {title}\n\n"
        f"전체 내용:\n{content}\n\n"
        f"다음 후보 문장들에서 엣지를 판별하세요:\n"
        + "\n".join(f"- {c}" for c in candidates)
    )

    response = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    raw = json.loads(response.choices[0].message.content)
    return [
        EdgeCandidate(**item)
        for item in raw.get("edges", [])
        if item.get("edge_type") != "NONE"
    ]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/ontology/test_edge_extractor.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add src/db/ontology/edge_extractor.py tests/unit/ontology/test_edge_extractor.py
git commit -m "feat: LLM 기반 엣지 추출기 구현"
```

---

## Task 6: 참조 리졸버

**Files:**
- Create: `src/db/ontology/resolver.py`
- Test: `tests/unit/ontology/test_resolver.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/ontology/test_resolver.py`:
```python
from src.db.ontology.models import OntologyGraph, OntologyNode, OntologyEdge
from src.db.ontology.resolver import build_lookup, resolve_edges


def _make_graph() -> OntologyGraph:
    return OntologyGraph(nodes=[
        OntologyNode(id="gaap-ch6", node_type="Standard", chapter="6"),
        OntologyNode(id="gaap-ch6-s1", node_type="Section", title="제 1 절 공통사항", order=1),
        OntologyNode(id="gaap-ch6-s2", node_type="Section", title="제 2 절 유가증권", order=2),
        OntologyNode(id="gaap-ch6-s1-최초인식", node_type="Subsection",
                     title="금융상품의 최초인식", paragraphs=["6.4", "6.4의2"]),
    ])


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
    src = next(n for n in resolved.nodes if n.id == "gaap-ch6-s1-최초인식")
    assert "제8장 문단 8.2" in src.unresolved_refs
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `uv run pytest tests/unit/ontology/test_resolver.py -v`
Expected: `ImportError`

- [ ] **Step 3: 리졸버 구현**

`src/db/ontology/resolver.py`:
```python
import re
from src.db.ontology.models import OntologyGraph

_SECTION_RE = re.compile(r'제\s*(\d+)\s*절')
_PARA_RE = re.compile(r'(\d+\.\d+(?:의\d+)?)')


def build_lookup(graph: OntologyGraph) -> dict[str, str]:
    """정규화된 참조 텍스트 → 노드 ID 매핑 테이블"""
    lookup: dict[str, str] = {}
    for node in graph.nodes:
        if node.node_type == "Section":
            m = _SECTION_RE.search(node.title)
            if m:
                num = m.group(1)
                for key in (f'제{num}절', f'제 {num} 절', f'제{num} 절', f'제 {num}절'):
                    lookup[key] = node.id
        if node.node_type == "Subsection":
            for para in node.paragraphs:
                norm = para.replace(' ', '')
                lookup[norm] = node.id
                lookup[f'문단{norm}'] = node.id
                lookup[f'문단 {norm}'] = node.id
    return lookup


def resolve_edges(graph: OntologyGraph) -> OntologyGraph:
    """unresolved_target을 노드 ID로 변환. 실패 시 unresolved_refs에 기록."""
    lookup = build_lookup(graph)
    node_map = {n.id: n for n in graph.nodes}
    resolved = []

    for edge in graph.edges:
        if edge.to_id or not edge.unresolved_target:
            resolved.append(edge)
            continue

        ref = edge.unresolved_target
        norm = ref.replace(' ', '')
        target_id = lookup.get(norm)

        if not target_id:
            m = _SECTION_RE.search(ref)
            if m:
                target_id = lookup.get(f'제{m.group(1)}절')

        if not target_id:
            m = _PARA_RE.search(ref)
            if m:
                target_id = lookup.get(m.group(1).replace(' ', ''))

        if target_id:
            resolved.append(edge.model_copy(update={"to_id": target_id, "unresolved_target": ""}))
        else:
            resolved.append(edge)
            src = node_map.get(edge.from_id)
            if src and ref not in src.unresolved_refs:
                src.unresolved_refs.append(ref)

    graph.edges = resolved
    return graph
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/unit/ontology/test_resolver.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add src/db/ontology/resolver.py tests/unit/ontology/test_resolver.py
git commit -m "feat: 텍스트 참조 → 노드 ID 리졸버 구현"
```

---

## Task 7: 빌더 + CLI

**Files:**
- Create: `src/db/ontology/builder.py`
- Test: `tests/integration/test_ontology_builder.py`

- [ ] **Step 1: 통합 테스트 작성**

`tests/integration/test_ontology_builder.py`:
```python
"""LLM 호출을 모킹하여 파이프라인 구조를 검증한다."""
from unittest.mock import patch
from src.db.ontology.builder import build_graph
from src.db.ontology.edge_extractor import EdgeCandidate

MD_PATH = "data/회계_sample.md"


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
    loaded = OntologyGraph.model_validate_json(out.read_text())
    assert len(loaded.nodes) == len(graph.nodes)
    assert len(loaded.edges) == len(graph.edges)
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `uv run pytest tests/integration/test_ontology_builder.py -v`
Expected: `ImportError`

- [ ] **Step 3: 빌더 구현**

`src/db/ontology/builder.py`:
```python
"""
온톨로지 구축 파이프라인 + CLI

파이프라인:
  1. parse_markdown   → Standard/Section/Subsection 노드 + CONTAINS 엣지
  2. detect_candidates → 엣지 후보 문장 (정규식)
  3. extract_edges    → EdgeCandidate 목록 (LLM)
  4. resolve_edges    → target_ref → 노드 ID 변환

CLI 사용법:
  uv run python -m src.db.ontology.builder \\
      --input data/회계_sample.md \\
      --output data/ontology/gaap-ch6.json \\
      --standard-id gaap-ch6 \\
      --standard-type GAAP
"""
import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from src.db.ontology.edge_detector import detect_candidates
from src.db.ontology.edge_extractor import extract_edges
from src.db.ontology.md_parser import parse_markdown
from src.db.ontology.models import OntologyEdge, OntologyGraph
from src.db.ontology.resolver import resolve_edges


def build_graph(
    md_path: str | Path,
    standard_id: str,
    standard_type: str,
    effective_date: str = "",
) -> OntologyGraph:
    text = Path(md_path).read_text(encoding="utf-8")
    graph = parse_markdown(text, standard_id, standard_type, effective_date)

    for node in graph.nodes:
        if node.node_type != "Subsection" or not node.content:
            continue
        candidates = detect_candidates(node.content)
        if not candidates:
            continue
        for ec in extract_edges(node.id, node.title, node.content, candidates):
            graph.edges.append(OntologyEdge(
                from_id=node.id,
                to_id="",
                edge_type=ec.edge_type,
                paragraph=ec.paragraph,
                source_text=ec.source_text,
                include=ec.include,
                condition_text=ec.condition_text,
                unresolved_target=ec.target_ref,
            ))

    return resolve_edges(graph)


def save_graph(graph: OntologyGraph, output_path: str | Path) -> None:
    Path(output_path).write_text(graph.model_dump_json(indent=2), encoding="utf-8")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="회계기준서 온톨로지 그래프 구축")
    parser.add_argument("--input", required=True, help="파싱된 마크다운 파일 경로")
    parser.add_argument("--output", required=True, help="출력 JSON 파일 경로")
    parser.add_argument("--standard-id", required=True, help="예: gaap-ch6")
    parser.add_argument("--standard-type", required=True, choices=["GAAP", "KIFRS"])
    parser.add_argument("--effective-date", default="")
    args = parser.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    print(f"파싱 중: {args.input}")
    graph = build_graph(args.input, args.standard_id, args.standard_type,
                        args.effective_date)
    save_graph(graph, args.output)

    nodes = len(graph.nodes)
    edges = len(graph.edges)
    unresolved = sum(1 for e in graph.edges if not e.to_id)
    print(f"완료: 노드 {nodes}개, 엣지 {edges}개 (미해소 참조: {unresolved}개)")
    print(f"저장: {args.output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통합 테스트 통과 확인**

Run: `uv run pytest tests/integration/test_ontology_builder.py -v`
Expected: 3 passed

- [ ] **Step 5: 전체 테스트 통과 확인**

Run: `uv run pytest tests/unit/ontology/ tests/integration/test_ontology_builder.py -v`
Expected: 전체 통과

- [ ] **Step 6: 실제 실행 (.env에 OPENAI_API_KEY 설정 필요)**

Run:
```bash
uv run python -m src.db.ontology.builder \
    --input data/회계_sample.md \
    --output data/ontology/gaap-ch6.json \
    --standard-id gaap-ch6 \
    --standard-type GAAP
```

Expected:
```
파싱 중: data/회계_sample.md
완료: 노드 XX개, 엣지 XX개 (미해소 참조: XX개)
저장: data/ontology/gaap-ch6.json
```

- [ ] **Step 7: 커밋**

```bash
git add src/db/ontology/builder.py tests/integration/test_ontology_builder.py
git commit -m "feat: 온톨로지 빌더 파이프라인 + CLI 구현"
```
