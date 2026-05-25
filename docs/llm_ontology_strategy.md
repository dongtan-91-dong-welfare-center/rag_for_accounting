# LLM 주도 온톨로지 추출 전략

## 1. 현재 문제

### rule-based의 구조적 한계

현재 extractor는 키워드 매칭과 정규식에 의존한다.
**키워드가 조항에 없으면 의미 엣지가 아예 생성되지 않는다.**

```
의미엣지 없는 조항 비율 (장별):
 1장 (목적·적용)     : 100%  ← 키워드 없음
 3장 (금융업 표시)   :  85%
24장 (보고기간후사건) :  67%
 2장 (재무제표 표시)  :  48%  ← 96개 조항 중 46개 엣지 없음
16장 (수익)          :  38%
```

### 문제의 본질

```
문단 2.3: "재무제표는 기업의 재무상태와 재무성과를 공정하게 표시하여야 한다."
```
→ rule-based: 키워드 없음 → 엣지 0개
→ LLM이 보면: `BalanceSheet APPLIES_TO FairPresentation`, `IncomeStatement APPLIES_TO FairPresentation` 추출 가능

rule-based는 **명시적 키워드**만 보지만, 온톨로지에서 중요한 것은 **암묵적 의미 관계**다.

---

## 2. 목표: LLM이 주체가 되는 추출

### 역할 재정의

| 구분 | rule-based | LLM 주도 |
|------|-----------|----------|
| 문서 구조 파싱 | ✅ 유지 | ✅ 유지 |
| 교차참조(REFERENCES) | ✅ 유지 | ✅ 유지 |
| 순서엣지(NEXT_CLAUSE) | ✅ 유지 | ✅ 유지 |
| **의미 관계 추출** | ❌ 키워드 의존 | **LLM이 판단** |
| **노드 연결** | ❌ 명시적 키워드만 | **맥락 이해** |
| **Rule 노드 생성** | ❌ 패턴 매칭만 | **조건·예외 이해** |

---

## 3. LLM 추출 설계

### 3-1. 처리 단위: 절(Section) 기준, 조항별 출력

절 단위로 LLM에 보내면:
- 맥락(이 절이 무엇을 다루는지) 유지
- 앞뒤 조항 관계 이해 가능
- API 호출 횟수 최소화

단, 출력은 **조항 번호별로 분리된 구조화 JSON**으로 받는다.

```
[입력] 제6장 제2절 "측정" 전체 조항 텍스트
[출력] 각 조항(6.7, 6.8, ...)마다 → 노드 연결 + 엣지 목록
```

### 3-2. 프롬프트 구조

```
[SYSTEM]
당신은 한국 회계기준서(일반기업회계기준)의 온톨로지 추출 전문가입니다.
다음 노드/엣지 스키마에 따라 정확하게 JSON을 출력하세요.

# 이 장의 도메인 개념 노드 (chapter_domains.json에서 동적 로드)
{chapter_domain_nodes}

# 공통 엣지 타입
APPLIES_TO: 이 조항이 해당 개념에 적용됨
REGULATES: 이 조항이 해당 프로세스를 규정함
MEASURED_BY: 측정기준 적용
RECOGNIZED_AS: 인식 기준
DERECOGNIZED_WHEN: 제거 조건
RELATED_TO_RISK: 위험 관련
DISCLOSES: 공시 요구
HAS_RULE: MeasurementRule/RecognitionRule 노드 연결

[USER]
다음은 '{section_title}' 절의 조항들입니다.

{clause_texts}

각 조항에 대해 아래 JSON 형식으로 출력하세요:
{
  "clauses": [
    {
      "clause_number": "6.7",
      "edges": [
        {
          "type": "APPLIES_TO",
          "target": "HeldToMaturitySecurity",
          "polarity": "include",
          "source_text": "만기보유증권은..."
        }
      ],
      "rules": [
        {
          "rule_type": "MeasurementRule",
          "subject": "HeldToMaturitySecurity",
          "basis": "AmortizedCost",
          "condition": "만기까지 보유할 의도와 능력이 있는 경우",
          "polarity": "include"
        }
      ]
    }
  ]
}
```

### 3-3. 증분 처리 전략

LLM은 비용이 크므로, **두 단계**로 나눈다:

1. **1단계 (rule-based)**: 기존 처리 그대로 실행 → 의미 엣지 없는 조항 목록 수집
2. **2단계 (LLM 보완)**: 의미 엣지 없는 조항이 포함된 절만 LLM으로 처리

```python
# 의미 엣지 없는 절만 선별
def _get_sections_needing_llm(self) -> list[Node]:
    semantic_src = {e.source for e in self.edges if e.type in SEMANTIC_TYPES}
    sections_with_gaps = set()
    for node in self.nodes:
        if (node.type == "Clause"
            and node.properties.get("part") == "main"
            and node.id not in semantic_src):
            sec_id = node.properties.get("section_id")
            if sec_id:
                sections_with_gaps.add(sec_id)
    return [n for n in self.nodes if n.id in sections_with_gaps]
```

---

## 4. 장별 프롬프트 컨텍스트 (chapter_domains.json 활용)

`_call_llm_for_relations()`는 현재 6장 전용 개념 ID를 하드코딩.
→ `self._subject_kws`, `self._process_kws`, `self._meas_pats`에서 **동적으로 개념 ID 목록 생성**.

```python
def _build_llm_concept_context(self) -> str:
    subjects = ", ".join(sorted(set(self._subject_kws.values())))
    processes = ", ".join(sorted(set(self._process_kws.values())))
    meas = ", ".join(sorted(set(cid for _, cid in self._meas_pats)))
    risks = ", ".join(sorted(set(self._risk_kws.values())))
    return f"""대상 개념: {subjects}
회계처리 개념: {processes}
측정기준: {meas}
위험 개념: {risks}"""
```

---

## 5. 개선 목표 (품질 지표 기준)

| 지표 | 현재 (전체 평균) | 목표 |
|------|----------------|------|
| 의미엣지없음 비율 | ~15% | < 5% |
| 측정Rule없음 | 0 (6장 기준) | 0 전 장 |
| 사례미연결 | 많음 | LLM으로 보완 |

---

## 6. 구현 우선순위

### Phase 1: `_call_llm_for_relations()` 동적화 (즉시)
- 하드코딩된 6장 개념 ID → `self._subject_kws` 등에서 동적 생성
- clause_number 출력 형식을 장 번호에 맞게 (현재 "6.X" 하드코딩)

### Phase 2: `enrich_with_llm()` 증분 처리로 개선
- 전체 절이 아닌, 의미 엣지 없는 절만 LLM 처리
- 이미 rule-based로 잘 된 절은 LLM 호출 생략 (비용 절감)

### Phase 3: 절 단위 → 조항 단위 출력 구조 개선
- 현재 section-level 엣지 생성 → clause-level로 정밀화
- `"clause_number"` 기반으로 정확한 조항에 엣지 연결

### Phase 4: Rule 노드 LLM 생성 전면 확대
- MeasurementRule 외 RecognitionRule, DisclosureRule도 LLM으로 추출
- 조건 텍스트 품질 향상 (rule-based는 문장 앞 150자 잘라서 넣음)

---

## 7. 당장 안 해도 되는 것

- LLM으로 REFERENCES 엣지 생성 (rule-based 정확도 90% → 충분)
- LLM으로 NEXT_CLAUSE 생성 (순서는 구조 기반이므로 rule이 정확)
- LLM으로 HAS_EXAMPLE/ILLUSTRATES 생성 (문단 번호 패턴 있으면 rule-based로 충분)
