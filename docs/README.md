# 문서 인덱스 — 무엇을 알고 싶은가?

> **한 줄 요약(BLUF):** 이 폴더는 "처음 온 사람이 소스를 안 열고 프로젝트를 이해하는" 단일 진실원(SSoT)이다. 아래 결정트리에서 질문을 골라 해당 문서로 가라.

회계 기준서 RAG 시스템 — 회계사가 질문하면 관련 회계기준 **조항**을 찾아 **근거(인용)와 함께** 답한다. 프로젝트 개요·설치·실행은 루트 [README.md](../README.md)를 먼저 보라.

## 무엇을 알고 싶은가?

**처음이라면** ★ [architecture/architecture_overview.md](architecture/architecture_overview.md)부터 전체 그림을 잡고, 구체적 질문이 생기면 아래 표에서 고른다.

| 질문 | 어디로 |
|---|---|
| 이 프로젝트는 무엇이고 어떻게 굴러가나 | [architecture/architecture_overview.md](architecture/architecture_overview.md) — ★현행 단일 진실 |
| 함수 계약(FUNC-001~009) 입출력·에러코드 | [architecture/func_interfaces.md](architecture/func_interfaces.md) |
| ingest·query를 어떻게 실행하나 | [guides/](guides/) (로컬·도커) + 루트 [README.md](../README.md) |
| 검색·답변 **통과 판정 규칙**은 | [policies/eval_pass_rules.md](policies/eval_pass_rules.md) |
| 임계값·모델·`RRF_K` 같은 상수는 | [src/utils/config.py](../src/utils/config.py) |
| 측정·감사 결과(벤치마크·인덱싱·v1 감사) | [measurements/](measurements/) |
| 참조 자료(DART 택소노미·rewrite 샘플·RAG 학습) | [reference/](reference/) |
| 왜 그렇게 결정했나 (ADR) | [decisions/README.md](decisions/README.md) |
| 회계기준 `data/`는 왜 레포에 없나 (BYO) | [decisions/0001-byo-corpus-kgaap.md](decisions/0001-byo-corpus-kgaap.md) |
| 왜 GraphRAG/AGE/Milvus를 버렸나 | [archive/README.md](archive/README.md) |

## 용어 (단일화 사전)

| 용어 | 뜻 |
|---|---|
| **조항 (Subsection)** | 회계기준서의 최소 인용 단위. 검색 정확도 1순위 타깃(Hit@1/MRR). |
| **RRF (Reciprocal Rank Fusion)** | Dense·Sparse 검색 결과를 순위 기반으로 병합(`RRF_K=60`). |
| **HIL (Human-in-the-Loop)** | 답변 신뢰도 미달 시 사용자에게 재질의를 요청하는 분기. |
| **CRAG** | 평가 임계치 미달 시 재검색하는 루프(`MAX_REWRITE_COUNT=3`). |
| **BYO (Bring Your Own)** | 원문 코퍼스를 레포에 두지 않고 사용자가 직접 제공하는 데이터 정책. |

## 작성 규칙

신규 문서는 다음을 지킨다.

**내용 — 가장 먼저 3가지**

1. **상단에 한 줄 요약(BLUF)** — 결론부터.
2. **규칙에는 항상 근거:** — 자의가 아님을 증명. 예: "통합 테스트가 운영 `chunks`를 DROP한 적 있음".
3. **용어는 위 사전으로 단일화** — 약어 첫 등장 시 괄호 병기.

**구조** — 단일 강제 템플릿은 없다(문서 목적이 다양함). 최소 골격만 지킨다: `제목 → BLUF(blockquote) → 본문`. 본문 섹션은 목적에 맞게 자유롭게 둔다(예: 배경·근거 / 제안 / 영향, 또는 표·결정트리).

**문체** — 간결한 **한다체**("~한다")를 신규 문서 기본으로 한다. 복잡한 중첩 복문은 끊어 한 문장에 한 개념만 담고, 전개를 단순하게 유지하며, 일반적이고 쉬운 표현을 쓴다(전문 약어는 위 사전·괄호 병기로 푼다).
