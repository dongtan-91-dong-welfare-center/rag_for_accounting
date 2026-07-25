/**
 * 조항 카드 표시 규칙 — 칩·제목·발췌를 API 응답에서 파생하는 순수 함수 모음.
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

export type Excerpt =
  | { kind: "text"; text: string }
  | { kind: "table-only" }
  | { kind: "empty" };

/**
 * 접힘 상태에 보여줄 발췌 — 첫 문단의 본문 첫 줄(마크다운 기호 제거).
 *
 * "질의에 걸린 문단 우선"은 파이프라인에 매칭 신호가 없어 v1에서는 첫 문단으로 확정했다(7/25 결정).
 * 표만으로 짜인 조항은 발췌가 표 조각(| … |)이 되어 읽을 수 없으므로, 표가 있다는 사실만 알리고 본문은 펼칠 때 표 모양으로 보여준다.
 */
export function excerptOf(content: string): Excerpt {
  let sawTable = false;
  for (const raw of content.split("\n")) {
    const line = raw.trim();
    if (!line || /^#{1,6}\s/.test(line)) continue;
    if (line.startsWith("|") || /^[-:|\s]+$/.test(line)) {
      sawTable = true;
      continue;
    }
    return { kind: "text", text: line.replace(/\*\*/g, "") };
  }
  return sawTable ? { kind: "table-only" } : { kind: "empty" };
}
