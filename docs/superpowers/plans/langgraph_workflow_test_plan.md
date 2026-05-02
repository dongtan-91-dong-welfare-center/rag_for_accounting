# LangGraph Workflow 테스트 설계서 (Func-009)

본 문서는 `src/agent/workflow.py`에 구현된 LangGraph RAG 파이프라인의 안정성과 신뢰성을 검증하기 위한 전체 테스트 항목을 정의합니다. 본 테스트 계획은 표준 RAG 흐름, CRAG 루프 제어, 그리고 노드 레벨의 예외 처리 및 로깅 아키텍처를 포괄적으로 검증하는 데 중점을 둡니다.

## 1. 테스트 전략 요약

| 구분 | 내용 |
| :--- | :--- |
| **프레임워크** | pytest |
| **테스트 계층** | Unit Test (구조 및 개별 로직), Integration Test (전체 흐름 및 상태 전이) |
| **핵심 검증 대상** | 노드 등록 및 연결, 조건부 라우팅(CRAG), 예외 복구(Decorator), 상태 데이터 누적 |
| **모킹 전략** | LLM 및 검색 엔진 의존성을 배제하기 위해 Mock 노드 및 가상 상태 데이터 활용 |

---

## 2. 테스트 그룹별 상세 항목

### 2.1. TestWorkflowConstruction: 파이프라인 구축 검증 (Unit)
**목표**: LangGraph 객체가 설계된 노드와 엣지 구조를 올바르게 가지고 있는지 확인합니다.

| 번호 | 테스트명 | 설명 |
| :--- | :--- | :--- |
| 1 | `test_workflow_builds_without_error` | `build_workflow()` 호출 시 에러 없이 `CompiledGraph` 객체가 생성되는지 확인 |
| 2 | `test_workflow_has_required_nodes` | 5개 핵심 노드(`rewrite`, `search`, `rerank`, `evaluate`, `generate`)가 모두 등록되었는지 확인 |
| 3 | `test_workflow_has_edges` | `START`에서 `rewrite`로, `generate`에서 `END`로 이어지는 기본 엣지 연결 확인 |
| 4 | `test_workflow_initial_state_structure` | `GraphState`가 초기화될 때 모든 필드가 정의된 기본값으로 설정되는지 확인 |

### 2.2. TestNormalFlowPath: 정상 경로 흐름 검증 (Unit)
**목표**: 표준 질의 입력 시 각 노드가 순차적으로 실행되며 데이터를 적절히 갱신하는지 확인합니다.

| 번호 | 테스트명 | 설명 |
| :--- | :--- | :--- |
| 5 | `test_normal_path_complete_flow` | `invoke()` 시 모든 노드가 순서대로 실행되어 최종 답변이 생성되는지 전체 프로세스 확인 |
| 6 | `test_rewrite_count_increments` | `rewrite` 노드를 통과할 때마다 `rewrite_count`가 1씩 증가하는지 확인 |
| 7 | `test_search_returns_chunks` | `search` 노드 실행 후 `retrieved_chunks` 필드에 검색 결과가 저장되는지 확인 |
| 8 | `test_rerank_transforms_chunks` | `rerank` 노드에서 검색 결과가 리랭킹 점수를 포함한 `RerankingResult`로 변환되는지 확인 |
| 9 | `test_evaluate_returns_result` | `evaluate` 노드에서 질의-컨텍스트 관련성 평가 결과(`EvaluationResult`)가 생성되는지 확인 |
| 10 | `test_generate_response_created` | `generate` 노드에서 최종 답변과 인용 정보가 포함된 `FinalResponse`가 생성되는지 확인 |

### 2.3. TestCRAGLoopPath: CRAG 루프 및 라우팅 검증 (Unit)
**목표**: 평가 결과에 따른 재작성(Rewrite) 루프 및 종료 조건이 정확하게 동작하는지 확인합니다.

| 번호 | 테스트명 | 설명 |
| :--- | :--- | :--- |
| 11 | `test_route_after_evaluate_to_rewrite` | `needs_external=True`이고 재시도 횟수가 남았을 때 `rewrite` 노드로 분기되는지 확인 |
| 12 | `test_route_after_evaluate_to_generate_on_max_count` | `MAX_REWRITE_COUNT`에 도달했을 때 추가 검색 없이 즉시 답변 생성으로 이동하는지 확인 |
| 13 | `test_route_after_evaluate_to_generate_on_needs_external_false` | 컨텍스트가 충분하여(`needs_external=False`) 즉시 답변 생성 단계로 이동하는지 확인 |

