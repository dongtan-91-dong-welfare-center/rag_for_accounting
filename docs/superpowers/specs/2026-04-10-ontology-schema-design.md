# 온톨로지 스키마 설계

> 회계기준서 GraphRAG 시스템을 위한 도메인 온톨로지
>
> 작성일: 2026-04-10
> 상태: 확정

---

## 1. 목적 및 범위

### 목적

일반기업회계기준(GAAP) 전체 장과 K-IFRS 기준서를 대상으로, 회계사/감사인이 특정 사례를 제시하면 해당 사례의 회계처리 방법을 조건 추적 및 예외 조항 탐색으로 찾아주는 GraphRAG 시스템의 지식 그래프 스키마를 정의한다.

### 문서 범위

- 일반기업회계기준 전 장 (제1장~제33장)
- K-IFRS 기준서
- 각 기준서 내 적용사례 섹션 포함

### 프레임워크 독립성

이 스키마는 EdgeQuake, Neo4j 등 특정 GraphRAG 프레임워크에 종속되지 않는다. 프레임워크 전환 시 이 스키마를 기준으로 변환 레이어만 교체한다.

---

## 2. 핵심 설계 결정

### 노드 최소 단위: Subsection

- **Subsection** = 기준서 내 소제목(小題目) 단위 청킹
- 예: "금융상품의 최초인식", "금융자산과 금융부채의 후속 측정"
- 문단 번호(6.4, 6.5, ...)는 Subsection의 속성으로 저장 — 별도 노드 아님
- 적용사례 텍스트는 해당 Subsection의 `content` 안에 포함, 별도 노드 없음

### 개념 노드 미포함

AccountingConcept 같은 개념 노드는 포함하지 않는다.

**이유:** 주 질의 유형(사례 제시 → 회계처리 방법)은 벡터 검색으로 관련 Subsection을 찾고, 그래프로 참조/예외/조건을 탐색하는 구조로 충분히 처리된다. 개념 노드는 "공정가치 측정이 필요한 전체 경우" 같은 개념 중심 탐색에 유리하지만, 이 시스템의 주 사용 패턴과 거리가 있다. 필요 시 운영 중 추가한다.

### 예시 텍스트 처리

문단 내 예시(예: 6.13의2의 임대차보증금)는 그래프 노드로 분리하지 않는다. Subsection의 `content` 텍스트에 포함된 채로 검색되고, LLM이 검색 시 해석한다.

---

## 3. 노드 타입

### Standard

기준서 단위 노드.

| 속성 | 타입 | 설명 |
|------|------|------|
| `id` | string | 고유 식별자. 예: `gaap-ch6`, `kifrs-1116` |
| `name` | string | 기준서 이름. 예: "제6장 금융자산·금융부채" |
| `type` | enum | `GAAP` \| `KIFRS` |
| `chapter` | string | 장 번호 또는 기준서 번호. 예: `6`, `1116` |
| `effective_date` | string | 시행일 |

### Section

장 내 절(節) 단위 노드.

| 속성 | 타입 | 설명 |
|------|------|------|
| `id` | string | 고유 식별자. 예: `gaap-ch6-s1` |
| `title` | string | 절 제목. 예: "제1절 공통사항" |
| `order` | int | 절 순서 |

### Subsection

최소 청킹 단위. 소제목 하나 = 노드 하나.

| 속성 | 타입 | 설명 |
|------|------|------|
| `id` | string | 고유 식별자. 예: `gaap-ch6-s1-최초인식` |
| `title` | string | 소제목. 예: "금융상품의 최초인식" |
| `content` | string | 전체 텍스트 (문단 내 예시 포함) |
| `paragraphs` | string[] | 포함된 문단 번호 목록. 예: `["6.4", "6.4의2"]` |
| `unresolved_refs` | string[] | 연결하지 못한 참조 원문. 예: `["제8장 문단 8.2"]` |
| `order` | int | Section 내 순서 |

---

