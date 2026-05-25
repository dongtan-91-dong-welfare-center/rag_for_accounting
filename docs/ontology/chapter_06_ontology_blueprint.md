# 제6장 금융자산·금융부채 온톨로지 설계안

대상 원문: `data/llm_parsed/제6장_금융자산·금융부채(수정목록_19-1_반영).md`

이 문서는 제6장 MD 파일을 기준으로 온톨로지를 다시 만들기 위한 설계 기준이다. 기존 산출물처럼 조항을 개념에 단순 연결하는 방식은 회계 규정의 조건, 예외, 처리 순서, 측정 기준, 공시 요구를 충분히 표현하지 못한다. 제6장은 `Rule` 중심으로 모델링해야 한다.

공통 노드, 공통 엣지, 필수 속성, part taxonomy, `extraction_status`, 실패 조건 중심 품질 기준은 `docs/ontology/common_schema.md`를 따른다. 이 문서는 공통 스키마를 반복하지 않고 제6장 특화 Rule과 추출 패턴을 정의한다.

## 1. 핵심 방향

제6장은 다음 질문에 답할 수 있어야 한다.

- 어떤 금융상품에 어떤 회계처리가 적용되는가?
- 어떤 조건을 충족하면 인식, 제거, 분류, 재분류, 측정, 손상, 공시가 발생하는가?
- 원칙 규정의 예외는 무엇인가?
- 측정 기준이 공정가치, 상각후원가, 취득원가 중 무엇이며 어떤 조건에서 바뀌는가?
- 위험회피회계에서 위험회피수단, 위험회피대상항목, 회피대상위험, 회계처리는 어떻게 연결되는가?
- 채권·채무조정에서 채무자와 채권자의 처리가 어떻게 다른가?
- 적용보충기준, 실무지침, 사례가 어느 본문 조항을 설명하는가?

따라서 `Clause -> Concept`만 만들지 말고, 조항에서 추출한 규범 단위를 `Rule` 노드로 만들고 그 Rule이 대상, 조건, 예외, 회계처리, 측정기준, 표시·공시 항목에 연결되도록 한다.

## 2. 문서 파트 분리

MD 파일은 하나지만 성격이 다른 파트가 섞여 있다.

| part | 존재 여부 | 범위 | 역할 |
|---|---|---|---|
| `main` | present | 6.1~6.102 | 본문 기준. 법적/규범적 규칙의 1차 출처 |
| `terms` | present | 용어의 정의 섹션 | 개념 노드 정의의 1차 출처 |
| `application_guidance` | present | 6.A1~6.A26, 6.A1의2 등 | 본문 기준 보충. 본문 조항을 설명하거나 세부 판단기준 제공 |
| `basis_for_conclusions` | present | 결6.* | 결론도출근거. 규정 이유, 판단 배경 |
| `practical_guidance` | present | 실6.* | 실무 적용 지침. 본문 조항의 해석·예시·판단기준 |
| `example` | present | 사례2~사례24 등 | 사례 기반 적용. 계산, 분개, 판단 흐름 |

모든 Clause에는 공통 스키마의 필수 속성을 유지한다. `main`과 나머지 파트는 같은 번호 체계처럼 보여도 의미가 다르므로 반드시 구분한다.

## 3. 기본 노드 모델

### 3.1 문서 구조 노드

```json
{
  "id": "clause_6_30",
  "type": "Clause",
  "label": "문단 6.30",
  "properties": {
    "part": "main",
    "clause_number": "6.30",
    "section": "제2절 유가증권",
    "topic": "유가증권의 최초 측정과 후속 측정",
    "source_text": "단기매매증권과 매도가능증권은 공정가치로 평가한다..."
  }
}
```

문서 구조는 `Chapter -> Section -> TopicGroup -> Clause -> SubClause`로 유지한다. 다만 `SubClause`를 단순 텍스트로만 붙이지 말고 `(1)`, `(2)`, `(가)`, `(나)`처럼 조건·예외·공시 항목이 열거되는 경우 독립 노드로 만들 수 있어야 한다.

### 3.2 도메인 개념 노드

제6장에는 최소한 다음 개념군이 필요하다.

