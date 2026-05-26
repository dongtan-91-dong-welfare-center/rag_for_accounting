# 회계기준서 온톨로지 스키마 설계 문서

> 작성일: 2026-05-17  
> 대상 파일: `src/ontology/extractor.py`, `data/ontology/schema.json`  
> 출력 위치: `data/ontology/chapter_XX.json` (33개 파일)

---

## 1. 목적

일반기업회계기준 33개 장(章)의 MD 파일을 파싱하여 **그래프 형식의 온톨로지 JSON**을 생성한다.

**활용 목적**
- GraphRAG: Apache AGE 그래프 DB에 노드/엣지로 임포트하여 조항 간 관계 탐색
- Semantic 검색: 개념 계층(IS_SUBCLASS_OF) + 키워드 엣지로 의미 기반 검색
- 분석: "어떤 조항이 단기매매증권의 공정가치 측정을 규정하는가?" 같은 질의 지원

---

## 2. 입출력 구조

### 입력
```
data/llm_parsed/제6장_금융자산·금융부채(수정목록_19-1_반영).md
```
LLM으로 파싱된 Markdown 파일. 헤딩 레벨이 문서 계층을 나타낸다.

```
# 장 (h1)     → Chapter
## 절 (h2)    → Section
### 소제목 (h3) → TopicGroup
#### 조항 (h4) → Clause  (예: 6.4, 6.4의2, 실6.1)
##### 항 (h5)  → 조항 content에 포함
###### 호 (h6) → 조항 content에 포함
```

### 출력 JSON 구조
```json
{
  "metadata": {
    "document_id": "gaap_kr_ch06",
    "chapter_number": 6,
    "source_file": "제6장_금융자산·금융부채(수정목록_19-1_반영).md",
    "standard": "일반기업회계기준",
    "node_count": 549,
    "edge_count": 1111
  },
  "nodes": [
    { "id": "clause_6_4", "type": "Clause", "label": "문단 6.4", "properties": { ... } }
  ],
  "edges": [
    { "id": "e00001", "source": "sec6_1", "target": "clause_6_4", "type": "CONTAINS", "properties": {} }
  ]
}
```

---

## 3. 노드 타입

### 3-1. 문서 구조 노드 (Document Structure)

| 타입 | ID 패턴 | 예시 | 설명 |
|---|---|---|---|
| `Chapter` | `ch{N}` | `ch6` | 장 전체 |
| `Section` | `sec{N}_{M}` | `sec6_1` | 제M절 |
| `TopicGroup` | `tg_{N}_{소제목}` | `tg_6_금융상품의_최초인식` | ### 헤딩으로 묶인 주제 |
| `Clause` | `clause_{N}_{X}` | `clause_6_4`, `clause_6_4_2` | 개별 조항 (6.4, 6.4의2) |

**Clause ID 변환 규칙**
```
6.4    → clause_6_4
6.4의2 → clause_6_4_2   (의 → _)
실6.1  → clause_실6_1
결6.2  → clause_결6_2
6.A1의2 → clause_6_A1_2
```

### 3-2. 도메인 개념 노드 (Concept)

`schema.json`에 정의된 개념을 매 장마다 전역 노드로 등록한다.

**금융상품 계층**
```
FinancialInstrument
├── FinancialAsset
│   └── Security
│       ├── EquityInstrument
│       ├── DebtInstrument
│       │   └── HeldToMaturitySecurity
│       ├── TradingSecurity
│       └── AvailableForSaleSecurity
├── FinancialLiability
├── Derivative
│   └── EmbeddedDerivative
└── HybridContract
```

**회계처리 계층**
```
AccountingProcess
├── InitialRecognition
├── SubsequentMeasurement
├── Derecognition
├── Impairment
├── Reclassification
├── HedgeAccounting
│   ├── FairValueHedge
│   ├── CashFlowHedge
│   └── NetInvestmentHedge
├── DebtRestructuring
├── AllowanceForDoubtfulAccounts
├── Disclosure
└── Transfer
```

**측정기준 계층**
```
MeasurementBasis
├── FairValue
├── AmortizedCost
└── CostMethod
```

**금융위험 계층**
```
FinancialRisk
├── CreditRisk
├── LiquidityRisk
└── MarketRisk
    ├── InterestRateRisk
    ├── ForeignCurrencyRisk
    └── PriceRisk
```

---

## 4. 엣지 타입

