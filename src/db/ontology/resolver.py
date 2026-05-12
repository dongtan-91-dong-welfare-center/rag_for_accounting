"""LLM이 반환한 원문 참조 텍스트를 실제 노드 ID로 변환한다.

LLM은 "제2절", "문단 6.4" 같은 원문 텍스트를 target_ref로 반환한다.
이 모듈은 그 텍스트를 그래프 안의 노드 ID로 매핑한다.

변환 실패 시:
  - 엣지의 to_id는 빈 문자열로 남는다.
  - 출발 노드의 unresolved_refs에 원문이 기록된다.
  - 전체 인제스트 완료 후 일괄 재처리를 상정한 구조다.
"""

import re
from src.db.ontology.models import OntologyGraph

_CHAPTER_RE = re.compile(r'제\s*(\d+)\s*장')
_SECTION_RE = re.compile(r'제\s*(\d+)\s*절')
_PARA_RE = re.compile(r'((?:실|결)?\d+\.(?:[A-Z]\d+|\d+)(?:의\d+)?)')  # "6.4", "6.4의2", "실6.142", "6.A13" 등


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
            for para in node.paragraphs:
                norm = para.replace(' ', '')    # 공백 제거 정규화
                # 시도 1에서 ref.replace(' ', '')로 조회하므로 공백 제거 버전 하나로 모든 표기 커버
                lookup[norm] = node.id          # 예: "6.4"
                lookup[f'문단{norm}'] = node.id # 예: "문단6.4" → "문단 6.4"도 커버

    return lookup


def resolve_edges(graph: OntologyGraph) -> OntologyGraph:
    """그래프의 모든 엣지에서 unresolved_target을 노드 ID로 변환한다.

    변환 순서:
      1. 전체 문자열 공백 제거 후 직접 룩업
      2. 실패 시 문단 번호(X.X) 패턴만 추출해서 재시도 (장+문단 혼합 시 문단 우선)
      3. 실패 시 절 번호(제N절) 패턴만 추출해서 재시도
      4. 실패 시 장 번호(제N장) 패턴만 추출해서 재시도 (최후 수단)
      5. 최종 실패 시 출발 노드의 unresolved_refs에 원문 기록
    """
    lookup = build_lookup(graph)
    # node_map: "노드 ID → 노드 객체" 딕셔너리. unresolved_refs를 기록할 때 사용한다.
    # {n.id: n for n in graph.nodes} 에서 n은 graph.nodes 리스트의 원소를 순서대로 가리킨다.
    # Python 리스트 원소는 객체의 참조(주소)이므로 n을 값으로 저장하면 복사가 아닌
    # 원본 객체를 그대로 가리킨다.
    # 따라서 node_map.get(id)로 꺼낸 src를 수정하면 graph.nodes 안의 원본 노드가 바뀐다.
    node_map = {n.id: n for n in graph.nodes}
    resolved = []

    for edge in graph.edges:
        # to_id가 이미 있거나 unresolved_target이 없으면 건드리지 않는다.
        if edge.to_id or not edge.unresolved_target:
            resolved.append(edge)
            continue

        ref = edge.unresolved_target

        # 시도 1: 공백을 제거한 전체 문자열로 직접 룩업
        norm = ref.replace(' ', '')
        target_id = lookup.get(norm)

        # 시도 1.5: "문단 XXXX" → "XXXX" 직접 룩업 ("문단 6.A13" → 공백 제거 후 "문단6.A13" → "6.A13")
        if not target_id and norm.startswith('문단'):
            target_id = lookup.get(norm[2:])

        # 시도 2: 문단 번호 패턴("X.X")만 뽑아서 재시도 (장+문단이 함께 올 때 문단 우선)
        if not target_id:
            m = _PARA_RE.search(ref)
            if m:
                target_id = lookup.get(m.group(1).replace(' ', ''))

        # 시도 3: 절 번호 패턴("제N절")만 뽑아서 재시도
        if not target_id:
            m = _SECTION_RE.search(ref)
            if m:
                target_id = lookup.get(f'제{m.group(1)}절')  # 공백 제거 버전으로 등록되어 있음

        # 시도 4: 장 번호 패턴("제N장")만 뽑아서 재시도 (문단·절 없을 때 최후 수단)
        if not target_id:
            m = _CHAPTER_RE.search(ref)
            if m:
                target_id = lookup.get(f'제{m.group(1)}장')  # 공백 제거 버전으로 등록되어 있음

        if target_id:
            # 성공: to_id 채우고 unresolved_target 비우기.
            # ref에서 문단 번호를 추출해 to_paragraph에 저장한다.
            # 절·장으로만 해소된 경우 _PARA_RE가 매칭되지 않으므로 to_paragraph는 빈 문자열이 된다.
            m = _PARA_RE.search(ref)
            to_para = m.group(1).replace(' ', '') if m else ""
            resolved.append(edge.model_copy(update={
                "to_id": target_id,
                "unresolved_target": "",
                "to_paragraph": to_para,
            }))
        else:
            # 실패: 엣지는 그대로 두고, 출발 노드에 미해소 참조 기록
            resolved.append(edge)
            src = node_map.get(edge.from_id)
            if src and ref not in src.unresolved_refs:
                src.unresolved_refs.append(ref)

    graph.edges = resolved
    return graph