| 개념군 | 예시 |
|---|---|
| 금융상품 | 금융상품, 금융자산, 금융부채 |
| 유가증권 | 유가증권, 지분증권, 채무증권, 만기보유증권, 단기매매증권, 매도가능증권 |
| 파생상품 | 파생상품, 내재파생상품, 복합계약, 주계약 |
| 측정기준 | 공정가치, 상각후원가, 취득원가, 현재가치, 거래가격 |
| 손익·자본 항목 | 당기손익, 기타포괄손익누계액, 미실현보유손익, 처분손익, 손상차손, 대손상각비, 채무조정이익 |
| 위험 | 신용위험, 유동성위험, 시장위험, 이자율위험, 외화위험, 가격위험, 현금흐름변동위험, 공정가치변동위험 |
| 위험회피 | 위험회피회계, 공정가치위험회피, 현금흐름위험회피, 순투자위험회피, 위험회피수단, 위험회피대상항목 |
| 채권·채무조정 | 채권자, 채무자, 조정대상채무, 출자전환채무, 출자전환채권, 조건변경, 자산이전, 지분증권 발행 |
| 공시 | 주석공시, 만기분석, 담보제공내역, 재분류정보, 신용파생상품 공시 |

개념 노드는 장마다 중복 생성하지 말고 전역 개념으로 관리하는 것이 좋다. 장 파일에는 조항·규칙·사례 노드와 전역 개념 ID를 참조하는 엣지를 둔다.

## 4. Rule 중심 모델

규칙은 조항보다 작은 의미 단위다. 하나의 조항에 여러 규칙이 들어갈 수 있다. 예를 들어 6.30은 두 개 이상의 측정 규칙으로 나눠야 한다.

### 4.1 공통 Rule 속성

모든 Rule 노드는 다음 속성을 갖는다.

```json
{
  "id": "rule_6_30_01",
  "type": "MeasurementRule",
  "label": "단기매매증권과 매도가능증권의 공정가치 평가",
  "properties": {
    "source_clause": "6.30",
    "source_text": "단기매매증권과 매도가능증권은 공정가치로 평가한다.",
    "condition_text": "",
    "exception_text": "",
    "polarity": "include",
    "modality": "shall",
    "part": "main",
    "extraction_status": "auto",
    "extraction_method": "rule+llm"
  }
}
```

### 4.2 Rule 타입

| Rule 타입 | 목적 | 예시 조항 |
|---|---|---|
| `ScopeRule` | 적용 범위·적용 제외 | 6.2, 6.3, 6.19, 6.82, 6.83 |
| `DefinitionRule` | 정의·분류 요건 | 6.20, 6.23, 6.36, 6.84 |
| `RecognitionRule` | 인식 규칙 | 6.4, 6.4의2, 6.39, 6.87, 6.88 |
| `DerecognitionRule` | 제거 규칙 | 6.5~6.11, 6.34의2, 6.34의3 |
| `ClassificationRule` | 분류·재분류 | 6.22~6.27, 6.34 |
| `MeasurementRule` | 최초·후속 측정 | 6.12~6.16, 6.29, 6.30, 6.90, 6.98 |
| `ImpairmentRule` | 손상·대손 | 6.17의2, 6.32, 6.33, 6.97, 6.98 |
| `PresentationRule` | 표시 | 6.8, 6.40 |
| `DisclosureRule` | 공시 | 6.18, 6.18의2, 6.35, 6.81, 6.94, 6.100~6.102 |
| `HedgeRule` | 위험회피 관계·조건·처리 | 6.48~6.79 |
| `DebtRestructuringRule` | 채권·채무조정 처리 | 6.85~6.99 |
| `ExceptionRule` | 원칙의 예외·적용 배제 | 6.2, 6.14, 6.26, 6.30, 6.38, 6.43, 6.47 |

## 5. 관계 타입

### 5.1 필수 관계