| 타입 | 방향 | 생성 방식 | 설명 |
|---|---|---|---|
| `CONTAINS` | 상위→하위 | 규칙 기반 | 문서 계층 포함 관계 |
| `IS_SUBCLASS_OF` | 하위→상위 | schema.json | 개념 계층 (예: TradingSecurity → Security) |
| `NEXT_CLAUSE` | 조항→다음조항 | 규칙 기반 | 본문(main) 조항 순서 |
| `REFERENCES` | 조항→조항/절/장 | 정규식 | 교차참조 ("문단 6.X", "제N절") |
| `APPLIES_TO` | 조항→금융상품 | 키워드 스캔 | 본문에 금융상품 키워드 포함 |
| `REGULATES` | 조항→회계처리 | 키워드 스캔 | 본문에 회계처리 키워드 포함 |
| `MEASURED_BY` | 조항→측정기준, 금융상품→측정기준 | 키워드 스캔(조항), LLM(금융상품) | 조항 본문에 측정 구문 패턴 포함 |

---

## 5. 파싱 파이프라인 (3단계)

```
MD 파일
  │
  ▼ 1단계: 개념 노드 초기화
  │   schema.json → 도메인 개념 노드 등록
  │   IS_SUBCLASS_OF 엣지 생성
  │
  ▼ 2단계: 문서 구조 파싱 (라인별 상태 머신)
  │   Chapter → Section → TopicGroup → Clause 계층 추출
  │   각 Clause에 content 누적 (다음 #### 헤딩 등장 시 flush)
  │   flush 시점에 키워드 스캔 + 교차참조 추출
  │
  ▼ 3단계: 엣지 생성
      NEXT_CLAUSE (main 조항 순서)
      APPLIES_TO / REGULATES / MEASURED_BY (키워드 힌트)
      REFERENCES (cross_ref_targets 해소)
```

---

## 6. 파트(Part) 분류 규칙

회계기준서는 **본문** 외에 부록/부속 섹션을 포함한다. 이들을 구분하기 위해 `part` 속성을 모든 TopicGroup/Clause에 부여한다.

| `part` 값 | 내용 | 전환 트리거 |
|---|---|---|
| `main` | 본문 규정 (기본값) | 장 시작 시 |
| `application_guidance` | 적용보충기준 (6.AX 조항) | `**부록A. 적용보충기준**` bold 텍스트 |
| `practical_guidance` | 실무지침 | `### 실무지침` 헤딩 |
| `basis_for_conclusions` | 결론도출근거 | `### 결론도출근거` 헤딩 |
| `application_examples` | 적용사례 | `### 적용사례` 헤딩 |

**설계 의도**
- `part == "main"` 필터로 실제 회계 규정 조항만 추출 가능
- `part == "practical_guidance"`로 실무 적용 예시만 추출 가능
- GraphRAG 쿼리 시 `part` 조건으로 검색 범위 제어

**전환 순서 예시 (제6장)**
```
본문 시작 (main)
  ↓  6.1 ~ 6.102 (main)
  ↓  **부록A. 적용보충기준** (bold text)
  ↓  6.A1의2 ~ (application_guidance)
  ↓  ### 실무지침
  ↓  실6.1 ~ (practical_guidance)
  ↓  ### 결론도출근거
  ↓  결6.2 ~ (basis_for_conclusions)
  ↓  ### 적용사례
  ↓  사례 1 ~ (application_examples)
```

---

## 7. 교차참조 추출 규칙

Clause 본문에서 정규식으로 다른 조항·절·장 참조를 탐지한다.

```python
CROSS_REF_PAT = re.compile(
    r"(?:문단|조문)\s*(결|실)?(\d+)\.(\d+(?:의\d+)?)"  # 문단 6.4, 문단 결6.2
    r"|제\s*(\d+)\s*절"                                  # 제2절
    r"|제\s*(\d+)\s*장"                                  # 제6장
)
```

**해소 로직**
- 같은 장 내 조항 참조 → `REFERENCES` 엣지로 연결
- 다른 장 참조 (예: `ch8`, `sec5_1`) → `external_refs` 프로퍼티에 기록 (엣지 미생성)

**예시**
```
문단 6.28 본문: "유가증권의 최초 측정에 대해서는 문단 6.12를 적용한다."
→ cross_ref_targets: ["clause_6_12"]
→ REFERENCES 엣지: clause_6_28 → clause_6_12
```

---

## 8. 키워드 기반 의미 엣지 규칙