## 4. 엣지 타입

### CONTAINS

계층 구조를 표현한다.

| 항목 | 내용 |
|------|------|
| From → To | Standard → Section, Section → Subsection |
| 속성 | `order` (int): 자식 노드의 순서 |

### REFERENCES

조항 간 상호참조. 미연결 참조는 출발 노드의 `unresolved_refs` 속성에 기록한다.

| 항목 | 내용 |
|------|------|
| From → To | Subsection → Standard \| Section \| Subsection |
| 속성 | `paragraph` (string): 참조 출처 하위 항목 번호. 예: `"6.14⑵㈏"` |
| 속성 | `source_text` (string): 참조가 등장한 원문 문장 |

하나의 Subsection에서 여러 엣지가 나올 수 있으며, `paragraph` 속성으로 어느 하위 항목(⑴⑵㈎㈏ 등)에서 발생한 참조인지 구분한다.

**예시 — 6.14 "금융자산과 금융부채의 후속 측정":**
```
(후속측정 Subsection)
  -[REFERENCES { paragraph: "6.14⑵",   source_text: "..." }]→ (6.30~6.31 Subsection)
  -[REFERENCES { paragraph: "6.14⑵㈎", source_text: "..." }]→ (6.46~6.47 Subsection)
  -[REFERENCES { paragraph: "6.14⑵㈏", source_text: "..." }]→ (제8장 8.2 Subsection)
```

- 6.3 → 제2절, 제3절, 제4절 (Section 참조)
- 6.14⑵㈏ → 제8장 문단 8.2 (다른 Standard의 Subsection 참조)

### EXCLUDES

적용범위 제외 관계. 제외 대상 중 일부가 다시 포함되는 경우 `include` 속성으로 표현한다.

| 항목 | 내용 |
|------|------|
| From → To | Subsection → Subsection |
| 속성 | `paragraph` (string): 제외 출처 하위 항목 번호. 예: `"6.14⑴"` |
| 속성 | `include` (string[]): 제외에서 재포함되는 항목 설명 목록 |
| 속성 | `source_text` (string): 해당 원문 문장 |

REFERENCES와 마찬가지로 하나의 Subsection에서 여러 EXCLUDES 엣지가 나올 수 있으며, `paragraph` 속성으로 어느 하위 항목의 제외인지 구분한다.

**예시 — 6.14 하위 항목별 제외:**
```
(후속측정 Subsection)
  -[EXCLUDES { paragraph: "6.14⑴", source_text: "..." }]→ (제2절 Section)
  -[EXCLUDES { paragraph: "6.14⑵", source_text: "..." }]→ (당기손익인식지정항목 Subsection)
```

**예시 — 6.2의 (2):**
```
(6.2 적용범위) -[EXCLUDES {
  include: [
    "리스제공자가 인식하는 리스채권의 제거와 손상",
    "리스이용자가 인식하는 금융리스부채의 제거",
    "리스에 내재된 파생상품"
  ]
}]→ (리스에 따른 권리와 의무 관련 subsection)
```

### HAS_CONDITION

"원칙은 A이나, 조건 충족 시 B" 패턴에만 적용한다. 조건 목록 나열(6.5의 ⑴⑵⑶ 형태)에는 사용하지 않는다.

| 항목 | 내용 |
|------|------|
| From → To | Subsection → Subsection |
| 속성 | `condition_text` (string): 조건 원문 |
| 속성 | `source_text` (string): 해당 원문 문장 |

**적용 기준:**
- O: "다만, 다음에 해당하는 경우에는 [다른 절]을 적용한다"
- X: "다음 요건을 모두 충족하는 경우 ⑴... ⑵... ⑶..." (조건 나열 → content 텍스트로 처리)

---

## 5. 추출 전략

### 정규식 탐지 → LLM 분류 파이프라인

