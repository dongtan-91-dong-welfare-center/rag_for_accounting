# decisions/ — 아키텍처 결정 기록(ADR)

> **한 줄 요약(BLUF):** "여러 대안 중 왜 이것을 골랐나"를 **결정 하나당 한 장**으로 남긴다. 코드·닫힌 이슈에 흩어진 근거를 한 곳에 박제해, 신규자가 폐기된 가정을 그대로 믿지 않게 한다.

## ADR이란

결정 하나당 메모 한 장: (1) 왜 필요했나 (2) 무엇을 골랐나 — **검토·기각한 대안 대비** (3) 무슨 결과(영향)가 있나 (4) 근거(이슈·코드·측정 링크).

## 메타 규약

- **Status** — 결정의 *생애주기*만 표기한다: `Proposed`(제안) · `Accepted`(채택) · `Superseded`(대체됨). **구현 완료도·freeze 게이트를 결합하지 않는다.** 채택된 결정을 뒤집으면 새 ADR로 "이전 것은 OOO로 대체"라 잇는다. Accepted 이후에도 *문서 자체의 명확화·근거 보강*은 계속 한다 — 불변인 것은 *결정 내용*이지 문서가 아니다.
- **Date** — 결정일 하나(`YYYY-MM-DD`). 이미 내린 결정을 뒤늦게 적었으면 기록일을 쓰고 `(소급)`을 붙인다. ADR 작성일은 결정일과 다를 때만 부차 정보로 둔다.
- **근거 / 관련** — 역할을 구분한다: `근거: #NNN`(결정을 부른 이슈) · `관련: #…`. **이슈가 없으면 `근거 코드: <경로>`** 로 코드를 근거로 명시한다.
- **대안 비교 필수** — §2(무엇을 골랐나)에 검토했다가 기각한 대안과 선택 기준을 반드시 담는다. 정량 비교가 없으면 "정량 비교 미기록"이라 솔직히 적고 관련 이슈로 링크한다(없는 데이터를 지어내지 않는다).

## 템플릿

```markdown
# ADR-NNNN — <결정을 한 줄로>

> **한 줄 요약(BLUF):** <무엇을·왜 한 줄>

- **Status:** Proposed | Accepted | Superseded
- **Date:** YYYY-MM-DD   (소급이면 `YYYY-MM-DD (소급)`)
- **근거:** #NNN · **관련:** #…   (이슈가 없으면 `근거 코드: <경로>`)

## 1. 왜 (Context)
## 2. 무엇을 골랐나 (Decision)   — 검토·기각한 대안 대비 포함
## 3. 결과(영향) (Consequences)   — +/− 둘 다
```

## 목록

| # | 결정 | Status |
|---|---|---|
| [0001](0001-byo-corpus-kgaap.md) | BYO 코퍼스 — 회계기준 원문을 레포에 두지 않음 (#102/KASB) | Accepted |
| [0002](0002-kure-v1-embedding.md) | 임베딩 모델 KURE-v1 (자체호스팅, 1024차원) | Accepted |
| [0003](0003-pgvector-hnsw-vectorstore.md) | 벡터 스토어 pgvector + HNSW (Milvus·AGE 대신) | Accepted |
| [0004](0004-rrf-hybrid-fusion.md) | 하이브리드 검색 융합 RRF (순위 기반) | Accepted |
| [0005](0005-langgraph-orchestration.md) | 오케스트레이션 LangGraph StateGraph + MemorySaver | Accepted |

> 0002~0005는 v1.0에서 이미 내린 결정을 소급 기록한 것이다(코드가 정본, ADR은 "왜"를 박제). 폐기된 결정들의 계보(GraphRAG/AGE → pgvector 등)는 회고 ADR로 박제하지 않고 [archive/README.md](../archive/README.md)가 커버한다.
