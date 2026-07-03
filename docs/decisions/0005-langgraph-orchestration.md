# ADR-0005 — 파이프라인 오케스트레이션: LangGraph StateGraph

> **한 줄 요약(BLUF):** 질의 파이프라인(rewrite→search→rerank→evaluate→generate)을 **LangGraph StateGraph + MemorySaver 체크포인터**로 오케스트레이션한다. 직접 함수 호출 대신 그래프로 짜서 HIL 중단/재개와 CRAG 재검색 루프를 구조적으로 지원한다.

- **Status:** Accepted
- **Date:** 2026-06-27 (소급)
- **근거 코드:** `src/agent/workflow.py`(FUNC-009) · `src/models/state.py`(`GraphState`) · 결정: 6/14 회의

## 1. 왜 (Context)
- 파이프라인은 조건 분기(비회계 조기 종료)·사람 개입(HIL)·품질 미달 시 재검색(CRAG 루프)이 필요하다.
- 이를 일반 함수 호출로 짜면 중단·재개·루프 상태 관리가 흩어진다.

## 2. 무엇을 골랐나 (Decision)
- **LangGraph StateGraph**로 노드·라우팅을 선언하고, **MemorySaver** 체크포인터로 HIL `interrupt`/`resume`를 지원한다.
- 공유 상태 `GraphState`(Pydantic)는 **증분 merge** — 각 노드는 변경 필드 dict만 반환한다. (공유 문서에서 각자 담당 칸만 고쳐 넣는 것과 같다 — 노드는 상태 전체가 아니라 바꾼 칸만 돌려주고, 프레임워크가 그 부분만 기존 상태에 덮어써 합친다.)
- CRAG 루프는 평가 미달 시 rewrite로 되돌아가며, 최대 반복은 `src/utils/config.py`의 `MAX_REWRITE_COUNT`가 정본이다.

**선정 근거 (대안 대비: Deep Agent)** — LangChain Deep Agent(LLM이 도구를 스스로 골라 반복·판단하는 자율 에이전트)도 검토했으나 기각(6/14 회의):
- **좁은 도메인·고정 흐름**: 타깃이 '기준서 질의'로 좁아 워크플로우 변동이 적다 → 고정 4콜(rewrite→검색→평가→생성)이 예측 가능·정확·저비용이다.
- **Deep Agent 기각 사유**: LLM 콜·비용·응답시간이 가변이고, 자유 입력에 취약하다 → 좁은 도메인엔 부적합.
- **전환 재검토**: 서비스 범위가 K-IFRS·법률 등으로 넓어질 때 v1.1+에서 다시 본다.

## 3. 결과(영향) (Consequences)
- (+) HIL 중단/재개·CRAG 루프·조건 라우팅을 일관되게 표현하고, 상태가 한 곳(`GraphState`)에 모인다.
- (−) LangGraph 의존·학습곡선이 있고, 디버깅 시 그래프 실행 추적이 필요하다(관찰성은 별도 트랙).
