# measurements/ — 측정·감사 결과

> **한 줄 요약(BLUF):** 벤치마크·인덱싱·감사 측정의 산출물 보관소. 파일명이 곧 종류·측정 시각을 말한다.

검색·답변 **통과 판정 규칙**은 여기 두지 않고 정책으로 승격했다 → [eval_pass_rules.md](../policies/eval_pass_rules.md).

## 네이밍 규약 (단일 출처)

| 패턴 | 뜻 |
|---|---|
| `baseline_<YYYYMMDD>_<HHMM>.json` | 벤치마크 1회 실행 원시 지표 |
| `benchmark_result_<YYYYMMDD>_<HHMM>.md` | 위 실행의 사람용 리포트 |
| `indexing_bench_<YYYYMMDD>_<HHMM>.{json,md}` | 인덱싱 성능 벤치마크 |
| `rechunk_ab_<YYYYMMDD>_<HHMM>.md` | 청킹 A/B 실험 기록 |
| `case_analysis_<이슈번호>.md` | 케이스 단위 실패 분석 |
| `v1_audit_report.md` | ★현행 v1.0 병합 감사 (폐기 아님 — archive 아님) |

`근거:` 타임스탬프를 파일명에 박아 "언제 측정인지"를 본문 안 열고 안다(신선도 표기). 같은 종류는 같은 접두로 묶여 정렬·대조가 쉽다.
