"""LLM이 반환한 원문 참조 텍스트를 실제 노드 ID로 변환한다.

LLM은 "제2절", "문단 6.4" 같은 원문 텍스트를 target_ref로 반환한다.
이 모듈은 그 텍스트를 그래프 안의 노드 ID로 매핑한다.

변환 실패 시 엣지의 to_id는 빈 문자열로 남고, unresolved_target에 원문이 유지된다.
"""

import re
from src.db.ontology.models import OntologyGraph

_CHAPTER_RE = re.compile(r'제\s*(\d+)\s*장')
_SECTION_RE = re.compile(r'제\s*(\d+)\s*절')
_PARA_RE = re.compile(r'((?:실|결)?\d+\.(?:[A-Z]\d+|\d+)(?:의\d+)?)')  # "6.4", "6.4의2", "실6.142", "6.A13" 등
_RANGE_SEP_RE = re.compile(r'\s*[~∼]\s*')  # 범위 표기 구분자


def _para_prefix(p: str) -> str:
    """paragraph 번호의 종류 prefix를 반환. 본문은 빈 문자열, 실무지침은 '실', 결론도출근거는 '결', 사례는 '사례'."""
    if p.startswith('사례'):
        return '사례'
    if p.startswith('실'):
        return '실'
    if p.startswith('결'):
        return '결'
    return ''


def _expand_range_target(target: str, paragraphs_in_order: list[str]) -> list[str] | None:
    """범위 표기 unresolved_target을 그래프의 paragraphs에 맞춰 개별 paragraph 번호 목록으로 확장.

    예: "문단 6.8의2~6.11" → ["6.8의2", "6.9", "6.10", "6.11"] 같은 종류(본문/실무지침/결론/사례) 안에서만 확장한다. 
    시작·끝의 prefix가 다르거나 그래프에서 찾을 수 없으면 None 반환
    None 반환 시 resolver는 unresolved_target을 원문 그대로 유지해 수동 확인이 가능하게 한다.
    """
    cleaned = re.sub(r'^문단\s*', '', target.strip())
    parts = _RANGE_SEP_RE.split(cleaned)
    if len(parts) != 2:
        return None
    start = parts[0].strip()
    end = parts[1].strip()
    if start not in paragraphs_in_order or end not in paragraphs_in_order:
        return None
    prefix = _para_prefix(start)
    if _para_prefix(end) != prefix:
        return None
    i_start = paragraphs_in_order.index(start)
    i_end = paragraphs_in_order.index(end)
    if i_end < i_start:
        return None
    # 범위 안에서 같은 prefix만 필터링 (등장 순서가 paragraph 번호 순서와 어긋나는 경우 방어).
    return [p for p in paragraphs_in_order[i_start:i_end + 1] if _para_prefix(p) == prefix]


def build_lookup(graph: OntologyGraph) -> dict[str, str]:
    """그래프의 노드들로부터 '참조 텍스트 → 노드 ID' 매핑 테이블을 만든다.

    - Section: "제2절", "제 2 절" 등 공백 변형을 모두 등록한다.
    - Subsection: paragraphs에 있는 번호를 "6.4", "문단6.4", "문단 6.4" 형태로 등록한다.
    """
    lookup: dict[str, str] = {}

    for node in graph.nodes:
        if node.node_type == "Standard":
            m = _CHAPTER_RE.search(node.name)
            if m:
                # 시도 1에서 ref.replace(' ', '')로 공백을 제거한 채 조회하므로
                # 공백 제거 버전 하나만 등록하면 "제 6 장" 등 모든 표기를 커버한다.
                lookup[f'제{m.group(1)}장'] = node.id

        if node.node_type == "Section":
            m = _SECTION_RE.search(node.title)
            if m:
                # m.group(0) : 패턴 전체가 매칭된 문자열 → "제 1 절"
                # m.group(1) : 첫 번째 괄호 (\d+)에 매칭된 문자열 → "1"
                lookup[f'제{m.group(1)}절'] = node.id

        if node.node_type == "Subsection":
            paragraph_keys = list(node.paragraphs)
            # 컨테이너 H3(실무지침/결론도출근거/적용사례) 수동 제거로 H4가 H3로 승격된 경우,
            # Subsection 자체가 paragraph(예: "결2.1", "실2.1", "2.32")이므로 title도 등록한다.
            title = node.title.strip()
            if _PARA_RE.match(title):
                paragraph_keys.append(title)
            for para in paragraph_keys:
                norm = para.replace(' ', '')    # 공백 제거 정규화
                # 시도 1에서 ref.replace(' ', '')로 조회하므로 공백 제거 버전 하나로 모든 표기 커버
                lookup[norm] = node.id          # 예: "6.4"
                lookup[f'문단{norm}'] = node.id # 예: "문단6.4" → "문단 6.4"도 커버

    return lookup


