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
_PARA_CORE = r'\d+\.(?:[A-Z]\d+|\d+)(?:의\d+)?'  # 접두어를 뺀 문단 번호 본체. 예: "6.4", "6.A13"
# 범위 표기 한 방에 매칭. 구분자: ~ ∼ 내지 에서 부터. 양 끝의 실/결 접두어를 각각 캡처한다.
# "문단" 토큰과 끝의 "까지"는 선택적으로 흡수한다.
# 예: "문단 22.37 내지 문단 22.44", "실12.9~실12.13", "실6.66~6.67", "6.87에서 6.89까지"
_RANGE_FULL_RE = re.compile(
    r'(실|결)?(' + _PARA_CORE + r')'
    r'\s*(?:[~∼]|내지|에서|부터)\s*'
    r'(?:문단\s*)?(실|결)?(' + _PARA_CORE + r')'
    r'(?:\s*까지)?'
)


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

    예: "문단 6.8의2~6.11" → ["6.8의2", "6.9", "6.10", "6.11"]
        "실12.9~실12.13"   → ["실12.9", ..., "실12.13"]
        "실6.66~6.67"      → ["실6.66", "실6.67"]  (끝 번호에 빠진 접두어를 시작에서 물려받음)
    같은 종류(본문/실무지침/결론/사례) 안에서만 확장한다. 양 끝 접두어가 서로 다르거나(실 vs 결)
    그래프에서 찾을 수 없으면 None 반환. None 반환 시 resolver는 unresolved_target을
    원문 그대로 유지해 수동 확인이 가능하게 한다.
    """
    m = _RANGE_FULL_RE.search(target)
    if not m:
        return None
    return _expand_match(m, paragraphs_in_order)


def _expand_match(m: re.Match, paragraphs_in_order: list[str]) -> list[str] | None:
    """_RANGE_FULL_RE 매치 하나를 그래프 paragraphs에 맞춰 개별 번호 목록으로 확장한다."""
    p1, n1, p2, n2 = m.group(1), m.group(2), m.group(3), m.group(4)
    # 한쪽만 접두어가 있으면 다른 쪽에 물려준다. 둘 다 있는데 다르면(실 vs 결) 확장 불가.
    if p1 and p2 and p1 != p2:
        return None
    prefix = p1 or p2 or ''
    start = prefix + n1
    end = prefix + n2
    if start not in paragraphs_in_order or end not in paragraphs_in_order:
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
            # Section 직속 문단(H3 없이 H2 바로 아래 둔 문단, 예: 3.16, 4.8)도 등록한다.
            # 이를 빠뜨리면 "문단 3.16" 같은 같은 장 참조가 해소되지 못한다.
            # 문단 번호는 장 안에서 유일하므로 Subsection 등록과 충돌하지 않으나,
            # 혹시 모를 충돌 시 기존(Subsection) 매핑을 보존하도록 setdefault를 쓴다.
            for para in node.paragraphs:
                norm = para.replace(' ', '')
                lookup.setdefault(norm, node.id)
                lookup.setdefault(f'문단{norm}', node.id)

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
    # 그래프의 모든 paragraphs를 등장 순서대로 수집 (범위 확장에 사용)
    paragraphs_in_order: list[str] = []
    for node in graph.nodes:
        for p in node.paragraphs:
            if p not in paragraphs_in_order:
                paragraphs_in_order.append(p)
    # 타 장(Standard) 참조용 결정적 id prefix. 현재 장 Standard id(예: "gaap-ch6")에서
    # 끝 숫자를 떼어 "gaap-ch"를 얻는다. "제N장"은 노드가 없어도 f"{prefix}{N}"으로 연결한다.
    chapter_id_prefix = ""
    for node in graph.nodes:
        if node.node_type == "Standard":
            chapter_id_prefix = re.sub(r'\d+$', '', node.id)
            break
    resolved = []

    for edge in graph.edges:
        # to_id가 이미 있거나 unresolved_target이 없으면 건드리지 않는다.
        if edge.to_id or not edge.unresolved_target:
            resolved.append(edge)
            continue

        ref = edge.unresolved_target

        # 시도 0: 범위 표기 감지 → 여러 엣지로 split. (~ ∼ 내지 에서~까지 부터~까지, 실/결 접두어 포함)
        # 확장 실패 시 원문 그대로 유지하고 일반 처리 분기로 떨어지지 않게 한다
        # (시작값만 매핑되는 부분 매핑 노이즈 방지).
        if _RANGE_FULL_RE.search(ref):
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
                # "28.5의1년규정"처럼 '의N'이 하위문단(예: 6.4의2)이 아니라 설명어인 경우,
                # '의N'을 떼고 본문단 번호("28.5")로 재시도한다.
                if not target_id and '의' in m.group(1):
                    target_id = lookup.get(m.group(1).split('의')[0])

        # 시도 3: 절 번호 패턴("제N절")만 뽑아서 재시도
        if not target_id:
            m = _SECTION_RE.search(norm)
            if m:
                target_id = lookup.get(f'제{m.group(1)}절')

        # 시도 4: 장 번호 패턴("제N장")만 뽑아서 재시도 (문단·절 없을 때 최후 수단)
        # 같은 장이면 lookup에서, 타 장이면 결정적 id(prefix+N)로 연결한다.
        # 타 장 Standard 노드는 현재 그래프에 없지만, 전 장을 합친 그래프에서 유효한 링크다.
        cross_chapter = False
        if not target_id:
            m = _CHAPTER_RE.search(norm)
            if m:
                target_id = lookup.get(f'제{m.group(1)}장')
                if not target_id and chapter_id_prefix:
                    target_id = f'{chapter_id_prefix}{m.group(1)}'
                    cross_chapter = True

        if target_id:
            # 성공: to_id 채우고 unresolved_target 비우기.
            # to_paragraph는 추출한 문단 번호가 실제로 해소된 노드에 속하는 경우에만 남긴다
            # (lookup 검증 — "제2절 문단 9.9"가 절로 폴백 해소될 때 검증 안 된 9.9를 남기지 않는다, #69).
            # 타 장 참조는 현재 장 그래프로 소속 검증이 불가능하므로 원문의 문단 번호를 그대로
            # 보존한다 (전 장 병합 그래프 내비게이션·review_auditor의 target_unjustified 판정에 사용).
            m = _PARA_RE.search(norm)
            to_para = m.group(1) if m else ""
            # 추출된 번호가 실제 문단이 아니고(룩업에 없음) '의N' 설명어가 붙은 경우 본문단 번호로 보정
            if to_para and to_para not in lookup and '의' in to_para:
                to_para = to_para.split('의')[0]
            if to_para and not cross_chapter and lookup.get(to_para) != target_id:
                to_para = ""
            resolved.append(edge.model_copy(update={
                "to_id": target_id,
                "unresolved_target": "",
                "to_paragraph": to_para,
            }))
        else:
            resolved.append(edge)

    # source_text 기반 범위 완성: LLM이 범위를 끝점으로 쪼개거나 접두어를 누락해도
    # 원문의 범위 표현을 직접 파싱해 누락된 구간 멤버를 결정적으로 보충한다.
    resolved.extend(_complete_ranges(resolved, lookup, paragraphs_in_order))

    # 외부 대상 없이 조건·예외만 있는 HAS_CONDITION은 "이 조항에 조건/예외가 있다"는
    # 메타데이터로 보존한다. to_id를 from_id로 채워 자기루프 엣지로 만든다
    # (빈 to_id는 그래프 DB에 삽입할 수 없으므로 자기루프로 표현).
    resolved = [
        e.model_copy(update={"to_id": e.from_id})
        if e.edge_type == "HAS_CONDITION" and not e.to_id and not e.unresolved_target
        else e
        for e in resolved
    ]

    # from_id == to_id 자기참조 제거 (같은 노드 내 참조는 content에 이미 포함돼 노이즈).
    # 단 HAS_CONDITION 자기루프는 조건/예외 존재를 나타내는 메타데이터이므로 보존한다.
    graph.edges = [
        e for e in resolved
        if not e.to_id or e.from_id != e.to_id or e.edge_type == "HAS_CONDITION"
    ]
    return graph


def _complete_ranges(resolved, lookup, paragraphs_in_order):
    """source_text의 범위 표현(키워드 고정 규칙)을 직접 파싱해 누락된 범위 멤버 엣지를 보충한다.

    같은 (from_id, source_text) 그룹에서 이미 연결된 to_paragraph를 제외한 나머지 구간 멤버를
    그래프에 존재하는 한 추가한다. 추가 엣지는 그룹의 기존 엣지를 템플릿으로 복제해
    edge_type·paragraph·source_text를 보존한다. 그래프에 없는 문단은 건너뛴다.
    """
    groups: dict[tuple[str, str], dict] = {}
    for e in resolved:
        if e.edge_type == "CONTAINS" or not e.source_text:
            continue
        g = groups.setdefault((e.from_id, e.source_text), {"covered": set(), "template": e})
        if e.to_id and e.to_paragraph:
            g["covered"].add(e.to_paragraph)

    added = []
    for (_from_id, source_text), g in groups.items():
        for m in _RANGE_FULL_RE.finditer(source_text):
            members = _expand_match(m, paragraphs_in_order)
            if not members:
                continue
            for p in members:
                if p in g["covered"]:
                    continue
                target_id = lookup.get(p)
                if not target_id:
                    continue
                g["covered"].add(p)  # 같은 그룹 내 중복 추가 방지
                added.append(g["template"].model_copy(update={
                    "to_id": target_id,
                    "to_paragraph": p,
                    "unresolved_target": "",
                }))
    return added