| 관계 | 방향 | 의미 |
|---|---|---|
| `HAS_RULE` | Clause -> Rule | 조항이 규칙을 포함 |
| `APPLIES_TO` | Rule -> Concept | 규칙 적용 대상 |
| `EXCLUDES` | Rule -> Concept/Clause | 적용 제외 대상 |
| `HAS_CONDITION` | Rule -> Condition | 성립 조건 |
| `HAS_EXCEPTION` | Rule -> ExceptionRule | 예외 |
| `MEASURED_BY` | MeasurementRule -> MeasurementBasis | 측정 기준 |
| `RECOGNIZES_AS` | Rule -> AccountingItem | 인식 항목 |
| `DERECOGNIZES` | DerecognitionRule -> Concept | 제거 대상 |
| `CLASSIFIES_AS` | ClassificationRule -> Concept | 분류 결과 |
| `RECLASSIFIES_TO` | ClassificationRule -> Concept | 재분류 결과 |
| `DISCLOSES` | DisclosureRule -> DisclosureItem/Concept | 공시 대상 |
| `HEDGES` | HedgeRule -> Risk | 회피 대상 위험 |
| `USES_HEDGING_INSTRUMENT` | HedgeRule -> Concept | 위험회피수단 |
| `HAS_HEDGED_ITEM` | HedgeRule -> Concept | 위험회피대상항목 |
| `REFERENCES` | Clause/Rule -> Clause/Section/Chapter | 명시 참조 |
| `ILLUSTRATES` | Example -> Clause/Rule | 사례가 설명하는 기준 |
| `SUPPLEMENTS` | Guidance -> Clause/Rule | 적용보충기준·실무지침이 본문을 보강 |
| `BASIS_FOR` | Basis -> Clause/Rule | 결론도출근거가 본문 기준의 배경이나 이유를 설명 |

### 5.2 관계 속성

모든 의미 관계에는 다음 속성을 넣는다.

```json
{
  "source_text": "문단에서 관계를 뒷받침하는 원문",
  "paragraph": "6.30",
  "subparagraph": "(1)",
  "polarity": "include | exclude | exception | prohibit | require",
  "condition": "조건 텍스트",
  "reference_type": "scope | applies | exception | measurement | disclosure | basis | example",
  "extraction_status": "auto",
  "extraction_method": "regex | rule | llm | manual"
}
```

`source_text`는 관계마다 다르게 가져가야 한다. 조항 전체를 넣으면 관계의 근거가 흐려진다.

## 6. 제6장 핵심 추출 패턴

### 6.1 적용 범위와 제외

6.2는 단순 `APPLIES_TO FinancialInstrument`가 아니다. 원칙과 예외가 동시에 있다.

필요 구조:

- `ScopeRule`: 모든 유형의 금융상품에 적용
- `EXCLUDES`: 종속기업·관계기업·조인트벤처 투자지분, 리스 권리와 의무, 퇴직급여, 발행자 지분상품, 보험계약, 사업결합계약, 대출약정 등
- `ExceptionRule`: 리스채권의 제거와 손상, 금융리스부채의 제거, 리스 내재파생상품, 보험계약 내재파생상품은 다시 적용

즉 `제외`와 `다만 적용`을 별도 Rule로 분리해야 한다.

### 6.2 제거 규칙

6.5는 금융자산 양도 판단이다.

- 대상: 금융자산. 단, 제2절 유가증권 적용대상 금융자산은 제외
- 조건: 6.5(1)~(3)을 모두 충족
- 결과: 매각거래
- 반대 결과: 담보 차입거래

필요 Rule:

```json
{
  "type": "DerecognitionRule",
  "source_clause": "6.5",
  "all_conditions": ["6.5(1)", "6.5(2)", "6.5(3)"],
  "result_when_true": "SaleTransaction",
  "result_when_false": "SecuredBorrowing"
}
```

6.8의2~6.11은 금융부채 제거 규칙이다. `소멸`, `법적 면제`, `조건이 실질적으로 변경`, `장부금액과 지급대가 차액은 당기손익`을 별도 Rule로 뽑는다.

### 6.3 측정 규칙

측정 규칙은 `대상 + 측정기준 + 조건 + 예외`를 한 묶음으로 만든다.

6.12:

- 금융자산·금융부채 최초인식: 공정가치
- 예외: 최초인식 이후 공정가치 측정 및 변동 당기손익 인식 대상이 아닌 경우 거래원가를 가산/차감
- 현금흐름위험회피회계에서 위험회피수단으로 지정되는 파생상품은 예외 구조 안에 다시 예외가 있음

6.14:

- 원칙: 금융자산·금융부채 후속측정은 상각후원가
- 제외: 제2절~제4절 대상인 유가증권, 파생상품, 채권·채무조정
- 예외: 당기손익인식지정항목은 6.30~6.31의 단기매매증권 후속측정 준용

6.29:

- 만기보유증권: 상각후원가

6.30:

- 단기매매증권: 공정가치
- 매도가능증권: 공정가치
- 예외: 시장성 없는 지분증권이고 공정가치를 신뢰성 있게 측정할 수 없는 경우 취득원가

