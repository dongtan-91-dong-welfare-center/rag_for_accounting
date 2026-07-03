# ADR-0004 — 하이브리드 검색 융합: RRF (Reciprocal Rank Fusion)

> **한 줄 요약(BLUF):** dense(의미)와 sparse(키워드) 검색 결과를 **RRF**(순위 기반 융합)로 합친다. 점수 가중합 대신 순위를 쓰므로, 분포가 다른 두 검색을 가중치 튜닝 없이 안정적으로 결합한다.

- **Status:** Accepted
- **Date:** 2026-06-27 (소급)
- **근거 코드:** `src/retrieval/searcher.py`(`reciprocal_rank_fusion`) · **관련:** #99(k 튜닝)

## 1. 왜 (Context)
- dense 코사인 점수와 sparse `ts_rank_cd` 점수는 척도·분포가 달라, 직접 가중합하면 한쪽이 지배한다.
- 가중치를 손으로 맞추면 코퍼스마다 재튜닝이 필요해 취약하다.
- 시험 A는 100점 만점, B는 5점 만점인데 두 점수를 그냥 더하면 A가 결과를 지배한다. RRF는 점수 대신 **등수**(1·2·3등)만 쓰므로 척도가 달라도 공정하게 합친다.

## 2. 무엇을 골랐나 (Decision)
- **RRF**: 각 검색의 *순위*만으로 `1/(k + rank)`를 합산해 병합한다. `k`는 `src/utils/config.py`(`RRF_K`)가 정본이고, 기본값은 원 논문의 실험값이다 — Cormack, Clarke, Büttcher, *"Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods"*, SIGIR 2009.
- 한쪽 검색 실패 시 단독 진행, 0건 시 재탐색한다(FUNC-005 동작 규약).

**메커니즘** — 문서별 점수 `= Σ 1/(k + rank)`로 각 검색의 *순위*만 쓴다. 예: 같은 문서가 dense 2위·sparse 5위면 `1/(k+2) + 1/(k+5)`. `k`가 클수록 상·하위 순위 간 점수 차가 완만해진다.

## 3. 결과(영향) (Consequences)
- (+) 점수 분포 차이에 강건하고, 가중치 튜닝이 불필요하며, 구현이 단순하다.
- (−) 점수 크기 정보를 버리고 순위만 쓴다(미세 신뢰도 손실).
- (−) `k` 최적값은 코퍼스에 의존한다 — 벤치 기반 튜닝은 #99(별도).