그래프 엣지는 LLM이 처음부터 전체 텍스트를 읽는 것이 아니라, 정규식으로 **후보 문단을 탐지**한 뒤 LLM이 엣지 타입·대상 노드·속성 값을 자유롭게 판별하는 2단계 방식으로 생성한다.

정규식은 후보를 좁히는 트리거일 뿐이며, 아래 탐지 패턴 매칭 예시는 가능한 결과를 예시한 것이지 LLM에 미리 지정하는 규칙이 아니다.

| 탐지 패턴 | 실문서 매칭 예시 |
|----------|----------------|
| `다만` | 6.2⑵, 6.2⑸, 6.12, 6.30, 6.34⑴, 6.56, 6.75 |
| `제외` | 6.2, 6.5, 6.9, 6.14, 6.17의2, 6.25, 6.38, 6.54 |
| `제\d+절` | 6.3, 6.14⑴, 6.19, 6.21 |
| `제\d+장` | 6.14⑵㈏ |
| `문단\s*\d+` | 6.21, 6.26, 6.28, 6.68, 6.73 |
| `불구하고` | 6.89, 6.90, 6.91, 6.A1의4, 실6.76, 실6.99 |
| `한하여` | 6.56 |

**LLM 판별 항목:**
- 엣지 타입: REFERENCES / EXCLUDES / HAS_CONDITION / 해당 없음
- 대상 노드: 어느 Standard / Section / Subsection을 가리키는가
- 자기 subsection 내 단순 언급이면 엣지 생성하지 않음
- EXCLUDES이면 재포함(include[]) 항목이 있는가
- REFERENCES 대상이 그래프에 없으면 `unresolved_refs`에 기록

### 미연결 참조 처리

REFERENCES 대상이 그래프에 아직 없는 경우:
1. 엣지를 만들지 않는다
2. 출발 Subsection의 `unresolved_refs` 배열에 원문 참조 텍스트를 기록
3. 전체 인제스트 완료 후 일괄 재처리로 해소

---

## 6. 질의 처리 흐름

사례 기반 질의에서 이 온톨로지가 어떻게 활용되는지 예시:

```
질의: "임대차보증금을 받았는데 금융부채로 인식해야 하나?"

① 벡터 검색 → RetrievedChunk 목록
   → 6.13의2 (임대차보증금 언급), 6.2 (적용범위) 히트

② 청크 메타데이터 기반 진입점 매핑 (chunks_to_node_ids)
   → 각 RetrievedChunk.metadata.ontology_node_id를 추출해 그래프 진입점
     노드 ID 목록 생성 (ontology_node_id ↔ OntologyNode.id)
   → ontology_node_id 누락 청크는 Silent Skip, 중복 노드는 순서 유지하며 제거

③ 그래프 탐색 (6.2 기준)
   → EXCLUDES 엣지 확인: 리스 관련 제외 항목과 무관
   → 적용범위 내에 해당함 확인

④ 그래프 탐색 (6.12, 6.13 기준)
   → REFERENCES: 6.13의2 → 6.12 (최초 측정: 공정가치)
   → HAS_CONDITION 확인: 예외 조건 없음

⑤ LLM 응답 생성
   → "임대차보증금은 금융부채에 해당하며, 최초인식 시 공정가치로 측정"
```

> ②단계는 `src/retrieval/ontology_bridge.py`의 `chunks_to_node_ids()`가 담당한다.
> 벡터 검색(`refactor/evaluate`)과 그래프 탐색(`feature/ontology`)을 잇는 매핑
> 레이어로, 청크와 온톨로지 노드를 독립 운영하면서 메타데이터로 연결한다.

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-10 | 초기 작성 |
| 2026-04-10 | 추출 전략 개정: 정규식은 후보 탐지만, LLM이 자유 판별. 탐지 패턴 단순화 및 실문서 예시 추가. 자기참조 판별 기준 명확화 |
| 2026-06-06 | §6 질의 처리 흐름에 청크→노드 진입점 매핑 단계(chunks_to_node_ids) 추가, 5단계로 재정렬 (#72) |
