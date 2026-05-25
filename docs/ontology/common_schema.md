# 온톨로지 공통 스키마

이 문서는 `docs/ontology/chapter_*_ontology_blueprint.md`가 공통으로 따라야 하는 추출 스키마이다. 장별 문서는 이 공통 스키마를 반복하지 않고, 해당 장의 특화 Rule, 개념, 예외, 품질 점검만 정의한다.

## 1. 문서 역할 분리

- `common_schema.md`: 공통 노드, 공통 엣지, 필수 속성, 원문 파트 taxonomy, 검증 실패 조건을 정의한다.
- `chapter_*_ontology_blueprint.md`: 장별 원문 파트 존재 여부, 본문 범위, 장별 Rule 타입, 장별 개념 매핑, 장별 예외와 공시 항목을 정의한다.
- `data/ontology/chapter_domains.json`: 자동 추출기가 사용할 장별 도메인 설정과 키워드, rule type, quality check를 보관한다.
- `chapter_part_inventory.md`: 1~15장의 원문 part 존재 여부와 본문 범위를 검증한 인벤토리이다.
- `chapter_minimal_examples.md`: 1~15장의 최소 JSON 예시 모음이다.

제6장은 표준 스펙의 원형이 아니라 `common_schema.md`를 따르는 제6장 특화 설계 문서로 취급한다.

## 2. 원문 파트 Taxonomy

| part | 의미 | 권위 수준 | 연결 원칙 |
|---|---|---:|---|
| `main` | 본문 기준 조항 | 1 | Rule의 1차 출처 |
| `terms` | 용어정의 | 1 | Concept 정의의 1차 출처 |
| `application_guidance` | 적용보충기준 | 2 | 본문 Rule의 세부 판단기준 |
| `practical_guidance` | 실무지침 | 2 | 본문 Rule의 해석, 적용지침 |
| `basis_for_conclusions` | 결론도출근거 | 3 | 본문 Rule의 배경, 근거, 의도 |
| `example` | 사례, 적용사례, 예시 | 4 | 본문/지침 적용 예시 |
| `minority_opinion` | 소수의견 | 4 | 관련 근거 또는 본문에 참조 연결 |

장별 문서는 각 part가 실제 원문에 존재하는지 `present | absent`로 명시한다. 존재하지 않는 part는 “있는 경우”라고 쓰지 않는다.

## 3. 필수 노드

### 3.1 Clause

```json
{
  "id": "clause_6_30",
  "type": "Clause",
  "properties": {
    "chapter": "6",
    "part": "main",
    "clause_number": "6.30",
    "section": "제2절 유가증권",
    "topic": "유가증권의 후속 측정",
    "page": 12,
    "source_text": "단기매매증권과 매도가능증권은 공정가치로 평가한다."
  }
}
```

필수 속성: `chapter`, `part`, `clause_number`, `page`, `source_text`.

`section`과 `topic`은 비어 있을 수 있지만 키는 유지한다. 원문 page를 확정할 수 없으면 `page: null`로 두고 `extraction_status: needs_review`, `review_notes: "page missing"`을 함께 둔다.

### 3.2 Rule

```json
{
  "id": "rule_6_30_01",
  "type": "MeasurementRule",
  "properties": {
    "source_clause": "6.30",
    "source_part": "main",
    "source_text": "단기매매증권과 매도가능증권은 공정가치로 평가한다.",
    "condition_text": "",
    "exception_text": "",
    "polarity": "require",
    "modality": "shall",
    "extraction_status": "auto",
    "review_notes": ""
  }
}
```

필수 속성: `source_clause`, `source_part`, `source_text`, `polarity`, `modality`, `extraction_status`.

`confidence`는 사용하지 않는다. 숫자 신뢰도 대신 `extraction_status`를 사용한다.

허용 상태:

- `auto`: 자동 추출되었고 아직 검토 전
- `reviewed`: 사람이 원문 대조 후 승인
- `needs_review`: 자동 추출 결과가 불완전하거나 모호함
- `disputed`: 리뷰어 간 판단이 충돌함
- `rejected`: 추출 결과가 폐기됨

### 3.3 Concept

전역 개념은 `global concept registry`에서 관리한다. 장별 문서는 전역 개념을 새로 만들지 않고, 다음만 정의한다.

- 장별 핵심 후보 개념
- 원문 표현과 전역 개념 ID의 alias/mapping
- 장 특화 개념이 전역 등록 후보인지 여부

동일한 회계 개념이 여러 장에 등장하면 하나의 전역 concept ID를 공유하고, 장별 표현은 alias로 연결한다.

### 3.4 DisclosureItem

공시 조항은 가능하면 `DisclosureRule -> DISCLOSES -> DisclosureItem`으로 분해한다. 열거형 공시는 각 항목을 별도 `DisclosureItem`으로 둔다.

## 4. 공통 관계 타입

