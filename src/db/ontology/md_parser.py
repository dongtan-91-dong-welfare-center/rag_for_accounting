import re
from src.db.ontology.models import OntologyGraph, OntologyNode, OntologyEdge

_CHAPTER_RE = re.compile(r'제\s*(\d+)\s*장')
_SECTION_RE = re.compile(r'제\s*(\d+)\s*절')
# (?:...) 비캡처 그룹: group(0)(전체 매칭)만 쓰므로 캡처 그룹이 필요 없다.
# [A-Z]\d+ : 부록 문단 형식 (예: 6.A13, 6.A1의2). 일반 숫자 패턴(\d+)보다 먼저 시도한다.
_PARA_RE = re.compile(r'^(?:실|결)?(?:\d+\.(?:[A-Z]\d+|\d+)(?:의\d+)?)|^사례\s*\d+')
# H3·H4 헤딩 및 본문 줄 끝의 참조 어노테이션. 예: "기타 (문단 6.28)", "...이다. (문단 10.8∼10.9)"
_PARA_ANNOT_RE = re.compile(r'\(문단\s*([^)]+)\)\s*$')


def _expand_range(start: str, end: str) -> list[str]:
    # 끝 정수 suffix를 기준으로 범위 확장. "실6.66~6.67"처럼 prefix가 달라도 start prefix로 생성한다.
    m_s = re.search(r'(\d+)$', start)
    m_e = re.search(r'(\d+)$', end)
    if m_s and m_e:
        n_s, n_e = int(m_s.group(1)), int(m_e.group(1))
        if n_e > n_s:
            prefix = start[:m_s.start()]
            return [f"{prefix}{i}" for i in range(n_s, n_e + 1)]
    return [start, end]


def _split_annot_refs(ref_text: str) -> list[str]:
    # "(문단 ...)" 내부의 범위 표기(∼~)를 확장해 개별 참조 목록으로 반환한다.
    parts = re.split(r'[∼~]', ref_text.strip())
    if len(parts) == 2:
        return _expand_range(parts[0].strip(), parts[1].strip())
    return [ref_text.strip()]


def _slugify(text: str) -> str:
    # 절·소절 제목을 노드 ID의 일부로 만들기 위해 공백을 _로 치환하고 40자로 자른다.
    # 예: "최초 인식" → "gaap-ch6-s1-최초_인식"
    return re.sub(r'\s+', '_', text.strip())[:40]


def _extract_para_id(heading_text: str) -> str | None:
    # H4+ 헤딩에서 문단 번호를 추출해 Subsection.paragraphs에 쌓기 위한 함수.
    # 헤딩 전체를 매칭해 번호 패턴(예: "6.4", "6.4의2", "실6.1", "사례 6.", "사례20")이면 반환, 아니면 None.
    # "사례 6" → "사례6" 으로 공백을 제거해 정규화한다.
    text = heading_text.strip()
    if not text:
        return None
    m = _PARA_RE.match(text)
    return m.group(0).replace(' ', '') if m else None


