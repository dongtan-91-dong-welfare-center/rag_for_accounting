"""회계 기준서 RAG — 사용자 대면 질의 화면 (최소 Streamlit UI).

⚠️ 유지보수 동결(deprecated): React(frontend/) + FastAPI(src/api/server.py)가 이 화면의 기능(질의·조항 표시·HIL 승인/재작성)을 대체한다.
신규 기능은 React에만 추가하고, 이 파일은 데모·비교용으로만 유지한다. 제거 시점은 v1.1에서 결정.

CLI(`src/main.py query`)와 동일한 워크플로(run_workflow → resume_workflow)를 브라우저에서 실행한다.
HIL(human_review) interrupt가 발생하면 승인/재작성을 화면에서 받아 재개한다.

실행 (app 컨테이너 안에서):
    docker compose exec app uv run streamlit run app.py \
        --server.port 8501 --server.address 0.0.0.0
    → 브라우저에서 http://localhost:8501  (docker-compose의 8501 포트 매핑 필요)

Streamlit은 사용자 상호작용마다 스크립트를 처음부터 다시 실행하므로,
진행 상태(idle/interrupted/done)와 중간 결과를 st.session_state에 보관해
run → (HIL 승인/재작성)* → done 흐름을 상태머신으로 관리한다.
"""
from __future__ import annotations

import streamlit as st

from src.agent.interrupts import extract_interrupt_payload, is_interrupt
from src.agent.workflow import resume_workflow, run_workflow
from src.db.connection import init_pool
from src.ui.clauses import build_clause_rows

STANDARD_OPTIONS = ["ALL", "GAAP", "KIFRS"]


# st.cache_resource: 동일 프로세스 내 재실행 간에 캐시 유지
@st.cache_resource
def _ensure_pool() -> bool:
    """DB 커넥션 풀을 프로세스당 1회 초기화한다(Streamlit 재실행 간 캐시).

    init_pool()은 idempotent하지만 cache_resource로 감싸 1회만 호출되게 하고, 풀은 앱 프로세스 수명 동안 닫지 않는다(매 재실행마다 close하지 않도록).
    """
    init_pool()
    return True


@st.cache_resource
def _warmup_embedding() -> bool:
    """임베딩 모델을 프로세스당 1회 preload해 첫 질의 콜드 로드를 step_timeout(노드 30s) 밖으로 분리.

    실패해도 앱을 막지 않는다 — 첫 질의가 기존 lazy 로드로 폴백한다.
    """
    from src.utils.embedding import warmup_model

    try:
        warmup_model()
    except Exception as e:  # noqa: BLE001 — preload 실패는 비치명적(lazy 폴백 존재)
        st.warning(f"임베딩 preload 실패 — 첫 질의가 느릴 수 있습니다: {e}")
    return True


def _apply(result: dict) -> None:
    """워크플로 결과를 세션 상태에 반영하고 다음 단계(interrupted/done)를 결정한다."""
    st.session_state.result = result
    st.session_state.thread_id = result.get("thread_id")
    st.session_state.stage = "interrupted" if is_interrupt(result) else "done"


def _render_retrieved_clauses(result: dict) -> None:
    """검색된 조항을 답변보다 먼저 노출한다(NFR-002: 조항 검색 1순위).

    노출 점수는 chunk.score(RRF 하이브리드)다. 
    USE_RERANKER=false에서는 rerank_score가 no-op(1.0)이라 변별력이 없기 때문이며, 리랭커를 켜면 점수 출처/라벨을 전환한다.
    """
    rows = build_clause_rows(result.get("reranked_chunks"))
    st.markdown(f"### 검색된 조항 (상위 {len(rows)}건)")
    if not rows:
        st.caption("검색된 조항 없음")
        return
    st.caption("질의와 가장 관련 높은 회계기준 조항입니다. 아래 답변은 이 조항을 참고해 생성됩니다.")
    for r in rows:
        label = f"[{r.rank}] {r.chapter}장"
        if r.node_id:
            label += f" · {r.node_id}"
        label += f"  ·  검색점수 {r.score:.3f}"
        with st.expander(label):
            st.write(r.content)


def _render_response(result: dict) -> None:
    """검색된 조항(1순위) → 답변 → 인용 순으로 렌더링한다."""
    response = result.get("final_response")
    if response is None:
        st.warning("답변을 생성하지 못했습니다.")
        return

    if response.is_answerable:
        st.success("답변 가능")
    else:
        st.warning("제공된 회계기준 문서에서 충분한 근거를 찾지 못했습니다.")

    # NFR-002: 조항 검색이 1순위이므로 답변보다 먼저 노출한다.
    _render_retrieved_clauses(result)

    st.markdown("### 답변")
    st.markdown(response.answer)
    st.metric("신뢰도", f"{response.confidence_score:.1%}")

    st.markdown(f"### 인용 ({len(response.citations)}건)")
    if not response.citations:
        st.caption("인용 없음")
    for i, c in enumerate(response.citations, start=1):
        with st.expander(f"[{i}] {c.document_id} / {c.chunk_id}  ·  관련도 {c.relevance_score:.2f}"):
            st.write(c.content)


# ───────────────────────────── 화면 ─────────────────────────────
st.set_page_config(page_title="회계 기준서 RAG", page_icon="📘")
st.title("회계 기준서 RAG 질의")

_ensure_pool()
_warmup_embedding()  # #168: 첫 질의 콜드 로드를 step_timeout 밖으로 분리
st.session_state.setdefault("stage", "idle")

# 질의 입력 폼 (HIL 확인 중에는 새 질의 시작을 막는다)
with st.form("query_form", clear_on_submit=False):
    query = st.text_input("질의", placeholder="예: 재고자산의 취득원가는 어떻게 측정하나요?")
    standard = st.selectbox("기준 필터", STANDARD_OPTIONS, index=0)
    submitted = st.form_submit_button(
        "질의", disabled=st.session_state.stage == "interrupted"
    )

if submitted and query.strip():
    with st.spinner("워크플로 실행 중… (rewrite → search → rerank → evaluate → generate)"):
        try:
            result = run_workflow(query.strip(), standard_filter=standard)
        except Exception as e:  # noqa: BLE001 — 화면에 오류를 노출하는 것이 목적
            st.error(f"실행 오류: {type(e).__name__}: {e}")
            st.stop()
    _apply(result)
    st.rerun()

# HIL interrupt — 재작성 전략 확인(승인/재작성)
if st.session_state.stage == "interrupted":
    payload = extract_interrupt_payload(st.session_state.result)
    st.info("재작성 전략이 사용자 확인을 요구합니다.")
    st.write(f"**전략:** {payload.get('strategy', '?')}")
    st.write(f"**원질의:** {payload.get('original_query', '')}")
    for j, q in enumerate(payload.get("search_queries", []), start=1):
        st.write(f"- 검색쿼리 {j}: {q}")

    approve = st.button("이대로 진행 (승인)")
    with st.form("rewrite_form", clear_on_submit=True):
        feedback = st.text_input("재작성 피드백")
        rewrite = st.form_submit_button("재작성 요청")

    decision = None
    if approve:
        decision = {"action": "approve"}
    elif rewrite:
        decision = {"action": "rewrite", "feedback": feedback}

    if decision is not None:
        with st.spinner("재개 중…"):
            try:
                result = resume_workflow(st.session_state.thread_id, decision)
            except Exception as e:  # noqa: BLE001
                st.error(f"재개 오류: {type(e).__name__}: {e}")
                st.stop()
        _apply(result)
        st.rerun()

# 최종 결과 렌더
if st.session_state.stage == "done":
    _render_response(st.session_state.result)