### 2.4. TestErrorHandling: 에러 처리 및 로깅 검증 (Integration)
**목표**: 노드 실행 중 발생하는 다양한 예외 상황이 데코레이터에 의해 관리되고 기록되는지 확인합니다.

| 번호 | 테스트명 | 설명 |
| :--- | :--- | :--- |
| 14 | `test_accounting_rag_error_caught` | 커스텀 예외(`AccountingRAGError`) 발생 시 이를 캐치하여 `error_logs`에 기록하는지 확인 |
| 15 | `test_generic_exception_caught` | 정의되지 않은 일반 예외 발생 시 `UNKNOWN` 타입으로 로깅하고 파이프라인을 유지하는지 확인 |
| 16 | `test_workflow_continues_after_error` | 중간 노드에서 에러가 발생해도 워크플로우가 중단되지 않고 마지막 단계까지 도달하는지 확인 |
| 17 | `test_error_log_structure` | `ErrorLog` 구조 및 KST(+09:00) 타임스탬프 형식을 포괄적으로 검증 |
| 18 | `test_error_logs_append_not_replace` | 여러 노드에서 에러 발생 시 로그가 덮어씌워지지 않고 리스트에 순차적으로 누적되는지 확인 |
| 19 | `test_error_node_field_accuracy` | 에러 로그의 `node` 필드가 실제 에러가 발생한 노드명과 정확히 일치하는지 확인 |
| 20 | `test_route_after_evaluate_error_detection` | `evaluate` 노드 자체에서 에러 발생 시 루프를 방지하고 답변 생성으로 안전하게 유도하는지 확인 |

### 2.5. TestEdgeCases: 엣지 케이스 검증 (Integration)
**목표**: 비정상적인 입력이나 데이터 부재 상황에서의 시스템 견고성을 확인합니다.

| 번호 | 테스트명 | 설명 |
| :--- | :--- | :--- |
| 21 | `test_empty_retrieval_flow` | 검색 결과가 전혀 없는 경우에도 에러 없이 "답변 불가" 응답을 생성하는지 확인 |
| 22 | `test_irrelevant_query_flow` | 비회계 질의 시 루프 회피 검증 |

### 2.6. TestStateTransition: 상태 전이 및 정합성 검증 (Unit)
**목표**: 파이프라인 전 과정에서 `GraphState`의 정합성이 유지되는지 확인합니다.

| 번호 | 테스트명 | 설명 |
| :--- | :--- | :--- |
| 23 | `test_retrieved_chunks_empty_initially` | 워크플로우 시작 전 검색 결과 리스트가 비어있는 상태인지 확인 |
| 24 | `test_reranked_chunks_depend_on_retrieved` | 리랭킹 결과의 개수가 원본 검색 결과의 개수를 초과하거나 누락되지 않는지 확인 |
| 25 | `test_evaluation_none_initially` | 워크플로우 시작 전 평가 결과 필드가 `None`으로 초기화되어 있는지 확인 |
| 26 | `test_final_response_none_initially` | 워크플로우 시작 전 최종 응답 필드가 `None`으로 초기화되어 있는지 확인 |
| 27 | `test_state_accumulation_full_flow` | 전체 실행 완료 후 모든 중간 상태 데이터(쿼리, 청크, 평가)가 최종 상태에 보존되는지 확인 |

---

## 3. 전체 요약

| 테스트 그룹 | 계층 | 항목 수 | 주요 검증 내용 |
| :--- | :--- | :--- | :--- |
| **TestWorkflowConstruction** | Unit | 4 | 그래프 구조, 노드/엣지 구성, 초기 상태 |
| **TestNormalFlowPath** | Unit | 6 | 표준 RAG 프로세스 실행 및 데이터 생성 |
| **TestCRAGLoopPath** | Unit | 3 | CRAG 루프 제어 로직 및 종료 조건 |
| **TestErrorHandling** | Integration | 7 | 예외 캐치, 에러 로그 누적, KST 타임스탬프 |
| **TestEdgeCases** | Integration | 2 | 검색 결과 부재 및 비관련 질의 대응 |
| **TestStateTransition** | Unit | 5 | 필드 초기화 및 실행 전후 상태 정합성 |
| **합계** | - | **27** | **LangGraph 파이프라인 완결성 입증** |