**main 파트 조항**에 한해 본문에서 키워드를 스캔하여 의미 엣지를 생성한다. 부록/실무지침 조항에는 생성하지 않는다.

### 8-1. 금융상품 키워드 맵 → APPLIES_TO

| 키워드 | 연결 개념 |
|---|---|
| 만기보유증권 | HeldToMaturitySecurity |
| 단기매매증권 | TradingSecurity |
| 매도가능증권 | AvailableForSaleSecurity |
| 지분증권 | EquityInstrument |
| 채무증권 | DebtInstrument |
| 유가증권 | Security |
| 파생상품 | Derivative |
| 내재파생상품 | EmbeddedDerivative |
| 금융자산 | FinancialAsset |
| 금융부채 | FinancialLiability |
| 금융상품 | FinancialInstrument |
| 복합계약 | HybridContract |

### 8-2. 회계처리 키워드 맵 → REGULATES

| 키워드 | 연결 개념 |
|---|---|
| 최초인식 | InitialRecognition |
| 후속측정 | SubsequentMeasurement |
| 제거 | Derecognition |
| 손상차손 / 손상 | Impairment |
| 재분류 | Reclassification |
| 위험회피회계 | HedgeAccounting |
| 공정가치위험회피 | FairValueHedge |
| 현금흐름위험회피 | CashFlowHedge |
| 순투자위험회피 | NetInvestmentHedge |
| 채권·채무조정 | DebtRestructuring |
| 대손충당금 | AllowanceForDoubtfulAccounts |
| 공시 / 주석 공시 | Disclosure |
| 양도 | Transfer |

### 8-3. 측정기준 패턴 → MEASURED_BY

단순 키워드 포함이 아닌 **"~로 평가/측정" 문맥 구문** 에서만 인식한다.  
`취득원가`, `원가` 단독 등장은 측정 문맥이 아닐 수 있으므로 제외한다.

| 패턴 | 연결 개념 | 예시 |
|---|---|---|
| `공정가치로 평가/측정`, `공정가치 측정` | FairValue | "공정가치로 평가한다" |
| `상각후원가로 평가/측정` | AmortizedCost | "상각후원가로 측정할 때에는" |
| `(취득원가\|원가)로 평가/측정` | CostMethod | "취득원가로 평가한다" |

---

## 9. 중복 처리 규칙

### 9-1. 페이지 단절로 인한 조항 번호 중복

LLM 파싱 시 페이지 경계에서 동일 조항 번호가 두 번 출력되는 경우가 있다.

```markdown
#### 6.56
외화공정가치 변동위험에 노출된 기존 자산·부채도 ...다만, 외화표시 투자주식은 해당 투자주식

<!-- page 23 -->

#### 6.56
외화표시 투자주식은 해당 투자주식이 거래소시장 또는 ...
```

**처리**: `_clause_id_map`에 이미 해당 번호가 있으면 새 노드를 만들지 않고 **기존 노드의 content에 병합**한다.

### 9-2. Section 노드 중복

결론도출근거·실무지침 섹션에서 `## 제N절` 헤딩이 반복 등장한다. `sec{N}_{M}` ID가 이미 존재하면 노드를 새로 만들지 않고 `section_id` 포인터만 이동한다.

### 9-3. TopicGroup 이름 중복

같은 이름의 TopicGroup이 다른 파트에 나올 수 있다 (예: "주석 공시"가 각 절마다 등장). `_{suffix}` 번호를 붙여 ID를 구분한다.

---

## 10. Clause 속성 상세

```json
{
  "id": "clause_6_29",
  "type": "Clause",
  "label": "문단 6.29",
  "properties": {
    "clause_number": "6.29",
    "clause_type": "main",
    "part": "main",
    "chapter_id": "ch6",
    "section_id": "sec6_2",
    "topic_group_id": "tg_6_유가증권의_최초_측정과_후속_측정",
    "page": 12,
    "is_deleted": false,
    "content": "만기보유증권은 상각후원가로 평가하여 ...",
    "instrument_hints": ["HeldToMaturitySecurity"],
    "process_hints": [],
    "measurement_hints": ["AmortizedCost", "CostMethod"],
    "cross_ref_targets": []
  }
}
```

