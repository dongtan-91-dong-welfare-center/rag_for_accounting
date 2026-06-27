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

## 재현 (산출물 생성 명령)

| 산출물 | 생성 명령 |
|---|---|
| `baseline_*.json` · `benchmark_result_*.md` | `uv run python scripts/benchmark_baseline.py` (옵션 `--all-cases` · `--case <ID>` · `--k <N>`) |
| `indexing_bench_*.{json,md}` | `uv run python scripts/benchmark_indexing.py` (옵션 `--chapters` · `--batch-size` · `--search-iters`) |

둘 다 기본 `--out-dir`이 이 디렉토리다. DB·KURE-v1 임베딩(MPS는 호스트 실행) 전제 → [local_dev_setup.md](../guides/local_dev_setup.md).

## 주요 이슈 맥락

산출물·분석이 자주 참조하는 이슈 번호의 한 줄 맥락(상세는 GitHub).

| 이슈 | 맥락 |
|---|---|
| `#96` | NFR-002 1순위 = 조항 검색 결정(채점·UI 우선순위 기준) |
| `#105` | 0차 스모크 베이스라인(193청크, 2026-06-12) |
| `#126` | DB 인프라 Apache AGE 잔재 제거 |
| `#159` | 검색 개선 트랙(RRF-k·리랭킹 sweep) |
| `#163` | 평가 후속(통과 규칙·핵심/보조 라벨링) |
| `#167` | 벤치마크 gold 교정(오라벨·K-IFRS 혼재) |