| relation | 방향 | 사용 조건 |
|---|---|---|
| `HAS_RULE` | Clause -> Rule | 본문 또는 지침 조항이 Rule을 포함할 때 |
| `APPLIES_TO` | Rule -> Concept | Rule 적용 대상 |
| `EXCLUDES` | Rule -> Concept/Clause | 적용 제외 대상 |
| `HAS_CONDITION` | Rule -> Condition | Rule 성립 조건 |
| `HAS_EXCEPTION` | Rule -> ExceptionRule | 원칙에 대한 예외 |
| `MEASURED_BY` | MeasurementRule -> MeasurementBasis | 측정 기준 |
| `RECOGNIZES_AS` | Rule -> AccountingItem | 인식 결과 |
| `DERECOGNIZES` | DerecognitionRule -> Concept | 제거 대상 |
| `CLASSIFIES_AS` | ClassificationRule -> Concept | 분류 결과 |
| `RECLASSIFIES_TO` | ClassificationRule -> Concept | 재분류 결과 |
| `DISCLOSES` | DisclosureRule -> DisclosureItem/Concept | 주석공시 항목 |
| `REFERENCES` | Clause/Rule -> Clause/Section/Chapter | 원문이 다른 문단, 장, 기준을 명시 참조할 때 |
| `SPECIALIZES` | Rule -> Rule/Chapter | 특정 장의 Rule이 더 일반적인 장의 Rule을 업종, 거래, 상황별로 특수화할 때 |
| `OVERRIDES` | Rule -> Rule/Clause | 원문이 다른 일반 규칙보다 우선 적용됨을 명시할 때 |
| `SUPPLEMENTS` | ApplicationGuidance/PracticalGuidance -> Clause/Rule | 적용보충기준 또는 실무지침이 본문 판단을 보충할 때 |
| `BASIS_FOR` | BasisForConclusions -> Clause/Rule | 결론도출근거가 본문 기준의 배경이나 이유를 설명할 때 |
| `ILLUSTRATES` | Example -> Clause/Rule | 사례가 본문 또는 지침 적용을 보여줄 때 |

`basis_for_conclusions`는 `SUPPLEMENTS`로 연결하지 않는다. 검색과 추론에서 권위 수준이 본문/실무지침보다 낮아야 하기 때문이다.

## 5. 관계 필수 속성

```json
{
  "source_text": "문단에서 관계를 뒷받침하는 최소 원문",
  "paragraph": "6.30",
  "subparagraph": "(1)",
  "polarity": "include",
  "condition": "",
  "reference_type": "measurement",
  "extraction_status": "auto",
  "extraction_method": "rule+llm"
}
```

필수 속성: `source_text`, `paragraph`, `polarity`, `reference_type`, `extraction_status`, `extraction_method`.

`source_text`는 조항 전체가 아니라 관계를 뒷받침하는 최소 문장 또는 구를 사용한다.

## 6. 최소 JSON 예시

각 장별 설계 문서는 아래 예시를 해당 장의 실제 조항과 Rule 타입으로 치환하여 최소 1개 이상 포함해야 한다.

```json
{
  "clause": {
    "id": "clause_XX_YY",
    "type": "Clause",
    "properties": {
      "chapter": "XX",
      "part": "main",
      "clause_number": "XX.YY",
      "section": "",
      "topic": "",
      "page": null,
      "source_text": "원문 최소 문장"
    }
  },
  "rule": {
    "id": "rule_XX_YY_01",
    "type": "RuleType",
    "properties": {
      "source_clause": "XX.YY",
      "source_part": "main",
      "source_text": "원문 최소 문장",
      "condition_text": "",
      "exception_text": "",
      "polarity": "require",
      "modality": "shall",
      "extraction_status": "auto",
      "review_notes": ""
    }
  },
  "edges": [
    {
      "from": "clause_XX_YY",
      "to": "rule_XX_YY_01",
      "type": "HAS_RULE",
      "properties": {
        "source_text": "원문 최소 문장",
        "paragraph": "XX.YY",
        "polarity": "include",
        "reference_type": "rule_extraction",
        "extraction_status": "auto",
        "extraction_method": "rule+llm"
      }
    }
  ]
}
```

## 7. 실패 조건 중심 품질 기준

임의 비율 목표보다 다음 실패 조건을 우선한다.

- 본문 조항에 원칙, 예외, 조건, 측정, 표시, 공시 중 하나가 있는데 Rule이 0개인 경우
- 적용 제외와 예외 적용을 같은 Rule에 섞어 방향이 모호한 경우
- 공시 열거 항목이 하나의 텍스트 덩어리로만 남아 `DisclosureItem`이 없는 경우
- 측정기준, 측정시점, 후속측정이 분리되지 않은 경우
- 다른 장 또는 문단 참조가 원문에 있는데 `REFERENCES`가 없는 경우
- 결론도출근거가 `SUPPLEMENTS`로 연결되어 본문과 같은 권위로 검색되는 경우
- 모든 의미 관계에 `source_text` 또는 `extraction_status`가 없는 경우
- `source_text`가 관계의 근거를 좁히지 못하고 조항 전체를 반복하는 경우
- 원문 part가 실제로 없는데 장별 문서가 있는 것처럼 설계한 경우

## 8. 장별 검증 체크리스트

각 장별 설계 문서는 최소한 다음을 포함해야 한다.

- 대상 원문 경로
- 원문 part 존재 여부 표
- 본문 조항 범위
- 장별 Rule 타입
- 장별 핵심 concept alias/mapping
- 주요 추출 패턴
- 최소 JSON 예시 1개 이상
- 실패 조건 중심 품질 기준