6.90~6.91:

- 조건변경으로 채무 조정 시 미래 현금흐름을 유효이자율로 할인한 현재가치와 장부금액의 차이를 현재가치할인차금 및 채무조정이익으로 인식
- 시장이자율 차이가 현저한 경우 6.91의 적절한 이자율 사용

6.98:

- 조건변경된 채권의 대손상각비는 미래 현금흐름 현재가치와 대손충당금 차감전 장부금액의 차이
- 예외: 시장가격 또는 담보자산 공정가치 기반 측정 가능

### 6.4 유가증권 분류·재분류

6.22~6.27은 분류 규칙이다.

- 유가증권은 만기보유증권, 단기매매증권, 매도가능증권 중 하나
- 만기보유증권 조건: 만기 확정, 상환금액 확정/확정 가능, 만기까지 보유할 적극적 의도와 능력
- 만기보유 불가: 6.24 조건
- 만기보유 분류 제한: 6.25
- 6.26은 6.25의 예외
- 지분증권과 만기보유증권이 아닌 채무증권은 단기매매증권 또는 매도가능증권

6.34는 재분류 규칙이다.

- 원칙: 단기매매증권은 다른 범주로 재분류 불가, 다른 범주도 단기매매증권으로 재분류 불가
- 예외: 드문 상황에서는 단기매매증권을 매도가능증권이나 만기보유증권으로 분류 가능
- 시장성 상실 시 매도가능증권으로 분류해야 함
- 매도가능증권과 만기보유증권은 상호 재분류 가능
- 재분류일 현재 공정가치로 평가 후 변경

이 조항은 단순 `REGULATES Reclassification`이 아니라 금지/허용/강제/측정을 각각 Rule로 분리한다.

### 6.5 파생상품과 내재파생상품

6.36~6.38:

- 파생상품 정의는 3개 조건을 모두 충족해야 함
- 6.38은 적용대상 제외

6.39~6.40:

- 권리와 의무를 자산·부채로 인식
- 공정가치 평가
- 매매목적 평가손익은 당기손익
- 위험회피수단 지정 시 위험회피유형별 처리
- 총액 표시, 상계 금지

6.41~6.47:

- 내재파생상품 분리 조건 3개
- 주계약이 금융상품이면 제6장, 아니면 다른 기준 적용
- 최초 검토 후 후속 재검토 금지, 단 6.43(1)~(3) 예외
- 분리 측정 불가 시 복합계약 전체를 당기손익인식지정항목
- 재분류 금지 조건
- 복합계약 전체 공정가치 평가 지정 가능, 단 6.47(1)~(2) 제외

필요 노드:

- `EmbeddedDerivativeSeparationRule`
- `HybridContractDesignationRule`
- `ReassessmentProhibitionRule`
- `ReclassificationProhibitionRule`

### 6.6 위험회피회계

위험회피회계는 별도 서브온톨로지로 다뤄야 한다.

필수 개념:

- `HedgingInstrument`
- `HedgedItem`
- `HedgedRisk`
- `FairValueHedge`
- `CashFlowHedge`
- `NetInvestmentHedge`
- `HedgeEffectiveness`
- `ForecastTransaction`
- `FirmCommitment`

6.49:

- 공정가치위험회피: 자산·부채·확정계약의 공정가치변동위험 상계
- 현금흐름위험회피: 자산·부채·예상거래의 미래현금흐름변동위험 상계
- 해외사업장순투자 위험회피

6.50~6.59:

- 위험회피대상항목 조건
- 예상거래는 발생가능성이 매우 높고 제3자 외부거래
- 금융상품 관련 예상거래는 시장이자율변동위험, 환율변동위험, 신용변동위험 가능
- 공정가치 평가손익을 당기손익으로 인식하는 자산·부채는 위험회피대상 제외
- 만기보유목적 투자채권은 신용위험·외화위험 위험회피 인정, 이자율변동위험 위험회피 불인정

6.60~6.65:

- 파생상품은 위험회피수단 가능
- 비파생금융자산·부채는 외화위험회피에만 위험회피수단 가능
- 신뢰성 있게 공정가치를 측정할 수 없는 지분상품은 위험회피수단 불가

6.66:

- 위험회피회계 적용조건 5개. 모두 충족해야 함

6.68~6.79:

- 공정가치위험회피 처리
- 현금흐름위험회피 처리
- 순투자 위험회피 처리
- 중단 조건
- 기타포괄손익누계액/당기손익/자산·부채 장부금액 조정 연결 필요