| 속성 | 타입 | 설명 |
|---|---|---|
| `clause_number` | string | 원본 조항 번호 (`6.29`, `6.4의2`, `실6.1`) |
| `clause_type` | string | `main` \| `application_guidance` \| `practical_guidance` \| `basis_for_conclusions` |
| `part` | string | 문서 내 위치 파트 (9절 참조) |
| `page` | int | 소스 PDF 페이지 번호 |
| `is_deleted` | bool | `<삭제>` 표시 여부 |
| `content` | string | 조항 전문 (항·호 포함) |
| `instrument_hints` | list | 본문에서 감지된 금융상품 개념 ID |
| `process_hints` | list | 본문에서 감지된 회계처리 개념 ID |
| `measurement_hints` | list | 본문에서 감지된 측정기준 개념 ID |
| `cross_ref_targets` | list | 본문에서 추출된 교차참조 노드 ID |
| `external_refs` | list | 해소되지 않은 외부 참조 (다른 장) |

---

## 11. 전체 통계 (2026-05-17 기준)

| 장 | 노드 | 엣지 |
|---|---|---|
| 제1장 | 45 | 43 |
| 제2장 | 268 | 466 |
| 제3장 | 102 | 141 |
| 제4장 | 135 | 195 |
| 제5장 | 82 | 115 |
| 제6장 | 549 | 1111 |
| 제7장 | 89 | 148 |
| 제8장 | 133 | 239 |
| 제9장 | 92 | 147 |
| 제10장 | 130 | 260 |
| 제11장 | 123 | 195 |
| 제12장 | 163 | 261 |
| 제13장 | 191 | 311 |
| 제14장 | 72 | 100 |
| 제15장 | 112 | 165 |
| 제16장 | 193 | 350 |
| 제17장 | 67 | 92 |
| 제18장 | 118 | 203 |
| 제19장 | 248 | 376 |
| 제20장 | 89 | 154 |
| 제21장 | 92 | 123 |
| 제22장 | 189 | 318 |
| 제23장 | 75 | 116 |
| 제24장 | 63 | 79 |
| 제25장 | 70 | 95 |
| 제26장 | 134 | 199 |
| 제27장 | 76 | 120 |
| 제28장 | 98 | 153 |
| 제29장 | 105 | 130 |
| 제30장 | 64 | 78 |
| 제31장 | 59 | 81 |
| 제32장 | 106 | 127 |
| 제33장 | 119 | 179 |

---

## 12. 실행 방법

```bash
# 단일 장
.venv/bin/python -m src.ontology.extractor \
  --input data/llm_parsed/제6장_금융자산·금융부채(수정목록_19-1_반영).md \
  --chapter 6

# 전체 33개 장
.venv/bin/python -m src.ontology.extractor --all

# LLM 의미 추출 추가 (로컬 LLM localhost:8000 필요)
.venv/bin/python -m src.ontology.extractor --all --use-llm
```

---

## 13. GraphRAG 활용 예시 (Apache AGE Cypher)

```cypher
-- 단기매매증권의 측정 방법을 규정하는 조항 찾기
MATCH (c:Clause)-[:APPLIES_TO]->(i {id: 'TradingSecurity'})
WHERE c.part = 'main'
RETURN c.clause_number, c.content

-- 6.29에서 시작하는 NEXT_CLAUSE 체인 (연속 조항 탐색)
MATCH path = (start:Clause {id: 'clause_6_29'})-[:NEXT_CLAUSE*1..5]->(next)
RETURN [n IN nodes(path) | n.clause_number] AS chain

-- 특정 조항이 참조하는 모든 조항 (2홉 이내)
MATCH (c:Clause {id: 'clause_6_14'})-[:REFERENCES*1..2]->(ref)
RETURN ref.clause_number, ref.content
```

---

## 14. 알려진 한계

| 항목 | 현황 | 개선 방향 |
|---|---|---|
| 키워드 정밀도 | 단순 포함 여부 판단 → 과탐지 가능 | `--use-llm` 옵션으로 LLM 정밀 추출 |
| 예외/단서 관계 | "다만", "단서" 조항 구조 미탐지 | 정규식 또는 LLM 추가 처리 필요 |
| 장 간 참조 해소 | `external_refs`에만 기록, 엣지 미생성 | 전체 장 병합 후 2차 처리 필요 |
| 표/수식 내용 | 본문 텍스트에 포함되나 구조 미분석 | 추후 별도 파서 추가 가능 |
| LLM 파싱 오류 | 페이지 단절 시 조항 번호 중복 가능 | content 병합으로 완화 처리됨 |
