# 평가 '통과' 규칙 정의

> **평가 원칙**: NFR-002 벤치마크 평가는 **검색(retrieval)과 내용(content) 두 축으로 분리**하여 각각 독립적으로 집계합니다. **1순위 기준은 정확한 조항 검색**이며 생성 답변 평가는 보조 지표로 활용합니다. 검색 축 지표는 `tests/utils/benchmark_metrics.py`에 구현되어 있습니다.
>
> 용어 정의: `retrieval_pass`(검색 통과)와 `content_pass`(내용 통과)는 아래 §1 표에서 정의합니다. 공통 용어(조항, RRF, Hit@K) 및 평가 배경은 [전체 아키텍처](../ARCHITECTURE.md)를 참조합니다.

---

## 1. 기본 원칙: 평가 기준의 분리

평가 통과는 서로 다른 두 품질 축이며 하나의 불리언 값으로 합치지 않습니다.

| 축 | 질문 | 지표 | 상태 |
|---|---|---|---|
| (a) 검색 | 정답에 꼭 필요한 **핵심 조항이 Top-5에 들었는가** | `retrieval_pass` | ✅ 구현 |
| (b) 내용 | 검색과 무관하게 **생성된 답변 내용이 적절한가** | `content_pass` | ⛔ 미구현 |

케이스별로 `retrieval_pass`와 `content_pass`를 **각각 독립적으로 기록**합니다. 둘을 임의로 합친 단일 통과값은 사용하지 않습니다.

---

## 2. 검색 통과 (`retrieval_pass`): 핵심 조항 Top-5

- **정의**: 멀티 조항 정답을 핵심 조항과 보조 조항으로 구분하고, **핵심 조항이 검색 Top-5 안에 있으면 통과**로 판정합니다. 보조 조항은 리포트에 기록하되 통과 판정에는 반영하지 않습니다.
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

### 핵심/보조 미지정 시 주의 (멀티 조항)

`core_paras`를 지정하지 않으면 gold 조항 **전체가 핵심**으로 처리된다. 통과 판정은 핵심 조항의 첫 hit만 보므로, 멀티 조항 케이스가 이렇게 되면 통과 기준이 "**gold 중 하나라도** Top-5"(느슨)가 되어, 핵심을 콕 집어 지정한 케이스("**그 핵심이** Top-5", 엄격)보다 헐거워진다.

- **단일 조항 케이스**: 미지정이어도 무해하다(핵심 = gold 1개).
- **멀티 조항 케이스에서 일부만 핵심이면**: 반드시 `core_paras`를 지정한다(안 하면 통과가 느슨해진다).
- 미지정 멀티 조항의 `core_paras` 라벨링은 아직 일부 미완이다(회계사 확인 필요).

---

## 3. 답변 내용 적절성 (`content_pass`): 별도 LLM 판정 (미구현)

- **정의**: 검색 결과와 무관하게 **생성된 답변 내용이 적절한가**를 별도 LLM 판정으로 평가하고, `retrieval_pass`와 **분리 집계**한다.
- **⚠️ in-graph `evaluate` 노드의 판정과 다른 축**: `evaluate`(`src/agent/nodes/evaluate.py`)의 `reasoning`은 CRAG의 `needs_external`(검색 컨텍스트가 외부 보강이 필요한가) 판정 사유이지, *answer ↔ expected_answer 적절성* 판정이 아니다. `content_pass`는 별도 judge다.
- **착수 시 확정할 계약** (구현 전 못박을 것):
  1. 입력: `expected_answer` + `answer`(전문) + gold 조항 본문 — 이미 `measure_case`가 `res.diag`에 영속화(`benchmark_metrics.py:244-259`).
  2. judge 프롬프트·rubric.
  3. 출력 스키마: `pass`/`partial`/`fail`.
  4. 합격 임계.
  5. `aggregate` 키 추가(현재 키엔 `content_pass` 없음).
  6. 비결정성 회귀 안정성 검증 방법(동일 입력 반복 판정 일관성).
- **선행 의존**: expected_answer 신뢰성이 전제다. gold·expected_answer 조항 대조 교정은 끝났고 잔여 회계사 확인이 남아 있어, 그 신뢰성이 확보된 뒤 착수한다. (gold만 교정하고 expected_answer가 코퍼스와 모순이면 judge가 "코퍼스대로 맞는 답"을 FAIL로 오판정.)

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

## 6. 성능 지표 기록 및 리포트 관리 기준
회의에서 요구한 성능 문서화 대상은 검색 성능, 답변 품질, 답변 속도, 검색 속도입니다. 다만 테스트 데이터셋에 정답 오류가 발견되었으므로, 정밀 검수 이전의 수치는 정본 문서에 영구 고정하지 않습니다.

검수 완료 후 측정 리포트는 `docs/benchmark/`에 새 파일로 기록하며(초기 측정 이력은 `docs/measurements/`에 보존), 다음 정보를 반드시 포함합니다.

| 항목 | 기록 내용 |
|---|---|
| 데이터셋 | 파일명, 케이스 수, gold/core 라벨링 기준 |
| 실행 환경 | CPU/GPU, RAM, Docker/호스트 환경, 임베딩 서버 분리 여부, 리랭커 활성화 여부 |
| 설정값 | `TOP_K_RETRIEVAL`, `RRF_K`, `USE_RERANKER`, `RERANK_THRESHOLD`, `OPENAI_MODEL` |
| 검색 지표 | `retrieval_pass`, exact Hit@1/Hit@K, MRR |
| 답변 지표 | `content_pass` 구현 후 pass/partial/fail 판정 결과 |
| 속도 지표 | 검색 latency, 전체 응답 latency, timeout/recursion fallback 건수 |
| 해석 | 지표의 변동 원인과 향후 개선 조치 사항 |

README에는 최신 대표 결과만 요약하고, 상세 수치는 `docs/benchmark/` 내의 개별 실측 리포트로 연결합니다.
