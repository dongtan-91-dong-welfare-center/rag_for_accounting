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

> 케이스별 [예상 근거 · 실제 근거 · 판정]을 대조합니다. 회계사 검토란을 직접 채워 근거 적절성을 판정합니다. (질문 및 답변 전문은 평가 자산 보호를 위해 마크다운 보고서에 기록하지 않으며, 원시 측정 데이터에서 확인합니다.)

### TEST-K-GAAP-001 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 2.65

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-002 (제18장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 18.4, 18.5

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-003 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 21.10, 21.8, 21.9

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-004 (제15장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 15.18, 15.20

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-005 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 6.41, 6.42, 6.43, 6.44, 6.45, 6.46, 6.47

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-006 (제31장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 31.10

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-007 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 6.29, 6.30, 6.31

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-008 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 10.26

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-009 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 10.45

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-010 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 6.31, 6.34

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-011 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 2.57

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-012 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 21.10, 21.11, 21.12, 21.8

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-013 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 6.29

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-014 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 21.12

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-015 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 2.16

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-016 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 2.20

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-017 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 2.20

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-018 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 2.65

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-019 (제5장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 5.11, 5.12

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-020 (제5장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 2

**① 예상 근거(gold)**: 5.14, 5.15, 5.16, 5.17

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-021 (제5장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 5.18, 5.19, 5.20

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-022 (제5장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 5.14, 5.15, 5.16, 5.17, 5.18, 5.19, 5.7

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-023 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 6.22, 6.23, 6.24, 6.25, 6.26, 6.27

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-024 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 6.31

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-025 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 6.29

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-026 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 6.32

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-027 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 6.34

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-028 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 6.41

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-029 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 6.47

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-030 (제6장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 6.31

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-031 (제7장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 7.3

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-032 (제7장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 7.17, 7.20, 7.4

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-033 (제7장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 7.6

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-034 (제7장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 7.12, 7.13, 7.14, 7.15

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-035 (제7장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 7.17

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-036 (제7장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 7.19, 7.20

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-037 (제8장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 8.4, 8.5, 8.6

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-038 (제8장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 8.11

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-039 (제8장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 8.16, 8.19, 8.8

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-040 (제8장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 8.20

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-041 (제8장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 8.24, 8.26

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-042 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 10.10, 10.11, 10.12, 10.13, 10.8, 10.9

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-043 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 10.14, 10.15, 10.16

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-044 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 10.17, 10.18, 10.19, 10.20, 10.21

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-045 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 예상 근거(gold)**: 10.38, 10.39, 10.40

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-046 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 10.34

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-047 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 예상 근거(gold)**: 10.22, 10.30

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-048 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 10.22, 10.23, 10.24, 10.25, 10.26, 10.27, 10.28, 10.29, 10.30, 10.31

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-049 (제10장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 10.41, 10.42

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-050 (제11장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 11.3, 11.4, 11.5, 11.6, 11.7

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-051 (제11장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 11.17, 11.18, 11.19, 11.20

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-052 (제11장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 11.26, 11.27, 11.28, 11.29, 11.30, 11.31, 11.32, 11.33, 11.34, 11.35, 11.36

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-053 (제11장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 예상 근거(gold)**: 11.33

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-054 (제11장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 11.10, 11.11, 11.12, 11.13, 11.14, 11.15, 11.16, 11.17, 11.18, 11.19, 11.20, 11.21, 11.22, 11.7, 11.8, 11.9

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-055 (제11장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 11.2, 11.3, 11.4

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-056 (제12장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 12.32

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-057 (제12장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 12.33

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-058 (제12장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 12.20

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-059 (제12장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 12.32

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-060 (제13장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 예상 근거(gold)**: 13.5, 13.6, 13.7, 13.8

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-061 (제13장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 13.6

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-062 (제13장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 13.13, 13.14, 13.15

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-063 (제13장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 13.19

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-064 (제13장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 13.21, 13.22, 13.23

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-065 (제13장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 13.35, 13.36

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-066 (제14장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 14.4

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-067 (제14장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 14.5

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-068 (제14장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 14.10, 14.11, 14.12, 14.7, 14.8, 14.9

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-069 (제14장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 14.4

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-070 (제14장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 14.6

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-071 (제15장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 15.3

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-072 (제15장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 15.8

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-073 (제2장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 2.31

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-074 (제15장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 2

**① 예상 근거(gold)**: 15.9

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-075 (제16장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 16.10

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-076 (제16장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 16.11, 16.12, 16.13

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-077 (제16장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 3

**① 예상 근거(gold)**: 16.15, 16.16, 16.17

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-078 (제16장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 16.39, 16.47, 16.48

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-079 (제16장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 16.53

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-080 (제16장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 16.10

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-081 (제17장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 17.5

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-082 (제17장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 17.3

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-083 (제17장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 17.4

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-084 (제17장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 17.8

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-085 (제18장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 18.4

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-086 (제18장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 18.6

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-087 (제18장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 2

**① 예상 근거(gold)**: 18.10, 18.11, 18.12, 18.9

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-088 (제18장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 예상 근거(gold)**: 18.4, 18.5

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-089 (제19장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 19.10, 19.11, 19.12, 19.13, 19.9

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-090 (제19장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 19.26, 19.27, 19.28

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-091 (제19장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 예상 근거(gold)**: 19.13, 19.16

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-092 (제20장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 예상 근거(gold)**: 20.4, 20.5, 20.6, 20.7

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-093 (제20장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 20.10, 20.11, 20.12, 20.8, 20.9

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-094 (제20장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 20.19, 20.20, 20.21, 20.22, 20.23, 20.24, 20.25, 20.26, 20.27, 20.28

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-095 (제20장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 20.13, 20.14, 20.15, 20.16, 20.17, 20.18

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-096 (제20장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 20.13, 20.14, 20.15, 20.16, 20.17, 20.18

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-097 (제20장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 20.4, 20.5, 20.6, 20.7

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-098 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 21.8

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-099 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 21.10

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-100 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 21.12

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-101 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 21.9

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-102 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 21.6

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-103 (제21장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 21.8

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-104 (제22장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 22.10

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-105 (제22장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 22.19, 22.20, 22.21, 22.22, 22.23, 22.44

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-106 (제22장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 22.55

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-107 (제22장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 22.25, 22.26, 22.27

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-108 (제22장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 22.48

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-109 (제23장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 23.10, 23.8, 23.9

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-110 (제23장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 23.14, 23.15, 23.16

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-111 (제23장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 23.10, 23.8, 23.9

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-112 (제31장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 1

**① 예상 근거(gold)**: 31.10

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-113 (제31장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ❌ · CRAG 2

**① 예상 근거(gold)**: 31.7

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

### TEST-K-GAAP-114 (제31장)

**판정:** 검색통과(핵심Top-5) ❌ · 검색 exact@10 ❌ · 생성 exact@1 ❌ · answerable ✅ · CRAG 1

**① 예상 근거(gold)**: 31.12

**② 실제 근거(인용 문단)**: —  ·  검색된 장: [None, None, None, None, None, None, None, None, None, None]

**③ 회계사 검토**: 근거(조항) 적절성: ☐적절 ☐부족 ☐오인용  /  메모: 

---

