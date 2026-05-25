# 1~15장 최소 JSON 예시

이 문서는 `common_schema.md`의 최소 예시 형식을 장별 실제 Rule 타입으로 치환한 검증용 예시 모음이다. `source_text`는 반드시 원문에서 그대로 가져온 문장 또는 구절만 사용한다. 요약이나 해석은 `label`, `topic`, `condition_text`, `review_notes`에만 둔다.

```json
[
  {
    "chapter": "1",
    "clause": {"id": "clause_1_1", "type": "Clause", "properties": {"chapter": "1", "part": "main", "clause_number": "1.1", "section": "목적", "topic": "기준 목적", "page": null, "source_text": "일반기업회계기준은 ‘주식회사 등의 외부감사에 관한 법률’의 적용대상기업 중 한국채택국제회계기준에 따라 회계처리하지 아니하는 기업의 회계와 감사인의 감사에 통일성과 객관성을 부여하기 위하여 동 기업의 회계처리 및 보고에 관한 기준을 정함을 목적으로 한다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_1_1_purpose", "type": "PurposeRule", "properties": {"source_clause": "1.1", "source_part": "main", "source_text": "동 기업의 회계처리 및 보고에 관한 기준을 정함을 목적으로 한다.", "condition_text": "한국채택국제회계기준에 따라 회계처리하지 아니하는 외부감사대상기업", "exception_text": "", "polarity": "include", "modality": "define", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "2",
    "clause": {"id": "clause_2_4", "type": "Clause", "properties": {"chapter": "2", "part": "main", "clause_number": "2.4", "section": "재무제표", "topic": "재무제표 구성", "page": null, "source_text": "재무제표는 재무상태표, 손익계산서, 현금흐름표, 자본변동표로 구성되며, 주석을 포함한다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_2_4_statement_structure", "type": "StatementStructureRule", "properties": {"source_clause": "2.4", "source_part": "main", "source_text": "재무제표는 재무상태표, 손익계산서, 현금흐름표, 자본변동표로 구성되며, 주석을 포함한다.", "condition_text": "", "exception_text": "", "polarity": "include", "modality": "define", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "3",
    "clause": {"id": "clause_3_2", "type": "Clause", "properties": {"chapter": "3", "part": "main", "clause_number": "3.2", "section": "적용범위", "topic": "금융업 표시 적용범위", "page": null, "source_text": "이 장은 중간기간을 포함한 모든 회계기간에 대하여 작성하는 재무제표, 연결재무제표 및 기업집단결합재무제표의 작성에 적용한다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_3_2_financial_industry_scope", "type": "FinancialIndustryScopeRule", "properties": {"source_clause": "3.2", "source_part": "main", "source_text": "이 장은 중간기간을 포함한 모든 회계기간에 대하여 작성하는 재무제표, 연결재무제표 및 기업집단결합재무제표의 작성에 적용한다.", "condition_text": "", "exception_text": "다른 장 또는 특수분야회계기준에서 정하고 있는 사항", "polarity": "include", "modality": "shall", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "4",
    "clause": {"id": "clause_4_2", "type": "Clause", "properties": {"chapter": "4", "part": "main", "clause_number": "4.2", "section": "연결재무제표의 작성기업", "topic": "연결재무제표 작성", "page": null, "source_text": "문단 4.3에서 정한 조건을 충족하는 경우를 제외하고 지배기업은 이 장에 따라 종속기업 투자를 연결한 연결재무제표를 작성한다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_4_2_consolidation_scope", "type": "ConsolidationScopeRule", "properties": {"source_clause": "4.2", "source_part": "main", "source_text": "지배기업은 이 장에 따라 종속기업 투자를 연결한 연결재무제표를 작성한다.", "condition_text": "지배기업이 종속기업 투자를 보유한다.", "exception_text": "문단 4.3에서 정한 조건을 충족하는 경우", "polarity": "require", "modality": "shall", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "5",
    "clause": {"id": "clause_5_3", "type": "Clause", "properties": {"chapter": "5", "part": "main", "clause_number": "5.3", "section": "회계정책의 선택과 적용", "topic": "회계정책 결정", "page": null, "source_text": "거래, 기타 사건 또는 상황에 적용되는 회계정책은 일반기업회계기준을 적용하여 결정한다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_5_3_policy_selection", "type": "PolicySelectionRule", "properties": {"source_clause": "5.3", "source_part": "main", "source_text": "회계정책은 일반기업회계기준을 적용하여 결정한다.", "condition_text": "거래, 기타 사건 또는 상황에 적용되는 회계정책을 결정한다.", "exception_text": "", "polarity": "require", "modality": "shall", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "6",
    "clause": {"id": "clause_6_1", "type": "Clause", "properties": {"chapter": "6", "part": "main", "clause_number": "6.1", "section": "목적", "topic": "금융자산·금융부채 목적", "page": null, "source_text": "이 장의 목적은 금융자산·금융부채에 대한 회계처리와 공시에 필요한 사항을 정하는 데 있다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_6_1_purpose", "type": "PurposeRule", "properties": {"source_clause": "6.1", "source_part": "main", "source_text": "금융자산·금융부채에 대한 회계처리와 공시에 필요한 사항을 정하는 데 있다.", "condition_text": "", "exception_text": "", "polarity": "include", "modality": "define", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "7",
    "clause": {"id": "clause_7_3", "type": "Clause", "properties": {"chapter": "7", "part": "main", "clause_number": "7.3", "section": "재고자산의 정의", "topic": "재고자산 정의", "page": null, "source_text": "'재고자산'은 정상적인 영업과정에서 판매를 위하여 보유하거나 생산과정에 있는 자산 및 생산 또는 서비스 제공과정에 투입될 원재료나 소모품의 형태로 존재하는 자산을 말한다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_7_3_inventory_definition", "type": "DefinitionRule", "properties": {"source_clause": "7.3", "source_part": "main", "source_text": "'재고자산'은 정상적인 영업과정에서 판매를 위하여 보유하거나 생산과정에 있는 자산 및 생산 또는 서비스 제공과정에 투입될 원재료나 소모품의 형태로 존재하는 자산을 말한다.", "condition_text": "", "exception_text": "", "polarity": "include", "modality": "define", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "8",
    "clause": {"id": "clause_8_3", "type": "Clause", "properties": {"chapter": "8", "part": "main", "clause_number": "8.3", "section": "지분법피투자기업의 범위", "topic": "지분법피투자기업 정의", "page": null, "source_text": "'지분법피투자기업'은 투자기업이 유의적인 영향력을 갖는 지분법 적용대상 피투자기업을 말한다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_8_3_equity_method_investee", "type": "DefinitionRule", "properties": {"source_clause": "8.3", "source_part": "main", "source_text": "'지분법피투자기업'은 투자기업이 유의적인 영향력을 갖는 지분법 적용대상 피투자기업을 말한다.", "condition_text": "", "exception_text": "", "polarity": "include", "modality": "define", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "9",
    "clause": {"id": "clause_9_2", "type": "Clause", "properties": {"chapter": "9", "part": "main", "clause_number": "9.2", "section": "조인트벤처의 정의", "topic": "조인트벤처 정의", "page": null, "source_text": "'조인트벤처'는 둘 이상의 당사자가 공동지배의 대상이 되는 경제활동을 수행하기 위해 만든 계약상 약정을 말한다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_9_2_joint_venture_definition", "type": "DefinitionRule", "properties": {"source_clause": "9.2", "source_part": "main", "source_text": "'조인트벤처'는 둘 이상의 당사자가 공동지배의 대상이 되는 경제활동을 수행하기 위해 만든 계약상 약정을 말한다.", "condition_text": "", "exception_text": "", "polarity": "include", "modality": "define", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "10",
    "clause": {"id": "clause_10_4", "type": "Clause", "properties": {"chapter": "10", "part": "main", "clause_number": "10.4", "section": "유형자산의 정의", "topic": "유형자산 정의", "page": null, "source_text": "'유형자산'은 재화의 생산, 용역의 제공, 타인에 대한 임대 또는 자체적으로 사용할 목적으로 보유하는 물리적 형태가 있는 자산으로서, 1년을 초과하여 사용할 것이 예상되는 자산을 말한다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_10_4_ppe_definition", "type": "DefinitionRule", "properties": {"source_clause": "10.4", "source_part": "main", "source_text": "'유형자산'은 재화의 생산, 용역의 제공, 타인에 대한 임대 또는 자체적으로 사용할 목적으로 보유하는 물리적 형태가 있는 자산으로서, 1년을 초과하여 사용할 것이 예상되는 자산을 말한다.", "condition_text": "", "exception_text": "", "polarity": "include", "modality": "define", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "11",
    "clause": {"id": "clause_11_3", "type": "Clause", "properties": {"chapter": "11", "part": "main", "clause_number": "11.3", "section": "식별가능성", "topic": "무형자산 식별가능성", "page": null, "source_text": "자산은 다음 중 하나에 해당하는 경우에 식별가능하다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_11_3_identifiability", "type": "IdentifiabilityRule", "properties": {"source_clause": "11.3", "source_part": "main", "source_text": "자산은 다음 중 하나에 해당하는 경우에 식별가능하다.", "condition_text": "분리가능하거나 계약상 권리 또는 기타 법적 권리로부터 발생한다.", "exception_text": "", "polarity": "include", "modality": "define", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "12",
    "clause": {"id": "clause_12_2", "type": "Clause", "properties": {"chapter": "12", "part": "main", "clause_number": "12.2", "section": "사업결합의 정의", "topic": "사업결합 정의", "page": null, "source_text": "사업결합이란 취득자가 하나 이상의 사업에 대한 지배력을 획득하는 거래나 그 밖의 사건을 말한다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_12_2_business_combination_definition", "type": "BusinessCombinationIdentificationRule", "properties": {"source_clause": "12.2", "source_part": "main", "source_text": "사업결합이란 취득자가 하나 이상의 사업에 대한 지배력을 획득하는 거래나 그 밖의 사건을 말한다.", "condition_text": "취득자가 하나 이상의 사업에 대한 지배력을 획득한다.", "exception_text": "", "polarity": "include", "modality": "define", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "13",
    "clause": {"id": "clause_13_1", "type": "Clause", "properties": {"chapter": "13", "part": "main", "clause_number": "13.1", "section": "목적", "topic": "리스 목적", "page": null, "source_text": "이 장의 목적은 리스의 회계처리와 공시에 필요한 사항을 정하는 데 있다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_13_1_purpose", "type": "PurposeRule", "properties": {"source_clause": "13.1", "source_part": "main", "source_text": "리스의 회계처리와 공시에 필요한 사항을 정하는 데 있다.", "condition_text": "", "exception_text": "", "polarity": "include", "modality": "define", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "14",
    "clause": {"id": "clause_14_1", "type": "Clause", "properties": {"chapter": "14", "part": "main", "clause_number": "14.1", "section": "목적", "topic": "충당부채 목적", "page": null, "source_text": "이 장의 목적은 충당부채, 우발부채, 우발자산의 회계처리와 공시에 필요한 사항을 정하는 데 있다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_14_1_purpose", "type": "PurposeRule", "properties": {"source_clause": "14.1", "source_part": "main", "source_text": "충당부채, 우발부채, 우발자산의 회계처리와 공시에 필요한 사항을 정하는 데 있다.", "condition_text": "", "exception_text": "", "polarity": "include", "modality": "define", "extraction_status": "auto", "review_notes": ""}}
  },
  {
    "chapter": "15",
    "clause": {"id": "clause_15_2", "type": "Clause", "properties": {"chapter": "15", "part": "main", "clause_number": "15.2", "section": "자본의 정의와 구성", "topic": "자본 정의", "page": null, "source_text": "자본은 기업의 자산에서 모든 부채를 차감한 후의 잔여지분을 나타내며, 주주로부터의 납입자본에 기업활동을 통하여 획득하고 기업의 활동을 위해 유보된 금액을 가산하고, 기업활동으로부터의 손실 및 소유자에 대한 배당으로 인한 주주지분 감소액을 차감한 잔액이다.", "extraction_status": "needs_review", "review_notes": "page missing"}},
    "rule": {"id": "rule_15_2_equity_definition", "type": "DefinitionRule", "properties": {"source_clause": "15.2", "source_part": "main", "source_text": "자본은 기업의 자산에서 모든 부채를 차감한 후의 잔여지분을 나타내며", "condition_text": "", "exception_text": "", "polarity": "include", "modality": "define", "extraction_status": "auto", "review_notes": ""}}
  }
]
```