위험회피는 반드시 다음 그래프 형태가 필요하다.

```json
{
  "type": "HedgeRule",
  "source_clause": "6.68",
  "hedge_type": "FairValueHedge",
  "condition": "문단 6.66의 조건을 충족하는 경우",
  "hedging_instrument_accounting": "평가손익을 당기손익",
  "hedged_item_accounting": "특정위험으로 인한 평가손익을 당기손익",
  "references": ["6.66"]
}
```

### 6.7 채권·채무조정

제4절은 채무자와 채권자를 분리해야 한다. 같은 사건이라도 양쪽 회계처리가 다르다.

필수 축:

- 역할: `Debtor`, `Creditor`
- 조정 방식: `AssetTransfer`, `EquityIssuance`, `TermsModification`, `Combination`
- 측정 기준: 공정가치, 현재가치, 유효이자율
- 인식 결과: 채무조정이익, 대손상각비, 대손충당금, 출자전환채무, 출자전환채권

6.85:

- 채권·채무조정시점 판단
- 합의일/법원인가일 원칙
- 조건 미충족 시 실질 완료 시점

6.86~6.94: 채무자 회계

- 자산이전: 채무 장부금액과 이전자산 공정가치 차이 -> 채무조정이익
- 지분증권 발행: 지분증권 공정가치와 채무 장부금액 차이 -> 채무조정이익
- 시장성 없는 지분증권 공정가치 신뢰성 측정 불가 시 예외
- 출자전환채무 자본조정 대체
- 조건변경: 미래 현금흐름 현재가치와 채무 장부금액 차이
- 결합 방식: 자산·지분 공정가치만큼 먼저 차감 후 나머지 조건변경 처리
- 공시: 조건변경, 변제액, 자산처분손익, 추가 금액, 우발 채무, 출자전환채무

6.95~6.102: 채권자 회계

- 자산·지분증권 수취: 공정가치로 회계처리
- 공정가치가 장부금액보다 작으면 대손충당금 우선 상계, 부족분 대손상각비
- 출자전환채권: 장부금액과 전환 주식 공정가치 중 낮은 금액
- 조건변경 채권: 공식 조정 전이라도 인식조건 충족 시 대손상각비 인식
- 미래 현금흐름 현재가치와 대손충당금 차감전 장부금액 차이 계산
- 공시: 대손충당금 변동, 추가 대여 약정, 출자전환채권

## 7. 사례와 보충 문단 연결

사례는 단순 `Example` 노드가 아니라 계산·분개·판단 흐름을 가진다. 최소한 다음 속성을 둔다.

```json
{
  "id": "example_6_case10",
  "type": "Example",
  "properties": {
    "case_number": "사례10",
    "topic": "공정가치위험회피회계/이자율스왑 거래",
    "part": "example",
    "related_clause_numbers": ["6.66", "6.67", "6.68", "6.69", "6.70"],
    "scenario": "사례 조건 요약",
    "solution_summary": "풀이 요약"
  }
}
```

사례 연결은 제목의 `(문단 X)`만 의존하면 안 된다. 제목에 문단이 없더라도 아래 키워드로 관련 조항을 추정해야 한다.

| 사례 | 연결 후보 |
|---|---|
| 사례2 매도가능증권을 만기보유증권으로 재분류 | 6.34, 6.A19, 6.A20 |
| 사례3 유가증권 대차거래 | 실6.72~실6.73, 6.5~6.7 |
| 사례4 자사주펀드 | 실6.66~실6.67 |
| 사례5 통화선도 매매목적 | 6.39, 6.80 |
| 사례6 공정가치위험회피 통화선도 | 6.66~6.70 |
| 사례8 공정가치위험회피 확정계약 | 6.49, 6.66~6.70 |
| 사례9 현금흐름위험회피 | 6.72~6.78 |
| 사례10 이자율스왑 공정가치위험회피 | 6.66~6.70 |
| 사례12 통화스왑 현금흐름위험회피 | 6.72~6.78 |
| 사례18~24 채권·채무조정 | 6.85~6.99, 실6.139~실6.153 |

보충 문단 연결:

- `6.A*`는 본문 조항을 보충하므로 `SUPPLEMENTS`를 사용한다.
- `실6.*`는 제목에 `(문단 6.X)`가 있으면 해당 본문 조항에 `SUPPLEMENTS`.
- `결6.*`는 괄호의 `(문단 6.X)` 또는 문장 내 참조를 기준으로 `BASIS_FOR`.

