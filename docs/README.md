# 프로젝트 문서 색인

본 문서는 회계 기준서 RAG 시스템의 전체 문서 구조와 각 문서의 역할 및 바로가기 링크를 제공합니다. 시스템 아키텍처, 기능 명세, 개발 및 운영 가이드, 벤치마크 평가 규칙, 데이터 정책 등 필요한 주제에 따라 해당 문서를 참고할 수 있습니다.

---

## 1. 아키텍처 및 핵심 명세

| 문서 | 담고 있는 내용 | 바로가기 |
|---|---|---|
| 프로젝트 README | 프로젝트 목적, 주요 기능 요약, 빠른 시작 및 실행 방법 안내 | [프로젝트 README](../README.md) |
| 전체 아키텍처 | 서비스 목적, 5단계 파이프라인 구조, 데이터베이스 및 런타임 구성 | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 함수 인터페이스 명세 | FUNC-001부터 FUNC-009까지 각 기능의 역할, 진입점 및 입출력 계약 | [func_interfaces.md](func_interfaces.md) |
| 예외 및 타임아웃 정책 | 에러 코드 분류 체계, 계층별 타임아웃 구조 및 장애 복구 규약 | [architecture/exception_policy.md](architecture/exception_policy.md) |
| 데이터 공개 및 격리 정책 | 기밀 노하우 자산 격리, 레포 분리 기준 및 데이터 보호 가이드 | [architecture/data_disclosure_policy.md](architecture/data_disclosure_policy.md) |

---

## 2. 개발 및 환경 구성 가이드

| 문서 | 담고 있는 내용 | 바로가기 |
|---|---|---|
| 로컬 개발 환경 셋업 | uv 의존성 설치, 환경변수 설정, ingest 및 query CLI 실행, 개발 서버 구동 | [guides/local_dev_setup.md](guides/local_dev_setup.md) |
| Docker 환경 구성 | Docker Compose 스택(`database`, `embedding`, `app`) 빌드 및 인프라 검증 | [guides/docker_setup_guide.md](guides/docker_setup_guide.md) |
| Rocky/RHEL 서버 배포 가이드 | Rocky Linux 및 RHEL 환경에서 Podman 기반 컨테이너 스택 배포, SELinux, 방화벽 및 운영 절차 | [guides/server_deploy_guide.md](guides/server_deploy_guide.md) |
| 서버 간 DB 이관 가이드 | `db_dump.sh` 및 `db_restore.sh`를 활용한 임베딩 데이터베이스 덤프 및 복원 | [guides/db_migration_guide.md](guides/db_migration_guide.md) |
| 하이브리드 검색 가이드 | Dense 및 Sparse 검색 원리, RRF 병합 가중치 설정, 장애 시 폴백 처리 | [guides/retrieval_guide.md](guides/retrieval_guide.md) |
| 문서 온톨로지 가이드 | 기준서 계층 구조화, 온톨로지 노드 청킹, 결정적 `chunk_id` 및 메타데이터 전파 | [guides/ontology_guide.md](guides/ontology_guide.md) |
| 문서 파싱 가이드 | PDF 파싱 정본 규칙, 물리 페이지 마커 시맨틱, 취소선 폐지 조문 제외 기준 | [guides/document_parsing_guide.md](guides/document_parsing_guide.md) |
| Codex 플러그인 가이드 | Codex 환경 플러그인 등록, 매니페스트 확인, 벤치마크 기반 스킬 트리거 검증 | [guides/codex_plugin_guide.md](guides/codex_plugin_guide.md) |

---

## 3. 평가 및 벤치마크 리포트

| 문서 | 담고 있는 내용 | 바로가기 |
|---|---|---|
| 평가 통과 규칙 | 검색 통과(핵심 Top-5) 기준, 답변 적절성 평가 방향 및 성능 기록 원칙 | [benchmark/eval_pass_rules.md](benchmark/eval_pass_rules.md) |
| BM25 리플레이 리포트 | 형태소 분석 전후 및 가중치 조정에 따른 검색 품질 실측 리포트 | [benchmark/bm25_replay_20260725_1911.md](benchmark/bm25_replay_20260725_1911.md) |
| 형태소 토큰화 실측 리포트 | 한국어 형태소 사전토큰화 적용에 따른 검색 지표 비교 분석 리포트 | [benchmark/sparse_morph_replay_20260725_2205.md](benchmark/sparse_morph_replay_20260725_2205.md) |
| 과거 측정 산출물 디렉터리 | 기준서 초기 적재 및 성능 측정 이력 보존 폴더 | [measurements/](measurements/) |


