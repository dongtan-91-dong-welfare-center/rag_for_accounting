"""마크다운 파일을 읽어 Standard/Section/Subsection 노드와 CONTAINS 엣지를 만든다.

파싱 규칙 (## 헤딩 기준):
  ## 제N장 ...   → Standard 이름·장 번호 확정
  ## 제N절 ...   → Section 노드 생성
  ## 그 외 제목  → Subsection 노드 생성
  ## 없는 줄     → 현재 Subsection의 content 누적, 문단 번호 수집
"""

import re
from src.db.ontology.models import OntologyGraph, OntologyNode, OntologyEdge
from src.parse.parser_dtos import _MARKER_RE

# "제 6 장", "제6장" 등 다양한 공백 표기를 모두 잡는다.
_CHAPTER_RE = re.compile(r'제\s*(\d+)\s*장')
_SECTION_RE = re.compile(r'제\s*(\d+)\s*절')


def _slugify(text: str) -> str:
    """제목을 노드 ID의 일부로 쓸 수 있도록 공백을 _로 바꾸고 40자로 자른다."""
    return re.sub(r'\s+', '_', text.strip())[:40]


def _extract_paragraph_id(line: str) -> str | None:
    """한 줄에서 문단 번호를 추출한다.

    "- 6.4 금융자산이나..." → "6.4"
    "- 실6.1 ..."          → "실6.1"
    숫자.숫자 패턴이 없는 줄(⑴, ⑵ 등 하위 항목)은 None을 반환한다.
    """
    content = re.sub(r'^-\s+', '', line).strip()  # 앞의 "- " 제거
    tokens = content.split()
    first_token = tokens[0] if tokens else ''
    # _MARKER_RE: "6.4", "실6.1", "6.4의2" 같은 문단 마커 패턴
    if _MARKER_RE.match(first_token) and re.search(r'\d+\.\d+', first_token):
        return first_token
    return None


def parse_markdown(
    text: str,
    standard_id: str,    # 그래프에서 쓸 고유 ID. 예: "gaap-ch6"
    standard_type: str,  # "GAAP" 또는 "KIFRS"
    effective_date: str = "",
) -> OntologyGraph:
    """마크다운 텍스트를 파싱해 OntologyGraph를 반환한다.

    반환된 그래프에는 CONTAINS 엣지만 들어 있다.
    REFERENCES/EXCLUDES/HAS_CONDITION 엣지는 builder.py에서 LLM을 통해 추가된다.
    """
    graph = OntologyGraph()

    # Standard 노드를 먼저 만들어 둔다.
    # chapter는 마크다운 헤딩을 파싱하면서 자동으로 채워진다.
    standard = OntologyNode(
        id=standard_id,
        node_type="Standard",
        standard_type=standard_type,
        effective_date=effective_date,
    )
    graph.nodes.append(standard)

    current_section: OntologyNode | None = None      # 현재 처리 중인 Section
    current_subsection: OntologyNode | None = None   # 현재 처리 중인 Subsection
    section_order = 0
    subsection_order = 0
    content_lines: list[str] = []  # 현재 Subsection의 내용을 줄 단위로 모아둠

    def flush_subsection() -> None:
        """쌓아둔 content_lines를 current_subsection에 저장하고 그래프에 추가한다.

        새 헤딩이 나올 때마다 이전 Subsection을 마무리하기 위해 호출된다.
        """
        nonlocal current_subsection, content_lines
        if current_subsection is None:
            return
        current_subsection.content = '\n'.join(content_lines).strip()
        graph.nodes.append(current_subsection)
        # 부모가 Section이면 Section에, 없으면 Standard에 CONTAINS 엣지 연결
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

        # ## 로 시작하지 않으면 현재 Subsection의 내용 줄이다.
        if not stripped.startswith('## '):
            if current_subsection is not None:
                content_lines.append(line)
                # 문단 번호가 있으면 paragraphs에 기록해 둔다 (나중에 참조 해소에 활용).
                para_id = _extract_paragraph_id(stripped)
                if para_id and para_id not in current_subsection.paragraphs:
                    current_subsection.paragraphs.append(para_id)
            continue

        heading = stripped[3:].strip()  # "## " 이후 텍스트
        chapter_match = _CHAPTER_RE.search(heading)
        section_match = _SECTION_RE.search(heading)

        if chapter_match:
            # "## 제 6 장 금융자산·금융부채" → Standard의 이름과 장 번호 확정
            standard.name = heading
            standard.chapter = chapter_match.group(1)  # "6"
            continue

        if section_match:
            # "## 제 1 절 공통사항" → 새 Section 시작
            flush_subsection()           # 이전 Subsection 마무리
            current_subsection = None
            section_order += 1
            subsection_order = 0         # Section이 바뀌면 Subsection 순서 리셋
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

        # 위 두 패턴에 해당하지 않는 ## 헤딩 → Subsection 시작
        flush_subsection()  # 이전 Subsection 마무리
        subsection_order += 1
        parent_id = current_section.id if current_section else standard_id
        # ID 예: "gaap-ch6-s1-금융상품의_최초인식"
        sub_id = f"{parent_id}-{_slugify(heading)}"
        current_subsection = OntologyNode(
            id=sub_id,
            node_type="Subsection",
            title=heading,
            order=subsection_order,
        )
        # content_lines는 다음 헤딩이 나올 때까지 계속 누적된다.

    # 파일 끝에 도달하면 마지막 Subsection을 마무리한다.
    flush_subsection()
    return graph
