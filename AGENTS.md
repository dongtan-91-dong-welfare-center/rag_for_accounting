# AGENTS.md

## 1. 프로젝트 개요

본 프로젝트는 회계사와 감사인이 비상장 중소기업 감사 업무에서 일반기업회계기준(K-GAAP) 조항을 신속하게 확인하고 인용 근거와 함께 답변을 생성할 수 있도록 지원하는 검색 증강 생성(RAG) 시스템입니다.

시스템 파이프라인은 질의 재작성(rewrite) → 하이브리드 검색(search: Dense + Sparse를 RRF로 병합) → 선택적 재순위화(rerank) → 품질 평가(evaluate: CRAG 품질 게이트) → 답변 생성(generate) 순서로 동작하며, LangGraph 프레임워크가 전체 워크플로를 오케스트레이션합니다.

## 2. 빌드 및 테스트 명령

본 프로젝트는 의존성 관리 및 패키지 실행을 위하여 `uv`를 사용합니다.

- **의존성 동기화**: `uv sync`
- **단위 테스트 실행**: `uv run pytest tests/unit` (또는 `uv run pytest -m unit`)
- **시스템 통합 테스트 실행**: `uv run pytest tests/integration`
- **테스트 마커 (`pyproject.toml` 기준)**:
  - `unit`: 개별 함수 논리 검증, 외부 의존성이 없는 단위 테스트 (Phase 0: Unit)
  - `system`: 가짜 데이터를 기반으로 한 예외 경로 및 데이터 규격 검증 (Phase 1: Fast Fail)
  - `benchmark`: 벤치마크 정답셋을 기반으로 한 답변 품질 검증 (Phase 2: Quality)
- **테스트 데이터 위치**: `data/test_data`

## 3. 단일 진실 공급원(SSoT) 규칙

- **모델·임계값·상수**: `src/utils/config.py` 파일이 단일 정본입니다. 문서에 수치나 모델명을 직접 복제하지 않고 이 파일을 가리키도록 작성합니다.
  - `근거:` 인덱싱(FUNC-003)과 검색(FUNC-005)이 `src/clients/embedding.py`를 공유하므로 모델과 차원을 단일 지점에서 고정해야 불일치 발생을 구조적으로 방지할 수 있습니다.
  - 주요 상수 예시: `OPENAI_MODEL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `RRF_K`, `TOP_K_RETRIEVAL`, `MAX_REWRITE_COUNT`, `MAX_HIL_COUNT`, `USE_RERANKER`.
- **스키마 정의**: `src/models/schemas.py` 파일이 파이프라인 전반의 공통 데이터 스키마 정본입니다. API 응답 스키마는 `src/api/schemas.py`를 정본으로 합니다.

## 4. 코딩 및 문서 작성 규칙

- **문장 작성 지침**:
  - 서술어와 종결어미를 갖춘 완성된 문장 형태로 서술하며, 명사구나 부사구 또는 연결어미로 문장을 끝맺지 않습니다.
  - 필수적인 문장 성분과 조사 및 어미를 생략하지 않고 명확하게 작성합니다.
  - 맥락에 부합하는 명확한 한자어를 적극적으로 활용하며, 지나친 비유적 표현은 지양합니다.
  - 문장 간의 관계를 모호하게 만드는 엠대시(—) 사용을 자제하고 콜론이나 명확한 접속사를 사용합니다.
- **코드 및 프로젝트 관례**:
  - 변수명, 코드 주석, 커밋 메시지, 로그 문자열 등 코드에 속하는 텍스트는 프로젝트의 기존 관례를 준수합니다.
- **주요 규칙**:
  - 기술적 결정이나 제약 사항을 서술할 때는 `근거:` 접두사를 사용하여 이유를 명시합니다.
  - 프로젝트 내 표준 용어를 단일화하여 일관성 있게 사용합니다.

## 5. 자율 진행 허용 경계

AI 에이전트가 작업을 수행할 때 승인 없이 자율적으로 진행할 수 있는 범위와 사전에 사용자의 확인을 받아야 하는 경계는 다음과 같습니다.

| 구분 | 허용 범위 |
|---|---|
| **승인 없이 진행 가능** | <ul><li>`data/test_data` 기반 `pytest -m unit` 및 `tests/integration` 실행과 재실행</li><li>테스트 실패 원인의 로컬 재현 및 분석</li><li>문서 내부 링크와 설명 문구의 오류 수정</li><li>린트 및 코드 포매팅 관련 수정</li><li>사용자로부터 요청받은 코드 변경으로 인해 발생한 테스트 실패를 해결하기 위한 수정 및 관련 테스트 재실행</li></ul> |
| **사전 확인 필요** | <ul><li>`benchmark` 마커 테스트 실행 (외부 API 호출 비용 발생)</li><li>데이터 스키마 및 마이그레이션 관련 변경</li><li>`git push` 및 원격 저장소 쓰기 작업</li><li>운영 데이터베이스 접근 및 변경</li><li>배포 설정 파일 및 시크릿(비밀값) 정보 변경</li></ul> |

## 6. 길찾기

- **문서 인덱스**: [docs/README.md](docs/README.md) (프로젝트 전체 문서 목록 및 인덱스 표)
- **현행 아키텍처 (단일 진실)**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **과거 설계 및 변경 이력**: [docs/ARCHITECTURE.md#변경-이력](docs/ARCHITECTURE.md#변경-이력)
- **설치 및 실행 가이드**: [README.md](README.md), [docs/guides/](docs/guides/)

## 7. 스킬 이중 경로 관리 규칙 (#303)

본 프로젝트의 `k-accounting` 스킬은 지원 도구에 따라 두 경로에 나누어 배치되어 있습니다.

- **Codex 플러그인 정본**: `src/skills/k-accounting/SKILL.md` (`src/`가 플러그인의 루트입니다)
- **Claude Code용 복사본**: `.claude/skills/k-accounting/SKILL.md` (저장소 내 자동 로드를 위해 고정 경로 사용)

두 파일의 내용은 항상 완벽히 동일해야 합니다. 스킬 내용을 수정하거나 설명(description)을 갱신할 때는 **반드시 두 파일을 동시에 수정**해야 하며, 수정 후 다음 명령을 실행하여 동기화 상태를 검증해야 합니다.

```bash
uv run pytest tests/unit/test_claude_skill.py
```