## 8. 추출 단계

### 8.1 1단계: 구조 파싱

1. page marker 저장
2. heading level로 Chapter/Section/TopicGroup/Clause/SubClause 추출
3. `main`, `application_guidance`, `terms`, `practical_guidance`, `basis_for_conclusions`, `example` part 판정
4. 중복 조항 번호는 part를 기준으로 구분
5. 삭제 조항은 `is_deleted=true`로 유지하되 규칙 추출에서 제외

### 8.2 2단계: 개념 사전 매핑

용어의 정의 섹션을 우선 사용하여 개념 노드를 만든다. 이후 본문·부록에서 출현하는 용어를 alias로 연결한다.

예:

```json
{
  "id": "TradingSecurity",
  "label_ko": "단기매매증권",
  "aliases": ["단기매매증권", "매매목적 유가증권"],
  "parent": "Security"
}
```

### 8.3 3단계: 규칙 추출

조항별로 다음 순서로 규칙을 추출한다.

1. 문장의 행위 동사 식별: 적용한다, 제외한다, 인식한다, 제거한다, 평가한다, 분류한다, 공시한다, 금지된다, 대체한다
2. 대상 식별
3. 조건 식별: `경우`, `요건`, `충족`, `한하여`, `때`, `시점`
4. 예외 식별: `다만`, `제외`, `적용하지 아니한다`, `금지`, `아니다`
5. 결과 식별: 측정기준, 손익항목, 자산/부채/자본 항목, 공시 항목
6. 명시 참조 추출

### 8.4 4단계: 후처리 검증

다음 검증을 통과하지 못하면 산출물을 실패로 본다.

- `다만`, `제외`, `적용하지 아니한다`가 있는 조항에는 `ExceptionRule` 또는 `EXCLUDES`가 있어야 한다.
- `측정`, `평가`, `공정가치`, `상각후원가`, `취득원가`가 있는 조항에는 `MeasurementRule`이 있어야 한다.
- `공시`, `주석`이 있는 조항에는 `DisclosureRule` 또는 `DISCLOSES`가 있어야 한다.
- `위험회피`가 있는 조항에는 `HedgeRule`이 있어야 한다.
- `문단 X`, `제N절`, `제N장`이 있는 문장에는 `REFERENCES`가 있어야 한다.
- 사례 노드는 원문에서 본문 또는 실무지침 적용을 설명하는 경우 하나 이상의 본문/실무지침 조항에 `ILLUSTRATES`로 연결되어야 한다.
- 모든 의미 엣지에는 `source_text`, `paragraph`, `polarity`, `extraction_status`, `extraction_method`가 있어야 한다.

## 9. 산출 JSON 예시

### 9.1 6.30 측정 규칙

```json
{
  "nodes": [
    {
      "id": "rule_6_30_01",
      "type": "MeasurementRule",
      "label": "단기매매증권의 공정가치 평가",
      "properties": {
        "source_clause": "6.30",
        "source_text": "단기매매증권과 매도가능증권은 공정가치로 평가한다.",
        "condition_text": "",
        "polarity": "include"
      }
    },
    {
      "id": "rule_6_30_02",
      "type": "MeasurementRule",
      "label": "매도가능증권의 공정가치 평가",
      "properties": {
        "source_clause": "6.30",
        "source_text": "단기매매증권과 매도가능증권은 공정가치로 평가한다.",
        "condition_text": "",
        "polarity": "include"
      }
    },
    {
      "id": "rule_6_30_03",
      "type": "MeasurementRule",
      "label": "시장성 없는 지분증권의 취득원가 평가",
      "properties": {
        "source_clause": "6.30",
        "source_text": "다만, 매도가능증권 중 시장성이 없는 지분증권의 공정가치를 신뢰성있게 측정할 수 없는 경우에는 취득원가로 평가한다.",
        "condition_text": "매도가능증권 중 시장성이 없는 지분증권이고 공정가치를 신뢰성 있게 측정할 수 없는 경우",
        "polarity": "exception"
      }
    }
  ],
  "edges": [
    {"source": "clause_6_30", "type": "HAS_RULE", "target": "rule_6_30_01"},
    {"source": "rule_6_30_01", "type": "APPLIES_TO", "target": "TradingSecurity"},
    {"source": "rule_6_30_01", "type": "MEASURED_BY", "target": "FairValue"},
    {"source": "rule_6_30_03", "type": "APPLIES_TO", "target": "EquityInstrument"},
    {"source": "rule_6_30_03", "type": "MEASURED_BY", "target": "CostMethod"},
    {"source": "rule_6_30_03", "type": "EXCEPTION_OF", "target": "rule_6_30_02"}
  ]
}
```

