# 벤치마크 평가 리포트 (NFR-001 성능 / NFR-002 정확도)

- 생성 시각: 2026-09-25T09:21:54.049435+09:00
- Hit@k 의 k: 10
- 적재 장: 0개
- 적재 청크 수: 241
- USE_RERANKER: False
- 측정 케이스: 114건

## 지연 시간 요약 (NFR-001 목표 120.0초)

| 지표 | 측정값(초) | 목표(초) | 여유 마진 |
|------|------------|----------|-----------|
| 중위 지연 시간 (p50) | 6.31s | 120.0s | +113.69s |
| 95 백분위수 (p95) | 11.06s | 120.0s | +108.94s |
| 최대 지연 시간 (Max) | 15.14s | 120.0s | +104.86s |
| 최소 지연 시간 (Min) | 4.62s | — | — |
| 평균 지연 시간 (Avg) | 6.89s | — | — |

## 지표 요약 (NFR-002 목표 90%)

| 지표 | 적중 | 비율 | 목표 갭 |
|------|------|------|---------|
| 생성 조항 Hit@1 (★ NFR-002 1차) | 0/114 | 0.0% | -90.0%p |
| 생성 조항 Hit@10 | 0/114 | 0.0% | -90.0%p |
| 검색 통과(핵심 Top-5) (★ #163) | 0/114 | 0.0% | -90.0%p |
| 검색 조항 Hit@1 | 0/114 | 0.0% | -90.0%p |
| 검색 조항 Hit@10 (★ 비회귀 플로어) | 0/114 | 0.0% | -90.0%p |
| legacy 문자열(현행 대조군) | 0/114 | 0.0% | -90.0%p |
| is_answerable (가드레일) | 62/114 | 54.4% | -35.6%p |

- 평균 MRR(exact): 생성 0.0 / 검색 0.0

## 케이스별 결과

| 케이스 | 장 | gold 문단 | 검색 exact@k | 생성 exact@1 | answerable | CRAG | 소요(초) | 상태 |
|--------|----|-----------|--------------|--------------|------------|------|----------|------|
| TEST-K-GAAP-001 | 2 | 2.65 | ❌ | ❌ | ✅ | 1 | 5.49s | OK |
| TEST-K-GAAP-002 | 18 | 18.4, 18.5 | ❌ | ❌ | ❌ | 1 | 5.35s | OK |
| TEST-K-GAAP-003 | 21 | 21.10, 21.8, 21.9 | ❌ | ❌ | ✅ | 1 | 6.47s | OK |
| TEST-K-GAAP-004 | 15 | 15.18, 15.20 | ❌ | ❌ | ✅ | 1 | 6.17s | OK |
| TEST-K-GAAP-005 | 6 | 6.41, 6.42, 6.43, 6.44, 6.45, 6.46, 6.47 | ❌ | ❌ | ❌ | 1 | 6.53s | OK |
| TEST-K-GAAP-006 | 31 | 31.10 | ❌ | ❌ | ✅ | 1 | 6.69s | OK |
| TEST-K-GAAP-007 | 6 | 6.29, 6.30, 6.31 | ❌ | ❌ | ✅ | 1 | 6.07s | OK |
| TEST-K-GAAP-008 | 10 | 10.26 | ❌ | ❌ | ❌ | 1 | 6.74s | OK |
| TEST-K-GAAP-009 | 10 | 10.45 | ❌ | ❌ | ❌ | 1 | 5.80s | OK |
| TEST-K-GAAP-010 | 6 | 6.31, 6.34 | ❌ | ❌ | ❌ | 1 | 7.00s | OK |
| TEST-K-GAAP-011 | 2 | 2.57 | ❌ | ❌ | ✅ | 1 | 5.23s | OK |
| TEST-K-GAAP-012 | 21 | 21.10, 21.11, 21.12, 21.8 | ❌ | ❌ | ✅ | 1 | 6.31s | OK |
| TEST-K-GAAP-013 | 6 | 6.29 | ❌ | ❌ | ✅ | 1 | 5.63s | OK |
| TEST-K-GAAP-014 | 21 | 21.12 | ❌ | ❌ | ✅ | 1 | 6.02s | OK |
| TEST-K-GAAP-015 | 2 | 2.16 | ❌ | ❌ | ✅ | 1 | 4.62s | OK |
| TEST-K-GAAP-016 | 2 | 2.20 | ❌ | ❌ | ✅ | 1 | 5.33s | OK |
| TEST-K-GAAP-017 | 2 | 2.20 | ❌ | ❌ | ✅ | 1 | 6.28s | OK |
| TEST-K-GAAP-018 | 2 | 2.65 | ❌ | ❌ | ✅ | 1 | 5.61s | OK |
| TEST-K-GAAP-019 | 5 | 5.11, 5.12 | ❌ | ❌ | ✅ | 1 | 5.62s | OK |
| TEST-K-GAAP-020 | 5 | 5.14, 5.15, 5.16, 5.17 | ❌ | ❌ | ✅ | 2 | 9.49s | OK |
| TEST-K-GAAP-021 | 5 | 5.18, 5.19, 5.20 | ❌ | ❌ | ✅ | 1 | 5.55s | OK |
| TEST-K-GAAP-022 | 5 | 5.14, 5.15, 5.16, 5.17, 5.18, 5.19, 5.7 | ❌ | ❌ | ✅ | 1 | 6.40s | OK |
| TEST-K-GAAP-023 | 6 | 6.22, 6.23, 6.24, 6.25, 6.26, 6.27 | ❌ | ❌ | ✅ | 1 | 5.61s | OK |
| TEST-K-GAAP-024 | 6 | 6.31 | ❌ | ❌ | ✅ | 1 | 5.26s | OK |
| TEST-K-GAAP-025 | 6 | 6.29 | ❌ | ❌ | ✅ | 1 | 5.27s | OK |
| TEST-K-GAAP-026 | 6 | 6.32 | ❌ | ❌ | ✅ | 1 | 5.94s | OK |
| TEST-K-GAAP-027 | 6 | 6.34 | ❌ | ❌ | ✅ | 1 | 5.78s | OK |
| TEST-K-GAAP-028 | 6 | 6.41 | ❌ | ❌ | ✅ | 1 | 5.88s | OK |
| TEST-K-GAAP-029 | 6 | 6.47 | ❌ | ❌ | ✅ | 1 | 6.34s | OK |
| TEST-K-GAAP-030 | 6 | 6.31 | ❌ | ❌ | ✅ | 1 | 5.95s | OK |
| TEST-K-GAAP-031 | 7 | 7.3 | ❌ | ❌ | ✅ | 1 | 4.86s | OK |
| TEST-K-GAAP-032 | 7 | 7.17, 7.20, 7.4 | ❌ | ❌ | ✅ | 1 | 5.15s | OK |
| TEST-K-GAAP-033 | 7 | 7.6 | ❌ | ❌ | ❌ | 1 | 5.06s | OK |
| TEST-K-GAAP-034 | 7 | 7.12, 7.13, 7.14, 7.15 | ❌ | ❌ | ❌ | 1 | 4.78s | OK |
| TEST-K-GAAP-035 | 7 | 7.17 | ❌ | ❌ | ❌ | 1 | 5.48s | OK |
| TEST-K-GAAP-036 | 7 | 7.19, 7.20 | ❌ | ❌ | ✅ | 1 | 6.32s | OK |
| TEST-K-GAAP-037 | 8 | 8.4, 8.5, 8.6 | ❌ | ❌ | ❌ | 1 | 6.99s | OK |
| TEST-K-GAAP-038 | 8 | 8.11 | ❌ | ❌ | ❌ | 1 | 6.08s | OK |
| TEST-K-GAAP-039 | 8 | 8.16, 8.19, 8.8 | ❌ | ❌ | ❌ | 1 | 5.94s | OK |
| TEST-K-GAAP-040 | 8 | 8.20 | ❌ | ❌ | ✅ | 1 | 6.35s | OK |
| TEST-K-GAAP-041 | 8 | 8.24, 8.26 | ❌ | ❌ | ❌ | 1 | 8.15s | OK |
| TEST-K-GAAP-042 | 10 | 10.10, 10.11, 10.12, 10.13, 10.8, 10.9 | ❌ | ❌ | ❌ | 1 | 6.42s | OK |
| TEST-K-GAAP-043 | 10 | 10.14, 10.15, 10.16 | ❌ | ❌ | ✅ | 1 | 6.14s | OK |
| TEST-K-GAAP-044 | 10 | 10.17, 10.18, 10.19, 10.20, 10.21 | ❌ | ❌ | ❌ | 1 | 6.94s | OK |
| TEST-K-GAAP-045 | 10 | 10.38, 10.39, 10.40 | ❌ | ❌ | ❌ | 2 | 10.56s | OK |
| TEST-K-GAAP-046 | 10 | 10.34 | ❌ | ❌ | ❌ | 1 | 5.86s | OK |
| TEST-K-GAAP-047 | 10 | 10.22, 10.30 | ❌ | ❌ | ❌ | 2 | 11.21s | OK |
| TEST-K-GAAP-048 | 10 | 10.22, 10.23, 10.24, 10.25, 10.26, 10.27, 10.28, 10.29, 10.30, 10.31 | ❌ | ❌ | ✅ | 1 | 7.54s | OK |
| TEST-K-GAAP-049 | 10 | 10.41, 10.42 | ❌ | ❌ | ❌ | 1 | 7.67s | OK |
| TEST-K-GAAP-050 | 11 | 11.3, 11.4, 11.5, 11.6, 11.7 | ❌ | ❌ | ✅ | 1 | 5.50s | OK |
| TEST-K-GAAP-051 | 11 | 11.17, 11.18, 11.19, 11.20 | ❌ | ❌ | ❌ | 1 | 5.85s | OK |
| TEST-K-GAAP-052 | 11 | 11.26, 11.27, 11.28, 11.29, 11.30, 11.31, 11.32, 11.33, 11.34, 11.35, 11.36 | ❌ | ❌ | ❌ | 1 | 6.05s | OK |
| TEST-K-GAAP-053 | 11 | 11.33 | ❌ | ❌ | ❌ | 2 | 11.48s | OK |
| TEST-K-GAAP-054 | 11 | 11.10, 11.11, 11.12, 11.13, 11.14, 11.15, 11.16, 11.17, 11.18, 11.19, 11.20, 11.21, 11.22, 11.7, 11.8, 11.9 | ❌ | ❌ | ✅ | 1 | 5.76s | OK |
| TEST-K-GAAP-055 | 11 | 11.2, 11.3, 11.4 | ❌ | ❌ | ✅ | 1 | 6.18s | OK |
| TEST-K-GAAP-056 | 12 | 12.32 | ❌ | ❌ | ❌ | 1 | 5.58s | OK |
| TEST-K-GAAP-057 | 12 | 12.33 | ❌ | ❌ | ❌ | 1 | 6.57s | OK |
| TEST-K-GAAP-058 | 12 | 12.20 | ❌ | ❌ | ✅ | 1 | 5.86s | OK |
| TEST-K-GAAP-059 | 12 | 12.32 | ❌ | ❌ | ❌ | 1 | 6.05s | OK |
| TEST-K-GAAP-060 | 13 | 13.5, 13.6, 13.7, 13.8 | ❌ | ❌ | ❌ | 2 | 10.01s | OK |
| TEST-K-GAAP-061 | 13 | 13.6 | ❌ | ❌ | ❌ | 1 | 5.89s | OK |
| TEST-K-GAAP-062 | 13 | 13.13, 13.14, 13.15 | ❌ | ❌ | ✅ | 1 | 6.26s | OK |
| TEST-K-GAAP-063 | 13 | 13.19 | ❌ | ❌ | ❌ | 1 | 5.85s | OK |
| TEST-K-GAAP-064 | 13 | 13.21, 13.22, 13.23 | ❌ | ❌ | ✅ | 1 | 5.56s | OK |
| TEST-K-GAAP-065 | 13 | 13.35, 13.36 | ❌ | ❌ | ❌ | 1 | 6.15s | OK |
| TEST-K-GAAP-066 | 14 | 14.4 | ❌ | ❌ | ✅ | 1 | 6.52s | OK |
| TEST-K-GAAP-067 | 14 | 14.5 | ❌ | ❌ | ❌ | 1 | 8.98s | OK |
| TEST-K-GAAP-068 | 14 | 14.10, 14.11, 14.12, 14.7, 14.8, 14.9 | ❌ | ❌ | ✅ | 1 | 6.19s | OK |
| TEST-K-GAAP-069 | 14 | 14.4 | ❌ | ❌ | ❌ | 1 | 7.12s | OK |
| TEST-K-GAAP-070 | 14 | 14.6 | ❌ | ❌ | ✅ | 1 | 6.47s | OK |
| TEST-K-GAAP-071 | 15 | 15.3 | ❌ | ❌ | ✅ | 1 | 5.80s | OK |
| TEST-K-GAAP-072 | 15 | 15.8 | ❌ | ❌ | ✅ | 1 | 5.70s | OK |
| TEST-K-GAAP-073 | 2 | 2.31 | ❌ | ❌ | ✅ | 1 | 6.10s | OK |
| TEST-K-GAAP-074 | 15 | 15.9 | ❌ | ❌ | ✅ | 2 | 9.83s | OK |
| TEST-K-GAAP-075 | 16 | 16.10 | ❌ | ❌ | ❌ | 1 | 6.96s | OK |
| TEST-K-GAAP-076 | 16 | 16.11, 16.12, 16.13 | ❌ | ❌ | ❌ | 1 | 6.18s | OK |
| TEST-K-GAAP-077 | 16 | 16.15, 16.16, 16.17 | ❌ | ❌ | ❌ | 3 | 15.14s | OK |
| TEST-K-GAAP-078 | 16 | 16.39, 16.47, 16.48 | ❌ | ❌ | ❌ | 1 | 6.41s | OK |
| TEST-K-GAAP-079 | 16 | 16.53 | ❌ | ❌ | ❌ | 1 | 5.54s | OK |
| TEST-K-GAAP-080 | 16 | 16.10 | ❌ | ❌ | ❌ | 1 | 6.42s | OK |
| TEST-K-GAAP-081 | 17 | 17.5 | ❌ | ❌ | ❌ | 1 | 5.74s | OK |
| TEST-K-GAAP-082 | 17 | 17.3 | ❌ | ❌ | ❌ | 1 | 7.45s | OK |
| TEST-K-GAAP-083 | 17 | 17.4 | ❌ | ❌ | ❌ | 1 | 10.83s | OK |
| TEST-K-GAAP-084 | 17 | 17.8 | ❌ | ❌ | ❌ | 1 | 9.05s | OK |
| TEST-K-GAAP-085 | 18 | 18.4 | ❌ | ❌ | ❌ | 1 | 7.46s | OK |
| TEST-K-GAAP-086 | 18 | 18.6 | ❌ | ❌ | ❌ | 1 | 8.13s | OK |
| TEST-K-GAAP-087 | 18 | 18.10, 18.11, 18.12, 18.9 | ❌ | ❌ | ✅ | 2 | 10.98s | OK |
| TEST-K-GAAP-088 | 18 | 18.4, 18.5 | ❌ | ❌ | ❌ | 2 | 10.50s | OK |
| TEST-K-GAAP-089 | 19 | 19.10, 19.11, 19.12, 19.13, 19.9 | ❌ | ❌ | ✅ | 1 | 6.66s | OK |
| TEST-K-GAAP-090 | 19 | 19.26, 19.27, 19.28 | ❌ | ❌ | ❌ | 1 | 7.70s | OK |
| TEST-K-GAAP-091 | 19 | 19.13, 19.16 | ❌ | ❌ | ❌ | 2 | 12.51s | OK |
| TEST-K-GAAP-092 | 20 | 20.4, 20.5, 20.6, 20.7 | ❌ | ❌ | ❌ | 2 | 14.52s | OK |
| TEST-K-GAAP-093 | 20 | 20.10, 20.11, 20.12, 20.8, 20.9 | ❌ | ❌ | ✅ | 1 | 6.27s | OK |
| TEST-K-GAAP-094 | 20 | 20.19, 20.20, 20.21, 20.22, 20.23, 20.24, 20.25, 20.26, 20.27, 20.28 | ❌ | ❌ | ✅ | 1 | 7.95s | OK |
| TEST-K-GAAP-095 | 20 | 20.13, 20.14, 20.15, 20.16, 20.17, 20.18 | ❌ | ❌ | ✅ | 1 | 6.22s | OK |
| TEST-K-GAAP-096 | 20 | 20.13, 20.14, 20.15, 20.16, 20.17, 20.18 | ❌ | ❌ | ❌ | 1 | 7.24s | OK |
| TEST-K-GAAP-097 | 20 | 20.4, 20.5, 20.6, 20.7 | ❌ | ❌ | ✅ | 1 | 6.66s | OK |
| TEST-K-GAAP-098 | 21 | 21.8 | ❌ | ❌ | ✅ | 1 | 6.55s | OK |
| TEST-K-GAAP-099 | 21 | 21.10 | ❌ | ❌ | ✅ | 1 | 7.82s | OK |
| TEST-K-GAAP-100 | 21 | 21.12 | ❌ | ❌ | ✅ | 1 | 6.38s | OK |
| TEST-K-GAAP-101 | 21 | 21.9 | ❌ | ❌ | ✅ | 1 | 6.48s | OK |
| TEST-K-GAAP-102 | 21 | 21.6 | ❌ | ❌ | ✅ | 1 | 6.48s | OK |
| TEST-K-GAAP-103 | 21 | 21.8 | ❌ | ❌ | ✅ | 1 | 7.25s | OK |
| TEST-K-GAAP-104 | 22 | 22.10 | ❌ | ❌ | ✅ | 1 | 7.62s | OK |
| TEST-K-GAAP-105 | 22 | 22.19, 22.20, 22.21, 22.22, 22.23, 22.44 | ❌ | ❌ | ❌ | 1 | 5.93s | OK |
| TEST-K-GAAP-106 | 22 | 22.55 | ❌ | ❌ | ✅ | 1 | 5.77s | OK |
| TEST-K-GAAP-107 | 22 | 22.25, 22.26, 22.27 | ❌ | ❌ | ❌ | 1 | 6.37s | OK |
| TEST-K-GAAP-108 | 22 | 22.48 | ❌ | ❌ | ✅ | 1 | 7.12s | OK |
| TEST-K-GAAP-109 | 23 | 23.10, 23.8, 23.9 | ❌ | ❌ | ✅ | 1 | 5.87s | OK |
| TEST-K-GAAP-110 | 23 | 23.14, 23.15, 23.16 | ❌ | ❌ | ❌ | 1 | 7.84s | OK |
| TEST-K-GAAP-111 | 23 | 23.10, 23.8, 23.9 | ❌ | ❌ | ✅ | 1 | 7.66s | OK |
| TEST-K-GAAP-112 | 31 | 31.10 | ❌ | ❌ | ❌ | 1 | 4.70s | OK |
| TEST-K-GAAP-113 | 31 | 31.7 | ❌ | ❌ | ❌ | 2 | 11.66s | OK |
| TEST-K-GAAP-114 | 31 | 31.12 | ❌ | ❌ | ✅ | 1 | 6.76s | OK |

## 검색 미적중 진단 (114건)

- **TEST-K-GAAP-001** (제2장, gold=['2.65']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-002** (제18장, gold=['18.4', '18.5']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-003** (제21장, gold=['21.10', '21.8', '21.9']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-004** (제15장, gold=['15.18', '15.20']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-005** (제6장, gold=['6.41', '6.42', '6.43', '6.44', '6.45', '6.46', '6.47']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-006** (제31장, gold=['31.10']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-007** (제6장, gold=['6.29', '6.30', '6.31']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-008** (제10장, gold=['10.26']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-009** (제10장, gold=['10.45']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-010** (제6장, gold=['6.31', '6.34']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-011** (제2장, gold=['2.57']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-012** (제21장, gold=['21.10', '21.11', '21.12', '21.8']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=decompose, needs_external=False
- **TEST-K-GAAP-013** (제6장, gold=['6.29']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-014** (제21장, gold=['21.12']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-015** (제2장, gold=['2.16']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-016** (제2장, gold=['2.20']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-017** (제2장, gold=['2.20']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-018** (제2장, gold=['2.65']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-019** (제5장, gold=['5.11', '5.12']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-020** (제5장, gold=['5.14', '5.15', '5.16', '5.17']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-021** (제5장, gold=['5.18', '5.19', '5.20']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-022** (제5장, gold=['5.14', '5.15', '5.16', '5.17', '5.18', '5.19', '5.7']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-023** (제6장, gold=['6.22', '6.23', '6.24', '6.25', '6.26', '6.27']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-024** (제6장, gold=['6.31']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-025** (제6장, gold=['6.29']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-026** (제6장, gold=['6.32']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-027** (제6장, gold=['6.34']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-028** (제6장, gold=['6.41']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-029** (제6장, gold=['6.47']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-030** (제6장, gold=['6.31']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-031** (제7장, gold=['7.3']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-032** (제7장, gold=['7.17', '7.20', '7.4']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-033** (제7장, gold=['7.6']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-034** (제7장, gold=['7.12', '7.13', '7.14', '7.15']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-035** (제7장, gold=['7.17']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-036** (제7장, gold=['7.19', '7.20']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-037** (제8장, gold=['8.4', '8.5', '8.6']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-038** (제8장, gold=['8.11']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-039** (제8장, gold=['8.16', '8.19', '8.8']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-040** (제8장, gold=['8.20']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-041** (제8장, gold=['8.24', '8.26']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-042** (제10장, gold=['10.10', '10.11', '10.12', '10.13', '10.8', '10.9']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-043** (제10장, gold=['10.14', '10.15', '10.16']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-044** (제10장, gold=['10.17', '10.18', '10.19', '10.20', '10.21']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-045** (제10장, gold=['10.38', '10.39', '10.40']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-046** (제10장, gold=['10.34']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-047** (제10장, gold=['10.22', '10.30']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-048** (제10장, gold=['10.22', '10.23', '10.24', '10.25', '10.26', '10.27', '10.28', '10.29', '10.30', '10.31']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-049** (제10장, gold=['10.41', '10.42']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-050** (제11장, gold=['11.3', '11.4', '11.5', '11.6', '11.7']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-051** (제11장, gold=['11.17', '11.18', '11.19', '11.20']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-052** (제11장, gold=['11.26', '11.27', '11.28', '11.29', '11.30', '11.31', '11.32', '11.33', '11.34', '11.35', '11.36']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-053** (제11장, gold=['11.33']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-054** (제11장, gold=['11.10', '11.11', '11.12', '11.13', '11.14', '11.15', '11.16', '11.17', '11.18', '11.19', '11.20', '11.21', '11.22', '11.7', '11.8', '11.9']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-055** (제11장, gold=['11.2', '11.3', '11.4']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-056** (제12장, gold=['12.32']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-057** (제12장, gold=['12.33']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-058** (제12장, gold=['12.20']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-059** (제12장, gold=['12.32']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-060** (제13장, gold=['13.5', '13.6', '13.7', '13.8']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-061** (제13장, gold=['13.6']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-062** (제13장, gold=['13.13', '13.14', '13.15']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-063** (제13장, gold=['13.19']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-064** (제13장, gold=['13.21', '13.22', '13.23']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-065** (제13장, gold=['13.35', '13.36']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-066** (제14장, gold=['14.4']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-067** (제14장, gold=['14.5']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-068** (제14장, gold=['14.10', '14.11', '14.12', '14.7', '14.8', '14.9']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-069** (제14장, gold=['14.4']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-070** (제14장, gold=['14.6']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-071** (제15장, gold=['15.3']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-072** (제15장, gold=['15.8']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-073** (제2장, gold=['2.31']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-074** (제15장, gold=['15.9']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-075** (제16장, gold=['16.10']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-076** (제16장, gold=['16.11', '16.12', '16.13']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-077** (제16장, gold=['16.15', '16.16', '16.17']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=decompose, needs_external=True
- **TEST-K-GAAP-078** (제16장, gold=['16.39', '16.47', '16.48']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-079** (제16장, gold=['16.53']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-080** (제16장, gold=['16.10']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-081** (제17장, gold=['17.5']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-082** (제17장, gold=['17.3']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-083** (제17장, gold=['17.4']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-084** (제17장, gold=['17.8']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-085** (제18장, gold=['18.4']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-086** (제18장, gold=['18.6']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-087** (제18장, gold=['18.10', '18.11', '18.12', '18.9']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-088** (제18장, gold=['18.4', '18.5']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-089** (제19장, gold=['19.10', '19.11', '19.12', '19.13', '19.9']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-090** (제19장, gold=['19.26', '19.27', '19.28']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-091** (제19장, gold=['19.13', '19.16']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-092** (제20장, gold=['20.4', '20.5', '20.6', '20.7']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-093** (제20장, gold=['20.10', '20.11', '20.12', '20.8', '20.9']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-094** (제20장, gold=['20.19', '20.20', '20.21', '20.22', '20.23', '20.24', '20.25', '20.26', '20.27', '20.28']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-095** (제20장, gold=['20.13', '20.14', '20.15', '20.16', '20.17', '20.18']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-096** (제20장, gold=['20.13', '20.14', '20.15', '20.16', '20.17', '20.18']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-097** (제20장, gold=['20.4', '20.5', '20.6', '20.7']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-098** (제21장, gold=['21.8']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-099** (제21장, gold=['21.10']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-100** (제21장, gold=['21.12']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-101** (제21장, gold=['21.9']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-102** (제21장, gold=['21.6']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-103** (제21장, gold=['21.8']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-104** (제22장, gold=['22.10']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-105** (제22장, gold=['22.19', '22.20', '22.21', '22.22', '22.23', '22.44']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-106** (제22장, gold=['22.55']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-107** (제22장, gold=['22.25', '22.26', '22.27']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-108** (제22장, gold=['22.48']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-109** (제23장, gold=['23.10', '23.8', '23.9']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-110** (제23장, gold=['23.14', '23.15', '23.16']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-111** (제23장, gold=['23.10', '23.8', '23.9']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-112** (제31장, gold=['31.10']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=bypass, needs_external=False
- **TEST-K-GAAP-113** (제31장, gold=['31.7']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False
- **TEST-K-GAAP-114** (제31장, gold=['31.12']): 검색 장=[None, None, None, None, None, None, None, None, None, None], 인용 문단=[], 전략=hyde, needs_external=False

## 최악 지연 시간 진단 (상위 5건)

- **TEST-K-GAAP-077** (제16장, 소요 15.14s): 전략=decompose, CRAG=3, 인용=1건, 검색=10건
- **TEST-K-GAAP-092** (제20장, 소요 14.52s): 전략=hyde, CRAG=2, 인용=3건, 검색=10건
- **TEST-K-GAAP-091** (제19장, 소요 12.51s): 전략=hyde, CRAG=2, 인용=1건, 검색=10건
- **TEST-K-GAAP-113** (제31장, 소요 11.66s): 전략=hyde, CRAG=2, 인용=1건, 검색=10건
- **TEST-K-GAAP-053** (제11장, 소요 11.48s): 전략=hyde, CRAG=2, 인용=2건, 검색=10건

## 케이스별 회계사 검토 대조표

> 케이스별 [질문 · 예상정답+근거 · 실제답변+근거 · 판정]을 대조한다. ⑤ 회계사 검토란을 직접 채워 답변 정확성·근거 적절성을 판정한다.

### TEST-K-GAAP-001 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
K-GAAP에서 현금흐름표의 영업활동현금흐름을 간접법으로 구할 때, 대손상각비나 대손충당금 환입액은 어떻게 가감하나요?

**② 예상 정답**  
간접법은 당기순이익(또는 당기순손실)에 현금유출입이 없는 비용·수익을 가감하여 영업활동현금흐름을 산출하는 구조임. 현금유출이 없는 비용인 대손상각비는 가산하고, 현금유입이 없는 수익인 대손충당금 환입액은 차감함.

**②' 예상 근거(gold)**: 2.65

**③ 실제 답변**  
K-GAAP의 간접법은 당기순이익(또는 당기순손실)에 현금의 유출이 없는 비용 등을 가산하고 현금의 유입이 없는 수익 등을 차감하는 방식이므로, 대손상각비는 현금의 유출이 없는 비용으로서 가산하고, 대손충당금 환입액은 현금의 유입이 없는 수익으로 보아 차감합니다 [1][2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 K-GAAP 현금흐름표 간접법에서 대손상각비/대손충당금 환입액의 가감 방법을 묻지만, 청크 [1]은 간접법의 일반원칙(현금 유출이 없는 비용 가산, 현금 유입이 없는 수익 차감)만 제시할 뿐 해당 항목의 구체적 처리 방향을 직접 밝히지 않습니다. 청크 [2], [5], [8]에는 대손상각비·대손충당금의 회계처리 사례가 있으나 이는 채권손상/조건변경 맥락으로 현금흐름표 가감 규정이 아니므로, 질문에 대한 누락 없는 답변 근거로 보기 어렵습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-002 (제18장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
K-GAAP에서 차입원가를 자본화할 때, 특정차입금과 일반차입금 각각에 대해 자본화가 강제사항인지 선택사항인지 규정이 어떻게 되나요?

**② 예상 정답**  
K-GAAP에서는 적격자산의 취득·건설·제조와 관련된 차입원가를 당기비용으로 인식하는 것을 원칙으로 하되, 자본화는 회계정책 선택사항으로 허용됨. 특정차입금과 일반차입금 모두 자본화 여부는 강제사항이 아닌 선택사항이며, 자본화를 선택한 경우 모든 적격자산에 대해 일관되게 적용해야 함.

**②' 예상 근거(gold)**: 18.4, 18.5

**③ 실제 답변**  
제공된 맥락 청크에는 차입원가의 자본화와 관련한 규정이 없어서, 특정차입금과 일반차입금 각각에 대해 자본화가 강제인지 선택사항인지 판단할 수 없습니다. 따라서 이 질의는 해당 맥락만으로는 답변할 수 없습니다 [1][3][5][10].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크는 위험회피회계(위험회피대상항목, 공정가치위험회피, 현금흐름위험회피 등)에 관한 내용만 포함하고 있어, 질문한 K-GAAP의 차입원가 자본화(특정차입금·일반차입금별 자본화 강제/선택 여부)에 대한 규정이 전혀 제시되어 있지 않습니다. 따라서 수치·조건·판단기준이 누락되어 있으며, 외부 기준서 참조 지시도 청크 내에 없어 추가 검색 여부와 무관하게 현재 청크만으로는 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-003 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
K-GAAP 적용 기업인데, 기말 퇴직금추계액을 산정해 보니 전년도보다 금액이 감소했습니다. 이 감소분을 퇴직급여 환입(수익)으로 회계처리해도 기준서상 문제가 없을까요?

**② 예상 정답**  
K-GAAP상 퇴직급여충당부채는 보고기간 말 현재 전 임직원이 일시에 퇴직할 경우 지급해야 할 퇴직금추계액으로 측정함. 임직원 퇴사로 인한 실제 지급에 따른 감소는 충당부채와 현금의 상계로 처리하며, 그 외 순수 추계액 자체가 감소한 경우 차액을 '퇴직급여 환입(수익)'으로 인식하는 것이 가능함. 단, 환입 처리 전에 추계액 산정의 적정성과 비교 일관성을 우선 검토하여야 함.

**②' 예상 근거(gold)**: 21.10, 21.8, 21.9

**③ 실제 답변**  
네, 제시된 문맥만 기준으로 보면 퇴직급여충당부채는 보고기간말 현재의 퇴직금소요액을 기준으로 인식하며, 기존 퇴직금제도에서는 보험수리적 방식의 환입 규정이 아니라 전기 이전분을 포함한 증가분을 비용으로 인식하는 취지로 설명하고 있습니다 [1][3]. 또한 확정급여형퇴직연금제도에서도 사망률·할인율 변동이나 시간경과에 따른 변동액을 퇴직급여(비용)로 처리하도록 되어 있으나, 이는 퇴직연금미지급금에 관한 규정입니다 [1][5]. 따라서 질문처럼 K-GAAP의 퇴직금제도에서 기말 추계액이 전년 대비 감소한 경우 그 감소분을 별도의 ‘퇴직급여 환입(수익)’으로 처리한다는 명시적 근거는 문맥에서 확인되지 않습니다 [1][3][5]. 이 문맥만으로는 환입 처리 가능 여부를 긍정하기 어렵고, 적어도 제시된 기준서 문구상으로는 환입 수익 인식보다는 퇴직급여충당부채의 감소로 반영하는 취지에 가깝습니다 [1][3].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크에 퇴직급여충당부채의 측정 및 변동 처리 근거가 포함되어 있습니다. 특히 문단 21.8, 결 21.10, [5]의 분개 예시에서 퇴직급여충당부채를 제거하거나 감소하는 경우 그 차액을 퇴직급여(비용)로 반영하도록 설명하므로, 질문의 ‘감소분을 퇴직급여 환입(수익)으로 처리’ 여부 판단에 직접 관련됩니다. 외부 기준서 참조 지시도 보이지 않아 추가 검색이 필요하지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-004 (제15장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
회사가 전환사채(CB)를 발행했는데, K-GAAP 상에서 이를 사채(장기성부채)와 전환권대가(자본)로 분리해서 인식하는 것이 맞는지 확인 부탁드립니다.

**② 예상 정답**  
K-GAAP 발행자 입장에서 전환사채의 발행금액은 부채요소와 자본요소로 분리하여 인식함. 부채요소는 전환권이 없는 유사한 일반사채의 시장이자율로 할인한 미래현금흐름의 현재가치로 측정하고, 자본요소인 전환권대가는 발행금액에서 부채요소를 차감한 잔여금액으로 측정하여 자본조정(기타자본요소)으로 분류함. 분리인식이 원칙임.

**②' 예상 근거(gold)**: 15.18, 15.20

**③ 실제 답변**  
네. 제공된 문맥에 따르면, 채권·채무조정의 일환으로 발행되는 전환사채는 전통적인 전환사채와 달리 제15장 ‘자본’의 규정에 불구하고 전환권을 인식하지 않고, 전환사채의 만기까지의 미래 현금흐름을 채무 발생시점의 유효이자율로 할인한 현재가치와 조정대상채무의 장부금액 차이를 채무조정이익으로 인식하도록 되어 있습니다 [6]. 또한 채권·채무조정으로 인하여 발행되는 전환증권은 전환권의 가치가 아주 미미할 것으로 보아 채무의 조건변경으로 회계처리하도록 하였습니다 [3]. 따라서 질의하신 “사채(장기성부채)와 전환권대가(자본)로 분리 인식”은 이 문맥상 일반적인 CB 발행에 대한 설명으로 보기 어렵고, 적어도 채권·채무조정으로 발행되는 전환사채의 경우에는 전환권대가를 별도로 자본으로 인식하지 않는 취지입니다 [3][6].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크는 전환사채/전환권의 회계처리와 채권·채무조정(출자전환) 상황을 설명할 뿐, 질문의 핵심인 K-GAAP에서 전환사채를 사채(장기성부채)와 전환권대가(자본)로 분리 인식하는지에 대한 명시적 기준을 직접 제시하지 않습니다. 특히 전환권 분리인식 여부, 분리 시 측정기준, 자본/부채 구분 조건이 누락되어 있어 이 청크만으로 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-005 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
당사가 전환사채(CB)를 발행한 게 아니라 '투자(취득)'한 경우입니다. K-GAAP에서는 내재된 전환권을 주계약인 채권과 분리하여 별도의 파생금융상품(자산)으로 분류 및 표시해야 하나요?

**② 예상 정답**  
K-GAAP에서 전환사채 보유자(투자자)는 내재된 전환권을 주계약인 채권과 분리하여 파생상품으로 회계처리하여야 하는지를 검토해야 한다.(6.41, 6.43)
1. 분리한 경우 : 6.42에 따라 회계처리
2. 분리하지 않은 경우 : 전환사채는 매도가능증권으로 분류할 수 없기 때문에 당기손익인식지정항목으로 지정한다.(6.46)

**②' 예상 근거(gold)**: 6.41, 6.42, 6.43, 6.44, 6.45, 6.46, 6.47

**③ 실제 답변**  
아니요. 제공된 맥락에 따르면 내재파생상품은 주계약과 경제적 특성 및 위험도에서 ‘명확하고 밀접한 관련성’이 없는 경우에 분리하며, 그 예로 주계약이 채권이고 수익률이나 원금상환금액이 주가 또는 주가지수에 연동된 경우를 들고 있습니다 [1]. 반면, 주계약과 내재파생상품이 모두 채권형인 경우에는 분리하지 않고 주계약에 따라 회계처리할 수 있다고 설명합니다 [1]. 따라서 질문하신 ‘전환사채(CB)를 투자(취득)한 경우’의 내재된 전환권을 자동으로 주계약인 채권과 분리하여 별도의 파생금융상품(자산)으로 표시해야 한다고는 이 맥락만으로 볼 수 없습니다 [1][3][4].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크는 내재파생상품 분리 일반론과 전환사채/신주인수권 행사 시 처리(실 6.52~6.54), 파생상품 정의 및 예시를 담고 있으나, 질문의 핵심인 '투자(취득)한 전환사채에서 내재된 전환권을 주계약인 채권과 분리하여 별도 파생금융상품(자산)으로 인식·표시하는지'에 대한 명시적 결론이나 K-GAAP 규정이 직접 제시되어 있지 않습니다. 또한 분리요건의 세부 판단기준(예: 취득자의 경우 회계처리, 분류·표시 기준)이 누락되어 있어 청크만으로는 답변을 확정할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-006 (제31장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
중소기업 임의감사를 나갔는데, 회사가 유형자산 감가상각비를 세법상 산식(정률법 등)으로 그대로 계산해 두었습니다. 이거 K-GAAP 상으로 허용되나요?

**② 예상 정답**  
K-GAAP 중소기업 회계처리 특례(일반기업회계기준 31.10)는 유형자산·무형자산의 내용연수 및 잔존가치의 결정을 법인세법 등 법령에 따를 수 있도록 허용함. 그러나 감가상각방법 자체(정률법 등 세법 산식)를 그대로 적용하도록 하는 특례는 없으며, 감가상각방법은 자산의 미래경제적효익이 소비되는 형태를 반영하는 합리적 방법을 선택해야 함. 따라서 세법상 내용연수·잔존가치는 특례로 그대로 쓸 수 있으나, 정률법 등 방법을 세법이라는 이유만으로 그대로 쓰는 것은 특례의 적용 범위가 아님.

**②' 예상 근거(gold)**: 31.10

**③ 실제 답변**  
네, 허용되지 않는다고 보아야 합니다. 일반기업회계기준에서 유형자산은 재화의 생산·용역 제공 등에 사용되는 물리적 형태가 있는 비화폐성자산이며, 토지와 감가상각 대상인 설비자산을 구분하여 표시합니다 [3]. 또한 유형자산은 취득원가를 기준으로 하되, 회계정책을 적용할 때는 재무제표 금액에 영향을 미치는 판단의 근거를 주석으로 기재할 수 있으나, 제공된 문맥 어디에도 감가상각비를 세법상 산식으로 그대로 계산해도 된다는 허용 근거는 없습니다 [10]. 따라서 중소기업 임의감사에서도 유형자산 감가상각은 세법상 방식이 아니라 회계기준에 따라 처리해야 하며, 세법상 정률법 등을 그대로 적용한 경우에는 회계처리 적정성 문제를 검토해야 합니다 [3][10].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 중소기업의 유형자산 감가상각비를 세법상 산식(정률법 등)으로 계산해도 K-GAAP상 허용되는지에 관한 것이지만, 청크에는 유형자산의 정의(실 2.32~2.34), 표시 방식(결 2.4 등), 감가상각방법의 허용범위나 세법상 산식 사용 가능 여부에 대한 직접 규정이 없습니다. 또한 감가상각방법 변경 사례(5번의 정률법→정액법)만 있을 뿐, 일반적으로 세법상 계산식을 그대로 적용할 수 있는지 판단할 수 있는 근거와 조건이 누락되어 있어 이 청크만으로는 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-007 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
K-GAAP 기업이 채권형 매도가능증권을 보유하고 있습니다. 유효이자율법으로 상각을 먼저 한 다음, 기말 상각후원가와 공정가치의 차액을 매도가능증권평가손익(자본)으로 잡는 절차가 맞나요?

**② 예상 정답**  
K-GAAP에서 채권형 매도가능증권은 먼저 유효이자율법을 적용하여 할인·할증액을 상각하여 상각후원가를 산정한 뒤, 기말 공정가치와 상각후원가의 차액을 '매도가능증권평가손익(기타포괄손익누계액, 자본)'으로 인식함.

**②' 예상 근거(gold)**: 6.29, 6.30, 6.31

**③ 실제 답변**  
네. 제공된 문맥에 따르면 매도가능증권으로 분류된 채무증권은 할인 또는 할증차금을 먼저 상각하여 이자수익을 인식한 후, 상각후원가와 공정가치의 차이인 미실현보유손익을 기타포괄손익누계액(자본)으로 처리합니다 [4]. 또한 매도가능증권 중 채무증권을 다른 범주로 재분류하는 경우에도, 재분류 시점까지의 미실현보유손익 잔액은 계속 기타포괄손익누계액으로 두고 잔여기간에 걸쳐 유효이자율법으로 상각하여 이자수익에 가감합니다 [6]. 따라서 질문하신 절차는 문맥상 맞는 처리로 보입니다 [4][6].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크 [4], [6], [3]에 매도가능증권 채무증권의 이자수익은 할인 또는 할증차금을 먼저 상각한 뒤, 상각후원가와 공정가치의 차이를 기타포괄손익누계액(자본)으로 처리한다고 명시되어 있어 질문의 핵심 주제는 직접 관련됩니다. 다만 질문은 K-GAAP 기업에 대한 절차의 정합성을 묻는 반면, 청크에는 'K-GAAP' 적용범위에서의 일반 규정만 있고 채권형 매도가능증권의 기말 상각후원가-공정가치 차액 처리 순서가 질문 표현과 동일하게 완결적으로 제시된 것은 아니어서, 외부 기준서 추가 검색 없이 단정 답변 근거를 충분히 추출하기는 어렵습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-008 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
과거 20년 말에 토지 재평가를 수행한 K-GAAP 기업입니다. 매 3년이나 5년마다 재평가를 수행한다는 문구가 있던데, 5년이 지나면 무조건 의무적으로 재평가를 다시 해야 한다는 뜻인가요?

**② 예상 정답**  
'매 3년이나 5년마다' 문구는 의무 주기가 아니라, 공정가치 변동이 빈번하지 않거나 중요하지 않은 자산의 재평가 빈도에 대한 예시적 가이드임. 핵심 원칙은 보고기간 말의 장부금액이 공정가치와 중요하게 차이나지 않도록 충분히 규칙적으로 재평가하는 것이며, 5년 경과 시 강제적으로 재평가를 다시 해야 하는 의무규정은 아님.

**②' 예상 근거(gold)**: 10.26

**③ 실제 답변**  
제공된 맥락만으로는 ‘토지 재평가를 5년이 지나면 무조건 의무적으로 다시 해야 하는지’에 대한 직접적인 규정을 확인할 수 없습니다. 다만 맥락상 공정가치 측정에서는 공시가격이 공정가치를 반영하지 않는 경우 가치평가기법을 사용하고, 시장상황과 관측가능한 시장정보를 정기적으로 반영해야 하며, 시장성이 없는 지분증권도 공정가치를 신뢰성 있게 측정할 수 없는 경우가 따로 설명되어 있을 뿐입니다 [1][5][9]. 따라서 이 자료만으로는 3년 또는 5년마다 재평가가 ‘무조건’ 의무라는 결론을 내릴 수 없고, 해당 재평가 주기 규정 자체는 제시된 맥락에 없습니다 [1][5][9].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 제공 청크는 금융상품 공정가치, 회계정책 변경, 포괄손익, 재무제표 양식 등만 담고 있어 ‘토지 재평가’와 ‘3년/5년마다 재평가 의무 여부’에 관한 K-GAAP 근거가 전혀 없습니다. 질문의 핵심인 재평가 주기와 5년 경과 시 의무 재평가 여부를 판단할 수 있는 수치·조건·기준이 누락되어 있어 추론 없이 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-009 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
K-GAAP 하에서 재평가모형을 적용 중인 토지/건물 등 유형자산을 처분할 때, 기존에 자본으로 인식해 둔 재평가잉여금은 당기손익으로 재분류조정(Recycling) 하는 것이 맞습니까?

**② 예상 정답**  
K-GAAP에서 재평가모형 적용 유형자산을 처분(제거)할 때, 재평가와 관련하여 기타포괄손익누계액(자본)에 인식해 둔 잔액이 있다면 그 자산을 제거하는 시점에 당기손익으로 인식함(재분류조정함). 처분손익 자체는 순매각금액과 장부금액의 차액으로 산정하여 당기손익에 반영함. (일반기업회계기준 10.45)

**②' 예상 근거(gold)**: 10.45

**③ 실제 답변**  
예. 제공된 문맥에 따르면, 일반기업회계기준에서는 위험회피대상 예상거래가 기존자산의 처분 등인 경우 기존자산의 공정가치 평가손익이 당기손익에 반영되면 위험회피대상에서 제외된다고 설명하고 있습니다. 다만 이는 '예상거래'의 위험회피 대상 여부에 관한 설명이며, 처분 시 자본에 누적된 재평가잉여금을 당기손익으로 재분류하는지 여부 자체는 제시된 문맥에 직접적으로 규정되어 있지 않습니다 [1][3].

따라서 이 문맥만으로는 K-GAAP 하에서 재평가모형 유형자산 처분 시 재평가잉여금의 당기손익 재분류조정 여부를 확정적으로 답하기 어렵습니다 [1][3].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 K-GAAP 하에서 유형자산 재평가모형 적용 후 처분 시 재평가잉여금의 당기손익 재분류조정 여부를 묻지만, 제공 청크는 대부분 위험회피회계와 유가증권 재분류, 해외사업장 환산손익에 관한 내용입니다. 유형자산 재평가잉여금의 처분 시 회계처리(재분류조정/이익잉여금 대체 등)와 직접 연결되는 문단이 청크 내에 없으므로 수치·조건·기준을 누락 없이 추출할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-010 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
K-GAAP에서 매도가능증권 중 지분상품을 처분할 때의 구체적인 회계처리가 궁금합니다. 기존에 인식했던 평가손익은 어떻게 처리하나요?

**② 예상 정답**  
K-GAAP에서 매도가능증권(지분상품 포함) 처분 시, 기존에 기타포괄손익누계액(자본)에 인식한 매도가능증권평가손익 누적액을 처분 시점에 당기손익으로 재분류조정(Recycling)함. 처분손익은 (처분가액 - 취득원가)로 산정되며, 누적 평가손익 가감을 통해 당기손익으로 일괄 반영됨.

**②' 예상 근거(gold)**: 6.31, 6.34

**③ 실제 답변**  
매도가능증권 중 공정가치로 평가하는 지분증권에 손상차손의 객관적 증거가 있는 경우, 당기에 인식할 손상차손은 ‘공정가치가 취득원가에 미달하는 금액’에서 ‘이전 기간에 이미 인식한 손상차손’을 차감한 금액입니다 [2]. 또한 공정가치 평가로 인해 기타포괄손익누계액에 미실현보유손실이 남아 있으면, 그 금액을 먼저 기타포괄손익누계액에서 제거하여 손상차손에 반영하고, 미실현보유이익이 남아 있으면 전액 기타포괄손익누계액에서 제거하여 유가증권 장부금액에서 직접 차감합니다 [2].

질의와 관련한 처분 시 처리에 대해, 제공된 문맥은 매도가능증권의 ‘매도’나 ‘재분류’에 따른 미실현보유손익의 처리, 그리고 실현손익 인식에 관한 규정만 제시하고 있습니다 [1][3][5][6]. 즉, 매도가능증권의 매도 또는 처분으로 실현된 이익·손실은 당기손익에 반영하며, 기타포괄손익누계액에 포함된 미실현보유손익은 실현 시 당기손익으로 인식됩니다 [3][5]. 따라서 처분 시에는 기존에 기타포괄손익누계액에 누적되어 있던 평가손익을 실현손익으로 당기손익에 반영하는 취지로 이해할 수 있습니다 [3][5][7].

다만, 지분상품의 ‘처분’에 대해 평가손익을 구체적으로 어떻게 대체분개하는지까지는 제시된 문맥에 직접적 서술이 없습니다. 따라서 이 문맥만으로는 지분상품 처분의 세부 분개를 단정할 수는 없고, 다만 처분으로 실현된 평가손익은 당기손익에 반영된다고만 답할 수 있습니다 [3][5].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 K-GAAP에서 매도가능증권 중 지분상품을 처분할 때 기존 평가손익의 처리인데, 청크에는 처분 시점의 구체적 회계처리(예: 처분손익에 포함 여부, 기타포괄손익누계액의 대체/재분류, 매도가능지분증권 처분분개)가 직접 제시되어 있지 않습니다. 다만 일부 관련 근거로는 6.A7에서 "매도가능증권과 만기보유증권의 매도, 상환 및 손상차손으로 실현된 이익이나 손실은 당기손익에 반영한다"고만 되어 있어, 지분상품 처분 시 평가손익 처리의 세부 기준을 이 청크만으로 완결적으로 답할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-011 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
회사가 기말에 외화환산손익을 계산한 후, 외화환산이익에서 손실을 뺀 순액으로만 손익계산서에 표시해 두었습니다. K-GAAP 상 외화환산손익을 이렇게 상계하여 순액 표시하는 것이 규정상 허용되나요?

**② 예상 정답**  
K-GAAP에서는 수익과 비용을 원칙적으로 총액으로 표시하며, 임의 상계 후 순액 표시는 허용되지 아니함. 외화환산이익과 외화환산손실은 성격이 상이한 별도의 손익항목으로서 각각 총액으로 표시해야 하며, 동일 거래에서 발생한 경우 등 예외적 상황이 아닌 한 상계하여 순액으로 표시할 수 없음.

**②' 예상 근거(gold)**: 2.57

**③ 실제 답변**  
네, 허용됩니다. 일반기업회계기준에서는 수익과 비용을 각각 총액으로 보고하는 것이 원칙이지만, 다른 장에서 상계를 허용하는 경우에는 상계하여 표시할 수 있습니다 [4]. 또한 외환차익과 외환차손처럼 동일 또는 유사한 성격의 중요하지 않은 차익·차손이 반복적으로 발생하는 경우에는 서로 상계할 수 있도록 규정하고 있으며, 다만 어느 한쪽 또는 각각의 금액이 중요하면 상계하여 표시하지 않습니다 [1]. 따라서 기말 외화환산손익도 외환차익과 외환차손의 성격상 중요하지 않은 경우에는 순액으로 상계 표시할 수 있습니다 [1][4].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크 [4]의 2.57은 수익·비용의 총액표시 원칙과 상계 허용 범위만 제시할 뿐, 외화환산손익을 '외화환산이익-손실의 순액'으로 손익계산서에 표시할 수 있는지에 대한 직접 규정이 없습니다. 반면 청크 [2]의 2.45~2.56은 손익계산서의 표시항목을 열거하지만 외화환산손익의 순액 상계 허용 여부, 구체적 계산 기준, 인식 시점까지는 포함하지 않아 질문에 대한 규정을 이 청크만으로 확정할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-012 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
확정급여형(DB) 퇴직연금 제도를 운용 중인 K-GAAP 기업입니다. 별도의 계리평가보고서 없이, 사외적립자산 내역만 기록하고 퇴직급여충당부채는 기말 일시퇴직기준 추계액으로 설정하면 올바른 회계처리인가요?

**② 예상 정답**  
K-GAAP에서 DB형 퇴직연금 운용기업의 퇴직급여충당부채는 보고기간 말 현재 전 종업원이 일시에 퇴직할 경우 지급할 퇴직금에 상당하는 일시퇴직기준 추계액으로 측정함. 보험수리적 가정에 의한 계리평가보고서가 강제되지 아니하며, 사외적립자산은 공정가치로 측정하여 퇴직급여충당부채에서 차감하는 형식으로 표시함. 제시된 처리는 적정함.

**②' 예상 근거(gold)**: 21.10, 21.11, 21.12, 21.8

**③ 실제 답변**  
아니요. 확정급여형(DB) 퇴직연금제도에서는 재무상태표에 퇴직급여충당부채와 퇴직연금미지급금을 퇴직연금운용자산과 차감하는 형식으로 표시하고, 퇴직연금운용자산은 기업이 직접 보유하는 것으로 보아 하나로 통합하여 '퇴직연금운용자산'으로 표시한 뒤 그 구성내역을 주석으로 공시해야 합니다 [7][1]. 또한 확정급여형 제도의 부채는 종업원이 퇴직하기 전에는 보고기간말 현재 퇴직할 경우 지급하여야 할 퇴직일시금 상당액을 퇴직급여충당부채로 인식하며, 종업원이 퇴직 후 연금 수령을 선택한 경우에만 퇴직연금미지급금을 인식합니다 [2][5]. 따라서 별도의 계리평가보고서 없이 사외적립자산 내역만 기록하고, 퇴직급여충당부채를 기말 일시퇴직기준 추계액으로 설정하는 방식만으로는 확정급여형 DB 퇴직연금의 회계처리를 모두 충족한다고 보기 어렵습니다 [2][7].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크에는 확정급여형(DB) 퇴직연금의 부채 측정이 ‘보고기간말 현재 종업원이 퇴직할 경우 지급하여야 할 퇴직일시금 상당액’인지, 또는 퇴직 후 연금수령 선택 시 ‘퇴직연금미지급금’으로 전환하는지에 대한 규정은 있으나, 질문의 핵심인 ‘별도의 계리평가보고서 없이’가 가능한지에 대한 명시적 판단 기준은 없다. 또한 사외적립자산 내역만 기록하고 퇴직급여충당부채를 기말 일시퇴직기준 추계액으로 설정하는 것이 올바른지 여부를 직접적으로 결론짓는 수치·조건(계리평가 필요 여부, 보고서 필요성 등)이 청크에 누락되어 있어 이 청크만으로는 답변을 확정할 수 없다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-013 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
K-GAAP 기업이 만기보유증권이나 장기성 채권을 보유하고 있을 때, 유효이자율법을 적용하여 이자수익을 인식해야 합니까?

**② 예상 정답**  
K-GAAP에서 만기보유증권과 장기성 채권의 이자수익은 유효이자율법을 적용하여 인식함. 취득가액과 만기 액면가의 차이(할인·할증액)는 상환기간에 걸쳐 유효이자율법으로 상각하여 이자수익에 가감함.

**②' 예상 근거(gold)**: 6.29

**③ 실제 답변**  
네. K-GAAP에서는 만기보유증권은 상각후원가로 평가하며, 장부금액과 만기액면금액의 차이를 상환기간에 걸쳐 유효이자율법으로 상각하여 이자수익에 반영합니다 [4]. 또한 모든 채무증권의 이자수익은 할인 또는 할증차금의 상각액을 가감하여 인식한다고 규정하고 있습니다 [5]. 따라서 만기보유증권이나 장기성 채권을 보유한 경우 유효이자율법을 적용하여 이자수익을 인식해야 합니다 [4][5].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크 [4], [5], [8]에 만기보유증권은 상각후원가로 평가하고 장부금액과 만기액면금액의 차이를 상환기간에 걸쳐 유효이자율법으로 상각하여 이자수익에 가감한다는 규정이 명시되어 있으며, [5]의 ‘모든 채무증권의 이자수익은 할인 또는 할증차금의 상각액을 가감하여 인식한다’는 문구로 장기성 채권에도 같은 원칙이 확인된다. 질문이 요구하는 적용 방법(유효이자율법에 의한 이자수익 인식)과 직접 대응하는 기준이 청크 내에 충분히 있어 외부 기준서 추가 검색은 필요하지 않다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-014 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
회사가 퇴직연금운용자산을 재무상태표에 계상할 때, 일부는 장기금융상품으로 잡고 일부는 퇴직급여충당부채의 차감 항목으로 쪼개서 표시했습니다. 분류 기준이 무엇인가요?

**② 예상 정답**  
K-GAAP상 퇴직연금운용자산은 원칙적으로 퇴직급여충당부채의 차감항목(투자자산 내)으로 표시함. 다만 운용자산이 퇴직급여충당부채를 초과하는 경우에 한해 그 초과액을 별도의 투자자산(장기금융상품 등)으로 표시함.

**②' 예상 근거(gold)**: 21.12

**③ 실제 답변**  
분류 기준은 ‘어떤 제도의 자산이냐’와 ‘초과자산인지 여부’입니다. 확정급여형퇴직연금제도에서 운용되는 자산은 기업이 직접 보유하는 것으로 보아 회계처리하고, 재무상태표에는 이를 하나로 통합하여 ‘퇴직연금운용자산’으로 표시합니다 [1][3]. 이 퇴직연금운용자산은 퇴직급여충당부채와 퇴직연금미지급금의 합계액에서 차감하는 형식으로 표시하며 [2][3][5], 퇴직연금운용자산이 그 합계액을 초과하는 경우에만 초과액을 투자자산 과목으로 표시합니다 [2][3][6]. 따라서 일부를 장기금융상품으로, 일부를 퇴직급여충당부채 차감항목으로 쪼개는 기준은 자산의 개별 성격이 아니라, 퇴직연금운용자산이 부채 합계액을 초과하는지 여부입니다 [2][3][6].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 퇴직연금운용자산을 재무상태표에서 장기금융상품과 퇴직급여충당부채 차감항목으로 나누어 표시하는 분류 기준을 묻고 있으며, 청크 [8]의 21.14 ⑴에 "퇴직금제도에서 경과적으로 존재하는 퇴직보험예치금은 확정급여형퇴직연금제도의 퇴직연금운용자산과 구분하여 퇴직급여충당부채에서 차감하는 형식으로 표시"한다고 명시돼 있습니다. 또한 청크 [3]의 21.14 및 [6] 예시에서 초과 시 "투자자산"으로 표시한다고까지 제시되어 있어 외부 기준서 검색 없이 답변 근거를 추출할 수 있습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-015 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
K-GAAP에서 기본 재무제표는 어떤 서식들로 구성되나요?

**② 예상 정답**  
재무제표는 재무상태표, 손익계산서, 현금흐름표, 자본변동표 및 주석으로 구성함. 주석은 재무제표의 일부를 이룸.

**②' 예상 근거(gold)**: 2.16

**③ 실제 답변**  
K-GAAP에서 재무제표는 재무상태표, 손익계산서, 현금흐름표, 자본변동표 및 주석으로 구분하여 작성합니다 [5]. 또한 재무제표는 재무상태표, 손익계산서, 현금흐름표, 자본변동표로 구성되며 주석을 포함한다고도 설명합니다 [4].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질문은 K-GAAP에서 기본 재무제표가 어떤 서식들로 구성되는지인데, 청크 [4], [5], [9]에 재무제표 구성요소가 직접 제시되어 있습니다(재무상태표, 손익계산서, 현금흐름표, 자본변동표 및 주석). 다만 이 내용은 ‘서식들’의 구체적 양식/예시까지는 제공하지 않고 구성요소 수준만 제시하므로, 질문이 요구하는 구체적 서식 정보를 청크만으로 완결적으로 답한다고 보기 어렵습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-016 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
자산을 유동자산으로 분류하는 기준은 무엇인가요?

**② 예상 정답**  
정상영업주기 내 실현·판매·소비될 것으로 예상되거나 보고기간종료일부터 1년 이내 실현될 자산, 단기매매목적 보유자산, 사용제한이 없는 현금및현금성자산은 유동자산으로 분류함. 그 외는 비유동자산으로 분류함.

**②' 예상 근거(gold)**: 2.20

**③ 실제 답변**  
자산은 1년을 기준으로 유동자산과 비유동자산으로 분류합니다. 다만, 사용의 제한이 없는 현금및현금성자산, 정상적인 영업주기 내에 실현될 것으로 예상되거나 판매목적 또는 소비목적으로 보유하고 있는 자산, 단기매매 목적으로 보유하는 자산, 그리고 보고기간종료일로부터 1년 이내에 현금화 또는 실현될 것으로 예상되는 자산은 유동자산으로 분류합니다 [1][2]. 또한 정상적인 영업주기 내에 판매되거나 사용되는 재고자산과 회수되는 매출채권 등은 1년 이내에 실현되지 않더라도 유동자산으로 분류하며, 비유동자산 중 1년 이내에 실현되는 부분도 유동자산으로 분류합니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크 [1], [2], [5], [6]에 자산의 유동자산 분류 기준이 직접 제시되어 있습니다. 예를 들어 '사용의 제한이 없는 현금및현금성자산', '정상적인 영업주기 내에 실현될 것으로 예상되거나…', '보고기간종료일로부터 1년 이내에 현금화 또는 실현될 것으로 예상되는 자산', '자산은 1년을 기준으로 유동자산과 비유동자산으로 분류한다'가 포함되어 있어 외부 기준서 추가 검색 없이 답변 가능합니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-017 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
사용이 제한된 예금도 현금및현금성자산으로 유동 분류하나요?

**② 예상 정답**  
현금및현금성자산은 유동자산으로 분류하나, 사용제한 기간이 보고기간종료일부터 1년을 초과하는 경우에는 비유동자산으로 분류함.

**②' 예상 근거(gold)**: 2.20

**③ 실제 답변**  
아니요. 현금및현금성자산으로 유동 분류되는 것은 ‘사용의 제한이 없는 현금및현금성자산’입니다 [2]. 또한 현금및현금성자산의 정의도 취득 당시 만기일(또는 상환일)이 3개월 이내인 금융상품 등을 말한다고 되어 있으므로, 사용이 제한된 예금은 이 범주에 그대로 포함된다고 보기 어렵습니다 [4][6]. 다만 맥락에는 사용이 제한된 예금이 별도로 유동/비유동으로 어떻게 분류되는지에 대한 직접 규정은 없습니다 [2][4].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크 [2]에는 '사용의 제한이 없는 현금및현금성자산'만 유동자산으로 분류한다고 되어 있어, 질문의 핵심인 '사용이 제한된 예금'이 현금및현금성자산에 포함되는지에 대한 직접 규정이 없습니다. 오히려 청크 [9]는 '설비확장 및 채무상환 등에 사용할 특정 목적의 예금'을 투자자산에 포함한다고 하여 별도 해석이 필요하므로, 이 청크만으로는 질문에 대한 확정 답변을 도출할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-018 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
간접법 현금흐름표에서 대손상각비와 대손충당금 환입액은 어떻게 가감하나요?

**② 예상 정답**  
간접법은 당기순이익에 현금유출입이 없는 비용·수익을 가감함. 현금유출이 없는 비용인 대손상각비는 가산하고, 현금유입이 없는 수익인 대손충당금 환입액은 차감함.

**②' 예상 근거(gold)**: 2.65

**③ 실제 답변**  
간접법 현금흐름표에서는 당기순이익(또는 당기순손실)에 현금의 유출이 없는 비용 등을 가산하고 현금의 유입이 없는 수익 등을 차감합니다 [1]. 또한 회수불가능한 채권의 대손은 대손충당금과 상계하고, 대손충당금이 부족하면 그 부족액을 대손상각비로 처리합니다 [2]. 따라서 대손상각비는 현금 유출이 없는 비용이므로 가산하고, 대손충당금 환입액은 현금 유입이 없는 수익이므로 차감합니다 [1][2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 간접법 현금흐름표에서 대손상각비와 대손충당금 환입액의 가감 방법인데, 청크 [1]의 2.65가 간접법의 원칙(당기순이익에 현금의 유출이 없는 비용은 가산, 현금의 유입이 없는 수익은 차감)을 제시하고, 청크 [2], [7], [8]이 대손상각비·대손충당금 추가설정·환입의 처리(추가설정은 대손상각비, 초과분은 대손충당금 환입)를 직접 설명한다. 따라서 외부 기준서 추가 검색 없이 청크만으로 답변 근거를 추출할 수 있다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-019 (제5장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
회계정책을 변경하면 과거 재무제표는 어떻게 처리하나요?

**② 예상 정답**  
회계정책의 변경은 원칙적으로 소급적용하여 비교표시하는 과거 재무제표를 재작성하고 기초 이익잉여금 등을 수정함. 소급적용이 실무적으로 불가능하면 전진적용함.

**②' 예상 근거(gold)**: 5.11, 5.12

**③ 실제 답변**  
회계정책을 변경하면 원칙적으로 전기 또는 그 이전 기간의 재무제표를 소급하여 재작성합니다. 다만 회계정책 변경의 누적효과를 합리적으로 결정하기 어려운 경우에는 전진적으로 처리하여 그 효과를 당기와 당기 이후 기간에 반영합니다. 따라서 과거 재무제표는 소급재작성하는 것이 원칙이고, 소급이 어려운 경우에만 예외적으로 전진적 처리합니다 [2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘회계정책을 변경하면 과거 재무제표를 어떻게 처리하는가’인데, 청크 [2]에 원칙적으로 소급적용하여 전기 또는 그 이전의 재무제표를 재작성한다는 내용과, 누적효과를 합리적으로 결정하기 어려운 경우 전진적으로 처리한다는 예외가 포함되어 있어 답변 근거가 직접 제시됩니다. 다만 일반기업회계기준의 회계정책 변경 처리에 대한 전체 조건·예외가 모두 제시된 것은 아니므로 엄격 기준상 질문을 완전하게 답할 수준으로는 보지 않아 false입니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-020 (제5장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 2

**① 질문**  
감가상각 내용연수·방법 같은 회계추정의 변경은 어떻게 처리하나요?

**② 예상 정답**  
회계추정의 변경은 소급하지 않고 변경한 기간과 그 이후 기간에 걸쳐 전진적으로 적용하여 효과를 반영함.

**②' 예상 근거(gold)**: 5.14, 5.15, 5.16, 5.17

**③ 실제 답변**  
감가상각의 내용연수나 방법 변경은 회계추정의 변경이므로, 일반적으로 변경된 추정치를 변경 시점부터 미래에 적용하는 전진적 처리로 반영합니다. 즉 당기와 당기 이후 기간의 감가상각비에 영향을 주며, 과거 재무제표를 소급하여 재작성하는 방식은 아닙니다 [1]. 다만 제공된 문맥에는 회계추정 변경의 구체적 처리 절차에 대한 직접 문구는 없고, 회계정책 변경의 소급·전진 적용과 표시 기준, 그리고 정률법에서 정액법으로의 변경 사례가 제시되어 있어 이를 통해 전진적 반영의 취지를 확인할 수 있습니다 [1][3].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 감가상각 내용연수·방법 변경 같은 '회계추정의 변경' 처리인데, 제공 청크에는 회계정책 변경(예: 결 2.14, 실 2.14/2.17의 이익잉여금 변동 반영)과 오류수정, 재분류만 있고 회계추정 변경의 인식·전진적 처리·당기 영향 반영 기준이 직접 제시되지 않습니다. 따라서 질문에 필요한 구체적 처리기준이 누락되어 있어 청크만으로는 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-021 (제5장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
전기에 중대한 오류가 있었음을 발견하면 어떻게 수정하나요?

**② 예상 정답**  
중대한 오류는 소급 재작성하여 비교표시 재무제표를 수정하고, 비교표시 이전 기간의 오류는 가장 이른 기간의 기초 이익잉여금에 반영함. 중대하지 않은 오류는 당기 영업외손익으로 처리할 수 있음.

**②' 예상 근거(gold)**: 5.18, 5.19, 5.20

**③ 실제 답변**  
전기에 중대한 오류가 발견되면, 그 오류의 영향으로 전기 또는 그 이전 기간의 재무제표를 소급하여 수정하고, 자본변동표에서는 전기에 이미 보고된 이익잉여금(또는 결손금) 금액을 별도로 표시한 뒤 중대한 전기오류수정으로 인한 영향을 가감한 수정후 기초이익잉여금을 표시합니다 [1]. 또한 이익잉여금의 변동항목에 ‘중대한 전기오류수정손익’을 포함하여 표시합니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘전기에 중대한 오류가 있었음을 발견하면 어떻게 수정하나요?’로, 청크 [1]의 2.80~2.81, [6] 결 2.13, [2]·[3]·[5]·[9]의 예시에서 중대한 전기오류수정손익을 이익잉여금 변동항목으로 표시하고 전기 이미 보고된 금액을 별도로 표시한 뒤 수정후 기초이익잉여금을 표시하는 방법이 명시되어 있습니다. 외부 기준서 참조 지시도 없고, 질문에 필요한 수정 방식이 청크 내에서 직접 확인되므로 추가 검색은 필요하지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-022 (제5장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
회계추정의 변경과 오류수정은 실무상 어떻게 구분하나요?

**② 예상 정답**  
당시 이용가능한 정보에 근거한 합리적 추정이 새로운 정보로 수정되는 것은 추정의 변경(전진)이고, 당시 이용가능했던 정보를 반영하지 못한 것은 오류(소급)로 봄.

**②' 예상 근거(gold)**: 5.14, 5.15, 5.16, 5.17, 5.18, 5.19, 5.7

**③ 실제 답변**  
실무상 구분의 핵심은 ‘당기 또는 전기오류의 정정인지’와 ‘과거 기간에 소급하여 재작성해야 하는 중대한 오류인지’입니다. 회계추정의 변경은 오류가 아니라 추정의 변경이므로, 일반적으로 그 효과를 당기와 당기 이후 기간에 전진적으로 반영합니다. 반면 오류수정은 원칙적으로 오류발견연도의 손익에 반영하되, 중대한 오류는 소급적용하여 전기 또는 그 이전 기간의 재무제표를 재작성합니다 [1][2].

또한 일반기업회계기준에서는 중대한 오류를 제외한 전기오류수정손익은 당기순손익에 반영되어 당기의 포괄손익에 포함되지만, 중대한 오류는 소급재작성하므로 당기의 포괄손익에는 포함되지 않습니다 [2]. 실무적으로는 개별 사안이 과거 재무제표를 다시 작성할 정도의 ‘중대성’이 있는지, 아니면 단순히 이후 기간에 추정치가 바뀐 것인지로 구분하면 됩니다 [2][4].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '회계추정의 변경과 오류수정'의 실무상 구분 기준을 묻지만, 청크에는 오류수정(결 2.13, 실 2.14~2.17)만 있고 회계추정의 변경을 오류수정과 어떻게 구별하는지에 대한 판단기준·정의·예시가 직접 제시되지 않았습니다. 또한 질문의 핵심인 구분 기준(예: 추정변경의 성격, 오류의 정의, 인식 시점 등)이 누락되어 있어 청크만으로는 답변을 확정할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-023 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
K-GAAP에서 유가증권은 어떤 계정으로 분류하나요?

**② 예상 정답**  
취득목적과 보유의도·능력에 따라 단기매매증권, 매도가능증권, 만기보유증권으로 분류하고, 유의적 영향력이 있으면 지분법적용투자주식으로 분류함.

**②' 예상 근거(gold)**: 6.22, 6.23, 6.24, 6.25, 6.26, 6.27

**③ 실제 답변**  
K-GAAP에서는 유가증권을 재무상태표의 자산 중 투자자산으로 분류합니다. 투자자산은 장기적인 투자수익을 얻기 위해 보유하는 채무증권과 지분증권 등을 포함하며, 매도가능증권과 만기보유증권은 비유동자산으로 분류되는 경우 장기투자증권으로 표시할 수 있습니다 [5][6]. 또한 유가증권은 실무상 단기매매증권, 매도가능증권, 만기보유증권으로 분류합니다 [1][2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질문은 'K-GAAP에서 유가증권은 어떤 계정으로 분류하나요?'인데, 청크에는 유가증권의 일반적 분류(단기매매증권, 매도가능증권, 만기보유증권, 장기투자증권 등)는 있으나 '어떤 계정으로'라는 재무상태표/계정과목 수준의 정확한 답을 특정하는 문구가 직접적으로 제시되지 않습니다. 특히 분류 기준과 계정과목을 묻는 질문에 대해 청크 [5], [6]은 자산 분류나 장기투자증권 표시 예시만 제공할 뿐, 유가증권 전체의 계정과목을 누락 없이 단정할 근거가 부족합니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-024 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
매도가능증권의 기말 평가손익은 어디에 인식하나요?

**② 예상 정답**  
매도가능증권의 미실현보유손익은 당기손익이 아니라 기타포괄손익누계액(자본)으로 처리하고, 그 유가증권을 처분하거나 손상차손을 인식하는 시점에 일괄하여 당기손익에 반영함.

**②' 예상 근거(gold)**: 6.31

**③ 실제 답변**  
매도가능증권의 기말 평가손익은 공정가치와 장부금액의 차이로서 기타포괄손익누계액으로 처리합니다. 다만 매도가능증권 중 채무증권에 손상차손이 발생한 경우에는 해당 미실현보유손실을 기타포괄손익누계액에서 제거하여 손상차손에 먼저 반영합니다 [1][2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크 [6]에 "매도가능증권으로 분류된 채무증권의 경우... 미실현보유손익을 기타포괄손익누계액으로 처리한다"고 직접 적시되어 있어, 매도가능증권의 기말 평가손익 인식처를 답할 수 있습니다. 또한 [2], [6], [10]에 손상차손·처분 관련 보충 규정도 함께 있어 별도 외부 기준서 참조 없이 답변 근거를 추출할 수 있습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-025 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
만기보유증권 등 채무증권은 이자수익을 어떻게 인식하나요?

**② 예상 정답**  
채무증권은 상각후원가로 측정하며, 액면금액과 취득가액의 차이를 유효이자율법으로 상환기간에 걸쳐 상각하여 이자수익에 가감함.

**②' 예상 근거(gold)**: 6.29

**③ 실제 답변**  
만기보유증권 등 모든 채무증권의 이자수익은 할인 또는 할증차금을 상각하여 인식합니다. 즉, 만기보유증권은 상각후원가로 평가하고, 장부금액과 만기액면금액의 차이를 상환기간에 걸쳐 유효이자율법으로 상각하여 이자수익에 가감합니다 [7]. 또한 모든 채무증권의 이자수익은 할인 또는 할증차금의 상각액을 가감하여 인식한다고 명시되어 있습니다 [4].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 만기보유증권 등 채무증권의 이자수익 인식방법인데, 청크 [4]의 "모든 채무증권의 이자수익은 할인 또는 할증차금의 상각액을 가감하여 인식한다"와 [7]의 "만기보유증권은 ... 상각후원가 ... 유효이자율법에 의하여 상각하여 ... 이자수익에 가감한다"가 직접적인 답변 근거를 제공합니다. 외부 기준서 참조 지시는 없고, 필요한 인식 방법이 청크 내에 모두 포함되어 있습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-026 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
유가증권 손상차손을 인식해야 하는 객관적 증거에는 어떤 것이 있나요?

**② 예상 정답**  
발행자의 심각한 재무상태 악화(예: 완전자본잠식), 이자·원금의 지급 지연 등 채무불이행은 손상 발생의 객관적 증거가 될 수 있음. 회수가능액이 채무증권 상각후원가·지분증권 취득원가보다 작으면 손상차손을 인식함.

**②' 예상 근거(gold)**: 6.32

**③ 실제 답변**  
유가증권 손상차손의 객관적 증거에는 다음이 포함될 수 있습니다. 유가증권발행자의 재무상태가 심각하게 악화된 경우(예: 당좌거래 정지, 청산 중, 1년 이상 휴업, 완전자본잠식), 이자 지급·원금 상환 지연 등 계약의 실질적 위반 또는 채무불이행, 재무적 곤경으로 인한 차입조건 완화가 불가피한 경우, 발행자의 파산가능성이 높은 경우, 과거 손상차손을 인식한 사유가 계속 존재하는 경우, 발행자의 재무상태 악화로 유가증권이 시장성을 잃은 경우, 비정상적으로 높은 또는 낮은 이자율의 채무증권을 법규나 채무조정협약 등에 의해 취득한 경우, 기업구조조정촉진법에 의한 관리절차를 신청하거나 진행 중인 경우, 그리고 이들에 준하는 기타 사유입니다 [1]. 다만, 유가증권이 상장폐지되어 시장성을 잃었다는 사실만으로는 반드시 손상차손의 증거가 되지 않으며, 발행자의 신용등급 하락 자체도 다른 정보와 함께 보아야 손상차손의 증거가 될 수 있습니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 유가증권 손상차손의 객관적 증거를 묻고 있으며, 청크 [1]의 6.A8에 그 사유가 ⑴~⑼로 직접 열거되어 있습니다(재무상태 심각한 악화, 채무불이행, 회생절차, 파산가능성, 손상사유 지속, 시장성 상실, 비정상적 이자율 채무증권 취득, 관리절차 신청/진행 등). 또한 6.A9에서 상장폐지나 신용등급 하락만으로는 반드시 증거가 아니라고 보충 설명하므로 외부 기준서 추가 검색 없이 답변 가능합니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-027 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
매도가능증권을 처분할 때 처분손익과 기존 평가손익은 어떻게 처리하나요?

**② 예상 정답**  
통제를 상실한 때 ①양도대가로 받았거나 받을 금액과 ②장부금액의 차이에, 기타포괄손익누계액의 미실현보유이익은 가산하고 미실현보유손실은 차감한 금액을 당기손익으로 처리함. 즉 이 시점에 미실현보유손익이 실현된 것으로 봄.

**②' 예상 근거(gold)**: 6.34

**③ 실제 답변**  
매도가능증권을 처분할 때에는, 그 증권과 관련하여 기타포괄손익누계액에 남아 있는 미실현보유손익을 처분손익에 반영합니다. 즉, 양도대가와 장부금액의 차이로 계산한 처분손익에 기타포괄손익누계액에 포함된 미실현보유이익은 가산하고 미실현보유손실은 차감하여 당기손익에 인식합니다 [5]. 또한 매도가능증권의 매도·상환 및 손상차손으로 실현된 이익이나 손실은 당기손익에 반영합니다 [4]. 경쟁제한적 자전거래에 해당하는 경우에는 처분손익을 인식하지 않으며, 매도 후 재매수하더라도 이를 매매거래로 보지 않고 당해 유가증권을 계속 보유한 것으로 봅니다 [3].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 매도가능증권 처분 시 처분손익과 기존 평가손익의 처리인데, 청크 [5]에 "유가증권을 양도하여 ... 기타포괄손익누계액에 포함되어 있는 미실현보유이익을 가산하고 미실현보유손실을 차감한 금액을 유가증권처분손익으로" 반영한다고 직접 제시되어 있습니다. 또한 [3], [4], [7] 등에서 매도가능증권 처분손익 및 미실현보유손익의 실현/처리 원칙이 함께 확인되어 외부 기준서 추가 검색 없이 답변 근거를 추출할 수 있습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-028 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
전환사채를 매도가능증권으로 취득한 경우 내재된 전환권을 분리해야 하나요?

**② 예상 정답**  
내재파생상품은 주계약과 경제적 특성·위험이 밀접하지 않는 등 요건을 모두 충족하면 별도의 파생상품으로 분리함. 만기보유·매도가능으로 분류하는 경우 전환권을 분리하나, 단기매매증권 등 전체를 공정가치로 평가하면 분리하지 않음.

**②' 예상 근거(gold)**: 6.41

**③ 실제 답변**  
전환사채를 매도가능증권으로 취득한 경우에는, 전환권이 내재파생상품 분리요건을 충족하는지에 따라 분리 여부를 판단해야 합니다. 주계약과 내재파생상품의 경제적 특성 및 위험도 사이에 ‘명확하고 밀접한 관련성’이 없는 경우에는 내재파생상품을 분리하여 일반적인 파생상품과 동일하게 회계처리하여야 합니다 [1]. 또한 주계약이 채권이면서 수익률 또는 원금상환금액이 주가나 주가지수에 연동된 경우에는 채권형 주계약과 주식형 내재파생상품의 차이가 명백하므로 별도로 분리하여야 한다고 설명하고 있습니다 [1]. 전환증권의 예에 전환사채가 포함되므로, 전환사채의 전환권은 내재된 전환권으로 볼 수 있습니다 [5]. 따라서 이 자료만으로는 전환사채를 매도가능증권으로 취득한 경우 전환권을 항상 분리하지 않아도 된다고 단정할 수 없고, 위 분리요건 충족 여부에 따라 판단해야 합니다 [1][5].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '전환사채를 매도가능증권으로 취득한 경우 내재된 전환권을 분리해야 하는지'인데, 청크에는 전환사채의 분리요건이나 매도가능증권 취득 시 전환권 분리 여부를 직접 답하는 기준이 없습니다. 제시된 내용은 전환사채 전환 시 취득원가(6.52), 전환증권 예시(5), 매도가능증권 일반 분류·평가(6.63~6.65, 6.A7)와 내재파생상품 일반론(6.97~6.98)만 있어 질문의 구체적 판단기준이 누락되어 있습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-029 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
분리요건을 충족하는 내재파생상품을 분리하지 않으려면 어떻게 하나요?

**② 예상 정답**  
분리요건을 충족함에도 분리하지 않는 경우에는 복합상품 전체를 당기손익인식항목으로 지정하여 공정가치로 평가하고 그 변동을 당기손익에 반영함.

**②' 예상 근거(gold)**: 6.47

**③ 실제 답변**  
내재파생상품이 분리요건을 충족하더라도, 주계약과 내재파생상품 간에 ‘명확하고 밀접한 관련성’이 없고 분리의 실익이 있는 경우에는 주계약에서 분리하여 일반적인 파생상품과 동일하게 회계처리해야 합니다. 반대로 CD금리 연동예금, 이자율스왑계약예금, 확정금리 만기연장예금처럼 주계약과 내재파생상품이 모두 채권형이라 경제적 특성 및 위험도의 차이가 명백하지 않고 공정가치 변동도 크지 않은 경우에는 분리하지 않고 주계약에 따라 회계처리할 수 있습니다 [1]. 다만 예금과 파생상품이 결합된 금융상품이라도 전체적으로 예금으로 보기 어려울 정도라면 예금과 내재파생상품을 분리하여 회계처리해야 합니다 [2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크 [1], [2]에 내재파생상품을 분리하지 않는 경우에 대한 판단기준이 직접 제시되어 있으며, 예금과 파생상품 결합상품에서 ‘경제적 특성 및 위험도 사이에 명확하고 밀접한 관련성’이 없고 문단 6.41의 요건을 충족하면 분리하여야 한다는 내용과, 반대로 ‘모두 채권형’이고 공정가치 변동 실익이 크지 않으면 분리하지 않고 주계약에 따라 회계처리할 수 있다는 예외가 포함되어 있다. 질의가 묻는 ‘분리요건을 충족하는 내재파생상품을 분리하지 않으려면 어떻게 하나요?’에 대해 현재 청크만으로 충분히 답변 가능하며, 외부 기준서 참조 지시는 보이지 않는다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-030 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
단기매매증권의 기말 평가손익은 매도가능증권과 어떻게 다르게 처리하나요?

**② 예상 정답**  
단기매매증권의 미실현보유손익은 당기손익으로 처리함. 반면 매도가능증권은 기타포괄손익누계액으로 처리한다는 점에서 차이가 있음.

**②' 예상 근거(gold)**: 6.31

**③ 실제 답변**  
단기매매증권은 보고기간말 현재의 공정가치로 평가하면서, 기말에 발생한 평가손익을 당기손익으로 인식합니다. 특히 보고기간말 현재 분배가 결정되어 기준가격에서 분배할 금액이 이미 차감되어 있으나 아직 지급되지 않은 경우에는, 단기매매증권은 그 분배할 금액을 미수수익으로 계상하고 수익증권의 장부금액에서 직접 차감한 뒤 공정가치(기준가격)로 평가합니다 [1].
반면 매도가능증권은 같은 상황에서 분배할 금액을 수익증권의 장부금액에서 직접 차감하여 미수수익으로 계상하되, 그 수익증권의 미실현보유이익(기타포괄손익누계액) 잔액은 미수수익 금액을 한도로 당기손익으로 대체합니다. 즉, 매도가능증권의 평가손익은 기본적으로 기타포괄손익누계액에 남고, 일부만 당기손익으로 대체될 수 있습니다 [1][7]. 따라서 기말 평가손익의 처리상 차이는, 단기매매증권은 전액 당기손익 처리인 반면 매도가능증권은 기타포괄손익누계액을 통해 처리된다는 점입니다 [1][7].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크 [8], [7], [1], [2]에 단기매매증권과 매도가능증권의 분류, 공정가치 평가, 그리고 기말 분배금/미실현보유손익 처리 차이가 직접 제시되어 있어 질문에 답할 수 있습니다. 특히 실 6.64에서 단기매매증권은 분배할 금액을 미수수익으로 계상하고 장부금액에서 직접 차감하는 반면, 매도가능증권은 미수수익 계상과 함께 미실현보유이익(기타포괄손익누계액)을 한도 내에서 당기손익으로 대체한다고 명시되어 있어 외부 기준서 추가 검색이 필요하지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-031 (제7장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
재고자산으로 분류되는 자산의 범위는 무엇인가요?

**② 예상 정답**  
정상적 영업과정에서 판매를 위해 보유하거나 생산과정에 있는 자산, 생산·용역제공 과정에 투입될 원재료·소모품 형태의 자산을 재고자산으로 함.

**②' 예상 근거(gold)**: 7.3

**③ 실제 답변**  
재고자산은 기업의 정상적인 영업주기 내에 판매되거나 사용되는 자산을 말하며, 재무상태표에서는 재고자산으로 별도 구분하여 표시합니다 [1][4]. 재고자산 내에 별도 표시하는 항목의 예로는 상품, 제품, 반제품, 재공품, 원재료, 저장품, 기타가 있습니다 [3].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘재고자산으로 분류되는 자산의 범위’인데, 청크에는 재고자산의 구체적 범위를 정의한 내용이 아니라 재무상태표 상의 분류 원칙과 재고자산의 예시만 있습니다(예: ‘재고자산 내에 별도 표시하는 항목의 예는 … 상품, 제품, 반제품, 재공품, 원재료, 저장품, 기타’). 따라서 질문에 필요한 분류 범위의 판단 기준이 누락되어 있어 청크만으로는 답할 수 없습니다. 외부 기준서 참조 지시는 없으므로 추가 검색 필요성도 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-032 (제7장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
재고자산의 재무상태표 금액은 무엇을 기준으로 하나요?

**② 예상 정답**  
재고자산은 취득원가와 순실현가능가치 중 낮은 금액으로 측정함. 순실현가능가치가 취득원가보다 하락하면 그 차액을 평가손실로 인식함.

**②' 예상 근거(gold)**: 7.17, 7.20, 7.4

**③ 실제 답변**  
재고자산의 재무상태표 금액은 재고자산의 세부 항목별 금액을 기준으로 표시하며, 재고자산 내에 별도 표시하는 항목의 예로 상품, 제품, 반제품, 재공품, 원재료, 저장품, 기타가 제시되어 있습니다 [2]. 또한 재무상태표에서 중요한 항목은 본문에 별도 항목으로, 중요하지 않은 항목은 성격이나 기능이 유사한 항목에 통합하여 표시할 수 있고, 그 세부 내용은 주석으로 기재합니다 [5]. 재무상태표의 자산은 유동자산과 비유동자산으로 구분되며, 재고자산은 유동자산에 속합니다 [7].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '재고자산의 재무상태표 금액은 무엇을 기준으로 하나요?'인데, 제공 청크에는 재고자산 표시의 예(상품, 제품, 반제품 등)만 있고 재고자산의 금액 산정기준(예: 취득원가, 순실현가능가치 등)이 명시되어 있지 않습니다. 따라서 질문에 답하는 데 필요한 구체적 기준이 누락되어 있어 청크만으로는 답변할 수 없습니다. 또한 현재 청크에는 다른 기준서를 참조하라는 외부 참조 지시도 보이지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-033 (제7장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
재고자산 매입원가에는 어떤 부대비용이 포함되나요?

**② 예상 정답**  
매입금액에 매입운임, 하역료, 보험료 등 취득과정에서 정상적으로 발생한 부대원가를 가산함. 매입할인·리베이트는 차감함.

**②' 예상 근거(gold)**: 7.6

**③ 실제 답변**  
제공된 맥락에는 재고자산의 ‘매입원가’에 포함되는 부대비용을 직접 열거한 문장은 없습니다. 다만 재고자산에 대해서는 상품, 제품, 반제품, 재공품, 원재료, 저장품, 기타와 같이 표시 항목만 예시되어 있을 뿐입니다 [2]. 따라서 이 맥락만으로는 재고자산 매입원가에 포함되는 부대비용이 무엇인지 정확히 답변할 수 없습니다.

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘재고자산 매입원가에 포함되는 부대비용’의 범위를 묻는데, 청크에는 재고자산의 구성항목(실 2.28)과 영업외비용/판매비와관리비/대손상각비 등의 항목만 있고 매입원가에 포함되는 운반비·하역비·관세·보험료 등 구체적 부대비용 기준이 없다. 또한 현재 청크 내에 다른 기준서를 참조하라는 지시도 없어 외부 기준서 탐색 여부 판단과 무관하게, 질문에 직접 답할 수 있는 근거가 부족하다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-034 (제7장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
K-GAAP에서 후입선출법(LIFO)으로 재고 단가를 결정할 수 있나요?

**② 예상 정답**  
가능함. 일반기업회계기준은 개별법, 선입선출법, 후입선출법, 가중평균법(총평균·이동평균), 매출가격환원법(소매재고법)을 허용함. 후입선출법을 인정하지 않는 K-IFRS와 이 점에서 차이가 있음.

**②' 예상 근거(gold)**: 7.12, 7.13, 7.14, 7.15

**③ 실제 답변**  
아니요. 제시된 맥락에는 재고 단가를 후입선출법(LIFO)으로 결정할 수 있다는 내용이 없고, 오히려 금융상품·가치평가 관련 조항만 제시되어 있어 K-GAAP에서의 재고 단가 산정방법 여부를 이 자료만으로 판단할 수 없습니다 [1][2][3][4][5][6][7][8][9][10].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 K-GAAP에서 후입선출법(LIFO)으로 재고 단가를 결정할 수 있는지에 대한 재고회계 기준을 묻지만, 제공 청크는 이익접근법·자산접근법·시장접근법, 파생상품, 금융상품 공정가치 등에 관한 내용만 포함하고 있어 재고 원가결정방법(LIFO/FIFO 등)에 대한 근거가 없습니다. 또한 외부 기준서 참조 지시도 없어 추가 검색 필요성(needs_external)은 확인되지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-035 (제7장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
재고자산 저가법의 순실현가능가치는 어떻게 산정하나요?

**② 예상 정답**  
순실현가능가치는 정상적 영업과정의 추정 판매가액에서 판매 시까지 정상적으로 발생하는 추정 완성·판매비용을 차감한 금액임.

**②' 예상 근거(gold)**: 7.17

**③ 실제 답변**  
재고자산 저가법에서는 순실현가능가치를 기준으로 평가하며, 순실현가능가치는 통상 예상 판매가격에서 완성·판매에 필요한 추가원가를 차감하여 산정하는 개념입니다. 다만, 제공된 맥락 청크에는 재고자산 저가법이나 순실현가능가치의 구체적 산정방법이 직접적으로 제시되어 있지 않습니다. 따라서 이 맥락만으로는 정확한 답변을 확정하기 어렵습니다.

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘재고자산 저가법의 순실현가능가치 산정’에 관한 것인데, 제공 청크에는 재고자산 저가법이나 순실현가능가치의 정의·산정방법이 전혀 나오지 않고, 대신 가치평가·공정가치·금융상품·유가증권 관련 내용만 있습니다. 따라서 질문에 직접 답할 근거가 청크 내에 없으므로 추가 기준서 검색이 필요한 상태입니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-036 (제7장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
재고자산 감모손실과 평가손실은 손익계산서에 어떻게 표시하나요?

**② 예상 정답**  
정상적 감모손실과 평가손실은 매출원가에 가산하고, 비정상적 감모손실은 영업외비용으로 처리함. 평가손실 환입은 매출원가에서 차감함.

**②' 예상 근거(gold)**: 7.19, 7.20

**③ 실제 답변**  
재고자산의 감모손실은 매출원가의 계산에 반영하는 것이므로 손익계산서에서는 매출원가에 포함되어 표시됩니다. 재고자산의 평가손실은 재고자산의 장부금액을 낮추는 손실로서, 주어진 문맥상 별도 항목으로 구분 표시된다고 정한 규정은 없으므로 손익계산서의 관련 비용항목에 포함하여 표시해야 합니다 [1][5].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '재고자산 감모손실과 평가손실을 손익계산서에 어떻게 표시하는지'를 묻지만, 청크 [1]에는 손익계산서의 기본 표시항목(매출액, 매출원가, 판매비와관리비, 영업외수익·비용 등)만 있고 재고자산 감모손실·평가손실의 구체적 표시 위치나 분류 기준이 직접 제시되어 있지 않습니다. 따라서 추론 없이 답변할 수 있는 수준의 근거가 부족하므로 적합하지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-037 (제8장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
지분법을 적용하는 유의적 영향력은 어떻게 판단하나요?

**② 예상 정답**  
직접·간접으로 피투자기업 의결권의 20% 이상을 보유하면 유의적 영향력이 있는 것으로 봄. 20% 미만이라도 실질적 영향력(이사회 참여, 중요거래 등)이 있으면 지분법을 적용함.

**②' 예상 근거(gold)**: 8.4, 8.5, 8.6

**③ 실제 답변**  
지분법을 적용하는 경우의 유의적 영향력은 구체적인 정량기준으로 제시되기보다, 사실과 정황을 근거로 합리적으로 판단하는 것으로 보아야 합니다. 제공된 맥락 중에서는 유의적 영향력 자체의 판단기준을 직접 설명한 문구는 없고, 다만 유의적인 영향력을 행사할 수 있는 주식(지분법적용투자주식)이 투자일임계약자산에 포함된 경우에는 그 주식에 지분법을 적용하여 평가한다고만 규정하고 있습니다 [6]. 따라서 이 맥락만으로는 유의적 영향력의 판단방법을 구체적으로 답할 수 없고, 지분법 적용 대상이 되는 경우의 처리만 확인할 수 있습니다 [6].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘지분법을 적용하는 유의적 영향력의 판단 기준’인데, 청크에는 유의적 영향력의 정의·판단요소(예: 의결권 지분율, 이사회 참여, 중요 정책 결정 참여 등)가 제시되어 있지 않습니다. 청크는 주로 공정가치 평가, 유가증권 분류, 투자일임계약자산의 지분법 적용 문구만 포함할 뿐, 질문에 답할 구체 기준을 직접 제공하지 않으므로 외부 기준서 추가 검색이 필요합니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-038 (제8장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
지분법 취득 시 취득원가와 순자산 공정가치 지분액의 차이는 어떻게 처리하나요?

**② 예상 정답**  
취득원가가 순자산 공정가치 지분액을 초과하면 그 차액을 투자주식에 포함된 영업권으로 보아 상각·손상 처리하고, 미달하면(염가매수) 그 차액을 취득 시 당기이익으로 인식함.

**②' 예상 근거(gold)**: 8.11

**③ 실제 답변**  
지분법 취득 시 취득원가가 순자산 공정가치 지분액보다 큰 경우, 그 차이는 일반적으로 영업권에 해당하여 지분법 취득원가에 포함하여 처리합니다. 다만 제공된 맥락 청크에는 지분법 취득 시 취득원가와 순자산 공정가치 지분액의 차이를 직접 규정한 문장이 없어, 이 문맥만으로는 정확한 회계처리를 확정할 수 없습니다. [answerable 여부를 판단하려면 지분법 관련 조항이 필요합니다.]

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘지분법 취득 시 취득원가와 순자산 공정가치 지분액의 차이’의 처리인데, 제공 청크에는 지분법(투자주식의 관계기업/공동기업 취득) 관련 문단이 없고 전환권 행사, 출자전환, 매도가능증권 재분류 등 다른 주제만 포함되어 있습니다. 차이금액을 어떻게 처리하는지에 대한 구체적 기준·조건·결론이 청크 내에 없어 이 청크만으로는 답할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-039 (제8장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
피투자기업의 당기순손익은 지분법에서 어떻게 반영하나요?

**② 예상 정답**  
피투자기업 당기순손익 중 투자지분 해당액을 지분법이익(손실)으로 인식하고 투자주식 장부금액을 증감시킴. 배당 수령액은 투자주식 장부금액에서 차감함.

**②' 예상 근거(gold)**: 8.16, 8.19, 8.8

**③ 실제 답변**  
지분법에서는 피투자기업의 당기순손익 중 투자기업 지분에 해당하는 부분을 인식합니다. 또한 지분법을 적용하는 경우 지분법 평가손익은 피투자회사의 손익 변동을 반영하는 방식으로 처리되므로, 질문의 ‘당기순손익’은 지분법 손익에 반영되는 기초가 됩니다. 다만, 제공된 맥락에는 지분법의 구체적 인식비율이나 계산방법이 직접 제시되어 있지 않아, 당기순손익이 지분법에서 어떻게 반영되는지에 대한 정확한 조항 근거를 확인할 수는 없습니다.

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '피투자기업의 당기순손익을 지분법에서 어떻게 반영하는지'라는 지분법 회계처리 기준을 묻지만, 제공 청크에는 지분법 관련 문단이 없고 대부분 위험회피회계·유가증권·포괄손익 사례만 있습니다. 따라서 질문에 필요한 반영 방식, 인식 시점, 산식/비율 등 핵심 기준이 청크에 누락되어 있어 이 청크만으로는 답할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-040 (제8장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
관계기업과의 내부거래에서 발생한 미실현손익은 어떻게 처리하나요?

**② 예상 정답**  
관계기업과의 상향·하향 거래에서 발생한 미실현손익 중 투자자 지분 해당분을 제거함.

**②' 예상 근거(gold)**: 8.20

**③ 실제 답변**  
관계기업과의 내부거래에서 발생한 미실현손익은 일반적으로 내부거래에 해당하므로 위험회피대상 예상거래가 될 수 없고, 연결재무제표를 작성하는 경우 연결실체 내 기업간의 예상거래도 내부거래에 해당합니다. 다만 외화위험회피회계에서 인정되는 예외는 있습니다 [5][5]. 따라서 이 질의에 대응하는 맥락에서는 내부거래로 인한 미실현손익을 일반적인 거래손익으로 바로 인식하는 것이 아니라, 관련 기준에 따라 내부거래로 보아 처리해야 합니다 [5].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '관계기업과의 내부거래에서 발생한 미실현손익'의 처리인데, 청크에는 유가증권 자전거래, 자기주식/매도가능증권, 위험회피회계, 유가증권 재분류 등의 내용만 있고 관계기업 내부거래 미실현손익의 제거·처리 기준은 없다. 따라서 질문에 필요한 구체적 회계처리 조건과 기준이 청크 내에 누락되어 있어 이 청크만으로 답할 수 없다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-041 (제8장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
피투자기업 누적손실로 투자주식이 영(0)이 되면 지분법을 계속 적용하나요?

**② 예상 정답**  
투자주식 장부금액이 영(0) 이하가 되면 지분법 적용을 중지하고 추가 손실을 인식하지 않음(추가 부담의무 제외). 이후 이익 발생 시 미인식 누적손실을 초과하는 부분부터 다시 인식함.

**②' 예상 근거(gold)**: 8.24, 8.26

**③ 실제 답변**  
제공된 맥락만으로는 피투자기업의 누적손실로 인해 투자주식 장부금액이 영(0)이 된 경우에도 지분법을 계속 적용하는지 여부를 직접적으로 확인할 수 없습니다. 맥락에는 지분법 적용투자주식이 투자일임계약자산에 포함된 경우에는 지분법을 적용하여 평가한다는 내용만 있고, 누적손실로 장부금액이 0이 된 이후의 계속 적용 여부는 제시되어 있지 않습니다 [5]. 따라서 이 질의는 주어진 맥락만으로 답변하기 어렵습니다 [5].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질문은 ‘피투자기업 누적손실로 투자주식이 영(0)이 되면 지분법을 계속 적용하는지’인데, 제공 청크에는 지분법 계속 적용 여부나 지분법 중단/재개 기준이 전혀 없습니다. 청크는 주로 유가증권 분류·손상·재분류 및 투자일임계약자산 관련 내용(예: 6.A15~6.A20, 실 6.61, 실 6.75 등)만 포함하며, 질문에 필요한 판단 기준·조건·예외가 누락되어 있습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-042 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
유형자산 취득원가에는 어떤 항목이 포함되나요?

**② 예상 정답**  
구입가격(관세·환급불가 취득세 포함, 매입할인 차감)에 자산을 의도된 장소·상태로 만드는 데 직접 관련된 원가(운반비·설치비·시운전비 등)와 복구원가의 현재가치를 가산함.

**②' 예상 근거(gold)**: 10.10, 10.11, 10.12, 10.13, 10.8, 10.9

**③ 실제 답변**  
유형자산은 재화의 생산이나 용역의 제공, 타인에 대한 임대, 또는 자체적으로 사용할 목적으로 보유하는 물리적 형태의 비화폐성자산이며, 토지, 건물, 기계장치 등을 포함합니다 [2]. 유형자산 중 별도 표시하는 분류 항목의 예로는 토지, 설비자산, 건설중인자산, 기타가 제시되어 있습니다 [2]. 따라서 유형자산 취득원가에는 이러한 유형자산을 취득하여 사용가능 상태로 만들기 위해 직접 관련되는 금액이 포함된다고 볼 수 있지만, 제공된 맥락에는 취득원가의 구체적 구성항목이 직접적으로 열거되어 있지는 않습니다 [2][4][10].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘유형자산 취득원가에 포함되는 항목’인데, 청크 [2]는 유형자산의 정의와 별도 표시 항목(토지, 설비자산, 건설중인자산)만 제시할 뿐 취득원가 구성요소를 설명하지 않습니다. [1], [4] 등도 자산 분류나 현금흐름 분류일 뿐 취득원가에 포함되는 직접원가·부대원가·설치비 등 구체 기준이 없어 청크만으로 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-043 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
유형자산 취득 후 수선·교체 지출은 자본화하나요, 비용처리하나요?

**② 예상 정답**  
미래 경제적효익을 증가시키는 지출(생산능력 증대, 내용연수 연장 등)은 자본화하고, 원상회복·정상 유지 목적의 수선비는 발생 기간의 비용으로 인식함.

**②' 예상 근거(gold)**: 10.14, 10.15, 10.16

**③ 실제 답변**  
유형자산의 수선·교체 지출은 원칙적으로 그 급여가 해당 자산의 원가에 포함되는 경우를 제외하고는 비용으로 인식합니다 [5]. 따라서 질문의 경우에도 수선·교체 지출은 통상 비용처리하며, 자산의 원가에 포함되는 예외적인 경우에만 자본화합니다 [5].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘유형자산 취득 후 수선·교체 지출의 자본화/비용처리’에 대한 일반 기준을 묻지만, 청크에는 해당 직접 규정이 없습니다. 제10장 유형자산에 대한 구체 문단, 수선·교체의 인식 기준, 자본화 여부 판단 조건이 제시되지 않았고, 제시된 내용은 배당·자기주식·감가상각방법 변경·무형자산 오류수정 등 다른 주제입니다. 따라서 제공된 청크만으로는 답할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-044 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
이종자산 교환으로 유형자산을 취득하면 취득원가는 무엇으로 하나요?

**② 예상 정답**  
원칙적으로 제공한 자산의 공정가치로 측정하되, 취득 자산의 공정가치가 더 명백하면 그 금액으로 함. 공정가치를 신뢰성 있게 측정할 수 없거나 상업적 실질이 없으면 제공한 자산의 장부금액으로 측정함.

**②' 예상 근거(gold)**: 10.17, 10.18, 10.19, 10.20, 10.21

**③ 실제 답변**  
이종자산 교환으로 유형자산을 취득한 경우의 취득원가는 교환으로 제공한 자산의 공정가치로 보는 것이 원칙입니다. 다만, 제공하거나 수취한 대가에 금융상품이 아닌 다른 것에 대한 대가가 포함된 경우의 금융상품 공정가치에 관한 규정은 있으나, 질문의 유형자산 교환 취득원가를 직접 규정하는 문장은 제시된 맥락에 없습니다 [1]. 따라서 주어진 맥락만으로는 이 질문에 대한 직접적인 회계기준 근거를 특정할 수 없습니다.

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘이종자산 교환으로 유형자산을 취득하면 취득원가가 무엇인지’에 관한 것이지만, 청크에는 유형자산의 취득원가 기준이 직접 제시되지 않고 금융상품·유가증권·전환권/신주인수권 행사 등 다른 주제만 있습니다. 특히 [9]는 유가증권 양도 후 새로운 자산 취득 시 처리를 다루지만 유형자산 취득원가의 일반 규정이나 이종자산 교환 기준은 없어, 질문에 필요한 수치·조건·판단기준이 누락되어 있습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-045 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 질문**  
유형자산 감가상각방법은 어떻게 선택하나요?

**② 예상 정답**  
자산의 경제적효익이 소비되는 형태를 반영하는 방법(정액법·정률법·생산량비례법 등)을 선택하여 매기 일관 적용함. 소비형태가 유의적으로 달라지면 방법을 변경하고 회계추정의 변경으로 처리함.

**②' 예상 근거(gold)**: 10.38, 10.39, 10.40

**③ 실제 답변**  
유형자산의 감가상각방법은 자산의 미래 경제적 효익이 기업에 소비되는 형식에 맞추어 선택해야 하며, 자산의 미래 경제적 효익이 소비될 것으로 예상되는 형식을 반영하는 방법을 체계적으로 적용하여야 합니다. 또한 최소한 매 회계연도 말에는 잔존가치와 내용연수, 그리고 감가상각방법을 재검토하고, 적절하다면 변경하여야 합니다 [4].

다만 제공된 맥락에서는 감가상각방법의 구체적인 선택 기준을 직접 설명한 부분은 유형자산의 분류만 제시하고 있어, 감가상각방법의 선택에 관한 명시적 근거를 확인할 수 없습니다 [4]. 따라서 질의에 대한 정확한 답변은 이 맥락만으로는 제시하기 어렵습니다 [4].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘유형자산 감가상각방법을 어떻게 선택하는지’에 관한 것이지만, 제공 청크 [4]는 유형자산의 정의와 토지/건설중인자산의 표시만 있고 감가상각방법 선택 기준이 없습니다. 감가상각의 선택 원칙, 내용연수/잔존가치/방법 변경 조건 등 질문에 필요한 판단 기준이 청크 내에 누락되어 있어 이 청크만으로는 답할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-046 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
유형자산의 감가상각은 언제부터 시작하나요?

**② 예상 정답**  
자산이 사용가능한 상태(경영진이 의도하는 방식으로 가동될 수 있는 상태)에 이른 때부터 감가상각을 시작하며, 실제 사용 여부와는 무관함.

**②' 예상 근거(gold)**: 10.34

**③ 실제 답변**  
유형자산의 감가상각은 자산이 사용가능한 때부터 시작합니다. 맥락에는 유형자산이 재화의 생산이나 용역의 제공, 임대 또는 자체 사용 목적으로 보유되는 자산이며, 건설중인자산은 별도 표시한다고만 제시되어 있어 감가상각 개시 시점에 대한 직접 문구는 없습니다 [4]. 따라서 제공된 맥락만으로는 정확한 개시 시점을 확정하여 답변할 수 없습니다 [4].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크 [4]에 유형자산의 정의와 분류 예시만 있고, 질문의 핵심인 감가상각의 시작 시점(예: 사용가능한 때부터/가동 가능한 때부터 등) 규정은 누락되어 있습니다. 따라서 제공된 청크만으로는 답할 수 없고 추가 기준서 검색이 필요하지만, 청크 내에 타 기준서 준용 지시가 명시적으로 보이지는 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-047 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 질문**  
유형자산을 재평가모형으로 측정할 수 있으며, 재평가증가액은 어떻게 처리하나요?

**② 예상 정답**  
원가모형과 재평가모형 중 선택 가능함. 재평가로 장부금액이 증가하면 기타포괄손익으로 인식해 재평가잉여금에 누적하되, 종전 당기손익으로 인식한 재평가감소를 회복하는 부분은 당기손익으로 인식함.

**②' 예상 근거(gold)**: 10.22, 10.30

**③ 실제 답변**  
유형자산을 재평가모형으로 측정할 수 있는지에 대한 직접적인 규정은 제공된 맥락에 없습니다. 다만, 제공된 맥락은 금융자산·금융부채 및 유가증권의 공정가치, 상각후원가, 평가기법 등에 관한 내용으로 유형자산의 재평가모형과 재평가증가액 처리에 관한 근거를 포함하지 않습니다 [1][5][8]. 따라서 이 맥락만으로는 질문에 정확히 답변할 수 없습니다.

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크는 금융상품의 공정가치 측정과 유가증권/퇴직연금 관련 내용이며, 질문의 핵심인 ‘유형자산을 재평가모형으로 측정할 수 있는지’와 ‘재평가증가액의 처리’에 대한 규정이 없습니다. 또한 유형자산 재평가모형의 적용조건, 재평가증가액의 기타포괄손익/이익잉여금 처리 등 수치·조건·기준이 전혀 제시되지 않아 이 청크만으로는 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-048 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
재평가잉여금은 자산 처분 시 당기손익으로 재분류하나요?

**② 예상 정답**  
K-GAAP에서 재평가잉여금은 당기손익으로 재분류(recycling)하지 않고, 자산을 제거·처분하는 시점에 이익잉여금으로 직접 대체함.

**②' 예상 근거(gold)**: 10.22, 10.23, 10.24, 10.25, 10.26, 10.27, 10.28, 10.29, 10.30, 10.31

**③ 실제 답변**  
아니요. 제시된 문맥에 따르면 재평가잉여금에 해당하는 미실현보유이익은 자산 처분 등으로 실현될 때 당기손익으로 인식하며, 매도가능증권과 만기보유증권의 매도·상환·손상차손으로 실현된 이익이나 손실도 당기손익에 반영합니다 [4]. 또한 유가증권을 양도하여 새로운 자산을 취득하는 경우에는 기타포괄손익누계액에 포함된 미실현보유이익을 가산하고 미실현보유손실을 차감한 금액을 유가증권처분손익으로 당기손익에 반영한다고 되어 있습니다 [2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질문은 “재평가잉여금은 자산 처분 시 당기손익으로 재분류하나요?”인데, 청크들은 유가증권의 재분류·매각·처분손익 및 해외사업장순투자 위험회피의 재분류조정만 다루고 있어 ‘재평가잉여금’의 처분 시 처리 기준이 직접 제시되지 않습니다. 특히 자산 처분 시 재평가잉여금의 당기손익 대체 여부에 대한 구체 규정, 인식 시점, 조건이 청크 내에 없어 추론 없이 답할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-049 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
유형자산의 손상차손은 어떻게 인식하나요?

**② 예상 정답**  
손상 징후가 있어 회수가능액(순공정가치와 사용가치 중 큰 금액)이 장부금액에 미달하면 그 차액을 손상차손으로 당기손익에 인식함.

**②' 예상 근거(gold)**: 10.41, 10.42

**③ 실제 답변**  
유형자산의 손상차손은 주어진 맥락에 유형자산에 대한 직접 규정이 없어 정확히 답변할 수 없습니다. 제공된 문맥은 주로 유가증권의 손상차손 인식 방법과 관련되어 있으며, 유형자산 손상차손의 인식 기준은 포함되어 있지 않습니다 [1][2][4][7][9].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질문은 ‘유형자산의 손상차손’ 인식 방법인데, 제공 청크에는 유형자산 손상에 대한 직접 규정이 없고 주로 유가증권(만기보유증권, 매도가능증권, 지분증권)의 손상차손 인식·측정만 포함되어 있습니다. 따라서 질문의 회계 주제와 직접 대응하는 인식 시점·측정기준이 누락되어 있어 이 청크만으로는 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-050 (제11장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
무형자산으로 인식하기 위한 요건은 무엇인가요?

**② 예상 정답**  
식별가능성, 자원에 대한 통제, 미래 경제적효익의 존재를 충족하고, 효익 유입 가능성이 매우 높으며 원가를 신뢰성 있게 측정할 수 있어야 함.

**②' 예상 근거(gold)**: 11.3, 11.4, 11.5, 11.6, 11.7

**③ 실제 답변**  
무형자산은 물리적 형체는 없지만 식별가능하고, 기업이 통제하고 있으며, 미래경제적효익이 있는 비화폐성자산이어야 합니다. 예로 산업재산권, 저작권, 개발비, 사업결합에서 발생한 영업권을 포함합니다 [2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '무형자산으로 인식하기 위한 요건'을 묻지만, 청크 [2]는 무형자산의 정의(식별가능, 통제, 미래경제적효익)만 제시할 뿐 인식요건(예: 미래경제적효익의 유입 가능성, 취득원가의 신뢰성 있는 측정 등)과 관련된 기준은 포함하지 않습니다. 또한 외부 기준서를 참조하라는 지시도 없어 needs_external은 false입니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-051 (제11장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
내부 프로젝트의 연구단계와 개발단계 지출은 각각 어떻게 처리하나요?

**② 예상 정답**  
연구단계 지출은 발생 시 연구비(비용)로 인식함. 개발단계 지출은 자산인식 요건을 모두 충족하면 개발비(무형자산)로 자본화하고, 요건 미충족 시 경상개발비 등 당기비용으로 인식함.

**②' 예상 근거(gold)**: 11.17, 11.18, 11.19, 11.20

**③ 실제 답변**  
주어진 맥락에는 내부 프로젝트의 연구단계·개발단계 지출 처리에 대한 기준이 제시되어 있지 않습니다. 따라서 해당 질의는 주어진 문맥만으로는 답변할 수 없습니다.

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 내부 프로젝트의 연구단계·개발단계 지출의 회계처리이지만, 제공된 청크는 위험회피회계, 재무제표 표시, 금융상품, 퇴직급여, 가치평가, 대손충당금 등만 포함하고 있어 연구개발비 처리 기준이 전혀 제시되지 않습니다. 따라서 질문에 직접 답할 수 있는 수치·조건·인식기준이 누락되어 있어 현재 청크만으로는 판단 불가입니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-052 (제11장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
무형자산의 상각방법과 상각기간은 어떻게 정하나요?

**② 예상 정답**  
경제적효익의 소비형태를 반영하는 방법을 사용하되 소비형태를 신뢰성 있게 추정할 수 없으면 정액법을 적용하고, 원칙적으로 20년 이내의 합리적 기간에 걸쳐 상각함.

**②' 예상 근거(gold)**: 11.26, 11.27, 11.28, 11.29, 11.30, 11.31, 11.32, 11.33, 11.34, 11.35, 11.36

**③ 실제 답변**  
제시된 맥락에는 무형자산의 상각방법과 상각기간을 정하는 기준이 직접적으로 나타나 있지 않아 답변할 수 없습니다. 다만 맥락상 무형자산은 비유동자산에 속하고, 재무상태표에서는 유형자산과 함께 비유동자산 항목으로 분류되어 표시된다는 점만 확인됩니다 [1][3].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 무형자산의 상각방법과 상각기간(예: 내용연수 결정, 잔존가치, 정액/정률법 등)을 묻지만, 제공 청크에는 무형자산 상각 규정이 없고 재무상태표 분류, 퇴직급여, 유가증권 상각후원가/상각, 대손상각 등에 관한 내용만 있습니다. 따라서 질문에 답할 핵심 기준이 누락되어 있으며, 청크 내에 다른 기준서로의 명시적 참조 지시도 없어 외부 기준서 추가 검색 필요성은 확인되지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-053 (제11장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 질문**  
무형자산의 잔존가치는 어떻게 보나요?

**② 예상 정답**  
무형자산의 잔존가치는 원칙적으로 영(0)으로 봄. 다만 상각기간 종료시점에 제3자의 구입약정이 있거나 활성시장이 존재하여 잔존가치를 결정할 수 있는 경우에는 잔존가치를 인식할 수 있음.

**②' 예상 근거(gold)**: 11.33

**③ 실제 답변**  
제공된 맥락에는 무형자산의 잔존가치에 관한 직접적인 규정이 없습니다. 다만 무형자산은 재무상태표에서 별도로 표시되는 비유동자산의 한 항목으로만 설명되어 있고 [2][8], 잔존가치의 산정·판단 기준은 제시되어 있지 않습니다 [2][8]. 따라서 이 맥락만으로는 무형자산의 잔존가치를 어떻게 보는지 답변할 수 없습니다.

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '무형자산의 잔존가치'에 관한 기준(예: 잔존가치의 정의, 감가상각 시 반영 여부, 내용연수·상각방법과의 관계)을 요구하지만, 청크에는 무형자산의 정의(실 2.35~2.37)와 재무상태표 분류(2.18)만 있고 잔존가치 관련 규정이 없습니다. 또한 외부 기준서로의 명시적 참조 지시도 없어 추가 검색 필요성은 보이지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-054 (제11장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
내부적으로 창출한 브랜드나 고객목록을 무형자산으로 인식할 수 있나요?

**② 예상 정답**  
내부창출 브랜드·고객목록·출판표제 등은 사업 전체의 원가와 구분하기 어려워 무형자산으로 인식하지 않고 발생 시 비용으로 처리함.

**②' 예상 근거(gold)**: 11.10, 11.11, 11.12, 11.13, 11.14, 11.15, 11.16, 11.17, 11.18, 11.19, 11.20, 11.21, 11.22, 11.7, 11.8, 11.9

**③ 실제 답변**  
아니요. 내부적으로 창출한 브랜드, 고객목록, 유사한 항목은 식별가능하고 기업이 통제하며 미래경제적효익이 있는 무형자산의 예시에 포함되어 있지 않습니다. 주어진 맥락에서는 무형자산의 예로 산업재산권, 저작권, 개발비, 영업권 등이 제시되고 있을 뿐입니다 [3]. 따라서 이 맥락만으로는 내부적으로 창출한 브랜드나 고객목록을 무형자산으로 인식할 수 있다고 보기 어렵습니다 [3].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘내부적으로 창출한 브랜드나 고객목록의 무형자산 인식 가능 여부’이지만, 제공 청크에는 무형자산의 일반적 정의(실 2.35)만 있고 브랜드·고객목록의 내부창출 여부, 인식요건, 금지규정(예: 내부창출 브랜드/고객목록) 등이 없다. 따라서 질문에 필요한 구체적 인식 기준이 누락되어 청크만으로는 답변할 수 없다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-055 (제11장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
무형자산이 갖추어야 할 식별가능성이란 무엇인가요?

**② 예상 정답**  
자산이 분리가능하거나(매각·이전·라이선스 등이 가능) 계약상 또는 법적 권리로부터 발생하는 경우 식별가능한 것으로 보아 무형자산 인식 요건 중 하나를 충족함.

**②' 예상 근거(gold)**: 11.2, 11.3, 11.4

**③ 실제 답변**  
무형자산의 식별가능성이란 무형자산이 물리적 형체는 없더라도, 기업이 통제하고 있으며 미래경제적효익이 있는 비화폐성자산이라는 점에서 구별될 수 있어야 한다는 의미입니다. 즉 산업재산권, 저작권, 개발비, 영업권 등이 무형자산에 포함됩니다 [2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 무형자산의 식별가능성 정의를 묻고 있으며, 청크 [2]에 "무형자산은 물리적 형체는 없지만 식별가능하고 기업이 통제하고 있으며 미래경제적효익이 있는 비화폐성자산"이라고 직접 제시되어 있습니다. 추가 수치나 외부 기준서 참조 없이 청크만으로 답변 근거를 바로 추출할 수 있으므로 관련성은 충분하고 외부 검색도 필요하지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-056 (제12장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
사업결합에서 영업권은 어떻게 산정하나요?

**② 예상 정답**  
취득자는 이전대가가 취득일의 식별가능한 순자산(자산-부채) 공정가치를 초과하는 금액을 측정하여 영업권으로 인식함.

**②' 예상 근거(gold)**: 12.32

**③ 실제 답변**  
제공된 맥락 청크에는 사업결합에서 영업권을 산정하는 기준이 직접적으로 제시되어 있지 않습니다. 다만 영업권이 사업결합에서 발생한 무형자산에 포함된다는 점만 확인할 수 있습니다 [5]. 따라서 이 맥락만으로는 영업권의 산정 방법을 정확히 답변할 수 없습니다.

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘사업결합에서 영업권 산정 방법’인데, 제공된 청크에는 영업권의 정의만 있을 뿐 산정 공식이나 측정기준이 없습니다. 예컨대 [5]는 ‘사업결합에서 발생한 영업권을 포함’한다고만 하고, 손익·유가증권·파생상품·중단사업 등 다른 주제만 다루므로 질문에 직접 답할 근거가 부족합니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-057 (제12장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
취득 순자산 공정가치가 이전대가를 초과하면 어떻게 처리하나요?

**② 예상 정답**  
재검토 후에도 취득한 순자산 공정가치가 이전대가를 초과하면 그 차액(염가매수차익)을 취득일에 당기이익으로 인식함.

**②' 예상 근거(gold)**: 12.33

**③ 실제 답변**  
취득한 자산(또는 인수한 부채)의 공정가치를 알 수 없는 경우, 자산을 취득하는 때에는 공정가치를 '0'으로 보아 처분손익을 계상합니다 [2]. 다만 질문의 ‘취득 순자산 공정가치가 이전대가를 초과’하는 상황에 대해서는, 제공된 맥락에는 해당 차액을 어떻게 별도로 처리하는지에 관한 직접 규정이 없어 이 자료만으로는 확정적으로 답변할 수 없습니다 [1][2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘취득 순자산 공정가치가 이전대가를 초과하면 어떻게 처리하나요?’로 사업결합 시 식별가능순자산의 공정가치가 이전대가를 초과하는 경우(염가매수차익) 처리에 관한 내용이 필요하지만, 청크에는 금융자산·금융부채의 최초인식, 양도, 재분류, 손상차손, 출자전환만 있고 해당 주제의 인식/측정/당기손익 처리 기준이 없다. 따라서 제공된 청크만으로는 답변 근거를 추출할 수 없다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-058 (제12장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
사업결합으로 취득한 자산과 인수한 부채는 무엇으로 측정하나요?

**② 예상 정답**  
취득법을 적용하여 취득일 현재 식별가능한 취득자산과 인수부채를 공정가치로 측정함.

**②' 예상 근거(gold)**: 12.20

**③ 실제 답변**  
사업결합으로 취득한 자산과 인수한 부채는 원칙적으로 최초인식시 공정가치로 측정합니다 [2]. 또한 금융상품의 최초인식시 자산의 경우에는 제공한 대가의 공정가치, 부채의 경우에는 수취한 대가의 공정가치로 본다고 규정하고 있습니다 [2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘사업결합으로 취득한 자산과 인수한 부채의 측정’인데, 제공 청크에는 사업결합의 취득자산·인수부채를 공정가치로 측정하는 기준이 직접 제시되어 있지 않습니다. 청크는 금융상품의 공정가치 측정(예: 6.12, 6.15)이나 채권·채무조정, 전환/신주인수권 행사 등 다른 주제를 다루므로 질문에 필요한 구체 기준이 누락되었습니다. 또한 ‘다른 기준서에 따른다’는 미해결 외부 참조 지시도 확인되지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-059 (제12장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
K-GAAP에서 사업결합으로 인식한 영업권은 상각하나요?

**② 예상 정답**  
K-GAAP은 영업권을 20년 이내의 내용연수 동안 정액법으로 상각함(상각하지 않는 K-IFRS와 차이).

**②' 예상 근거(gold)**: 12.32

**③ 실제 답변**  
네. 제공된 맥락에 따르면 K-GAAP에서 사업결합으로 발생한 영업권은 무형자산에 포함되며, 무형자산 중 별도 표시하는 항목의 예로 영업권이 제시되어 있습니다 [5]. 또한 이 맥락들에는 영업권의 상각 여부를 직접 규정한 문장은 없으므로, 이 자료만으로는 사업결합으로 인식한 영업권을 상각하는지 여부를 확정하여 답할 수 없습니다 [5].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 K-GAAP에서 사업결합으로 인식한 영업권의 상각 여부인데, 제공된 청크는 영업권의 '무형자산 포함' 여부(실 2.35)만 보여줄 뿐 상각/손상/내용연수 등 처분 기준이 없다. 따라서 질문에 필요한 구체적 판단 기준이 청크 내에 누락되어 있어 이 청크만으로 답할 수 없다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-060 (제13장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 질문**  
리스를 금융리스와 운용리스로 어떻게 분류하나요?

**② 예상 정답**  
리스자산 소유에 따른 위험과 보상의 대부분이 이전되면 금융리스, 그렇지 않으면 운용리스로 분류함. 형식보다 거래의 실질에 따라 리스실행일에 분류함.

**②' 예상 근거(gold)**: 13.5, 13.6, 13.7, 13.8

**③ 실제 답변**  
리스는 리스제공자가 인식하는 리스채권의 제거와 손상, 리스이용자가 인식하는 금융리스부채의 제거, 그리고 리스에 내재된 파생상품에 대해서는 이 장을 적용하지만, 맥락에는 리스를 금융리스와 운용리스로 구분하는 구체적 분류기준은 제시되어 있지 않습니다 [1]. 따라서 제공된 맥락만으로는 리스를 금융리스와 운용리스로 어떻게 분류하는지 답할 수 없습니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크에는 리스가 금융리스와 운용리스로 분류되는 구체적 기준, 임계율, 판단 조건, 분류 절차가 제시되어 있지 않습니다. 오히려 [1]에서 '리스에 따른 권리와 의무'를 금융상품 장의 적용제외로 언급할 뿐이며, 리스 분류 질문에 직접 답할 수 있는 내용은 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-061 (제13장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
어떤 경우에 일반적으로 금융리스로 분류되나요?

**② 예상 정답**  
소유권 이전 약정, 염가매수선택권 행사 확실, 리스기간이 내용연수의 대부분, 최소리스료 현재가치가 공정가치의 대부분, 특수용도 자산 등에 해당하면 일반적으로 금융리스로 분류함.

**②' 예상 근거(gold)**: 13.6

**③ 실제 답변**  
제공된 맥락에는 ‘일반적으로 금융리스로 분류되는 경우’에 대한 기준이 제시되어 있지 않습니다. 다만, 맥락상 금융리스는 ‘리스에 따른 권리와 의무’에 해당하는 항목으로서 이 장의 일반 적용대상에서 제외되며, 리스이용자가 인식하는 금융리스부채의 제거에 대해서만 이 장을 적용한다고 되어 있습니다 [2]. 따라서 이 자료만으로는 금융리스의 일반적인 분류 기준을 답할 수 없습니다 [2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '일반적으로 금융리스로 분류되는 경우'인데, 제공된 청크는 금융자산/금융부채의 인식·측정·제거 및 리스의 적용제외(“리스에 따른 권리와 의무… 다만 … 금융리스부채의 제거”)만 다루고 있어 금융리스의 분류기준(예: 소유권 이전, 저가매입선택권, 리스기간/현재가치 비율 등)이 전혀 포함되어 있지 않습니다. 따라서 청크만으로는 답변 근거를 추출할 수 없고, 외부 기준서 검색이 필요합니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-062 (제13장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
금융리스 이용자는 리스개시 시 어떻게 인식하나요?

**② 예상 정답**  
리스자산의 공정가치와 최소리스료 현재가치 중 작은 금액을 리스자산과 리스부채로 인식함. 이후 리스자산은 감가상각하고 리스료는 이자비용과 원금상환으로 구분함.

**②' 예상 근거(gold)**: 13.13, 13.14, 13.15

**③ 실제 답변**  
금융리스 이용자는 리스개시 시 금융리스부채를 인식합니다. 다만, 본문 맥락에는 리스개시 시 금융리스부채의 구체적 최초 측정 방법이나 자산 인식 범위는 제시되어 있지 않습니다. 금융리스에 따른 권리와 의무는 원칙적으로 이 장의 적용대상에서 제외되지만, 리스이용자가 인식하는 금융리스부채의 제거에는 이 장을 적용한다고 되어 있습니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '금융리스 이용자'가 리스개시 시 인식하는 내용인데, 청크에는 금융상품/금융부채 일반 규정만 있고 금융리스 이용자의 리스개시 시점 인식(예: 사용권자산·리스부채 등) 기준이 제시되지 않았습니다. 특히 [1]은 리스 규정에서 금융리스부채 제거만 언급하고, 실제 인식 방식·측정 기준은 청크 내에 없어 추론 없이 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-063 (제13장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
운용리스 이용자의 리스료는 어떻게 인식하나요?

**② 예상 정답**  
운용리스료는 리스기간에 걸쳐 정액기준(다른 체계적 기준이 더 적절하면 그 기준)으로 비용을 인식하며, 리스자산을 이용자의 자산으로 계상하지 않음.

**②' 예상 근거(gold)**: 13.19

**③ 실제 답변**  
운용리스 이용자의 리스료는 리스기간 동안 발생한 비용으로 인식하는 것이 원칙이며, 이와 별개로 금융리스부채나 리스채권 등은 해당되지 않습니다. 다만 제공된 맥락에는 운용리스 이용자의 리스료 인식방법을 직접 규정한 문장이 없어, 질의에 대해 정확한 기준문 인용으로 답변할 수는 없습니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 운용리스 이용자의 리스료 인식방법인데, 청크 [1]은 금융상품의 적용범위에서 ‘리스에 따른 권리와 의무’가 제외된다는 내용일 뿐이고, 청크 [4]·[8]·[3] 등도 퇴직급여/퇴직연금 회계만 다뤄 운용리스 리스료 인식기준이 없다. 따라서 질문에 필요한 인식 시점·기준·계산 근거가 청크 내에 누락되어 있어 답변 근거를 추출할 수 없다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-064 (제13장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
리스제공자가 금융리스로 분류한 경우 회계처리는 어떻게 하나요?

**② 예상 정답**  
리스자산을 제거하고 리스순투자를 리스채권으로 인식함. 수취하는 리스료를 원금 회수분과 이자수익으로 구분하여 인식함.

**②' 예상 근거(gold)**: 13.21, 13.22, 13.23

**③ 실제 답변**  
리스제공자가 금융리스로 분류한 경우, 이 장(금융상품 관련 회계처리)은 리스에 따른 권리와 의무에는 적용되지 않지만, 리스제공자가 인식하는 리스채권의 제거와 손상에는 적용합니다. 따라서 금융리스로 분류된 리스에서는 리스채권의 제거 및 손상에 관해 이 장의 규정을 적용하고, 그 외 리스에 따른 권리·의무 자체에는 이 장을 적용하지 않습니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘리스제공자가 금융리스로 분류한 경우 회계처리’인데, 제공된 청크 [1]은 리스제공자의 금융리스채권 제거·손상에 대한 적용 제외만 언급할 뿐 구체적인 금융리스 회계처리 절차(인식 시점, 측정, 분개, 수치/판단기준)를 제시하지 않습니다. 따라서 질문에 직접 답할 충분한 근거가 없고, 외부 기준서 참조 지시도 청크 내에 명시되어 있지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-065 (제13장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
판매후리스(sale and leaseback) 거래는 어떻게 회계처리하나요?

**② 예상 정답**  
리스백이 금융리스이면 판매손익을 리스실행일에 인식하지 않고 리스자산 감가상각기간에 걸쳐 이연 상각·환입함. 운용리스이고 공정가치로 거래된 것이 확실하면 판매손익을 즉시 인식함.

**②' 예상 근거(gold)**: 13.35, 13.36

**③ 실제 답변**  
제공된 맥락 청크에는 금융자산의 양도·담보거래, 유가증권대차, 유가증권 재분류, 선물거래 등에 대한 회계처리만 제시되어 있고, 판매후리스(sale and leaseback) 거래의 회계처리 기준은 포함되어 있지 않습니다 [1][3][4][6][8]. 따라서 이 자료만으로는 판매후리스 거래를 어떻게 회계처리하는지 정확히 답변할 수 없습니다.

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크는 금융자산 양도·담보거래, 유가증권 대차, 유가증권 재분류 등만 다루고 있어 판매후리스(sale and leaseback) 회계처리의 인식·측정 기준이 전혀 포함되어 있지 않습니다. 질문에 필요한 회계처리 절차, 인식 시점, 손익 인식 기준이 누락되어 있어 청크만으로는 답변할 수 없습니다. 다만 현재 청크에는 '타 기준서 준용'이나 외부 기준서 참조 지시가 없어 needs_external은 false입니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-066 (제14장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
충당부채를 인식하려면 어떤 요건을 충족해야 하나요?

**② 예상 정답**  
과거사건의 결과로 현재의무가 존재하고, 그 이행에 자원이 유출될 가능성이 매우 높으며, 금액을 신뢰성 있게 추정할 수 있는 경우 충당부채를 인식함.

**②' 예상 근거(gold)**: 14.4

**③ 실제 답변**  
충당부채는 보고기간말 현재 전종업원이 일시에 퇴직할 경우 지급하여야 할 퇴직금에 상당하는 금액으로 인식합니다 [7]. 또한 급여규정의 개정이나 급여 인상으로 퇴직금 소요액이 증가한 경우에는 그 증가분을 당기비용으로 인식합니다 [7]. 따라서 충당부채를 인식하려면 보고기간말 현재 지급의무가 존재하고, 그에 따라 지급해야 할 금액을 신뢰성 있게 측정할 수 있어야 합니다 [7].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘충당부채 인식 요건’인데, 제공 청크는 주로 부채 분류와 퇴직급여충당부채 관련 회계처리(예: ‘퇴직급여충당부채는 보고기간말 현재 전종업원이 일시에 퇴직할 경우 지급하여야 할 퇴직금에 상당하는 금액’)만 포함하며 일반적인 충당부채 인식요건(현재의무, 자원유출 가능성, 신뢰성 있는 추정 가능성)은 제시되지 않았습니다. 또한 GAAP 범위에서 해당 요건을 직접 설명하는 기준 문단이 청크 내에 없으므로, 이 청크만으로는 질의에 답할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-067 (제14장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
우발부채는 재무제표에 어떻게 반영하나요?

**② 예상 정답**  
우발부채는 부채로 인식하지 않고, 자원 유출 가능성이 아주 낮지 않은 한 주석으로 기재함.

**②' 예상 근거(gold)**: 14.5

**③ 실제 답변**  
우발부채는 일반적으로 재무상태표에 인식하지 않고, 주석으로 공시하는 것이 원칙입니다. 다만 제시된 맥락에는 우발부채의 인식·측정 기준이 직접적으로 제시되어 있지 않으므로, 정확한 처리방법까지는 판단할 수 없습니다 [2][6][10].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘우발부채를 재무제표에 어떻게 반영하는지’인데, 제공 청크는 자산·부채의 유동/비유동 분류, 부채의 결제·약정사항, 주석 공시 일반만 다루며 우발부채의 인식·측정·공시 기준이 직접 나오지 않습니다. 따라서 질문에 답할 구체적 기준이 누락되어 있어 청크만으로는 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-068 (제14장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
충당부채 금액은 어떻게 측정하나요?

**② 예상 정답**  
보고기간말 현재의무 이행에 필요한 지출의 최선의 추정치로 측정하며, 화폐의 시간가치가 중요하면 현재가치로 할인함. 다수 항목은 기대값, 단일 의무는 가장 가능성이 높은 결과로 추정함.

**②' 예상 근거(gold)**: 14.10, 14.11, 14.12, 14.7, 14.8, 14.9

**③ 실제 답변**  
충당부채 금액은 보고기간말 현재 전종업원이 일시에 퇴직할 경우 지급하여야 할 퇴직금에 상당하는 금액으로 측정합니다 [3]. 또한 확정급여형퇴직연금제도에서는 종업원이 아직 퇴직하지 않은 경우에도 보고기간말 현재 퇴직할 경우 지급하여야 할 퇴직일시금에 상당하는 금액을 퇴직급여충당부채로 인식합니다 [3][7][10]. 즉, 미래 예상퇴직일의 평균임금이나 보험수리적 현재가치가 아니라, 보고기간말 현재 기준의 퇴직일시금 상당액으로 측정하는 것이 원칙입니다 [2][3][7][10].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘충당부채 금액은 어떻게 측정하나요?’로 일반적인 충당부채 측정기준을 묻지만, 제공 청크는 대부분 퇴직급여충당부채·퇴직연금미지급금·대손충당금 등 특정 사례에 한정되어 있습니다. 일반 충당부채의 측정 기준(예: 최선의 추정치, 현재가치 적용, 위험과 불확실성 반영)이나 관련 문단이 직접 제시되지 않아, 청크만으로 질의에 포괄적으로 답할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-069 (제14장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
판매 후 무상수리 보증의무에 대한 충당부채는 어떻게 인식하나요?

**② 예상 정답**  
판매 시점에 과거 경험률 등으로 예상 보증비용을 신뢰성 있게 추정하여 제품보증충당부채로 인식하고 동액을 비용으로 계상함. 실제 지출 시 충당부채와 상계함.

**②' 예상 근거(gold)**: 14.4

**③ 실제 답변**  
판매 후 무상수리 보증의무는 과거 사건(판매)으로 인해 현재의무가 발생하고, 그 의무를 이행하기 위해 유출될 자원의 금액을 합리적으로 추정할 수 있는 경우 충당부채로 인식하는 것이 일반적인 처리입니다. 다만, 제공된 맥락에는 판매 후 무상수리 보증의무에 대한 직접적인 문단은 없고, 부채 인식에 관한 일반 규정만 제시되어 있어 이를 보증의무에 직접 적용한 구체 조문 인용은 할 수 없습니다 [2][4][5][6]. 따라서 현재 맥락만으로는 판매 후 무상수리 보증의무의 인식 기준을 직접 확정적으로 답변하기는 어렵습니다.

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘판매 후 무상수리 보증의무에 대한 충당부채의 인식’인데, 제공된 청크는 퇴직급여충당부채·퇴직연금미지급금 및 부채의 유동/비유동 분류에 관한 내용만 포함하고 있어 관련 회계주제가 직접적으로 다르다. 판매보증충당부채의 인식 시점, 측정기준, 추정방법, K-GAAP/K-IFRS 기준 조문은 청크 내에 없으므로 이 청크만으로는 답할 수 없다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-070 (제14장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
승소 가능성이 높은 소송의 우발자산은 재무제표에 반영하나요?

**② 예상 정답**  
우발자산은 자산으로 인식하지 않고, 자원 유입 가능성이 매우 높은 경우 주석으로 공시함. 유입이 확정된 경우에는 관련 자산과 이익을 인식함.

**②' 예상 근거(gold)**: 14.6

**③ 실제 답변**  
승소 가능성이 높은 소송이라도 그 우발자산은 일반적으로 재무제표에 인식하지 않고 주석으로 공시하는 것이 적절합니다. 주석에는 우발상황이 재무제표에 인식되지 않는 항목에 대한 추가 정보를 포함하여야 하며, 우발상황 또는 약정사항과 같이 재무제표에 인식되지 않는 정보도 주석에 포함된다고 되어 있습니다 [3]. 따라서 질문의 소송 우발자산은 재무제표 본문에 반영하기보다 주석으로 공시하는 것으로 이해할 수 있습니다 [3].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘승소 가능성이 높은 소송의 우발자산을 재무제표에 인식(반영)하는지’에 관한 인식·공시 기준이 필요하지만, 청크에는 우발자산의 인식 여부/기준이 직접 제시되어 있지 않습니다. 현재 청크는 자산·부채의 유동/비유동 분류, 주석공시 일반원칙(예: 2.83, 2.85)만 포함할 뿐, 우발자산의 재무제표 반영 여부를 바로 도출할 수 있는 문단이 없어 추론이 필요합니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-071 (제15장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
주식을 액면 이하로 발행하면 그 차액은 어떻게 처리하나요?

**② 예상 정답**  
발행금액이 액면금액에 미달하면 그 차액을 주식발행초과금 범위 내에서 상계하고, 미상계 잔액은 자본조정의 주식할인발행차금으로 처리함.

**②' 예상 근거(gold)**: 15.3

**③ 실제 답변**  
주식을 액면 이하로 발행한 경우, 액면금액과 발행가액의 차액은 자본거래의 성격상 자본잉여금으로 처리하지 않고, 자본조정 항목인 ‘주식할인발행차금’으로 회계처리합니다 [4]. 즉, 차액은 자본금의 가감 성격으로 보아 자본조정으로 분류합니다 [4].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 "주식을 액면 이하로 발행하면 그 차액은 어떻게 처리"인지 묻지만, 제공된 청크에는 주식할인발행차금(액면 미만 발행차액) 처리 규정이 직접 제시되어 있지 않습니다. [4]의 "주식할인발행차금"은 자본조정 항목으로만 예시될 뿐 처리방법이 없고, [2][3][5][6][7][9][10]은 출자전환·무상증자·유가증권 평가 등 다른 주제입니다. 따라서 청크만으로는 답변 근거를 추출할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-072 (제15장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
자기주식을 취득하면 재무제표에 어떻게 표시하나요?

**② 예상 정답**  
자기주식은 자산으로 인식하지 않고 취득원가로 자본조정(자본 차감)에 표시함. 취득·보유 자체로는 손익을 인식하지 않음.

**②' 예상 근거(gold)**: 15.8

**③ 실제 답변**  
자기주식은 자본조정 중 별도 항목으로 구분하여 표시합니다 [1]. 또한 자본조정에는 자기주식이 포함된다고 규정되어 있습니다 [9]. 따라서 자기주식을 취득하면 재무상태표의 자본 항목에서 자기주식을 별도로 표시합니다 [1][9].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 자기주식을 취득했을 때 재무제표 표시 방법인데, 청크 [1] 2.38에서 '자본조정 중 자기주식은 별도 항목으로 구분하여 표시한다'고 직접 명시하고 있어 추론 없이 답변할 수 있습니다. 또한 [9] 2.31에서도 '자기주식'이 자본조정에 포함된다고 확인되며, 외부 기준서 참조 지시도 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-073 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
자본조정 항목에는 어떤 것들이 포함되나요?

**② 예상 정답**  
자본거래에 해당하나 자본금·자본잉여금으로 분류할 수 없는 항목으로, 자기주식, 주식할인발행차금, 감자차손, 자기주식처분손실 등이 포함됨.

**②' 예상 근거(gold)**: 2.31

**③ 실제 답변**  
자본조정은 당해 항목의 성격상 자본거래에 해당하지만 최종 납입된 자본으로 볼 수 없거나, 자본의 가감 성격으로 자본금이나 자본잉여금으로 분류할 수 없는 항목입니다. 예시로 자기주식, 주식할인발행차금, 주식선택권, 출자전환채무, 감자차손 및 자기주식처분손실 등이 포함됩니다 [1]. 또한 자본변동표에서는 자본조정 중 자기주식은 별도 항목으로 구분하여 표시하고, 주식할인발행차금·주식선택권·출자전환채무·감자차손 및 자기주식처분손실 등은 기타자본조정으로 통합하여 표시할 수 있습니다 [2][3].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크 [1]의 2.31과 [3]의 2.38에 자본조정의 정의와 예시가 직접 제시되어 있으며, 자기주식·주식할인발행차금·주식선택권·출자전환채무·감자차손·자기주식처분손실 등을 포함한다고 명시되어 있습니다. 질의가 요구하는 ‘자본조정 항목’의 구성은 청크만으로 추출 가능하므로 외부 기준서 추가 검색은 필요하지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-074 (제15장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 2

**① 질문**  
자기주식을 처분할 때 발생한 손익은 어떻게 처리하나요?

**② 예상 정답**  
처분금액과 취득원가의 차이는 자기주식처분이익(자본잉여금) 또는 자기주식처분손실(자본조정)로 처리하고 당기손익으로 인식하지 않음. 처분손실은 기존 처분이익과 우선 상계함.

**②' 예상 근거(gold)**: 15.9

**③ 실제 답변**  
자기주식은 자본조정으로 처리되며, 자기주식처분손실도 자본조정에 포함됩니다 [3]. 따라서 자기주식을 처분할 때 발생한 손익은 자본거래로 보아 자본항목으로 처리하는 것이 원칙입니다 [3]. 또한 자본잉여금에는 자기주식처분이익이 포함된다고 규정하고 있어, 처분이익은 자본잉여금으로 처리합니다 [3].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '자기주식을 처분할 때 발생한 손익'의 처리이나, 청크 [2]와 [3]에는 자기주식처분이익은 자본잉여금, 자기주식처분손실은 자본조정으로 분류된다는 정보만 있고 처분손익의 인식·처리 기준이 직접적으로 제시되지 않습니다. 반면 [1], [6], [8], [10]은 유가증권/매도가능증권의 처분손익 또는 미실현보유손익에 관한 내용으로 질문 주제와 다르므로, 제공 청크만으로는 자기주식 처분손익을 답할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-075 (제16장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
재화 판매 수익은 어떤 요건을 충족할 때 인식하나요?

**② 예상 정답**  
재화 소유에 따른 유의적 위험과 보상이 구매자에게 이전되고, 판매자가 통상적 통제를 유지하지 않으며, 수익·원가를 신뢰성 있게 측정할 수 있고 효익 유입 가능성이 높을 때 인식함.

**②' 예상 근거(gold)**: 16.10

**③ 실제 답변**  
재화 판매 수익은 재화의 소유에 따른 위험과 효익이 구매자에게 이전되고, 판매자가 재화에 대해 통상적으로 요구되는 정도의 관리상 지속적 관여나 효과적인 통제를 하지 않으며, 수익금액과 거래와 관련된 원가를 신뢰성 있게 측정할 수 있을 때 인식합니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '재화 판매 수익'의 인식요건을 묻고 있으나, 제공 청크는 파생상품 인식·평가(실 6.90~6.98), 금융자산/부채 제거(6.4~6.11), 유가증권 양도 등만 포함하며 수익 인식 기준의 구체적 요건(예: 위험과 보상의 이전, 수익인식 시점, 수행의무 충족 등)이 전혀 제시되어 있지 않습니다. 또한 청크 내에 다른 기준서로의 참조 지시도 없어 외부 기준서 추가 검색 필요성은 확인되지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-076 (제16장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
용역 제공 수익은 어떻게 인식하나요?

**② 예상 정답**  
거래 결과를 신뢰성 있게 추정할 수 있으면 보고기간말 진행기준(진행률)에 따라 인식하고, 신뢰성 있게 추정할 수 없으면 회수가능한 원가 범위 내에서만 수익을 인식함.

**②' 예상 근거(gold)**: 16.11, 16.12, 16.13

**③ 실제 답변**  
제공된 맥락에서는 ‘용역 제공 수익’ 자체의 인식 기준이 직접적으로 제시되어 있지 않습니다. 다만 관련 내용으로는 종업원이 제공한 근무용역의 대가로 기업이 제공하는 보수에 대해서는, 종업원이 근무용역을 제공한 회계기간에 관련 비용과 부채를 인식하는 원칙이 제시되어 있습니다 [7][9]. 따라서 이 맥락만으로는 용역 제공 수익의 인식 시점이나 방법을 확정적으로 답변할 수 없습니다.

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '용역 제공 수익'의 인식 방법인데, 제공된 청크는 주로 종업원 근무용역 대가, 유가증권 손상차손, 금융상품, 수익/비용 총액표시 등 다른 주제이며 용역 제공 수익의 인식 시점·기준·측정방법이 누락되어 있습니다. 특히 [4]의 '관련된 제16장 "수익"의 규정에 따른다'는 외부 기준서 참조만 있을 뿐, 해당 수익 인식 규정 자체는 현재 청크에 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-077 (제16장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 3

**① 질문**  
이자·배당·로열티 수익은 각각 언제 인식하나요?

**② 예상 정답**  
이자수익은 유효이자율을 적용해 기간 경과에 따라, 로열티수익은 계약의 실질에 따라 발생기준으로, 배당수익은 배당받을 권리가 확정되는 시점에 인식함.

**②' 예상 근거(gold)**: 16.15, 16.16, 16.17

**③ 실제 답변**  
이자수익과 배당금수익은 관련된 제 16장 ‘수익’의 규정에 따라 측정·인식하며, 문단 6.A7에 따르면 모든 유가증권으로부터 발생하는 배당금수익과 이자수익은 당기손익에 포함합니다 [5]. 또한 모든 채무증권의 이자수익은 할인 또는 할증차금의 상각액을 가감하여 인식합니다 [5].

로열티수익의 인식 시점은 제공된 맥락 청크에 명시되어 있지 않아, 이 문맥만으로는 정확히 답변할 수 없습니다 [5].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 이자·배당·로열티 수익의 인식 시점을 묻지만, 청크에는 배당금수익·이자수익에 대해 "관련된 제16장 '수익'의 규정에 따른다"는 참조만 있고(청크 [5] 6.A7), 정작 각 수익의 구체적 인식 시점(예: 유효이자율, 사용·권리발생 기준, 로열티의 발생기준 등)이 제시되어 있지 않습니다. 또한 로열티 수익에 관한 내용은 청크 내에 아예 없으므로, 현재 청크만으로는 답변을 완결할 수 없어 외부 기준서 검색이 필요합니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-078 (제16장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
건설형 공사계약의 진행률은 어떻게 측정하나요?

**② 예상 정답**  
누적발생 공사원가를 총공사예정원가(자본화대상 금융비용 제외)로 나눈 비율 등으로 진행률을 산정하고, 계약수익에 진행률을 곱해 누적 인식할 수익을 계산함.

**②' 예상 근거(gold)**: 16.39, 16.47, 16.48

**③ 실제 답변**  
제공된 맥락 청크에는 건설형 공사계약의 진행률을 측정하는 방법에 관한 내용이 없습니다. 따라서 주어진 자료만으로는 해당 질문에 답변할 수 없습니다. [1][2][3][6][8]

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘건설형 공사계약의 진행률’ 측정 방법인데, 제공 청크는 유가증권·금융상품·파생상품의 공정가치, 손상차손, 스왑계약 회계에 관한 내용만 포함합니다. 공사계약 진행률 산정 기준, 예를 들어 원가 대비 진척도나 산출물 기준 등은 청크 내에 없으므로 질문에 직접 답할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-079 (제16장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
총공사예정원가가 총공사계약수익을 초과할 것으로 예상되면 어떻게 하나요?

**② 예상 정답**  
예상되는 손실 전액을 진행률과 무관하게 즉시 당기비용으로 인식하고 공사손실충당부채로 계상함.

**②' 예상 근거(gold)**: 16.53

**③ 실제 답변**  
제공된 맥락 청크에는 총공사예정원가와 총공사계약수익의 비교, 그리고 그 초과 예상 시의 회계처리에 관한 내용이 없습니다. 따라서 이 질문은 주어진 맥락만으로는 답변할 수 없습니다.

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '총공사예정원가가 총공사계약수익을 초과할 것으로 예상되면'의 회계처리를 묻지만, 제공된 청크에는 공사계약/공사손실충당부채 관련 문단이 전혀 없고 유가증권, 퇴직급여, 확정계약 등의 내용만 있습니다. 따라서 질문에 필요한 수치·조건·판단기준이 청크 내에 누락되어 있어 이 청크만으로는 답할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-080 (제16장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
반품가능성이 있는 판매의 수익은 어떻게 인식하나요?

**② 예상 정답**  
반품액을 신뢰성 있게 추정할 수 있으면 예상 반품액을 차감한 순액으로 수익을 인식하고 반품충당부채를 설정함. 추정이 곤란하면 반품기간 종료·인수 시점까지 수익인식을 이연함.

**②' 예상 근거(gold)**: 16.10

**③ 실제 답변**  
제시된 맥락에는 ‘반품가능성이 있는 판매’의 수익 인식 기준이 직접적으로 나오지 않아, 이 질의에 대해서는 정확한 답변을 할 수 없습니다. 다만 맥락상 판매 관련 손상·대손·유가증권 회수가능액 및 수익 인식 규정은 있으나, 반품가능 판매의 수익 인식 시점이나 금액을 정하는 조항은 포함되어 있지 않습니다 [1][4][9].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '반품가능성이 있는 판매의 수익 인식'에 관한 것으로, 제시된 청크에는 관련된 수익 인식 기준이나 반품/환불부채, 반품권 있는 판매의 인식시점·측정 기준이 없습니다. 청크들은 주로 유가증권 손상, 대손충당금, 위험회피회계, 이자수익/대손상각비 등에 관한 내용이므로 질문의 회계 주제를 직접적으로 뒷받침하지 못합니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-081 (제17장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
자산 취득에 사용된 정부보조금은 재무상태표에 어떻게 표시하나요?

**② 예상 정답**  
자산관련 정부보조금은 관련 자산의 차감계정으로 처리하거나 취득원가에서 직접 차감하여 장부금액을 줄이고, 감가상각 시 보조금을 상각액에 비례해 상계함.

**②' 예상 근거(gold)**: 17.5

**③ 실제 답변**  
자산 취득에 사용된 정부보조금이 이 맥락에 직접적으로 규정되어 있지는 않으므로, 주어진 문맥만으로는 재무상태표 표시방법을 확정하여 답변할 수 없습니다. 제공된 문맥은 퇴직연금운용자산, 단체퇴직보험예치금, 투자자산의 표시 등에 관한 내용만 포함하고 있어 정부보조금의 표시기준은 확인되지 않습니다 [1][4][8].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '자산 취득에 사용된 정부보조금'의 재무상태표 표시를 묻지만, 청크에는 정부보조금 관련 문단이 없고 퇴직연금운용자산·투자자산·재무상태표 일반 표시기준만 있습니다. 따라서 질문의 회계 주제와 직접 대응하는 근거가 청크 내에 없어 수치·조건·표시방법을 추출할 수 없으므로 false입니다. 또한 청크에 '다른 기준서에 따른다'는 외부 기준서 참조 지시는 없으므로 needs_external은 false입니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-082 (제17장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
특정 비용 보전 목적의 수익관련 정부보조금은 어떻게 인식하나요?

**② 예상 정답**  
보전 대상 원가를 비용으로 인식하는 기간에 걸쳐 체계적 기준에 따라 정부보조금을 당기손익으로 인식함.

**②' 예상 근거(gold)**: 17.3

**③ 실제 답변**  
특정 비용 보전 목적의 수익관련 정부보조금은 그 보전하려는 비용과 대응되도록 인식하는 것이 원칙입니다. 다만 제공된 맥락에는 정부보조금의 인식기준이 직접적으로 기재되어 있지 않아, 이 질문에 대해 맥락만으로는 정확한 답변을 할 수 없습니다. 관련 내용은 맥락에 포함되어 있지 않습니다 [1][2][4].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '특정 비용 보전 목적의 수익관련 정부보조금'의 인식시점/조건을 묻지만, 제공 청크에는 수익관련 정부보조금이나 정부보조금 회계처리에 대한 내용이 전혀 없습니다. 청크는 수익증권, 손익계산서 표시, 위험회피회계, 퇴직연금운용자산 등 다른 주제만 다루므로, 추론 없이 답변 근거를 추출할 수 없습니다. 외부 기준서 참조 지시도 없으므로 needs_external은 false입니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-083 (제17장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
토지 등 비화폐성자산을 정부보조금으로 이전받으면 어떻게 처리하나요?

**② 예상 정답**  
일반적으로 비화폐성자산의 공정가치를 평가하여 보조금과 자산 모두를 그 공정가치로 회계처리함.

**②' 예상 근거(gold)**: 17.4

**③ 실제 답변**  
토지 등 비화폐성자산을 정부보조금으로 이전받은 경우, 제공하거나 수취한 대가에 금융상품이 아닌 다른 것에 대한 대가가 포함되었다 하더라도 그 금융상품의 공정가치는 원칙적으로 시장가격으로 평가하며, 시장가격이 없으면 평가기법을 사용해 공정가치를 추정합니다 [1][9]. 또한 토지는 감가상각하지 않는 유형자산에 해당하는 비화폐성자산이므로 별도 표시할 수 있습니다 [6]. 다만, 제공된 맥락에는 정부보조금으로 비화폐성자산을 이전받는 경우의 구체적인 인식·측정 기준은 직접적으로 제시되어 있지 않아, 이 질의에 대한 결론을 단정적으로 답하기는 어렵습니다 [1][6][9].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘토지 등 비화폐성자산을 정부보조금으로 이전받았을 때의 회계처리’인데, 청크에는 정부보조금이나 비화폐성자산 수령의 인식·측정 기준이 직접 제시되어 있지 않습니다. 현재 내용은 금융자산/금융부채, 채권·채무조정, 유형자산의 일반 정의에 관한 것으로, 질문의 회계 주제와 직접 대응하는 규정이 없어 추론 없이 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-084 (제17장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
정부보조금을 반환하게 된 경우 회계처리는 어떻게 하나요?

**② 예상 정답**  
반환은 회계추정의 변경으로 처리함. 자산관련 보조금은 반환액만큼 자산 장부금액을 증가시키고 보조금이 없었다면 인식했을 추가 감가상각누계액을 즉시 비용으로 인식하며, 수익관련 보조금은 이연 잔액과 상계 후 초과분을 즉시 비용으로 인식함.

**②' 예상 근거(gold)**: 17.8

**③ 실제 답변**  
정부보조금을 반환하게 된 경우, 반환액은 보조금을 인식할 때와 반대 방향으로 회계처리하여, 관련 자산·부채의 장부금액에서 가감하는 방식이 아니라면 기타포괄손익누계액으로 인식된 금액을 정리하는 방식으로 처리해야 합니다. 다만, 제공된 맥락 청크에는 정부보조금 반환에 대한 직접적인 규정이 없어 구체적 계정처리(당기손익 처리 여부, 자산 차감 여부 등)는 확인할 수 없습니다. 따라서 이 맥락만으로는 정확한 회계처리를 단정할 수 없습니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 정부보조금 반환 시 회계처리인데, 청크들은 현금흐름위험회피회계, 유가증권 재분류·손상, 결손금처리 등 다른 주제만 다룹니다. 정부보조금의 반환 인식 시점, 상계/비용처리/부채처리 기준이 전혀 제시되지 않아 청크만으로 답할 수 없으므로 관련성은 없고, 또한 현재 청크에 다른 기준서로의 명시적 참조 지시도 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-085 (제18장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
차입원가를 자본화할 수 있는 적격자산은 무엇인가요?

**② 예상 정답**  
유형자산·무형자산·투자부동산과, 제조·건설·개발 개시일부터 의도된 용도로 사용·판매 가능한 상태가 되기까지 1년 이상 소요되는 재고자산이 적격자산임.

**②' 예상 근거(gold)**: 18.4

**③ 실제 답변**  
차입원가를 자본화할 수 있는 적격자산은 단순히 ‘유동자산’이나 ‘비유동자산’ 전반이 아니라, 차입원가의 자본화 대상이 되는 특정 자산을 의미합니다. 다만 제시된 맥락에는 적격자산의 정의나 범위에 관한 직접적인 규정이 없고, 유동자산·비유동자산의 분류 및 비유동자산의 예시만 제시되어 있어 이 맥락만으로는 적격자산을 특정할 수 없습니다 [1][4][6][9][10]. 따라서 주어진 자료만으로는 질문에 대한 정확한 답변을 할 수 없습니다 [1][4].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘차입원가를 자본화할 수 있는 적격자산’의 정의·범위가 필요하지만, 제공 청크에는 유동/비유동 분류, 자산 항목 예시, 재무상태표 표시만 있을 뿐 차입원가 자본화 요건이나 적격자산의 구체적 범위가 없습니다. 또한 외부 기준서를 참조하라는 지시는 보이지 않으므로 추가 기준서 참조 필요성은 확인되지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-086 (제18장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
자본화할 차입원가는 어떻게 구성되나요?

**② 예상 정답**  
적격자산 취득을 위해 직접 차입한 특정차입금 차입원가와, 일반목적으로 차입한 자금 중 적격자산 취득에 소요된 것으로 볼 수 있는 일반차입금 차입원가로 나누어 산정함.

**②' 예상 근거(gold)**: 18.6

**③ 실제 답변**  
제공된 맥락에는 ‘자본화할 차입원가’의 구성요소를 직접 설명하는 내용이 없습니다. 따라서 주어진 문서만으로는 질문에 대한 정확한 답변을 할 수 없습니다. [1][2][3][5][6][7][8][9][10]

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '자본화할 차입원가의 구성'에 관한 기준과 구성요소를 요구하지만, 제공 청크에는 자본화할 차입원가(이자비용, 차입부대비용 등)의 정의·범위·계산요소가 없고 자본항목 분류, 금융상품, 유동부채 분류, 자산/자본 변동 사례만 있습니다. 따라서 질문에 직접 답할 수 있는 근거가 누락되어 있으며, 외부 기준서 참조 지시도 청크에 명시되어 있지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-087 (제18장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 2

**① 질문**  
일반차입금에 대한 자본화 차입원가는 어떻게 계산하나요?

**② 예상 정답**  
회계기간 중 적격자산에 대한 평균지출액에서 특정차입금 사용분을 초과하는 부분에 자본화이자율(일반차입금 가중평균이자율)을 적용하여 계산하되, 실제 발생한 일반차입금 차입원가를 한도로 함.

**②' 예상 근거(gold)**: 18.10, 18.11, 18.12, 18.9

**③ 실제 답변**  
일반차입금에 대한 자본화 차입원가는 일반적으로 당해 거래에 내재된 이자율인 유효이자율로 계산하되, 이를 구할 수 없거나 동종시장이자율과의 차이가 유의적인 경우에는 동종시장이자율을 적용합니다 [2]. 동종시장이자율을 실무적으로 산정할 수 없는 경우에는 객관적이고 합리적인 기준에 의하여 산출한 채무자의 가중평균차입이자율을 적용할 수 있고, 그것도 어려우면 회사채 유통수익률을 기초로 채무자의 신용도 등을 반영하여 합리적으로 추정한 자금조달비용을 적용합니다 [2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘일반차입금에 대한 자본화 차입원가 계산방법’인데, 청크에는 자본화 차입원가의 산정식·자본화율·가중평균차입이자율·적격자산 등의 직접 기준이 없습니다. 청크 [2]는 현재가치평가와 유효이자율/동종시장이자율/가중평균차입이자율을 설명할 뿐이고, [8]~[9]는 대손충당금이나 부도채권 관련 사례로 주제와 다릅니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-088 (제18장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 질문**  
K-GAAP에서 차입원가 자본화는 강제인가요, 선택인가요?

**② 예상 정답**  
차입원가는 당기비용 인식이 원칙이나 자본화는 회계정책 선택사항으로 허용됨. 자본화를 선택하면 모든 적격자산에 일관되게 적용함.

**②' 예상 근거(gold)**: 18.4, 18.5

**③ 실제 답변**  
제공된 맥락 청크에는 K-GAAP에서 차입원가 자본화가 강제인지 선택인지에 대한 직접적인 규정이 없습니다. 따라서 이 자료만으로는 답변할 수 없습니다 [1][2][3][4][5][6][7][8][9][10].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 K-GAAP에서 차입원가 자본화의 강제/선택 여부를 묻지만, 제공 청크에는 차입원가 자본화의 인식 요건, 적용 대상, 강제·선택 여부를 직접 규정한 내용이 없습니다. 현재 청크는 자본 분류, 가치평가, 파생상품, 유가증권, 퇴직급여 등의 내용만 포함하며 차입원가 자본화 기준은 확인되지 않으므로 외부 기준서 추가 검색이 필요합니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-089 (제19장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
주식결제형 주식기준보상(스톡옵션)의 보상원가는 어떻게 측정하나요?

**② 예상 정답**  
부여한 지분상품의 부여일 공정가치로 측정하고, 가득기간에 걸쳐 주식보상비용으로 인식하며 동액을 자본(자본조정)으로 계상함.

**②' 예상 근거(gold)**: 19.10, 19.11, 19.12, 19.13, 19.9

**③ 실제 답변**  
주식결제형 주식기준보상(스톡옵션)의 보상원가는 부여한 주식기준보상의 공정가치로 측정하며, 제공하거나 수취한 대가에 금융상품이 아닌 다른 것에 대한 대가가 포함된 경우에는 그 금융상품의 공정가치를 시장가격 또는 평가기법으로 추정합니다 [1][5]. 공정가치의 최선의 추정치는 활성시장에서 공시되는 가격이고, 활성시장이 없으면 평가기법을 사용하되 시장정보를 최대한 사용하여 공정가치를 추정합니다 [1][5]. 또한 공정가치는 계속기업가정을 전제로 한 가격이므로 강제된 거래나 비자발적 청산가격은 포함하지 않습니다 [5].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질문은 주식결제형 주식기준보상(스톡옵션)의 보상원가 측정이지만, 청크들은 금융자산·금융부채의 공정가치/상각후원가, 파생상품, 유가증권 평가 사례만 담고 있어 해당 주제의 측정기준(예: 부여일 공정가치, 가득기간, 추정치 반영 등)이 전혀 제시되지 않았습니다. 또한 ‘타 기준서 준용’ 같은 미해결 외부 참조 지시는 확인되지 않으므로 외부 기준서 검색 필요성도 이 청크 자체에서는 드러나지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-090 (제19장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
현금결제형 주식기준보상은 어떻게 회계처리하나요?

**② 예상 정답**  
부담하는 부채를 부채의 공정가치로 측정하고, 매 보고기간말과 최종결제일에 재측정하여 공정가치 변동액을 보상원가(당기손익)로 인식함.

**②' 예상 근거(gold)**: 19.26, 19.27, 19.28

**③ 실제 답변**  
현금결제형 주식기준보상은 제시된 맥락에 직접적인 회계처리 규정이 없어, 이 자료만으로는 정확한 답변을 확정할 수 없습니다. 다만, 금융상품의 현금흐름이 변경되는 경우에는 변경된 계약상 미래현금흐름의 현재가치를 계산하여 해당 금융자산의 순장부금액이나 금융부채의 상각후원가를 재계산하고, 그 조정금액은 당기손익으로 인식한다고 규정하고 있습니다 [1][3]. 또한 금융상품은 최초인식시 공정가치로 측정하며, 공정가치의 최선의 추정치는 활성시장에서 공시되는 가격이고, 활성시장이 없으면 평가기법을 사용합니다 [6].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '현금결제형 주식기준보상'의 회계처리인데, 제공 청크는 금융상품의 상각후원가·공정가치 측정, 유가증권, 파생상품, 대손충당금, 선물거래 등 금융상품 관련 내용만 포함하고 있어 직접적인 관련 주제(주식기준보상)를 다루지 않습니다. 또한 현금결제형 주식기준보상의 인식시점, 측정기준, 보상원가 인식방법 등 답변에 필요한 기준이 청크 내에 없어 추론 없이 답할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-091 (제19장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 질문**  
스톡옵션의 중도 퇴사 등 비가득이 예상되면 비용을 어떻게 조정하나요?

**② 예상 정답**  
용역제공조건 등 비시장조건은 가득될 것으로 기대되는 수량 추정에 반영해 매 기간 비용을 조정하고, 시장조건은 부여일 공정가치에 반영하여 이후 추정을 변경하지 않음.

**②' 예상 근거(gold)**: 19.13, 19.16

**③ 실제 답변**  
스톡옵션에서 중도 퇴사 등으로 비가득이 예상되면, 가득이 예상되는 인원수와 가득이 예상되지 않는 인원수의 변동을 반영하여 당초 인식한 보상비용을 조정하는 방식으로 처리합니다. 다만, 제공된 맥락에는 스톡옵션의 구체적인 비가득(중도 퇴사) 예상 시 비용 조정 방법이 직접적으로 제시되어 있지 않고, 관련된 내용은 퇴직급여의 경우 급여규정 개정 등으로 소요액이 증가한 경우 당기분과 전기 이전분을 일괄하여 당기비용으로 인식한다는 설명뿐입니다 [2]. 따라서 이 맥락만으로는 스톡옵션의 비가득 예상 시 비용을 정확히 어떻게 조정하는지 확정적으로 답변할 수 없습니다 [2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질문은 스톡옵션의 중도 퇴사 등으로 인한 비가득(예상 미가득) 시 비용 조정 방법을 묻고 있으나, 제공 청크에는 해당 주제의 회계처리 기준이 없습니다. 청크 [1], [3], [7], [8]은 파생상품·옵션·스왑 회계이며, [2]는 퇴직급여, [4]~[6], [9], [10]은 유가증권·재무제표 일반 내용으로 스톡옵션의 가득/비가득에 따른 보상비용 조정 기준(추정 가득주식수 재산정, 누적 보상비용 조정 등)이 제시되어 있지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-092 (제20장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 질문**  
유형·무형자산의 손상 징후에는 어떤 것이 있나요?

**② 예상 정답**  
시장가치의 급격한 하락, 기술·시장·경제·법률 환경의 불리한 변화, 시장이자율 상승, 자산의 진부화·물리적 손상, 경제적 성과 저하 등이 손상 징후에 해당함.

**②' 예상 근거(gold)**: 20.4, 20.5, 20.6, 20.7

**③ 실제 답변**  
유형자산은 재화의 생산이나 용역의 제공, 타인에 대한 임대 또는 자체적으로 사용할 목적으로 보유하는 물리적 형태가 있는 비화폐성자산이며, 토지·건물·기계장치 등을 포함합니다 [10]. 무형자산은 물리적 형체는 없지만 식별가능하고 기업이 통제하며 미래경제적효익이 있는 비화폐성자산으로, 산업재산권·저작권·개발비·영업권 등을 포함합니다 [4]. 다만 제공된 맥락에는 유형·무형자산의 손상 징후를 직접적으로 열거한 내용은 없고, 손상 징후의 예시는 유가증권에 대해서만 제시되어 있으므로 이 질문은 맥락만으로는 답변하기 어렵습니다 [8].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘유형·무형자산의 손상 징후’인데, 제공 청크에는 유형자산·무형자산의 손상 징후 규정이 아니라 유가증권 손상차손(6.A8~6.A18)과 재무상태표 분류(2.18~2.34, 2.35~2.37)만 있습니다. 따라서 질문에 필요한 구체적 판단기준이 청크 내에 없으므로 답변 근거를 직접 추출할 수 없습니다. 외부 기준서 참조 지시는 보이지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-093 (제20장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
손상검사 시 회수가능액은 무엇으로 측정하고 손상차손은 어떻게 인식하나요?

**② 예상 정답**  
회수가능액은 순공정가치(공정가치-처분부대원가)와 사용가치 중 큰 금액임. 회수가능액이 장부금액에 미달하면 그 차액을 손상차손으로 당기손익에 인식함.

**②' 예상 근거(gold)**: 20.10, 20.11, 20.12, 20.8, 20.9

**③ 실제 답변**  
손상검사 시 회수가능액은 유가증권 취득 당시의 유효이자율로 할인한 기대현금흐름의 현재가치로 측정합니다. 다만 취득원가로 평가하는 지분증권의 경우에는 유가증권발행자의 순자산을 자산별 시장가격·공시지가·감정금액 등으로 평가한 공정가치로 회수가능액을 추정합니다 [1][2]. 손상차손은 회수가능액과 장부금액의 차이금액으로 인식하며, 상각후원가로 보고되는 유가증권의 손상차손은 취득 당시의 유효이자율을 사용하여 측정하고 당기손익에 반영합니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 손상검사 시 회수가능액의 측정방법과 손상차손 인식방법을 묻고 있으며, 청크 [1]의 6.A10에 '기대현금흐름의 현재가치(회수가능액)'와 '그 차이금액을 손상차손으로 인식'하며 '당기손익에 반영'한다고 직접 제시되어 있습니다. 또한 6.A11~6.A14, 6.A15~6.A18에서 변동금리, 지분증권, 회복, 이자수익 등 부수 기준도 확인되므로 외부 기준서 추가 검색 없이 답변 가능합니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-094 (제20장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
과거 인식한 손상차손은 환입할 수 있나요?

**② 예상 정답**  
손상 사유가 해소되면 손상차손을 환입하되, 손상을 인식하지 않았을 경우의 장부금액(상각 반영 후)을 한도로 함. 다만 영업권 손상차손은 환입하지 않음.

**②' 예상 근거(gold)**: 20.19, 20.20, 20.21, 20.22, 20.23, 20.24, 20.25, 20.26, 20.27, 20.28

**③ 실제 답변**  
과거에 인식한 손상차손은 원칙적으로 손상차손을 인식한 기간 후에 발생한 사건과 객관적으로 관련된 경우에만 회복된 금액을 당기이익으로 인식할 수 있습니다. 다만 회복 후 장부금액은 당초 손상차손을 인식하지 않았다면 회복일 현재의 상각후원가(문단 6.A13의 지분증권은 취득원가) 를 초과할 수 없습니다 [2]. 따라서 단순한 공정가치 상승만으로는 환입할 수 없고, 손상차손의 회복에 해당하는 경우에 한해 제한적으로 환입 가능합니다 [1][2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘과거 인식한 손상차손의 환입 가능 여부’인데, 청크에는 일반기업회계기준 유가증권 손상차손의 인식·측정·회복 규정이 일부 포함되어 있으나, 질문에 대한 직접적인 결론(환입 가능/불가의 일반원칙)과 적용대상별 조건이 모두 명시되어 있지 않습니다. 다만 [1]의 6.A18과 [2]의 6.A12에는 손상차손의 회복 시 ‘이전 인식 손상차손 금액을 한도로 하여 회복된 금액을 당기이익으로 인식한다’고 되어 있어 회복 인식은 확인되지만, 질문이 묻는 ‘과거 인식한 손상차손은 환입할 수 있나요?’를 포괄적으로 답하기엔 범위가 좁고, 다른 자산(채권/채무조정 등)과의 구분도 필요합니다. 외부 기준서 참조 지시는 청크에 없으므로 needs_external은 false입니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-095 (제20장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
개별 자산의 회수가능액을 추정하기 어려우면 어떻게 하나요?

**② 예상 정답**  
개별 자산의 회수가능액 추정이 곤란하면 그 자산이 속한 현금창출단위(독립적 현금유입을 창출하는 최소 자산집합) 단위로 손상을 검토함.

**②' 예상 근거(gold)**: 20.13, 20.14, 20.15, 20.16, 20.17, 20.18

**③ 실제 답변**  
개별 자산의 회수가능액을 추정하기 어려운 경우에는, 개별 유가증권별로 측정하기 어렵더라도 유사한 유가증권의 포트폴리오를 기준으로 손상차손을 측정하여 인식할 수 있습니다 [5]. 또한 취득원가로 평가하는 지분증권처럼 미래 기대현금흐름에 의한 평가가 사실상 어려운 경우에는, 자산에 대한 시장가격·공시지가·감정가액 등 사용가능한 정보를 이용하여 합리적으로 회수가능액을 추정하여야 합니다 [5][2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의 ‘개별 자산의 회수가능액을 추정하기 어려우면 어떻게 하나요?’에 대해 청크 [5]의 실 6.60이 직접 답하고 있으며, ‘미래의 기대현금흐름에 의한 평가가 사실상 어렵기 때문에 회수가능액은 다른 사용가능한 정보를 이용하여 합리적으로 추정하여야 한다’고 명시합니다. 또한 ‘유가증권 발행기업의 자산에 대한 시장가격, 토지의 공시지가, 감정가액, 기타 추정회수금액 등 사용가능한 정보를 이용하여 평가한 공정가치로 회수가능액을 추정’한다고 구체적 기준까지 포함되어 있어 외부 기준서 추가 검색이 필요하지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-096 (제20장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
사업결합으로 인식한 영업권의 손상은 어떻게 검토하나요?

**② 예상 정답**  
영업권은 관련 현금창출단위에 배분하여 손상을 검토하며, 배분된 현금창출단위의 손상차손은 우선 영업권에 배분하고 나머지를 다른 자산에 배분함.

**②' 예상 근거(gold)**: 20.13, 20.14, 20.15, 20.16, 20.17, 20.18

**③ 실제 답변**  
사업결합으로 인식한 영업권의 손상은 보고기간말마다 회수가능액을 분석하여 손상여부를 판단하고, 손상차손이 발생한 객관적인 증거가 있는 경우에는 회수가능액과 장부금액의 차이금액을 손상차손으로 인식합니다 [6]. 다만, 이는 사업결합으로 인식한 영업권에 대한 구체적 규정이 아니라 유가증권 및 채권 관련 손상규정에 관한 내용이므로, 제시된 맥락만으로는 영업권 손상의 상세한 검토방법을 직접 확인할 수 없습니다 [1][2][6].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘사업결합으로 인식한 영업권의 손상 검토’에 관한 것인데, 제공된 청크들은 매도가능증권·만기보유증권·대손충당금·파생상품 등 유가증권 및 금융자산 손상 관련 내용만 담고 있어 영업권 손상검사 기준이 없습니다. 따라서 질문에 필요한 손상 검토 시점, 회수가능액 산정, 현금창출단위 배분 등 핵심 기준이 누락되어 청크만으로 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-097 (제20장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
자산손상 검사는 언제 수행하나요?

**② 예상 정답**  
매 보고기간말 손상 징후가 있는지 검토하고, 징후가 있으면 회수가능액을 추정함. 아직 사용가능하지 않은 무형자산 등은 징후와 관계없이 매년 손상검사를 수행함.

**②' 예상 근거(gold)**: 20.4, 20.5, 20.6, 20.7

**③ 실제 답변**  
자산손상 검사는 해당 자산에 대해 손상차손이 발생하였다는 객관적인 증거가 있는지 여부를 기준으로 수행합니다. 예를 들어 유가증권의 경우 발행자의 재무상태 악화, 채무불이행, 파산 가능성, 계약의 실질적 위반 등과 같은 사유가 있으면 손상차손 발생 여부를 판단합니다 [4]. 또한 취득원가로 평가하는 지분증권은 보고기간말마다 회수가능액을 분석하여 손상여부를 판단하여야 합니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질문은 ‘자산손상 검사는 언제 수행하나요?’라는 일반적 시점(보고기간말/매년/특정 사건 발생 시 등)을 묻지만, 청크에는 만기보유증권·취득원가 지분증권의 손상차손 인식 기준과 ‘보고기간말 마다 회수가능액을 분석’(6.A13) 정도만 있고 자산손상 검사의 일반적 수행 시점이 누락되어 있습니다. 또한 청크에는 현재 기준서 밖의 문단을 참조하라는 미해결 외부 참조 지시가 없으므로 외부 검색 필요성은 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-098 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
K-GAAP에서 퇴직급여충당부채는 어떤 기준으로 측정하나요?

**② 예상 정답**  
보고기간말 현재 전 종업원이 일시에 퇴직할 경우 지급하여야 할 퇴직금에 상당하는 금액(일시퇴직기준 추계액)으로 측정함.

**②' 예상 근거(gold)**: 21.8

**③ 실제 답변**  
K-GAAP에서 퇴직급여충당부채는 보고기간말 현재 전 종업원이 일시에 퇴직할 경우 지급하여야 할 퇴직금에 상당하는 금액으로 측정합니다 [1]. 또한 급여규정의 개정이나 급여 인상으로 퇴직금 소요액이 증가한 경우에는 당기분과 전기 이전분을 합하여 당기비용으로 인식합니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 K-GAAP에서 퇴직급여충당부채의 측정기준을 묻고 있으며, 청크에 “보고기간말 현재 전종업원이 일시에 퇴직할 경우 지급하여야 할 퇴직금에 상당하는 금액으로 한다”(21.8) 및 이에 대한 결론 설명(21.3, 21.7)과 예시(10)가 직접 제시되어 있습니다. 외부 기준서 참조 지시 없이 청크만으로 답변 가능하므로 추가 검색은 필요하지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-099 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
확정급여형(DB) 퇴직연금제도의 퇴직급여 관련 부채는 어떻게 측정하나요?

**② 예상 정답**  
종업원 퇴직 전에는 보고기간말 현재 퇴직할 경우 지급할 퇴직일시금에 상당하는 금액을 측정하여 퇴직급여충당부채로 인식함. 보험수리적 계리평가가 강제되지 않음.

**②' 예상 근거(gold)**: 21.10

**③ 실제 답변**  
확정급여형(DB) 퇴직연금제도에서 퇴직급여와 관련된 부채는 두 경우로 나누어 측정합니다. 
1) 종업원이 아직 퇴직하기 전에는, 보고기간말 현재 종업원이 퇴직할 경우 지급해야 할 퇴직일시금에 상당하는 금액을 측정하여 퇴직급여충당부채로 인식합니다. 가입기간 요건을 갖추었더라도 퇴직 전이면 동일하게 퇴직일시금 기준으로 측정합니다 [1][2][7].
2) 종업원이 가입기간 요건을 갖추고 퇴직한 후 퇴직연금 수령을 선택한 경우에는, 보고기간말 이후 지급할 예상퇴직연금합계액의 현재가치를 측정하여 퇴직연금미지급금으로 인식합니다. 이때 예상퇴직연금합계액은 사망률 등 보험수리적 가정을 사용해 추정하고, 현재가치는 우량회사채 시장수익률(그러한 시장이 없으면 국공채 수익률)로 할인합니다 [1][2][7].
또한 퇴직연금미지급금은 사망률·할인율 변화와 시간 경과에 따라 변동하며, 그 변동액은 퇴직급여(비용)로 회계처리합니다 [1][2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크 [1], [2], [7], [9]에 확정급여형(DB) 퇴직연금제도의 퇴직급여 관련 부채 측정방법이 명시되어 있습니다. 종업원이 퇴직하기 전에는 보고기간말 현재 퇴직 시 지급할 퇴직일시금 상당액으로 '퇴직급여충당부채'를 인식하고, 퇴직 후 연금 수령을 선택하면 예상퇴직연금합계액을 사망률 등 보험수리적 가정과 우량회사채(없으면 국공채) 시장수익률로 할인한 현재가치로 '퇴직연금미지급금'을 인식한다고 적시되어 있어 외부 기준서가 필요하지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-100 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
확정급여형 퇴직연금의 사외적립자산(퇴직연금운용자산)은 재무상태표에 어떻게 표시하나요?

**② 예상 정답**  
퇴직연금운용자산은 공정가치로 측정하여 퇴직급여충당부채(및 퇴직연금미지급금)에서 차감하는 형식으로 표시하고, 자산이 부채 합계를 초과하면 그 초과액을 투자자산으로 표시함.

**②' 예상 근거(gold)**: 21.12

**③ 실제 답변**  
확정급여형퇴직연금의 사외적립자산인 퇴직연금운용자산은 재무상태표에서 퇴직급여와 관련된 부채(퇴직급여충당부채와 퇴직연금미지급금)에서 차감하는 형식으로 표시합니다 [2]. 또한 퇴직연금운용자산은 하나로 통합하여 ‘퇴직연금운용자산’으로 표시하고, 그 구성내역은 주석으로 공시합니다 [2][4]. 만약 퇴직연금운용자산이 관련 부채의 합계액을 초과하면 그 초과액은 투자자산의 과목으로 표시합니다 [2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크에 확정급여형퇴직연금제도의 표시방법이 직접 제시되어 있습니다. 특히 21.11과 21.12에서 재무상태표에는 운용자산을 하나로 통합하여 '퇴직연금운용자산'으로 표시하고, 퇴직급여충당부채·퇴직연금미지급금에서 차감하며, 초과 시 투자자산으로 표시한다고 명시되어 있어 질의에 바로 답할 수 있습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-101 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
급여규정 개정·급여 인상으로 퇴직금소요액이 증가하면 어떻게 처리하나요?

**② 예상 정답**  
급여규정 개정·급여 인상으로 증가한 퇴직금소요액은 당기분과 전기 이전분을 일괄하여 당기비용(퇴직급여)으로 인식함.

**②' 예상 근거(gold)**: 21.9

**③ 실제 답변**  
급여규정의 개정이나 급여 인상으로 퇴직금소요액이 증가한 경우에는 그 증가분을 당기분과 전기 이전분을 합하여 당기비용으로 인식합니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘급여규정 개정·급여 인상으로 퇴직금소요액이 증가하면 어떻게 처리하나요?’인데, 청크 [1]의 21.9에 ‘급여규정의 개정과 급여의 인상으로 퇴직금소요액이 증가되었을 경우에는 당기분과 전기 이전분을 일괄하여 당기비용으로 인식한다’고 직접 규정되어 있어 외부 기준서 없이 답변 가능합니다. 추가로 현재 청크 내에 타 기준서 준용 지시나 미해결 참조는 보이지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-102 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
확정기여형(DC) 퇴직연금제도의 회계처리는 어떻게 하나요?

**② 예상 정답**  
DC형은 회사가 납입할 기여금을 당기 퇴직급여(비용)로 인식하며, 납입으로 의무가 소멸하므로 퇴직급여충당부채를 별도로 계상하지 않음.

**②' 예상 근거(gold)**: 21.6

**③ 실제 답변**  
확정기여형(DC) 퇴직연금제도에서는 당해 회계기간에 기업이 납부하여야 할 부담금(기여금)을 퇴직급여(비용)로 인식하고, 퇴직연금운용자산·퇴직급여충당부채·퇴직연금미지급금은 인식하지 않습니다 [8][9]. 즉, 확정기여제도는 기업의 부담금만 정해지고 종업원에게 지급될 최종 퇴직급여에 대해 기업이 약속하지 않으므로, 각 회계기간의 부담금만 비용으로 처리합니다 [8][9].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 확정기여형(DC) 퇴직연금제도의 회계처리인데, 청크 [8]과 [9]에 '확정기여제도를 설정한 경우에는 ... 부담금(기여금)을 퇴직급여(비용)로 인식' 및 '퇴직연금운용자산, 퇴직급여충당부채 및 퇴직연금미지급금은 인식하지 아니한다'는 핵심 규정이 직접 포함되어 있어 답변 근거가 충분합니다. 다만 질문 자체에 특정 수치·기간·추가 판단조건은 없으므로 누락 이슈도 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-103 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
종업원 퇴사로 실제 퇴직금을 지급할 때 회계처리는 어떻게 하나요?

**② 예상 정답**  
지급액을 설정되어 있는 퇴직급여충당부채와 우선 상계하고, 충당부채를 초과하는 금액은 당기 퇴직급여로 인식함. 퇴직연금운용자산에서 지급되면 해당 자산과 충당부채를 함께 감소시킴.

**②' 예상 근거(gold)**: 21.8

**③ 실제 답변**  
종업원이 아직 퇴직하기 전이면 보고기간말 현재 퇴직할 경우 지급하여야 할 퇴직일시금에 상당하는 금액을 측정하여 퇴직급여충당부채로 인식합니다. 종업원이 퇴직연금 수급요건 중 가입기간 요건을 갖추었더라도 퇴직 전이라면 마찬가지로 퇴직일시금 기준으로 퇴직급여충당부채를 측정합니다 [2][5].

반대로 종업원이 이미 퇴사한 뒤 퇴직연금 수령을 선택한 경우에는 기존의 퇴직급여충당부채를 제거하고, 퇴직 후 기업이 지급할 것으로 예상되는 퇴직연금합계액의 현재가치를 새 부채인 퇴직연금미지급금으로 인식합니다 [1][2]. 이때 예상퇴직연금합계액은 퇴직 후 사망률 등의 보험수리적 가정을 사용해 추정하고, 현재가치는 보고기간말 현재 우량회사채 시장수익률(적절한 시장이 없으면 국공채 수익률)을 사용해 할인하여 계산합니다 [2].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘종업원 퇴사로 실제 퇴직금을 지급할 때의 회계처리’인데, 청크에는 퇴직금제도/확정급여형퇴직연금제도의 측정·인식은 있으나 실제 지급 시 분개 자체나 지급시점 처리의 구체적 회계처리가 직접적으로 제시되어 있지 않습니다. 다만 청크 [2]·[9]에 ‘퇴직급여충당부채에서 차감하는 형식’ 등 관련 계정 처리 방향은 있으므로 주제는 관련되지만, 질문을 바로 답하기엔 지급 시점의 구체 기준이 누락되어 있습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-104 (제22장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
가산할 일시적차이에 대한 이연법인세부채는 어떻게 인식하나요?

**② 예상 정답**  
가산할 일시적차이가 있으면 원칙적으로 모두 이연법인세부채로 인식함. 미래에 가산되어 납부할 세액효과를 반영하는 것임.

**②' 예상 근거(gold)**: 22.10

**③ 실제 답변**  
가산할 일시적차이에 대해서는 미래에 부담하게 될 법인세부담액을 나타내는 이연법인세부채로 인식하며, 비유동부채 내에서 별도로 구분 표시합니다. 이는 가산할 일시적차이로 인하여 미래에 부담하게 될 법인세부담액이기 때문에 미래 현금흐름 예측에 유용한 정보를 제공한다고 설명하고 있습니다 [4].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘가산할 일시적차이에 대한 이연법인세부채의 인식 방법’인데, 청크 [4]·[6]에는 이연법인세부채의 표시 위치와 의미(“가산할 일시적차이로 인하여 미래에 부담하게 될 법인세부담액”)만 있을 뿐, 인식 시점·인식 요건·측정 기준은 없습니다. 따라서 질문에 답하기 위한 핵심 기준이 누락되어 있어 현재 청크만으로는 답변 근거를 충분히 추출할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-105 (제22장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
이연법인세자산은 항상 전액 인식하나요?

**② 예상 정답**  
차감할 일시적차이·이월결손금 등을 활용할 만큼의 미래 과세소득이 예상되는 범위 내에서만 이연법인세자산을 인식하고, 실현가능성이 낮아지면 감액함.

**②' 예상 근거(gold)**: 22.19, 22.20, 22.21, 22.22, 22.23, 22.44

**③ 실제 답변**  
아니요. 이연법인세자산은 항상 전액 인식하는 것이 아니라, 비유동자산으로 분류되는 경우 기타비유동자산에 별도 표시하며, 미래의 현금흐름 예측에 유용한 정보를 제공하는 범위에서 구분 표시합니다 [1][7]. 다만 제시된 맥락에는 이연법인세자산의 인식 금액을 전액으로 해야 하는지 여부에 대한 직접적인 규정은 없으므로, 이 맥락만으로는 전액 인식 여부를 단정할 수 없습니다 [1][7].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크에는 이연법인세자산의 재무제표상 표시 위치(유동자산/기타비유동자산)와 ‘비유동자산으로 분류되는 이연법인세자산’의 의미만 있을 뿐, 질문한 ‘항상 전액 인식하는지’에 대한 인식요건·실현가능성·평가충분성 등 판단 기준이 없습니다. 따라서 제공된 청크만으로 전액 인식 여부를 답할 수 없으므로 질문에 직접적으로는 불충분합니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-106 (제22장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
이연법인세자산과 이연법인세부채는 상계하여 표시하나요?

**② 예상 정답**  
동일 과세당국·과세대상 기업과 관련된 이연법인세자산과 부채는 상계하여 순액으로 표시함.

**②' 예상 근거(gold)**: 22.55

**③ 실제 답변**  
아니요. 제공된 기준에 따르면 자산과 부채는 원칙적으로 상계하여 표시하지 않으며, 법적 구속력 있는 상계권리와 순액결제 또는 동시결제 의도가 있는 경우에만 상계하여 표시합니다 [5]. 또한 이연법인세자산은 비유동자산으로 구분 표시하고, 이연법인세부채는 비유동부채로 구분 표시한다고 되어 있어 각각 별도로 표시하는 취지입니다 [1][6]. 따라서 이연법인세자산과 이연법인세부채를 일반적으로 상계하여 표시하지 않습니다 [1][5][6].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크에는 이연법인세자산·이연법인세부채의 '각각 별도 표시'만 확인될 뿐, 둘을 상계하여 표시하는지에 대한 직접 규정이 없습니다. 오히려 '자산과 부채는 원칙적으로 상계하여 표시하지 않는다'는 일반원칙(2.41)과 특정 예외(2.42, 21.14)만 제시되어 있어, 질문의 결론을 이 청크만으로 확정할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-107 (제22장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
세무상 이월결손금에 대해서도 이연법인세자산을 인식할 수 있나요?

**② 예상 정답**  
이월결손금·세액공제 등이 미래 과세소득으로 실현될 가능성이 높은 범위에서 이연법인세자산을 인식하며, 소멸기한과 미래 과세소득 예측을 고려함.

**②' 예상 근거(gold)**: 22.25, 22.26, 22.27

**③ 실제 답변**  
네. 제공된 문맥에 따르면 비유동자산으로 분류되는 이연법인세자산은 차감할 일시적차이 등으로 인하여 미래에 경감될 법인세부담액으로서, 미래 현금흐름 예측에 유용하므로 구분 표시합니다 [1]. 또한 이연법인세자산은 기타비유동자산의 별도 표시 항목 예시에 포함되어 있습니다 [1]. 다만 문맥에는 ‘세무상 이월결손금’에 대한 인식 가능 여부를 직접 규정한 내용은 없으므로, 이 문맥만으로 이월결손금에 대해 이연법인세자산을 인식할 수 있는지까지는 단정할 수 없습니다 [1].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크는 이연법인세자산의 정의와 재무상태표 표시(유동자산/비유동자산, 이연법인세부채와의 구분)만 다루고 있어, 질문의 핵심인 ‘세무상 이월결손금에 대해서도 인식 가능한지’에 대한 인식 요건·한도·충족 조건이 누락되어 있습니다. 또한 현재 청크에는 다른 기준서로의 명시적 참조 지시가 없어 외부 기준서 추가 검색 필요성은 확인되지 않습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-108 (제22장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
재평가잉여금·매도가능증권평가손익 등 자본항목의 법인세효과는 어디에 반영하나요?

**② 예상 정답**  
자본(기타포괄손익)에 직접 반영되는 항목의 세효과는 당기손익이 아니라 관련 자본항목에서 직접 가감함.

**②' 예상 근거(gold)**: 22.48

**③ 실제 답변**  
재평가잉여금·매도가능증권평가손익 등은 기타포괄손익누계액에 포함되는 자본항목이며, 그 법인세효과도 함께 기타포괄손익누계액 및 관련 자본항목의 표시와 연결하여 반영합니다 [2][3]. 또한 포괄손익계산서에서는 기타포괄손익 항목으로 매도가능증권평가손익 등에 대해 법인세효과를 표시하는 예시가 제시되어 있습니다 [7]. 따라서 이들 자본항목의 법인세효과는 해당 항목의 기타포괄손익누계액 표시와 관련하여 반영하는 것으로 보아야 합니다 [2][3][7].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 재평가잉여금·매도가능증권평가손익 등 자본항목의 법인세효과를 어디에 반영하는지 묻지만, 청크에는 관련 세무처리의 일반 원칙이나 반영 위치가 직접적으로 제시되지 않았습니다. 다만 [7]에서 기타포괄손익의 구성항목으로 '매도가능증권평가손익(법인세효과: ×××원)'이 예시될 뿐이고, [2], [3]은 자본 항목의 분류·표시만 설명하여 법인세효과의 반영처(예: 당기손익/자본조정/이익잉여금 등)를 바로 도출할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-109 (제23장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
기말 외화자산·부채는 어떤 환율로 환산하나요?

**② 예상 정답**  
화폐성 외화자산·부채는 보고기간말 마감환율로 환산하고 환산손익을 당기손익으로 인식함. 비화폐성 항목은 원칙적으로 취득·부담 당시의 환율(역사적 환율)로 환산함.

**②' 예상 근거(gold)**: 23.10, 23.8, 23.9

**③ 실제 답변**  
기말 외화자산·부채는 보고기간종료일의 현물환율로 환산합니다. 다만 통화선도환율은 통화선도계약의 공정가치 측정에 사용되며, 만기시점 현금흐름을 현재가치로 할 때 적절한 할인율로 할인합니다 [9].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 '기말 외화자산·부채를 어떤 환율로 환산하는지'에 대한 일반 규정이 필요하지만, 제공 청크에는 그 직접 규정이 없습니다. 청크 [9]의 '통화선도환율' 설명과 [6]의 외화환산/위험회피 예시는 있으나, 기말 외화자산·부채의 환산환율(예: 보고기간종료일 현물환율 적용) 자체를 명시한 문단이 없으므로 추론 없이 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-110 (제23장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
기능통화가 다른 해외사업장 재무제표는 어떻게 환산하나요?

**② 예상 정답**  
해외사업장의 자산·부채는 마감환율, 자본은 발생 당시 환율, 손익항목은 거래발생 당시 환율 또는 평균환율로 환산하고, 환산차이는 해외사업환산손익으로 기타포괄손익에 인식함.

**②' 예상 근거(gold)**: 23.14, 23.15, 23.16

**③ 실제 답변**  
기능통화가 다른 해외사업장의 재무제표는 해외사업장순투자의 위험회피에 대한 문단만 제시되어 있어, 일반적인 재무제표 환산 방법 자체는 이 맥락만으로는 확인할 수 없습니다. 다만 제시된 내용에 따르면 해외사업장순투자의 위험회피는 현금흐름위험회피와 유사하게 회계처리하며, 위험회피수단의 손익 중 효과적인 부분은 기타포괄손익으로 인식하고, 비효과적인 부분은 당기손익으로 인식합니다. 또한 기타포괄손익으로 인식한 효과적인 부분은 향후 해외사업장의 처분시점에 재분류조정으로 자본에서 당기손익으로 재분류합니다 [4].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질문은 "기능통화가 다른 해외사업장 재무제표는 어떻게 환산하나요?"로, 해외사업장 재무제표의 환산방법(예: 환산기준통화, 자산·부채·손익·자본의 환산 규칙, 환산차이 처리)이 필요합니다. 그러나 제공 청크에는 해외사업장 환산의 구체 절차나 기준이 없고, 관련된 내용은 6.79의 해외사업장순투자 위험회피 회계뿐이며 이는 환산방법 자체를 설명하지 않습니다. 따라서 답변 근거가 청크 내에 충분히 없으므로 false입니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-111 (제23장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
결산 시 외화매출채권에서 발생한 환산손익은 어디에 인식하나요?

**② 예상 정답**  
화폐성항목인 외화매출채권은 마감환율로 환산하고 장부금액과의 차이를 외화환산손익으로 당기손익에 인식함.

**②' 예상 근거(gold)**: 23.10, 23.8, 23.9

**③ 실제 답변**  
결산 시 외화매출채권은 화폐성항목이므로 결산일 현재의 환율로 환산하여, 환산으로 인해 발생한 환산손익은 당기손익에 인식합니다. 이는 외화표시 채권·채무의 환율변동에 따른 평가손익을 당기손익으로 본다는 취지와 일치합니다 [4][10].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘결산 시 외화매출채권에서 발생한 환산손익의 인식처’인데, 제공 청크는 주로 위험회피회계와 외화위험 관련 내용(예: 실 6.109~6.112, 6.126)만 담고 있어 외화매출채권의 결산환산손익을 어디에 인식하는지에 대한 직접 규정이 없습니다. 특히 매출채권의 환산손익이 당기손익인지 기타포괄손익인지, 또는 외화채권의 결산 시 회계처리 조건이 무엇인지가 청크 내에 누락되어 있어 추론 없이 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-112 (제31장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 질문**  
중소기업 특례로 유형자산 내용연수·잔존가치를 세법에 따를 수 있나요?

**② 예상 정답**  
중소기업 회계처리 특례를 적용하면 유형자산·무형자산의 내용연수 및 잔존가치의 결정을 법인세법 등 법령에 따를 수 있음. 다만 감가상각방법 자체를 세법이라는 이유만으로 그대로 쓰는 것은 특례 범위가 아님.

**②' 예상 근거(gold)**: 31.10

**③ 실제 답변**  
중소기업 특례로 유형자산의 내용연수·잔존가치를 세법에 따를 수 있는지에 대해서는, 제공된 맥락 청크만으로는 직접 확인할 수 있는 근거가 없습니다. 맥락에는 재무제표의 표시, 자산·부채의 분류 및 일부 공시 예시만 제시되어 있고, 유형자산의 내용연수·잔존가치를 세법에 따를 수 있는지에 관한 규정은 포함되어 있지 않습니다 [1][2][4][6][8][10]. 따라서 이 맥락만으로는 답변할 수 없습니다.

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘중소기업 특례로 유형자산 내용연수·잔존가치를 세법에 따를 수 있는지’인데, 제공 청크에는 유형자산의 분류·표시 예시만 있고 내용연수, 잔존가치, 세법 준용에 관한 규정이 없습니다. 따라서 질문에 필요한 구체적 조건·기준이 청크 내에 누락되어 있어 이 청크만으로는 답변할 수 없습니다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-113 (제31장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 질문**  
중소기업 특례에서 장기 채권·채무의 현재가치 평가를 생략할 수 있나요?

**② 예상 정답**  
중소기업 회계처리 특례를 적용하면 장기연불조건 매매거래 등에서 발생한 채권·채무를 명목금액으로 측정하여 현재가치평가를 생략할 수 있음.

**②' 예상 근거(gold)**: 31.7

**③ 실제 답변**  
질의에 대한 직접적인 문구는 제공된 맥락에서 확인되지 않습니다. 다만 일반적으로 장기연불조건의 매매거래나 장기금전대차거래 등에서 발생하는 채권·채무는 명목금액과 공정가치의 차이가 유의적인 경우 현재가치로 평가한다고 되어 있습니다 [5]. 따라서 중소기업 특례에서 장기 채권·채무의 현재가치 평가를 생략할 수 있다고 이 맥락만으로는 말할 수 없고, 오히려 유의적 차이가 있으면 현재가치 평가를 하는 것이 원칙으로 보입니다 [5].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 질의는 ‘중소기업 특례에서 장기 채권·채무의 현재가치 평가를 생략할 수 있는지’인데, 제공 청크에는 장기연불조건 거래나 채권·채무조정 시 ‘현재가치로 평가한다’는 내용(예: 실 6.20의 2, 6.20의 4, 결 6.3~6.7, 6.90~6.91)은 있으나 ‘중소기업 특례’에서 이를 생략할 수 있는지에 대한 명시적 예외·면제 규정이 없다. 또한 적용 기준서 범위가 GAAP이지만, 청크 내에도 중소기업 특례의 생략 가능 여부를 직접 답할 수 있는 기준이 확인되지 않는다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-114 (제31장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 질문**  
중소기업 특례에서 이연법인세를 인식하지 않아도 되나요?

**② 예상 정답**  
중소기업 회계처리 특례를 적용하면 법인세비용을 법인세법 등에 따라 납부할 금액으로 계상할 수 있어 이연법인세자산·부채를 인식하지 않을 수 있음.

**②' 예상 근거(gold)**: 31.12

**③ 실제 답변**  
네. 제공된 맥락에 따르면 이연법인세자산은 당좌자산 내 별도 표시 항목의 예로 제시되고 [8], 비유동자산으로 분류되는 이연법인세자산도 기타비유동자산의 별도 표시 항목 예로 제시됩니다 [1]. 또한 이연법인세부채 역시 유동부채 또는 비유동부채 내 별도 표시 항목의 예로 규정되어 있어 [2][4], 맥락상 이연법인세는 재무상태표에서 분류·표시 대상입니다. 따라서 이 제공 문구만으로는 중소기업 특례에 따라 이연법인세를 인식하지 않아도 된다고 볼 근거는 없습니다 [1][2][4][8].

**③' 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**④ 판정 근거(LLM eval)**: 청크에는 이연법인세자산·이연법인세부채의 표시 규정만 있고, 질문의 핵심인 ‘중소기업 특례에서 이연법인세를 인식하지 않아도 되는지’에 대한 인식 면제 여부나 중소기업 특례 조건이 없다. 따라서 질문에 답하려면 별도의 중소기업 관련 기준서/문단 확인이 필요하므로 현재 청크만으로는 충분하지 않다.

**⑤ 회계사 검토** — 답변 정확성: ☐정확 ☐부분 ☐오류  /  근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---
