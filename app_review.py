"""데이터셋 리뷰 도구 - Streamlit 기반 QA 데이터셋 검수 앱.

dataset_accounting_sample.json의 각 항목을 검수하고,
회계_sample.md 원본 페이지와 대조할 수 있습니다.

실행: streamlit run app_review.py
"""

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

# =============================================================================
# 상수 및 매핑
# =============================================================================

QUESTION_TYPE_KO = {
    "factoid": "사실 확인형",
    "definition": "용어 정의형",
    "numerical": "수치 계산형",
    "procedural": "절차 설명형",
    "reasoning": "추론형",
    "comparison": "비교형",
    "multi_hop": "다단계 추론형",
}

DIFFICULTY_KO = {
    "easy": "쉬움",
    "medium": "보통",
    "hard": "어려움",
}

DIFFICULTY_COLOR = {
    "easy": "green",
    "medium": "orange",
    "hard": "red",
}

QUALITY_OPTIONS = {
    "unreviewed": "미검수",
    "good": "적합 ✅",
    "needs_edit": "수정 필요 ✏️",
    "bad": "부적합 ❌",
}

QUALITY_COLOR = {
    "unreviewed": "gray",
    "good": "green",
    "needs_edit": "orange",
    "bad": "red",
}

DATASET_PATH = Path("easy_sample.json")
MD_PATH = Path("easy_sample.md")


# =============================================================================
# 데이터 로드
# =============================================================================