def resolve_edges(graph: OntologyGraph) -> OntologyGraph:
    """그래프의 모든 엣지에서 unresolved_target을 노드 ID로 변환한다.

    변환 순서:
      0. 범위 표기(X~Y) 감지 시 그래프 paragraphs로 확장해 여러 엣지로 split.
         확장 실패하면 원문 그대로 유지 (수동 확인용)
      1. 전체 문자열 공백 제거 후 직접 룩업
      2. 실패 시 문단 번호(X.X) 패턴만 추출해서 재시도 (장+문단 혼합 시 문단 우선)
      3. 실패 시 절 번호(제N절) 패턴만 추출해서 재시도
      4. 실패 시 장 번호(제N장) 패턴만 추출해서 재시도 (최후 수단)
    """
    lookup = build_lookup(graph)
    # to_paragraph는 Subsection으로 해소된 경우에만 설정한다.
    # 해소된 노드의 node_type을 확인하기 위한 매핑.
    node_type_map = {node.id: node.node_type for node in graph.nodes}
    # 그래프의 모든 paragraphs를 등장 순서대로 수집 (범위 확장에 사용)
    paragraphs_in_order: list[str] = []
    for node in graph.nodes:
        for p in node.paragraphs:
            if p not in paragraphs_in_order:
                paragraphs_in_order.append(p)
    resolved = []

    for edge in graph.edges:
        # to_id가 이미 있거나 unresolved_target이 없으면 건드리지 않는다.
        if edge.to_id or not edge.unresolved_target:
            resolved.append(edge)
            continue

        ref = edge.unresolved_target

        # 시도 0: 범위 표기 감지 → 여러 엣지로 split.
        # 확장 실패 시 원문 그대로 유지하고 일반 처리 분기로 떨어지지 않게 한다
        # (시작값만 매핑되는 부분 매핑 노이즈 방지).
        if '~' in ref or '∼' in ref:
            expanded = _expand_range_target(ref, paragraphs_in_order)
            if expanded:
                for p in expanded:
                    target_id = lookup.get(p)
                    if target_id:
                        resolved.append(edge.model_copy(update={
                            "to_id": target_id,
                            "unresolved_target": "",
                            "to_paragraph": p,
                        }))
                    else:
                        # 그래프엔 있지만 lookup 키로는 못 찾는 드문 경우 — 원문 유지
                        resolved.append(edge.model_copy(update={
                            "unresolved_target": f"문단 {p}",
                        }))
            else:
                # 범위 확장 실패: 원문 그대로 둬서 사용자가 확인할 수 있게 한다.
                resolved.append(edge)
            continue

        # 시도 1: 공백을 제거한 전체 문자열로 직접 룩업
        norm = ref.replace(' ', '')
        target_id = lookup.get(norm)

        # 시도 1.5: "문단 XXXX" → "XXXX" 직접 룩업 ("문단 6.A13" → 공백 제거 후 "문단6.A13" → "6.A13")
        if not target_id and norm.startswith('문단'):
            target_id = lookup.get(norm[2:])

        # 시도 2: 문단 번호 패턴("X.X")만 뽑아서 재시도 (장+문단이 함께 올 때 문단 우선)
        if not target_id:
            m = _PARA_RE.search(norm)
            if m:
                target_id = lookup.get(m.group(1))

        # 시도 3: 절 번호 패턴("제N절")만 뽑아서 재시도
        if not target_id:
            m = _SECTION_RE.search(norm)
            if m:
                target_id = lookup.get(f'제{m.group(1)}절')

        # 시도 4: 장 번호 패턴("제N장")만 뽑아서 재시도 (문단·절 없을 때 최후 수단)
        if not target_id:
            m = _CHAPTER_RE.search(norm)
            if m:
                target_id = lookup.get(f'제{m.group(1)}장')

        if target_id:
            # 성공: to_id 채우고 unresolved_target 비우기.
            # to_paragraph는 Subsection으로 해소됐을 때만 norm에서 문단 번호를 추출해 저장한다.
            # 절·장으로 해소된 경우, norm에 문단 패턴("6.4")이 섞여 있어도
            # (예: "제2절 문단 6.4") 그 Section/Standard에 해당 문단이 없을 수 있으므로 빈 문자열로 남긴다.
            m = _PARA_RE.search(norm)
            to_para = m.group(1) if (m and node_type_map.get(target_id) == "Subsection") else ""
            resolved.append(edge.model_copy(update={
                "to_id": target_id,
                "unresolved_target": "",
                "to_paragraph": to_para,
            }))
        else:
            resolved.append(edge)

    # to_id가 확정된 후 from_id == to_id인 자기참조 엣지를 제거한다.
    # 같은 노드 내 문단 간 참조는 content에 이미 포함되어 있어 검색·생성 단계에서 노이즈가 된다.
    graph.edges = [e for e in resolved if not e.to_id or e.from_id != e.to_id]
    return graph
