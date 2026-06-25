# decisions/ — 아키텍처 결정 기록(ADR)

> **한 줄 요약(BLUF):** "왜 그렇게 골랐나"를 **결정 하나당 한 장**으로 남긴다. 코드·닫힌 이슈에 흩어진 근거를 한 곳에 박제해, 신규자가 폐기된 가정을 그대로 믿지 않게 한다.

## ADR이란

결정 하나당 메모 한 장: (1) 왜 필요했나 (2) 무엇을 골랐나 (3) 무슨 대가가 있나 (4) 근거(이슈·측정 링크).

## Status 흐름

`Draft` → (PR 리뷰 / 회계사·법무 확인) → `Accepted`(freeze)

`근거:` Draft 단계에서 사실오류를 박제하지 않기 위해 freeze를 확인 뒤로 미룬다. 한 번 freeze된 ADR은 수정하지 않고, 새 ADR로 "이전 것은 OOO로 대체됨"이라 잇는다.

## 목록

| # | 결정 | Status |
|---|---|---|
| [0001](0001-byo-corpus-kgaap.md) | BYO 코퍼스 — 회계기준 원문을 레포에 두지 않음 (#102/KASB) | Draft |

> 폐기된 결정들의 계보(GraphRAG/AGE → pgvector 등)는 회고 ADR로 박제하지 않고 [archive/README.md](../archive/README.md)가 커버한다.