def parse_markdown(
    text: str,
    standard_id: str,
    standard_type: str,
) -> OntologyGraph:
    """마크다운 텍스트를 파싱해 OntologyGraph를 반환한다.

    헤딩 레벨 매핑:
      #   (H1) 제N장 → Standard 이름·chapter 확정. 재등장 시 섹션 컨텍스트 초기화.
      ##  (H2) 제N절 → Section 노드. 절 번호 없는 헤딩(예: 용어의 정의)도 Section으로 처리.
                       같은 절이 재등장하면(부록A 등) 기존 노드를 재사용해 내용을 이어붙인다.
      ### (H3)       → Subsection 노드 (content/paragraphs 둘 다 비면 skip)
      #### + (H4+)   → 문단 번호 또는 하위 항목 → 현재 노드의 content에 누적

    반환된 그래프에는 CONTAINS 엣지만 들어 있다.
    REFERENCES/EXCLUDES/HAS_CONDITION 엣지는 builder.py에서 LLM을 통해 추가된다.
    """
    graph = OntologyGraph()
    standard = OntologyNode(
        id=standard_id,
        node_type="Standard",
        standard_type=standard_type,
    )
    graph.nodes.append(standard)

    current_section: OntologyNode | None = None
    current_subsection: OntologyNode | None = None
    section_order = 0
    subsection_order = 0
    content_lines: list[str] = []
    section_content_lines: list[str] = []
    subsection_occurrence: dict[str, int] = {}  # base_id → 등장 횟수. 재등장 시 suffix(-2, -3)로 id 구분.
    heading_ref_targets: list[str] = []  # 현재 H3 헤딩 어노테이션에서 추출한 참조 원문
    heading_ref_source: str = ""         # 어노테이션이 포함된 원래 H3 헤딩 텍스트 (source_text 용)
    current_para_id: str = ""            # H4에서 추출된 현재 문단 번호. 본문 어노테이션 엣지의 paragraph 필드에 사용.

    def flush_subsection() -> None:
        # 새 H2·H3 헤딩이 등장할 때마다 호출된다.
        # 루프를 돌면서 content_lines에 쌓아둔 줄들을 current_subsection.content로 확정하고
        # graph에 노드·엣지를 추가한 뒤, 두 변수를 초기화해 다음 소절을 받을 준비를 한다.
        # content도 paragraphs도 없는 빈 소절은 graph에 추가하지 않고 버린다.
        nonlocal current_subsection, current_para_id  # = None/'' 재할당이 바깥 변수에 반영되려면 nonlocal 필요
        if current_subsection is None:              # H3 없이 H2가 연속으로 나오는 경우 등 flush할 소절이 없을 때 가드
            return
        content = '\n'.join(content_lines).strip()
        if content or current_subsection.paragraphs:
            current_subsection.content = content
            graph.nodes.append(current_subsection)
            parent_id = current_section.id if current_section else standard_id
            graph.edges.append(OntologyEdge(
                from_id=parent_id,
                to_id=current_subsection.id,
                edge_type="CONTAINS",
                order=current_subsection.order,
            ))
            # H3 헤딩 어노테이션에서 추출한 참조를 REFERENCES 엣지로 추가
            for ref in heading_ref_targets:
                graph.edges.append(OntologyEdge(
                    from_id=current_subsection.id,
                    to_id="",
                    edge_type="REFERENCES",
                    source_text=heading_ref_source,
                    unresolved_target=ref,
                ))
        current_subsection = None
        current_para_id = ""
        content_lines.clear()
        heading_ref_targets.clear()

    def flush_section_content() -> None:
        # 새 H2 헤딩 등장 시 또는 파일 끝에서 호출된다.
        # section_content_lines에 쌓인 줄들을 current_section.content로 확정한다.
        # Section 노드는 H2에서 이미 graph에 추가되므로 flush에서 graph 조작은 없다.
        # current_section이 없거나 section_content_lines가 비어 있으면(Section 직속 내용 없음) 조건이 False가 되어 content 할당을 건너뛴다.
        if current_section and section_content_lines:
            current_section.content = '\n'.join(section_content_lines).strip()
        section_content_lines.clear()

    for line in text.split('\n'):
        stripped = line.strip()

        # H1: Standard (# 제N장)
        if stripped.startswith('# ') and not stripped.startswith('## '):
            heading = stripped[2:].strip()
            m = _CHAPTER_RE.search(heading)
            if m:
                # 부록 등에서 장 헤딩이 재등장하면 섹션 컨텍스트를 초기화해 이후 내용이 Standard 직속으로 붙는다.
                flush_subsection()
                flush_section_content()
                current_section = None
                subsection_order = 0
                standard.name = heading
                standard.chapter = m.group(1)
                continue
            # 장 제목이 아닌 # 라인(예: # 검토)은 아래 일반 텍스트 처리로 내려감

        # H2: Section (## 제N절, 또는 절 번호 없는 헤딩)
        if stripped.startswith('## ') and not stripped.startswith('### '):
            heading = stripped[3:].strip()
            m = _SECTION_RE.search(heading)
            flush_subsection()
            flush_section_content()
            # 절 번호가 없는 헤딩(예: 용어의 정의)은 제목을 slugify해 id를 만든다.
            sec_id = f"{standard_id}-s{m.group(1)}" if m else f"{standard_id}-{_slugify(heading)}"
            # 같은 id가 이미 있으면(부록 등에서 절이 재등장) 기존 노드를 재사용해 내용을 이어붙인다.
            existing = next((n for n in graph.nodes if n.id == sec_id), None)
            if existing:
                current_section = existing
                # 기존 섹션의 subsection 수에서 이어받아 order가 겹치지 않도록 한다.
                subsection_order = sum(1 for e in graph.edges if e.from_id == sec_id and e.edge_type == "CONTAINS")
            else:
                section_order += 1
                subsection_order = 0
                current_section = OntologyNode(
                    id=sec_id, node_type="Section",
                    title=heading, order=section_order,
                )
                graph.nodes.append(current_section)
                graph.edges.append(OntologyEdge(
                    from_id=standard_id, to_id=sec_id,
                    edge_type="CONTAINS", order=section_order,
                ))
            continue

        # H3: Subsection (###)
        if stripped.startswith('### ') and not stripped.startswith('#### '):
            flush_subsection()
            heading = stripped[4:].strip()
            # 헤딩 끝의 "(문단 X.X)" 어노테이션 추출 → 깨끗한 ID 생성 + REFERENCES 엣지 예약
            m_annot = _PARA_ANNOT_RE.search(heading)
            if m_annot:
                heading_ref_source = heading
                for r in _split_annot_refs(m_annot.group(1)):
                    heading_ref_targets.append(f"문단 {r}")
                heading = heading[:m_annot.start()].strip()
            else:
                heading_ref_source = ""
            parent_id = current_section.id if current_section else standard_id
            base_id = f"{parent_id}-{_slugify(heading)}"
            # 부록 등에서 동일 제목의 Subsection이 재등장할 수 있다.
            # Subsection은 임베딩 단위이므로 Section처럼 내용을 병합하면 길이가 과도해진다.
            # 대신 별도 노드로 생성하고 id에 -2, -3 suffix를 붙여 충돌을 방지한다.
            count = subsection_occurrence.get(base_id, 0)
            subsection_occurrence[base_id] = count + 1
            sub_id = base_id if count == 0 else f"{base_id}-{count + 1}"
            subsection_order += 1
            current_subsection = OntologyNode(
                id=sub_id,
                node_type="Subsection",
                title=heading,
                order=subsection_order,
            )
            continue

        # H4+: 문단 번호 헤딩 또는 하위 항목
        if stripped.startswith('####'):
            heading_text = re.sub(r'^#{4,6}\s*', '', stripped)
            para_id = _extract_para_id(heading_text)
            if para_id:
                current_para_id = para_id
            # 헤딩 끝의 "(문단 X.X)" 어노테이션 추출 → 즉시 REFERENCES 엣지 생성
            m_annot = _PARA_ANNOT_RE.search(heading_text)
            if m_annot:
                # Subsection이 살아있으면 우선 사용, 없으면 Section으로 fallback (or 단락 평가)
                from_node = current_subsection or current_section
                if from_node:
                    for r in _split_annot_refs(m_annot.group(1)):
                        graph.edges.append(OntologyEdge(
                            from_id=from_node.id,
                            to_id="",
                            edge_type="REFERENCES",
                            source_text=heading_text,
                            unresolved_target=f"문단 {r}",
                            paragraph=para_id or "",
                        ))
                line = re.sub(r'\s*\(문단\s*[^)]+\)', '', line)
            if current_subsection is not None:
                content_lines.append(line)
                if para_id and para_id not in current_subsection.paragraphs:
                    current_subsection.paragraphs.append(para_id)
            elif current_section is not None:
                # Section 직속 문단: ### 없이 ## 바로 아래에 등장한 경우
                section_content_lines.append(line)
                if para_id and para_id not in current_section.paragraphs:
                    current_section.paragraphs.append(para_id)
            continue

        # 일반 텍스트 (본문, 주석, 표, 페이지 마커 등)
        if current_subsection is not None:
            m_annot = _PARA_ANNOT_RE.search(stripped)
            if m_annot:
                for r in _split_annot_refs(m_annot.group(1)):
                    graph.edges.append(OntologyEdge(
                        from_id=current_subsection.id,
                        to_id="",
                        edge_type="REFERENCES",
                        source_text=stripped,
                        unresolved_target=f"문단 {r}",
                        paragraph=current_para_id,
                    ))
                line = re.sub(r'\s*\(문단\s*[^)]+\)', '', line)
            content_lines.append(line)
        elif current_section is not None:
            m_annot = _PARA_ANNOT_RE.search(stripped)
            if m_annot:
                for r in _split_annot_refs(m_annot.group(1)):
                    graph.edges.append(OntologyEdge(
                        from_id=current_section.id,
                        to_id="",
                        edge_type="REFERENCES",
                        source_text=stripped,
                        unresolved_target=f"문단 {r}",
                    ))
                line = re.sub(r'\s*\(문단\s*[^)]+\)', '', line)
            section_content_lines.append(line)

    flush_subsection()
    flush_section_content()
    return graph