def load_dataset() -> list[dict]:
    """JSON 데이터셋을 로드합니다."""
    with open(DATASET_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_dataset(data: list[dict]) -> None:
    """JSON 데이터셋을 저장합니다."""
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@st.cache_data
def load_pages() -> dict[int, str]:
    """마크다운 파일을 '## Page N' 기준으로 파싱하여 {페이지번호: 텍스트} 딕셔너리를 반환합니다."""
    content = MD_PATH.read_text(encoding="utf-8")
    pages: dict[int, str] = {}
    # '## Page N'으로 분할
    parts = re.split(r"^(## Page \d+)\s*$", content, flags=re.MULTILINE)
    # parts: ['', '## Page 1', '본문1', '## Page 2', '본문2', ...]
    for i in range(1, len(parts), 2):
        header = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        page_num = int(re.search(r"\d+", header).group())
        pages[page_num] = body.strip()
    return pages


def get_stats(data: list[dict]) -> dict:
    """데이터셋 통계를 계산합니다."""
    return {
        "total": len(data),
        "by_type": Counter(d["question_type"] for d in data),
        "by_difficulty": Counter(d["difficulty"] for d in data),
        "by_cluster": Counter(d["metadata"].get("cluster_id", -1) for d in data),
    }


# =============================================================================
# UI 컴포넌트
# =============================================================================

def render_sidebar(data: list[dict], stats: dict) -> tuple:
    """사이드바: 필터 및 통계 표시. (필터된 데이터, 선택된 인덱스)를 반환합니다."""
    st.sidebar.title("데이터셋 리뷰 도구")
    st.sidebar.markdown(f"**총 항목:** {stats['total']}개")

    # 통계 요약
    st.sidebar.markdown("### 질문 유형 분포")
    for qtype, count in sorted(stats["by_type"].items(), key=lambda x: -x[1]):
        ko_name = QUESTION_TYPE_KO.get(qtype, qtype)
        pct = count / stats["total"] * 100
        st.sidebar.markdown(f"- {ko_name} (`{qtype}`): **{count}**개 ({pct:.0f}%)")

    st.sidebar.markdown("### 난이도 분포")
    for diff, count in sorted(stats["by_difficulty"].items(), key=lambda x: -x[1]):
        ko_name = DIFFICULTY_KO.get(diff, diff)
        st.sidebar.markdown(f"- {ko_name}: **{count}**개")

    # 검수 현황
    st.sidebar.markdown("### 검수 현황")
    review_counts = Counter(
        d.get("review", {}).get("quality", "unreviewed") for d in data
    )
    for qkey in QUALITY_OPTIONS:
        cnt = review_counts.get(qkey, 0)
        color = QUALITY_COLOR[qkey]
        st.sidebar.markdown(f"- :{color}[{QUALITY_OPTIONS[qkey]}]: **{cnt}**개")
    reviewed = stats["total"] - review_counts.get("unreviewed", 0)
    pct = reviewed / stats["total"] * 100 if stats["total"] else 0
    st.sidebar.progress(pct / 100, text=f"검수 진행률: {reviewed}/{stats['total']} ({pct:.0f}%)")

    st.sidebar.markdown("---")

    # 필터
    st.sidebar.markdown("### 필터")
    type_options = ["전체"] + list(QUESTION_TYPE_KO.keys())
    selected_type = st.sidebar.selectbox(
        "질문 유형",
        options=type_options,
        format_func=lambda x: QUESTION_TYPE_KO.get(x, x),
    )

    diff_options = ["전체"] + list(DIFFICULTY_KO.keys())
    selected_diff = st.sidebar.selectbox(
        "난이도",
        options=diff_options,
        format_func=lambda x: DIFFICULTY_KO.get(x, x),
    )

    cluster_ids = sorted(stats["by_cluster"].keys())
    cluster_options = ["전체"] + cluster_ids
    selected_cluster = st.sidebar.selectbox(
        "클러스터",
        options=cluster_options,
        format_func=lambda x: f"클러스터 {x} ({stats['by_cluster'][x]}개)" if x != "전체" else "전체",
    )

    quality_options = ["전체"] + list(QUALITY_OPTIONS.keys())
    selected_quality = st.sidebar.selectbox(
        "검수 상태",
        options=quality_options,
        format_func=lambda x: QUALITY_OPTIONS.get(x, x),
    )

    # 검색
    search_query = st.sidebar.text_input("질문 검색", placeholder="키워드 입력...")

    # 필터 적용
    filtered = data
    if selected_type != "전체":
        filtered = [d for d in filtered if d["question_type"] == selected_type]
    if selected_diff != "전체":
        filtered = [d for d in filtered if d["difficulty"] == selected_diff]
    if selected_cluster != "전체":
        filtered = [d for d in filtered if d["metadata"].get("cluster_id") == selected_cluster]
    if selected_quality != "전체":
        filtered = [
            d for d in filtered
            if d.get("review", {}).get("quality", "unreviewed") == selected_quality
        ]
    if search_query:
        q = search_query.lower()
        filtered = [
            d for d in filtered
            if q in d["question"].lower()
            or q in d.get("expected_answer", "").lower()
        ]

    st.sidebar.markdown(f"**필터 결과:** {len(filtered)}개")

    return filtered


def render_quality_review(item: dict) -> bool:
    """품질 평가 UI를 렌더링합니다. 저장 시 True를 반환합니다."""
    st.markdown("---")
    st.markdown("### 품질 평가")

    current_quality = item.get("review", {}).get("quality", "unreviewed")
    current_comment = item.get("review", {}).get("comment", "")

    col_q1, col_q2 = st.columns([1, 2])
    with col_q1:
        quality = st.radio(
            "품질 판정",
            options=list(QUALITY_OPTIONS.keys()),
            format_func=lambda x: QUALITY_OPTIONS[x],
            index=list(QUALITY_OPTIONS.keys()).index(current_quality),
            key=f"quality_{item['id']}",
            horizontal=True,
        )
    with col_q2:
        comment = st.text_area(
            "검수 코멘트",
            value=current_comment,
            placeholder="수정이 필요한 이유, 부적합 사유 등을 기록하세요...",
            key=f"comment_{item['id']}",
        )

    changed = (quality != current_quality) or (comment != current_comment)

    if changed:
        if st.button("💾 평가 저장", key=f"save_{item['id']}", type="primary"):
            return True
    else:
        st.button("💾 평가 저장", key=f"save_{item['id']}", disabled=True)

    # 현재 상태 표시
    if current_quality != "unreviewed":
        color = QUALITY_COLOR[current_quality]
        st.markdown(f"현재 상태: :{color}[{QUALITY_OPTIONS[current_quality]}]")

    return False


def render_item_detail(item: dict, idx: int, total: int, pages: dict[int, str]):
    """단일 항목의 상세 정보를 표시합니다."""
    qtype_ko = QUESTION_TYPE_KO.get(item["question_type"], item["question_type"])
    diff_ko = DIFFICULTY_KO.get(item["difficulty"], item["difficulty"])
    diff_color = DIFFICULTY_COLOR.get(item["difficulty"], "gray")

    # 헤더
    st.markdown(f"## 항목 {idx + 1} / {total}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("질문 유형", qtype_ko)
    col2.markdown(f"**난이도**")
    col2.markdown(f":{diff_color}[{diff_ko}]")
    col3.metric("클러스터", item["metadata"].get("cluster_id", "N/A"))
    col4.metric("언어", "한국어" if item["language"] == "ko" else "영어")

    # 질문
    st.markdown("### 질문")
    st.info(item["question"])

    # 기대 답변
    st.markdown("### 기대 답변")
    st.success(item["expected_answer"] or "(없음)")

    # 근거 문맥
    st.markdown("### 근거 문맥 (expected_contexts)")
    contexts = item.get("expected_contexts") or []
    if contexts:
        for ci, ctx in enumerate(contexts):
            # '...' 포함 여부 경고
            has_ellipsis = "..." in ctx
            label = f"문맥 {ci + 1}"
            if has_ellipsis:
                label += " ⚠️ 중략(...) 포함"
            with st.expander(label, expanded=len(contexts) <= 2):
                if has_ellipsis:
                    st.warning("이 문맥에 `...`(중략)이 포함되어 있습니다. 원문 전체 인용인지 확인하세요.")
                st.markdown(f"```\n{ctx}\n```")
    else:
        st.warning("근거 문맥이 없습니다.")

    # 태그 및 메타데이터
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### 태그")
        tags = item.get("tags", [])
        st.markdown(" ".join(f"`{t}`" for t in tags) if tags else "(없음)")
    with col_b:
        st.markdown("### 메타데이터")
        st.json(item.get("metadata", {}))

    # 소스 페이지 원문 보기
    source_pages = item.get("metadata", {}).get("source_pages", [])
    if source_pages:
        st.markdown("---")
        st.markdown(f"### 원본 페이지 ({len(source_pages)}개)")
        st.markdown(f"페이지: {', '.join(str(p) for p in source_pages)}")

        # 페이지 선택
        selected_pages = st.multiselect(
            "확인할 페이지 선택",
            options=source_pages,
            default=source_pages[:3],
            format_func=lambda p: f"Page {p}",
        )

        for pg in selected_pages:
            page_text = pages.get(pg, "(페이지를 찾을 수 없습니다)")
            with st.expander(f"📄 Page {pg}", expanded=True):
                st.markdown(page_text)


def render_overview_table(data: list[dict]):
    """전체 항목을 테이블 형태로 표시합니다."""
    rows = []
    for i, item in enumerate(data):
        # '...' 포함 여부 체크
        contexts = item.get("expected_contexts") or []
        has_issue = any("..." in c for c in contexts)
        quality = item.get("review", {}).get("quality", "unreviewed")
        rows.append({
            "#": i + 1,
            "질문 (앞 60자)": item["question"][:60] + ("..." if len(item["question"]) > 60 else ""),
            "유형": QUESTION_TYPE_KO.get(item["question_type"], item["question_type"]),
            "난이도": DIFFICULTY_KO.get(item["difficulty"], item["difficulty"]),
            "클러스터": item["metadata"].get("cluster_id", ""),
            "문맥수": len(contexts),
            "품질": QUALITY_OPTIONS.get(quality, quality),
            "주의": "⚠️" if has_issue else "",
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=min(len(rows) * 38 + 40, 600),
    )


# =============================================================================
# 메인 앱
# =============================================================================

def main():
    st.set_page_config(
        page_title="RAG 데이터셋 리뷰",
        page_icon="📋",
        layout="wide",
    )

    data = load_dataset()
    pages = load_pages()
    stats = get_stats(data)

    filtered = render_sidebar(data, stats)

    # 탭 구성
    tab_detail, tab_overview = st.tabs(["📝 항목별 검수", "📊 전체 목록"])

    with tab_detail:
        if not filtered:
            st.warning("필터 조건에 맞는 항목이 없습니다.")
            return

        # 항목 네비게이션
        col_nav1, col_nav2 = st.columns([3, 1])
        with col_nav1:
            current_idx = st.slider(
                "항목 선택",
                min_value=0,
                max_value=len(filtered) - 1,
                value=0,
                format=f"항목 %d / {len(filtered)}",
            )
        with col_nav2:
            st.markdown(f"**ID:** `{filtered[current_idx]['id'][:8]}...`")

        current_item = filtered[current_idx]
        render_item_detail(current_item, current_idx, len(filtered), pages)

        # 품질 평가
        quality_key = f"quality_{current_item['id']}"
        comment_key = f"comment_{current_item['id']}"
        saved = render_quality_review(current_item)
        if saved:
            # 실제 data 리스트에서 해당 항목을 찾아 업데이트
            for d in data:
                if d["id"] == current_item["id"]:
                    d.setdefault("review", {})
                    d["review"]["quality"] = st.session_state[quality_key]
                    d["review"]["comment"] = st.session_state[comment_key]
                    break
            save_dataset(data)
            st.success("평가가 저장되었습니다!")
            st.rerun()

    with tab_overview:
        st.markdown(f"### 전체 목록 ({len(filtered)}개)")
        render_overview_table(filtered)


if __name__ == "__main__":
    main()
