# ADR-0005 — 파이프라인 오케스트레이션: LangGraph StateGraph

> **한 줄 요약(BLUF):** 질의 파이프라인(rewrite→search→rerank→evaluate→generate)을 **LangGraph StateGraph + MemorySaver 체크포인터**로 오케스트레이션한다. 직접 함수 호출 대신 그래프로 짜서 HIL 중단/재개와 CRAG 재검색 루프를 구조적으로 지원한다.

- **Status:** Draft — freeze 조건: PR 리뷰 + 회고 정확성 확인
- **Date:** ADR 작성 2026-06-27
- **근거 이슈:** 코드 `src/agent/workflow.py`(FUNC-009) · 상태 `src/models/state.py`(`GraphState`)

## 1. 왜 (Context)
- 파이프라인은 조건 분기(비회계 조기 종료)·사람 개입(HIL)·품질 미달 시 재검색(CRAG 루프)이 필요하다.
- 이를 일반 함수 호출로 짜면 중단·재개·루프 상태 관리가 흩어진다.

## 2. 무엇을 골랐나 (Decision)
- **LangGraph StateGraph**로 노드·라우팅을 선언하고, **MemorySaver** 체크포인터로 HIL `interrupt`/`resume`를 지원한다.
- 공유 상태 `GraphState`(Pydantic)는 **증분 merge** — 각 노드는 변경 필드 dict만 반환한다.
- CRAG 루프는 평가 미달 시 rewrite로 되돌아가며, 최대 반복은 `src/utils/config.py`의 `MAX_REWRITE_COUNT`가 정본이다.

## 3. 대가 (Consequences)
- (+) HIL 중단/재개·CRAG 루프·조건 라우팅을 일관되게 표현하고, 상태가 한 곳(`GraphState`)에 모인다.
- (−) LangGraph 의존·학습곡선이 있고, 디버깅 시 그래프 실행 추적이 필요하다(관찰성은 별도 트랙).