### 9.2 6.66 위험회피 적용조건

```json
{
  "id": "rule_6_66_hedge_accounting_conditions",
  "type": "HedgeRule",
  "properties": {
    "source_clause": "6.66",
    "requirement_mode": "all",
    "conditions": [
      "위험회피 종류, 위험관리 목적, 위험회피전략을 공식 문서화",
      "높은 위험회피효과 기대",
      "현금흐름위험회피 예상거래 발생가능성이 매우 높음",
      "위험회피효과를 신뢰성 있게 측정 가능",
      "위험회피기간에 계속 평가"
    ]
  }
}
```

### 9.3 6.85 채권·채무조정 시점

```json
{
  "id": "rule_6_85_restructuring_date",
  "type": "DebtRestructuringRule",
  "properties": {
    "source_clause": "6.85",
    "subject": "DebtRestructuringDate",
    "default_rule": "합의일 또는 법원 인가일",
    "exception": "약정 조건이 충족되지 않아 사건이 이루어지지 않으면 실질 완료 시점"
  }
}
```

## 10. 구현 우선순위

1. 문서 구조 파서 안정화
2. 전역 개념 registry에 대한 제6장 alias/mapping 구축
3. `Rule` 노드 타입과 관계 타입 확정
4. 본문 6.1~6.102만 먼저 규칙 추출
5. 6.A, 실6, 결6, 사례는 본문 연결 위주로 2차 추출
6. 품질검증 리포트 자동 생성
7. GraphRAG 검색에서는 `Clause`가 아니라 `Rule`을 1차 검색 단위로 사용

## 11. 최소 품질 기준

제6장 온톨로지 산출물은 다음 기준을 만족해야 한다.

- 본문 조항 6.1~6.102 중 삭제 조항을 제외하고 원칙·조건·예외·측정·표시·공시 의미가 있는 조항은 모두 하나 이상의 Rule을 가져야 한다.
- 측정 관련 조항은 모두 측정기준, 측정시점, 후속측정 중 해당 요소를 명시한 `MeasurementRule`을 가져야 한다.
- 공시 관련 조항은 모두 `DisclosureRule`을 가져야 한다.
- 예외 표현 조항은 모두 `ExceptionRule`, `EXCLUDES`, `HAS_EXCEPTION` 중 하나를 가져야 한다.
- 위험회피회계 조항 6.48~6.79는 모두 `HedgeRule` 또는 위험회피 관련 관계를 가져야 한다.
- 채권·채무조정 조항 6.82~6.102는 채무자/채권자 역할이 구분되어야 한다.
- 사례는 원문에서 본문 또는 실무지침 적용을 설명하는 경우 모두 관련 조항에 `ILLUSTRATES`로 연결되어야 한다.
- 모든 의미 엣지는 빈 properties를 허용하지 않는다.

## 12. 다른 장으로 확장할 때의 원칙

다른 장도 같은 방식으로 처리하되, 개념은 전역 registry로 관리하고 장별 문서에는 alias/mapping만 둔다. 공통 구조는 `common_schema.md`를 유지하고 Rule 타입을 장 특성에 맞게 추가한다.

| 장 | 추가 개념·규칙 예시 |
|---|---|
| 제7장 재고자산 | Inventory, NetRealizableValue, CostFormula, WriteDownRule |
| 제10장 유형자산 | PropertyPlantEquipment, DepreciationRule, RevaluationRule |
| 제13장 리스 | Lessee, Lessor, FinanceLease, OperatingLease, LeaseClassificationRule |
| 제16장 수익 | RevenueRecognitionRule, ConstructionContractRule, ProgressMeasurement |
| 제22장 법인세 | TemporaryDifference, DeferredTaxAsset, DeferredTaxLiability |

핵심은 장별 키워드만 늘리는 것이 아니라, 해당 장에서 반복되는 판단 구조를 Rule로 먼저 정의한 뒤 조항을 매핑하는 것이다.
