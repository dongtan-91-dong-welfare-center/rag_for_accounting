# 평가 '통과' 규칙 정의

> 작성: 2026-06-24. 본 문서는 NFR-002 벤치마크의 '통과' 판정을 **두 축으로 분리**해 명문화한다 — 코드(`tests/utils/benchmark_metrics.py`)에 이미 구현된 검색 축과, 미구현 상태인 내용 축의 계약을 함께 규정한다.
>
> **[2026-06-13 결정] NFR-002 1순위 = 정확한 조항 검색**(LLM 답변은 참고용). 따라서 두 축은 합치지 않고 각각 집계한다.

---

## 1. 원칙 — '통과'는 두 축, 합치지 않는다

평가 '통과'는 서로 다른 두 품질 축이며 **하나의 boolean으로 뭉개지 않는다**.

| 축 | 질문 | 지표 | 상태 |
|---|---|---|---|
| (a) 검색 (Retrieval) | 정답에 꼭 필요한 **핵심 조항이 Top-5에 들었는가** | `retrieval_pass` | ✅ 구현 |
| (b) 내용 (Content) | 검색과 무관하게 **생성된 답변 내용이 적절한가** | `content_pass` | ⛔ 미구현 |

케이스별로 `retrieval_pass`·`content_pass`를 **각각 기록**한다. 둘을 AND/OR로 합친 단일 통과값은 쓰지 않는다.

---

## 2. 검색 통과 (`retrieval_pass`) — 핵심 조항 Top-5

- **정의**: 멀티 조항 정답을 **핵심(core)/보조(auxiliary)** 로 구분하고, **핵심 조항이 검색 Top-5 안에 있으면 통과**. 보조 조항은 리포트에 기록하되 통과 판정엔 쓰지 않는다.
- **매칭**: `exact`(정규화된 조항키 완전일치)만 사용. `prefix`(계층 포함)는 진단 지표로만 집계하고 통과 판정엔 미사용.

### 코드 위치 대조표

| 항목 | 값/규칙 | 코드 |
|---|---|---|
| Top-N 컷오프 | `RETRIEVAL_PASS_TOP_N = 5` | `benchmark_metrics.py:36` |
| 통과 함수 | 핵심 조항 첫 hit ≤ 5 (`exact`) | `retrieval_pass()` `:152` |
| 핵심 조항 해석 | `case.core_paras` 정규화; **미지정 시 gold 전체를 핵심으로 폴백** | `resolve_core_paras()` `:147-149` |
| 케이스 반영 | `measure_case`가 케이스별 산출 | `:237` |
| 집계/리포트 | `aggregate` 키 `retrieval_pass` · 요약표 "검색 통과(핵심 Top-5)" | `:278`, `:299` |
| 핵심/보조 스키마 | `BenchmarkCase.core_paras` | `benchmark_loader.py:25` |

### ⚠️ 핵심/보조 폴백의 멀티조항 비대칭 (정책 명문화)

`core_paras` 미지정 멀티조항 케이스는 `resolve_core_paras` 폴백으로 **gold 전체가 핵심**이 된다. `rank_hit`은 첫 hit만 보므로 이 경우 통과 = "gold 중 하나라도 Top-5"(ANY)가 되어, `core_paras`를 지정한 케이스(핵심 1개만 Top-5)와 의미가 비대칭이다.

- **정책**: **단일 조항 케이스는 폴백이 무해**(핵심=gold 1개). **멀티 조항 케이스는 핵심이 일부일 때 반드시 `core_paras`를 지정**한다.
- 현황(2026-06-24): `core_paras` 지정은 `003`·`004` 2건. `007`(`6.29`,`6.31`)은 라벨링 대상, `012`(`21.8`,`21.10`)는 #167 회계사 확인 후 라벨링.

---

## 3. 답변 내용 적절성 (`content_pass`) — 별도 LLM 판정 ⛔ 미구현

- **정의**: 검색 결과와 무관하게 **생성된 답변 내용이 적절한가**를 별도 LLM 판정으로 평가하고, `retrieval_pass`와 **분리 집계**한다.
- **⚠️ in-graph `evaluate` 노드의 판정과 다른 축**: `evaluate`(`src/agent/nodes/evaluate.py`)의 `reasoning`은 CRAG의 `needs_external`(검색 컨텍스트가 외부 보강이 필요한가) 판정 사유이지, *answer ↔ expected_answer 적절성* 판정이 아니다. `content_pass`는 별도 judge다.
- **착수 시 확정할 계약** (구현 전 못박을 것):
  1. 입력: `expected_answer` + `answer`(전문) + gold 조항 본문 — 이미 `measure_case`가 `res.diag`에 영속화(`benchmark_metrics.py:244-259`).
  2. judge 프롬프트·rubric.
  3. 출력 스키마: `pass`/`partial`/`fail`.
  4. 합격 임계.
  5. `aggregate` 키 추가(현재 키엔 `content_pass` 없음).
  6. 비결정성 회귀 안정성 검증 방법(동일 입력 반복 판정 일관성).
- **선행 의존**: expected_answer 신뢰성이 전제이므로 **#167(009·006 등 expected_answer 교정) 확정 후** 착수. (gold만 교정하고 expected_answer가 코퍼스와 모순이면 judge가 "코퍼스대로 맞는 답"을 FAIL로 오판정.)

---

## 4. 테스트 시트 항목 ↔ 코드 키 매핑

> 출처: 외부 기획 테스트 시트(항목 번호 2.5.x). 시트 원문은 본 저장소에 없으므로, 항목의 **의미**를 현행 코드 키에 매핑한다.

| 테스트 시트 항목 | 의미 | 코드 키 (`aggregate`) | 비고 |
|---|---|---|---|
| 2.5.5 | top-1 적중("가장 적절한 조항이 최상단") | `generation_exact_hit@1` (`:271`, ★NFR-002 1차) · 진단용 `retrieval_exact_hit@1` (`:300`) | 회계사에 제공되는 인용(생성) 기준이 헤드라인 |
| 2.5.6 | top-5 적중 | `retrieval_pass`(핵심 Top-5) (`:278`) | `retrieval_exact_hit@k`는 `k=10` 컷오프라 별개 — Top-5는 `retrieval_pass`로 본다 |

---

## 5. 비고

- `retrieval_pass`는 `exact` 전용이다. 현 코퍼스의 gold는 전부 2단(`2.65`,`18.4` 등)이라 무해하나, 향후 3단 gold(`2.6.5`)와 2단 청크(`2.6`)가 공존하면 검색이 옳아도 `retrieval_pass=False`가 될 수 있다 → 그때 통과 규칙(prefix 포함 여부) 재검토.
- 조항번호 정규화 규칙·단위테스트는 `tests/unit/utils/test_clause_normalization.py` 참조.
- 관련: #167(gold·answer 신뢰성), #165(케이스 분석), #157(측정 운영화·CLOSED).
