/**
 * 조항 표시 규칙 — 칩·제목·답변 인용 마커 치환을 API 응답에서 파생하는 순수 함수 모음.
 *
 * 문단번호 추출 자체는 서버 공용 규칙(src/utils/clause_paras.py)이 하고 프론트는 paras를 소비만 한다.
 * Python↔TypeScript로 규칙이 두 벌이 되면 채점과 화면이 어긋난다. 여기는 "받은 번호를 어떻게 보여줄지"만 담당한다.
 * React 렌더와 분리해 둔 이유: 표시 규칙은 입력→출력이 명확한 순수 로직이라, 테스트 러너가 갖춰지면 컴포넌트 없이 바로 검증할 수 있다.
 */

/** 칩이 이 개수를 넘으면 범위 한 칩으로 줄인다 — 다발 청크는 문단이 수십 개라칩을 다 붙이면 카드 머리가 본문보다 길어진다. */
const MAX_CHIPS = 6;

/** 칩 표시 목록. 예: 8개 문단 → ["6.13 ~ 6.20 · 8개 문단"] 한 칩으로 축약. */
export function paraChips(paras: string[]): string[] {
  if (paras.length <= MAX_CHIPS) return paras;
  return [`${paras[0]} ~ ${paras[paras.length - 1]} · ${paras.length}개 문단`];
}

/**
 * 내부 이름표에서 사람이 읽는 제목을 만든다.
 * 예: "gaap-ch6-s1-최초인식" → "최초인식", "gaap-ch10-용어의_정의-원가" → "용어의 정의 · 원가".
 *
 * 카드 제목의 node_id는 시스템이 문서 구조를 정리하려고 붙인 내부 이름표라 회계사가 쓰지 않는다.
 * 절 코드(s1)와 분할 순번(-2) 세그먼트는 뜻이 없어 걸러낸다.
 * 칩이 하나도 없는 카드(용어 정의·사례 등)는 이 제목이 유일한 식별 표지가 된다.
 */
export function humanNodeTitle(nodeId: string, documentId: string): string {
  if (!nodeId) return "";
  const rest = nodeId.startsWith(`${documentId}-`) ? nodeId.slice(documentId.length + 1) : nodeId;
  const segments = rest
    .split("-")
    .filter((seg) => !/^s\d+$/.test(seg) && !/^\d+$/.test(seg));
  if (segments.length === 0) return "";
  return segments.join(" · ").replace(/_/g, " ");
}

export type AnswerSegment =
  | { kind: "text"; text: string }
  | { kind: "ref"; citationIndex: number; label: string };

const MARKER_RE = /\[(\d+)\]/g;

/**
 * 답변 본문의 인용 마커([1]·[2])를 실제 조항 번호 라벨로 바꾼 세그먼트 열을 만든다.
 * 예: "…한도로 합니다 [2]." + citations[1].paras=["18.12"] → "…한도로 합니다(18.12)."
 *
 * 마커↔인용 매핑은 백엔드 extract_citations_from_text와 같은 규칙으로 복원한다:
 * citations 배열은 마커가 본문에 처음 등장한 순서로 쌓이므로, k번째로 처음 등장한 마커 번호가 citations[k-1]이다.
 * citations 길이를 넘는 마커(모델이 지어낸 번호는 백엔드가 버린다)는 치환하지 않고 본문 텍스트로 남긴다.
 * 문단번호가 없는 인용(용어 정의 등)은 조항 번호 대신 [k] 표기를 유지하되 클릭은 가능하다.
 */
export function answerSegments(
  answer: string,
  citations: { paras: string[] }[],
): AnswerSegment[] {
  const firstSeen: number[] = []; // 마커 번호의 첫 등장 순서
  for (const m of answer.matchAll(MARKER_RE)) {
    const n = Number(m[1]);
    if (!firstSeen.includes(n)) firstSeen.push(n);
  }
  const citationIndexOf = new Map<number, number>();
  firstSeen.slice(0, citations.length).forEach((n, i) => citationIndexOf.set(n, i));

  const segments: AnswerSegment[] = [];
  let cursor = 0;
  for (const m of answer.matchAll(MARKER_RE)) {
    const index = m.index ?? 0;
    const ci = citationIndexOf.get(Number(m[1]));
    if (ci === undefined) continue; // 매핑 불가 마커는 텍스트로 남긴다(cursor를 안 움직임)
    if (index > cursor) {
      // 마커 앞의 공백은 지운다 — "합니다 [2]." 를 "합니다(18.12)." 로 붙여 쓴다.
      segments.push({ kind: "text", text: answer.slice(cursor, index).replace(/\s+$/, "") });
    }
    const paras = citations[ci].paras;
    const label = paras.length > 0 ? `(${paras[0]}${paras.length > 1 ? " 외" : ""})` : `[${ci + 1}]`;
    segments.push({ kind: "ref", citationIndex: ci, label });
    cursor = index + m[0].length;
  }
  if (cursor < answer.length) segments.push({ kind: "text", text: answer.slice(cursor) });
  return segments;
}
