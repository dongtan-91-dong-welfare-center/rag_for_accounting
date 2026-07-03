"""온톨로지 엣지 품질 감사 → 사람 검토 대기 큐(review_pending.json) 생성.

data/ontology/gaap-ch*.json 전 장을 훑어 자동으로는 옳고 그름을 판정할 수 없는 의심 엣지를 6개 카테고리로 모은다.
각 항목에 `suggested`(권장 판정+근거)를 채우고 `decision`은 비워 둔다.
사람이 검토 후 decision을 채우면 gaap json에 반영하고 항목을 삭제한다.

6 카테고리:
  prefix_dropped               실/결 접두어 손실로 본문에 잘못 연결된 의심 엣지
  target_unjustified           to_paragraph가 source_text에서 정당화 안 됨(범위·접두어 고려 후)
  type_conflict                같은 from/to/문단/source_text에 상충하는 edge_type
  exact_duplicate              같은 from/to/문단/type/source_text 중복(count>=2)
  cross_chapter_residual       제N장 없이 문단·절 번호만 적힌 미해소 참조(타 장 추론 또는 파싱누락)
  has_condition_selfloop_optional  외부 조항을 가리키는 HAS_CONDITION 자기루프(링크 승격 선택지)

CLI 사용법:
  uv run python -m src.db.ontology.review_auditor \\
      --ontology-dir data/ontology \\
      --output data/ontology/review_pending.json
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

# 문단 번호(접두어/부록/의N 포함)와 범위·절·장 표기. resolver/semcheck와 동일 규칙.
_PARA = r'(?:사례|실|결)?\d+\.(?:[A-Z]\d+|\d+)(?:의\d+)?'
PARA_RE = re.compile(_PARA)
SEC_RE = re.compile(r'제\s*(\d+)\s*절')
CHAP_RE = re.compile(r'제\s*(\d+)\s*장')
# 범위 표기(전체 확장 대상): ~∼ / 에서~까지 / 부터~까지 / 내지. (한국 법령 관례, 사용자 결정)
RANGE = [re.compile(rf'({_PARA})\s*[~∼]\s*(?:문단\s*)?({_PARA})'),
         re.compile(rf'({_PARA})\s*에서\s*(?:문단\s*)?({_PARA})\s*까지'),
         re.compile(rf'({_PARA})\s*부터\s*(?:문단\s*)?({_PARA})\s*까지'),
         re.compile(rf'({_PARA})\s*내지\s*(?:문단\s*)?({_PARA})')]
EXC_SIG = ['제외', '적용하지 아니', '적용하지 않', '적용대상이 아니', '해당하지 아니',
           '적용되지 아니', '적용되지 않', '적용하지아니', '포함하지 아니']
COND_SIG = ['경우', '한하여', '한함', '조건', '때에만', '때에 한', '에 한정']

README = {
    "purpose": "사람이 직접 판정할 미해소/의심 엣지 모음. Claude와 함께 검토 후 decision을 채운다.",
    "prefix_dropped": "실/결 접두어가 누락돼 본문으로 잘못 연결된 의심 엣지. decision 값: fix(접두어 버전으로 교정) | keep | delete",
    "target_unjustified": "to_paragraph가 source_text에서 정당화 안 됨(범위·공백 고려 후). decision: fix|delete|keep",
    "type_conflict": "같은 from/to/문단/source_text에 상충 edge_type. decision: keep:<type>|delete",
    "exact_duplicate": "같은 from/to/문단/type/source_text 중복. decision: dedup(1개만 유지)|keep",
    "cross_chapter_residual": "제N장 없이 문단번호/절번호만 적힌 타 장 참조(번호 앞자리=장) 또는 같은장 파싱누락 의심. decision: link:gaap-chN | parse_fix | keep",
    "suggested": "Claude 권장 판정+근거. decision이 비어있으면 이 값을 따를지 검토. decision에 직접 최종값 기입.",
    "has_condition_selfloop_optional": "외부 대상 없는 HAS_CONDITION 17건은 자기루프로 자동 보존됨(검토 불필요). 그중 외부 조항을 가리키는 건만 외부 링크 승격 선택지로 남김. decision: link:<대상> | keep(자기루프 유지)",
}

CATEGORIES = ['prefix_dropped', 'target_unjustified', 'type_conflict',
              'exact_duplicate', 'cross_chapter_residual', 'has_condition_selfloop_optional']


def _pref(p: str) -> str:
    for x in ('사례', '실', '결'):
        if p.startswith(x):
            return x
    return ''


def _numpart(p: str) -> str:
    return re.sub(r'^(사례|실|결)', '', p)


def _lead_chapter(p: str) -> int | None:
    m = re.match(r'^(?:사례|실|결)?(\d+)\.', p)
    return int(m.group(1)) if m else None


def _ptuple(p: str):
    """접두어 제거된 문단번호 → (major, letter, minor, sub). 범위 비교용."""
    m = re.match(r'^(\d+)\.([A-Z]?)(\d+)(?:의(\d+))?$', _numpart(p))
    if not m:
        return None
    return (int(m.group(1)), m.group(2) or '', int(m.group(3)), int(m.group(4) or 0))


def _in_range(tp: str, a: str, b: str) -> bool:
    """tp가 범위 [a,b] 내부인가 (접두어 상속 + 튜플 비교)."""
    pr = _pref(a) or _pref(b)
    if _pref(tp) != pr:
        return False
    ta, tb, tt = _ptuple(a), _ptuple(b), _ptuple(tp)
    if not (ta and tb and tt):
        return False
    if not (ta[0] == tb[0] == tt[0] and ta[1] == tb[1] == tt[1]):  # 같은 major·letter
        return False
    return (ta[2], ta[3]) <= (tt[2], tt[3]) <= (tb[2], tb[3])


def _justified(tp: str, st: str) -> bool:
    """to_paragraph(tp)가 source_text(st)에서 정당화되는가 (직접 등장 또는 범위 내부)."""
    if tp in set(PARA_RE.findall(st)):
        return True
    for pat in RANGE:
        for m in pat.finditer(st):
            if _in_range(tp, m.group(1), m.group(2)):
                return True
    return False


def audit_chapter(graph: dict, ch: int, buckets: dict) -> None:
    """한 장의 엣지를 감사해 buckets(카테고리별 리스트)에 의심 항목을 누적한다."""
    # graph 안의 모든 문단 번호 집합
    # 예시: {'3.A1', '3.A2', '3.B1', '3.B2', '3.B3', '3.B4'}
    all_paras = {p for n in graph['nodes'] for p in n.get('paragraphs', [])}
    # CONTAINS 제외한 모든 엣지
    sem = [e for e in graph['edges'] if e['edge_type'] != 'CONTAINS']

    # exact_duplicate: (from,to,to_para,type,source) 동일 항목 2건 이상
    dgroup = defaultdict(list)
    for e in sem:
        k = (e['from_id'], e.get('to_id', ''), e.get('to_paragraph', ''),
             e['edge_type'], e.get('source_text', ''))
        dgroup[k].append(e)
    for items in dgroup.values():
        if len(items) >= 2:
            e = items[0]
            buckets['exact_duplicate'].append({
                'chapter': ch, 'from_id': e['from_id'], 'to_paragraph': e.get('to_paragraph', ''),
                'edge_type': e['edge_type'], 'count': len(items),
                'source_text': e.get('source_text', ''), 'decision': '', 'note': '',
                'suggested': 'dedup — 동일 from/to/문단/type/source 중복, 1개만 유지'})

    # type_conflict: (from,to,to_para,source) 동일한데 edge_type 상충
    cgroup = defaultdict(set)
    csample = {}
    for e in sem:
        k = (e['from_id'], e.get('to_id', ''), e.get('to_paragraph', ''), e.get('source_text', ''))
        cgroup[k].add(e['edge_type'])
        csample[k] = e
    for k, types in cgroup.items():
        if len(types) >= 2:
            e = csample[k]
            st = e.get('source_text', '')
            if any(s in st for s in EXC_SIG):
                sug = 'keep:EXCLUDES — source에 제외 신호, 그 외 타입 삭제'
            elif any(s in st for s in COND_SIG):
                sug = 'keep:HAS_CONDITION — source에 조건 신호, 그 외 타입 삭제'
            else:
                sug = 'keep:REFERENCES — 제외/조건 신호 없음, 그 외 타입 삭제'
            buckets['type_conflict'].append({
                'chapter': ch, 'from_id': e['from_id'], 'to_id': e.get('to_id', ''),
                'to_paragraph': e.get('to_paragraph', ''), 'types': sorted(types),
                'source_text': st, 'decision': '', 'note': '', 'suggested': sug})

    for e in sem:
        et = e['edge_type']
        st = e.get('source_text', '')
        tid = e.get('to_id', '')
        tp = e.get('to_paragraph', '')
        ut = e.get('unresolved_target', '')

        # has_condition_selfloop_optional: 자기루프인데 source가 외부(장/타장 문단)를 가리킴
        if et == 'HAS_CONDITION' and tid and tid == e['from_id']:
            mc = CHAP_RE.search(st)
            refp = [p for p in PARA_RE.findall(st) if _lead_chapter(p) and _lead_chapter(p) != ch]
            ref = f'제{mc.group(1)}장' if mc else (f'문단 {refp[0]}' if refp else None)
            if ref:
                buckets['has_condition_selfloop_optional'].append({
                    'chapter': ch, 'from_id': e['from_id'], 'edge_type': 'HAS_CONDITION(자기루프)',
                    'references': ref, 'source_text': st, 'decision': '',
                    'suggested': f'link:{ref} — 조건이 {ref}을(를) 가리킴(자기루프 대신 외부 링크로 승격 권장)',
                    'note': ''})
            continue

        # target_unjustified: 해소된 문단 엣지인데 tp가 source에서 미정당화
        if tid and tp and tid != e['from_id'] and not _justified(tp, st):
            src_paras = PARA_RE.findall(st)
            if src_paras:
                sug = f'fix→{src_paras[0]} — source는 {src_paras[0]}을 가리킴(현재 {tp}는 오연결)'
            else:
                sug = f'delete — source_text에 {tp} 언급 없음'
            buckets['target_unjustified'].append({
                'chapter': ch, 'edge_type': et, 'from_id': e['from_id'], 'to_paragraph': tp,
                'to_id': tid, 'source_text': st, 'decision': '', 'note': '', 'suggested': sug})

        # prefix_dropped: 본문 N.M로 연결됐는데 source엔 접두어판(실/결N.M)이 있음
        if tid and tp and re.match(r'^\d+\.', tp) and (f'실{tp}' in st or f'결{tp}' in st):
            buckets['prefix_dropped'].append({
                'chapter': ch, 'edge_type': et, 'from_id': e['from_id'], 'to_paragraph': tp,
                'to_id': tid, 'source_text': st, 'decision': '', 'note': '',
                'suggested': f'fix — source에 접두어판(실/결{tp})이 있는데 본문 {tp}로 연결됨'})

        # cross_chapter_residual: 미해소 + 문단/절 번호(제N장 명시 없이)
        if not tid and ut:
            mp = PARA_RE.search(ut)
            ms = SEC_RE.search(ut)
            if CHAP_RE.search(ut):
                continue  # 제N장 명시는 정상 해소 대상
            if mp:
                lc = _lead_chapter(mp.group(0))
                if lc and lc != ch:
                    sug = f'link:gaap-ch{lc} — 번호 앞자리가 {lc}장(타 장 문단 참조)'
                elif mp.group(0) in all_paras:
                    sug = 'link — 같은 장 문단이 그래프에 존재(해소 실패)'
                else:
                    sug = f'parse_fix — 같은 장({ch}) 문단인데 그래프에 없음(파싱 누락 의심)'
                buckets['cross_chapter_residual'].append({
                    'chapter': ch, 'edge_type': et, 'from_id': e['from_id'], 'unresolved_target': ut,
                    'source_text': st, 'kind': '문단(타장추론?)', 'decision': '', 'note': '', 'suggested': sug})
            elif ms:
                msrc = CHAP_RE.search(st)
                sug = (f'link:gaap-ch{msrc.group(1)} — source가 제{msrc.group(1)}장의 해당 절을 가리킴'
                       if msrc else 'keep — 절 참조이나 장 특정 불가')
                buckets['cross_chapter_residual'].append({
                    'chapter': ch, 'edge_type': et, 'from_id': e['from_id'], 'unresolved_target': ut,
                    'source_text': st, 'kind': '절(타장추론?)', 'decision': '', 'note': '', 'suggested': sug})


def generate_review_pending(ontology_dir: str | Path) -> dict:
    """ontology_dir의 gaap-ch1~33.json을 감사해 review_pending 딕셔너리를 반환한다."""
    ontology_dir = Path(ontology_dir)
    buckets = {c: [] for c in CATEGORIES}
    for ch in range(1, 34):
        fp = ontology_dir / f'gaap-ch{ch}.json'
        if not fp.exists():
            continue
        graph = json.loads(fp.read_text(encoding='utf-8'))
        audit_chapter(graph, ch, buckets)
    return {'_README': README, **buckets}


def main() -> None:
    parser = argparse.ArgumentParser(description="온톨로지 엣지 품질 감사 → review_pending.json 생성")
    parser.add_argument("--ontology-dir", default="data/ontology", help="gaap-ch*.json 디렉토리")
    parser.add_argument("--output", default="data/ontology/review_pending.json", help="출력 JSON 경로")
    args = parser.parse_args()

    result = generate_review_pending(args.ontology_dir)
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(len(result[c]) for c in CATEGORIES)
    print(f"감사 완료: 총 검토항목 {total}건")
    for c in CATEGORIES:
        print(f"  {c}: {len(result[c])}")
    print(f"저장: {args.output}")


if __name__ == "__main__":
    main()
