# DART Taxonomy Linkbase 구조 가이드

> 2024 DART Taxonomy (`2024-DART_Taxonomy_20240926_배포용최종.xlsx`) 분석
> 온톨로지 설계를 위한 4개 링크베이스 정리
> 약어: Taxonomy/택소노미(XBRL 기반 재무보고 분류체계) · Linkbase/링크베이스(개념 간 관계를 정의하는 계층) · ELR(Extended Link Role, 링크베이스 내 표현 그룹). 공통 용어는 [용어 사전](../README.md#용어-단일화-사전) 참조.

---

## 전체 구조 한눈에 보기

4개 링크베이스의 역할 분담: 

| 링크베이스                  | 역할                    | 결과물                     |
| --------------------------- | ----------------------- | -------------------------- |
| **Label Link**        | 개념에 이름 붙이기      | 노드(점) 생성              |
| **Presentation Link** | 재무제표 표시 계층      | 노드 간 엣지(선)           |
| **Calculation Link**  | 산술 계산 관계          | 노드 간 엣지(선) + weight  |
| **Definition Link**   | 차원/세그먼트 분해 구조 | 테이블-축-도메인-멤버 엣지 |

**Label Link가 먼저 노드를 만들고, 나머지 3개가 그 노드들 사이에 선을 긋는다.**

---

## 1. Label Link

### 파일 구조

```
행1: LinkRole  | http://www.xbrl.org/2003/role/link
행2: Definition|
행3:           |    ko    |    en          ← 언어 구분
행4: # | prefix | name | totalLabel | label | documentation | terseLabel | verboseLabel | dart_label | ...
행5~: 실제 데이터 (8,014행)
```

### 규모

| 항목                 | 수치                           |
| -------------------- | ------------------------------ |
| 전체 개념 수         | 8,014개                        |
| `ifrs-full` prefix | 5,242개 — 국제 IFRS 기준 개념 |
| `dart` prefix      | 2,686개 — 한국 DART 추가 개념 |
| `dart-gcd` prefix  | 86개 — 일반 기업공시 개념     |

### label 타입별 채움률

| label 타입        | ko             | en             | 용도                      |
| ----------------- | -------------- | -------------- | ------------------------- |
| `label`         | **100%** | **100%** | 기본 이름 → 핵심 필드    |
| `documentation` | **0%**   | 59%            | 개념 설명. ko는 없고 en만 |
| `totalLabel`    | 3%             | 3%             | 합계 표현 (자산총계 등)   |
| `terseLabel`    | 4%             | 4%             | 짧은 이름                 |
| `dart_label`    | 14%            | 14%            | DART 공시 화면 표시 이름  |

### 실제 데이터 예시

```
ifrs-full:Revenue
  [ko] label       : 수익(매출액)
  [ko] totalLabel  : 수익 합계
  [ko] terseLabel  : 영업수익
  [ko] dart_label  : 영업수익          ← DART 실무 표현
  [en] label       : Revenue
  [en] documentation: The income arising in the course of an entity's ordinary activities...

ifrs-full:Assets
  [ko] label       : 자산
  [ko] totalLabel  : 자산총계
  [en] label       : Assets
  [en] totalLabel  : Total assets

dart:PersonalExpense                   ← dart prefix = 한국 추가 개념
  [ko] label       : 인건비
  [ko] dart_label  : 인건비
  [en] label       : Personal expense
```

### 온톨로지 적용

Label Link는 엣지를 만들지 않는다. **Concept 노드의 속성**을 채운다.

```python
# Concept 노드
{
  "element_id": "ifrs-full:Revenue",
  "prefix":     "ifrs-full",
  "name":       "Revenue",
  "label_ko":   "수익(매출액)",    # 항상 존재
  "label_en":   "Revenue",        # 항상 존재
  "label_total_ko": "수익 합계",   # 3%만
  "label_dart": "영업수익",        # 14%만 — DART 화면 표시명
  "description": "The income arising..."  # en만, 59%
}
```

> **실무 팁**: `label_dart`가 있으면 우선 사용. DART 공시 시스템이 이 값을 화면에 표시하기 때문.

---

## 2. Presentation Link

### 파일 구조

ELR(섹션)이 연속으로 쌓이는 구조. **437개 ELR, 55,828행.**

```
행1: LinkRole  | http://dart.fss.or.kr/role/ifrs/dart_2024-06-30_role-D210000
행2: Definition| [D210000] 재무상태표, 유동/비유동법 - 연결
행3: prefix | name | label | depth | order | priority | parent | arcrole | ...
행4~: 계층 데이터
─────────────────────────────────────────────
행N: LinkRole  | ...D310000               ← 다음 섹션 시작
...
```

### ELR 목록 샘플

```
D210000: 재무상태표, 유동/비유동법 - 연결
D210005: 재무상태표, 유동/비유동법 - 별도
D220000: 재무상태표, 유동성배열법 - 연결
D310000: 손익계산서, 기능별 분류 - 연결
D320000: 손익계산서, 성격별 분류 - 연결
D410000: 포괄손익계산서, 세후 - 연결
...
```

표시 방식(유동/비유동법, 유동성배열법)과 연결/별도마다 별도 섹션이 있다.

### 실제 데이터 예시 — D210000 재무상태표

```
[depth=0] StatementOfFinancialPositionAbstract   재무상태표 [개요]
  [depth=1, order=1] AssetsAbstract              자산 [개요]
    [depth=2, order=1] CurrentAssets             유동자산
      [depth=3, order=1] CashAndCashEquivalents  현금및현금성자산
        [depth=4, order=1] Cash                  현금
        [depth=4, order=2] CashEquivalents       현금성자산
      [depth=3, order=3] ShorttermDeposits...    단기금융상품
      [depth=3, order=4] TradeAndOtherCurrent... 매출채권 및 기타유동채권
        [depth=4, order=1] ShortTermTradeReceivable  매출채권
        [depth=4, order=2] AllowanceForDoubtful...   대손충당금, 매출채권
        ...21개 하위 항목
```

| 컬럼            | 예시                         | 의미                |
| --------------- | ---------------------------- | ------------------- |
| `prefix:name` | `ifrs-full:CurrentAssets`  | Concept 노드 식별자 |
| `depth`       | `2`                        | 트리 깊이           |
| `order`       | `1`                        | 같은 부모 내 순서   |
| `parent`      | `ifrs-full:AssetsAbstract` | 부모 노드           |

### 온톨로지 적용

```python
# PRESENTS_AS 엣지
{
  "from": "ifrs-full:AssetsAbstract",
  "to":   "ifrs-full:CurrentAssets",
  "type": "PRESENTS_AS",
  "properties": {
    "elr":   "D210000",   # 어느 재무제표 섹션
    "order": 1,           # 형제 노드 중 순서
    "depth": 2,
  }
}
```

### RAG 활용 예

```
"유동자산에 포함되는 항목들 알려줘"
→ CurrentAssets 노드에서 PRESENTS_AS 엣지 하위 탐색
→ [현금및현금성자산, 단기금융상품, 매출채권 및 기타유동채권, ...]

"매출채권이 재무상태표 어디에 위치해?"
→ ShortTermTradeReceivable에서 부모 방향 역탐색
→ 매출채권 → 매출채권 및 기타유동채권 → 유동자산 → 자산
```

---

## 3. Calculation Link

### 파일 구조

Presentation Link와 동일한 ELR 패턴. **58개 ELR, 11,312행.**
Presentation(437개)보다 훨씬 적음 — 산술 관계가 정의된 섹션만 존재.

헤더: `prefix | name | label | depth | order | priority | weight | parent | arcrole | ...`

Presentation과 비교해 **`weight` 컬럼이 추가**된 것이 핵심.

### weight의 의미

| weight | 의미        | 예시                                 |
| ------ | ----------- | ------------------------------------ |
| `+1` | 부모에 더함 | 현금, 현금성자산 → 현금및현금성자산 |
| `-1` | 부모에서 뺌 | 대손충당금 → 매출채권 (차감 표시)   |

### 실제 데이터 예시

**재무상태표 — 차감 항목**

```
TradeAndOtherCurrentReceivables (매출채권 및 기타유동채권)
  weight=+1  ShortTermTradeReceivable          단기매출채권, 총액
  weight=-1  AllowanceForDoubtfulAccount...    대손충당금       ← 차감
  weight=+1  CurrentFinanceLeaseReceivables    단기금융리스채권
  weight=-1  AllowanceForDoubtful...Lease      대손충당금       ← 차감
```

**손익계산서 — 비용 항목**

```
GrossProfit (매출총이익)
  weight=+1  Revenue          수익(매출액)
  weight=-1  CostOfSales      매출원가          ← 비용이라 -1

OperatingIncomeLoss (영업이익)
  weight=+1  GrossProfit      매출총이익
  weight=-1  TotalSGA...      판매비와관리비    ← 비용이라 -1

ProfitLossBeforeTax (법인세비용차감전순이익)
  weight=+1  OperatingIncomeLoss
  weight=-1  FinanceCosts          금융원가     ← -1
  weight=-1  OtherLosses           기타손실     ← -1

ProfitLossFromContinuingOperations (계속영업이익)
  weight=+1  ProfitLossBeforeTax
  weight=-1  IncomeTaxExpense      법인세비용   ← -1
```

### Presentation vs Calculation 비교

같은 `Assets → CurrentAssets` 관계가 두 곳에 모두 존재. 역할이 다름.

|           | Presentation             | Calculation              |
| --------- | ------------------------ | ------------------------ |
| 목적      | 어떻게**보여줄까** | 어떻게**계산할까** |
| 핵심 정보 | depth, order             | weight (±1)             |
| 용도      | 재무제표 화면 배치       | 산술 검증 / 공식 추출    |

### 온톨로지 적용

```python
# CALCULATED_FROM 엣지
{
  "from":   "ifrs-full:TradeAndOtherCurrentReceivables",
  "to":     "ifrs-full:ShortTermTradeReceivable",
  "type":   "CALCULATED_FROM",
  "properties": {"weight": +1, "elr": "D210000"}
}
{
  "from":   "ifrs-full:TradeAndOtherCurrentReceivables",
  "to":     "ifrs-full:AllowanceForDoubtfulAccount...",
  "type":   "CALCULATED_FROM",
  "properties": {"weight": -1, "elr": "D210000"}   # 차감
}
```

### RAG 활용 예

```
"매출채권 순액이 어떻게 계산돼?"
→ weight=+1 항목들 합산 - weight=-1 항목들

"영업이익에서 당기순이익까지 어떤 항목이 차감되나?"
→ Calculation 그래프 탐색, weight=-1 항목 수집
→ [판매비와관리비, 금융원가, 기타손실, 법인세비용]
```

---

## 4. Definition Link

### 파일 구조

**1,418개 ELR, 64,902행.** 가장 크다.

헤더: `prefix | name | label | depth | order | priority | parent | arcrole | targetRole | usable | closed | contextElement | ...`

앞의 두 링크베이스와 달리 **5가지 arcrole**이 조합돼서 구조를 표현한다.

### 5가지 arcrole

| arcrole                 | 건수     | 의미                       |
| ----------------------- | -------- | -------------------------- |
| `domain-member`       | 47,498건 | 트리 계층 (도메인 → 멤버) |
| `hypercube-dimension` | 3,563건  | 테이블 → 축 연결          |
| `dimension-domain`    | 3,560건  | 축 → 도메인 연결          |
| `all`                 | 1,417건  | 개념 → 테이블 연결        |
| `dimension-default`   | 197건    | 축의 기본값 지정           |

### 실제 데이터 예시 — D871100a 영업부문

```
[all] 개념 → 테이블
  DisclosureOfOperatingSegmentsAbstract (영업부문 공시)
    --all--> DisclosureOfOperatingSegmentsTable [표]  (closed=true, ctx=segment)

[hypercube-dimension] 테이블 → 축
  DisclosureOfOperatingSegmentsTable
    ├── --hypercube-dimension--> SegmentsAxis                          부문 [축]
    ├── --hypercube-dimension--> SegmentConsolidationItemsAxis         합계 [축]
    └── --hypercube-dimension--> ConsolidatedAndSeparateFinancialStatementsAxis  연결/별도 [축]

[dimension-domain] 축 → 도메인
  SegmentsAxis                       --dimension-domain--> SegmentsMember [부문 도메인]
  SegmentConsolidationItemsAxis      --dimension-domain--> EntitysTotalForSegmentConsolidationItemsMember

[domain-member] 도메인 → 멤버
  SegmentsMember
    ├── ReportableSegmentsMember     보고부문
    └── AllOtherSegmentsMember       기타부문

  EntitysTotalForSegmentConsolidationItemsMember
    ├── OperatingSegmentsMember      영업부문
    └── MaterialReconcilingItemsMember  조정사항
          ├── EliminationOfIntersegmentAmountsMember  부문간 제거
          └── UnallocatedAmountsMember                미배분액

보고 항목 (domain-member of LineItems):
  ├── Revenue             수익(매출액)
  ├── InterestExpense     이자비용
  └── DepreciationAndAmortisationExpense  감가상각비
```

**D210000 재무상태표의 경우** (단순한 케이스):

```
[all] StatementOfFinancialPositionAbstract
        --all--> ConsolidatedAndSeparateFinancialStatementsTable
[hypercube-dimension] Table --> ConsolidatedAndSeparateFinancialStatementsAxis
[dimension-domain]   Axis   --> ConsolidatedAndSeparateFinancialStatementsDomain
[domain-member]      Domain --> ConsolidatedMember (연결), SeparateMember (별도)
```

### 온톨로지 적용

5가지 arcrole이 각각 별도 엣지 타입이 된다:

```python
(영업부문공시) -[REPORTED_IN]->   (영업부문테이블)          # all
(영업부문테이블) -[HAS_AXIS]->    (SegmentsAxis)            # hypercube-dimension
(SegmentsAxis) -[HAS_DOMAIN]->   (SegmentsMember)          # dimension-domain
(SegmentsMember) -[HAS_MEMBER]-> (ReportableSegmentsMember) # domain-member
(연결별도축) -[DEFAULT_MEMBER]->  (ConsolidatedMember)      # dimension-default
```

### RAG 활용 예

```
"영업부문별 매출액 보고 구조가 어떻게 돼?"
→ DisclosureOfOperatingSegmentsTable 탐색
→ 축: SegmentsAxis → [보고부문, 기타부문]
→ 보고 항목: Revenue, InterestExpense, Depreciation...

"연결/별도 재무제표 구분은 어디서 하나?"
→ ConsolidatedAndSeparateFinancialStatementsAxis
→ 멤버: ConsolidatedMember, SeparateMember
→ default: ConsolidatedMember (명시 없으면 연결 기준)
```

---

## 전체 온톨로지 설계 요약

### 노드 타입

| 노드          | 출처            | 예시                                    |
| ------------- | --------------- | --------------------------------------- |
| `Concept`   | Label Link      | ifrs-full:Revenue, dart:PersonalExpense |
| `Hypercube` | Definition Link | DisclosureOfOperatingSegmentsTable      |
| `Axis`      | Definition Link | SegmentsAxis                            |
| `Domain`    | Definition Link | SegmentsMember                          |
| `Member`    | Definition Link | ReportableSegmentsMember                |

### 엣지 타입

| 엣지                | 출처                             | 주요 속성              |
| ------------------- | -------------------------------- | ---------------------- |
| `PRESENTS_AS`     | Presentation                     | elr, order, depth      |
| `CALCULATED_FROM` | Calculation                      | elr, weight(±1)       |
| `REPORTED_IN`     | Definition (all)                 | closed, contextElement |
| `HAS_AXIS`        | Definition (hypercube-dimension) | —                     |
| `HAS_DOMAIN`      | Definition (dimension-domain)    | —                     |
| `HAS_MEMBER`      | Definition (domain-member)       | —                     |
| `DEFAULT_MEMBER`  | Definition (dimension-default)   | —                     |

### 3개 링크베이스 비교

|           | Presentation          | Calculation           | Definition            |
| --------- | --------------------- | --------------------- | --------------------- |
| 핵심 질문 | 어디에**표시**? | 어떻게**계산**? | 어떻게**분해**? |
| 구조      | 단순 트리             | 트리 + weight         | 테이블-축-도메인-멤버 |
| ELR 수    | 437개                 | 58개                  | 1,418개               |
| 행 수     | 55,828                | 11,312                | 64,902                |

---

## 변경 이력

| 날짜       | 내용                               |
| ---------- | ---------------------------------- |
| 2026-04-03 | 초기 작성. xlsx 실데이터 기반 분석 |
