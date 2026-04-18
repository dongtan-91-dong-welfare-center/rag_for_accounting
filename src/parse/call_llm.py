import base64
import re
from pathlib import Path

import fitz  # PyMuPDF
import httpx

BASE_URL = "http://localhost:8000/v1"
MODEL = "qwen3.6-35b"


# ────────────────────────────────────────────────
# 2) PDF → RAG 친화 markdown
# ────────────────────────────────────────────────
HEADING_RULE = """[heading 레벨 규약 — 반드시 이 규약을 지킬 것]
- # (h1)    : 장        (예: "제6장 금융자산·금융부채")
- ## (h2)   : 절        (예: "제1절 공통사항")
- ### (h3)  : 소제목     (예: "금융상품의 최초인식", "금융상품의 제거",
                              "대손충당금", "주석 공시")
              → 절(##) 안에서 여러 조항(6.X)을 내용적으로 묶는 단락 표지.
              → "제N절/제N장" 접두어가 없고 "6.X" 조항번호도 없는 명사구 제목.
              → 이런 소제목을 놓치지 말고 반드시 ### 레벨로 표시하세요.
- #### (h4) : 조        (예: "6.1", "6.4의2", "6.17의2")
- ##### (h5): 항        (예: "(1)", "(2)", "(11)")
- ###### (h6): 호       (예: "(가)", "(나)")

책 제목, 부록명, 의결일자 등은 heading 이 아닌 본문 또는 **굵은 글씨** 로만 표기하세요.
"""

COMMON_RULES = """[변환 규칙]
1. 위 heading 규약을 그대로 적용합니다.
2. 본문은 원문을 충실히 보존하되, 문단이 어색하게 끊긴 경우 자연스럽게 이어 정리합니다.
3. 표는 원본 형태의 markdown table 을 먼저 출력한 뒤, 바로 아래에
   "이 표는 …을 나타내며, 주요 내용은 …이다" 형식의 자연어 풀이를 병기합니다.
4. 그림·도식·플로우차트 등 이미지 요소는 주변 문맥과 함께
   "이 도식은 …을 설명한다. 구성 요소는 … 관계는 …이다" 형식의 해석 텍스트로 작성합니다.
5. 페이지 번호, 머리말·꼬리말, 장식 요소(로고, 구분선)는 출력하지 않습니다.
6. 코드블록(```) 은 사용하지 않습니다. 순수 markdown 본문만 출력하세요.
7. 결과는 한국어로 작성합니다.

설명이나 사족 없이 변환된 markdown 본문만 반환하세요.
"""


def _fmt(v: str | None) -> str:
    return v if v else "(아직 확인되지 않음)"


def build_page_prompt(state: dict, prev_page_md: str | None = None) -> str:
    """현재 6단계 state + 직전 페이지 markdown 을 주입한 프롬프트를 구성."""
    jang = _fmt(state.get("jang"))
    jeol = _fmt(state.get("jeol"))
    sojemok = _fmt(state.get("sojemok"))
    last_article = _fmt(state.get("last_article"))
    last_item = _fmt(state.get("last_item"))
    last_ho = _fmt(state.get("last_ho"))

    prev_block = ""
    if prev_page_md:
        prev_block = (
            "[직전 페이지 markdown — 참고용]\n"
            "아래는 바로 앞 페이지의 변환 결과입니다. 이 페이지는 이 내용 뒤에 이어집니다.\n"
            "특히 직전 페이지의 마지막 문단·문장이 중간에 끊겨 있다면, 이 페이지 첫 부분은\n"
            "그 문장을 자연스럽게 이어 완성하는 본문으로 시작해야 합니다.\n"
            "직전 페이지 내용을 다시 반복하지 말고, '이어지는 부분'만 작성하세요.\n"
            "```markdown\n"
            f"{prev_page_md}\n"
            "```\n\n"
        )

    state_block = (
        "[현재 문서 위치 — 이전 페이지까지의 상태]\n"
        f"- 장 (#):       {jang}\n"
        f"- 절 (##):      {jeol}\n"
        f"- 소제목 (###):  {sojemok}\n"
        f"- 직전 조 (####): {last_article}\n"
        f"- 직전 항 (#####): {last_item}\n"
        f"- 직전 호 (######): {last_ho}\n\n"
        "[이 페이지 작성 시 규약 — 레벨 혼용 금지, 매우 엄격]\n"
        "1. `#` (h1) → 텍스트가 '제N장 ...' 으로 시작하는 경우에만. 그 외 모든 상황에서 `#` 금지.\n"
        "2. `##` (h2) → 텍스트가 '제N절 ...' 으로 시작하는 경우에만. 그 외 모든 상황에서 `##` 금지.\n"
        "   · '목적', '적용범위', '개요' 같은 2~4자 명사구라도 `##` 아님 → `###` 로 작성.\n"
        "3. `###` (h3) → '제N장/제N절' 접두어도 없고 '6.X' 조항번호도 없는 모든 소제목 (예: '목적',\n"
        "   '적용범위', '금융상품의 최초인식', '대손충당금', '주석 공시'). 중요해 보여도 `##` 로 올리지 않음.\n"
        "4. `####` (h4) → '6.X', '6.X의N' 조항번호. 이 번호가 이것 외 다른 레벨에 등장하지 않도록 주의.\n"
        "5. `#####` (h5) → '(1)', '(2)' 등 아라비아 숫자 항 번호.\n"
        "6. `######` (h6) → '(가)', '(나)' 등 한글 자모 호 번호.\n"
        "\n"
        "7. 새로운 장/절/소제목이 이 페이지에 없으면 위 계층을 그대로 이어 작성.\n"
        f"8. 직전 페이지가 '{last_article} {last_item}' 에서 끝났다면,\n"
        "   이 페이지는 같은 조의 다음 항 또는 바로 다음 조로 이어질 가능성이 높습니다.\n"
        " 이전 페이지의 구조를 반영해서 이 페이지 첫 부분을 자연스럽게 작성하세요."
    )
    return (
        "이 이미지는 한국 회계 기준서 PDF의 한 페이지입니다.\n"
        "페이지 내용을 RAG(검색 증강 생성)에 적합한 markdown 으로 변환해 주세요.\n\n"
        f"{HEADING_RULE}\n{prev_block}{state_block}\n{COMMON_RULES}"
    )


def render_page_png(pdf_path: Path, page_index: int, dpi: int = 250) -> bytes:
    """PDF 의 특정 페이지를 PNG bytes 로 렌더링."""
    with fitz.open(pdf_path) as doc:
        page = doc[page_index]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return pix.tobytes("png")


def parse_page_via_llm(
    image_bytes: bytes,
    state: dict,
    prev_page_md: str | None = None,
    max_tokens: int = 8192,
) -> dict:
    """페이지 PNG 을 vision LLM 에 넘겨 markdown 생성."""
    b64 = base64.b64encode(image_bytes).decode()
    resp = httpx.post(
        f"{BASE_URL}/chat/completions",
        json={
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": build_page_prompt(state, prev_page_md),
                        },
                    ],
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
            #"chat_template_kwargs": {"enable_thinking": False}, # Thinking 옵션
        },
        timeout=600.0,
    )
    resp.raise_for_status()
    return resp.json()


# ────────────────────────────────────────────────
# state 추출 로직
# ────────────────────────────────────────────────
_HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_JANG_PAT = re.compile(r"제\s*\d+\s*장")
_JEOL_PAT = re.compile(r"제\s*(\d+)\s*절")
_ARTICLE_PAT = re.compile(r"^\s*(\d+\.\d+(?:의\d+)?)")
_ITEM_PAT = re.compile(r"^\s*\(\s*(\d+)\s*\)")
_HO_PAT = re.compile(r"^\s*\(\s*([가-힣])\s*\)")
_SOJEMOK_EXCLUDE = re.compile(r"(제\s*\d+\s*[장절])|^\s*\d+\.\d+")

_STATE_KEYS = ("jang", "jeol", "sojemok", "last_article", "last_item", "last_ho")


def _empty_state() -> dict:
    return {k: None for k in _STATE_KEYS}


def _state_brief(state: dict) -> str:
    """로그용 한 줄 요약."""
    return (
        f"장={state.get('jang')!r} 절={state.get('jeol')!r} "
        f"소제목={state.get('sojemok')!r} 조={state.get('last_article')!r} "
        f"항={state.get('last_item')!r} 호={state.get('last_ho')!r}"
    )


def is_toc_page(md_text: str) -> bool:
    """목차/표지 페이지 감지 — ## 레벨에서 서로 다른 '제N절' 이 3개 이상이면 ToC."""
    jeol_numbers: set[str] = set()
    for m in _HEADING_LINE_RE.finditer(md_text):
        level = len(m.group(1))
        if level != 2:
            continue
        title = m.group(2).strip()
        mm = _JEOL_PAT.search(title)
        if mm:
            jeol_numbers.add(mm.group(1))
    return len(jeol_numbers) >= 3


def update_state(md_text: str, state: dict) -> tuple[dict, bool, bool]:
    """페이지 md 를 순서대로 훑으며 6단계 state 를 갱신.

    - 장(#): "제N장"    → 하위(절/소제목/조/항/호) 모두 리셋
    - 절(##): "제N절"    → 하위(소제목/조/항/호) 리셋
    - 소제목(###): 명사구  → 하위(조/항/호) 리셋
    - 조(####): "6.X"   → 하위(항/호) 리셋
    - 항(#####): "(N)"   → 하위(호) 리셋
    - 호(######): "(가)"

    Returns:
        (new_state, changed, is_toc)
    """
    if is_toc_page(md_text):
        return dict(state), False, True

    new_state = dict(state)
    changed = False
    for m in _HEADING_LINE_RE.finditer(md_text):
        level = len(m.group(1))
        title = m.group(2).strip()

        if level == 1 and _JANG_PAT.search(title):
            new_state.update(
                jang=title, jeol=None, sojemok=None,
                last_article=None, last_item=None, last_ho=None,
            )
            changed = True
        elif level == 2 and _JEOL_PAT.search(title):
            new_state.update(
                jeol=title, sojemok=None,
                last_article=None, last_item=None, last_ho=None,
            )
            changed = True
        elif level == 3 and not _SOJEMOK_EXCLUDE.search(title):
            new_state.update(
                sojemok=title,
                last_article=None, last_item=None, last_ho=None,
            )
            changed = True
        elif level == 4:
            am = _ARTICLE_PAT.match(title)
            if am:
                new_state.update(
                    last_article=am.group(1),
                    last_item=None, last_ho=None,
                )
                changed = True
        elif level == 5:
            im = _ITEM_PAT.match(title)
            if im:
                new_state.update(
                    last_item=f"({im.group(1)})",
                    last_ho=None,
                )
                changed = True
        elif level == 6:
            hm = _HO_PAT.match(title)
            if hm:
                new_state["last_ho"] = f"({hm.group(1)})"
                changed = True
    return new_state, changed, False

def page_cache_path(cache_dir: Path, page_idx: int) -> Path:
    return cache_dir / f"page_{page_idx + 1:03d}.md"

def convert_pdf_to_md(
    pdf_path: Path,
    out_path: Path,
    cache_dir: Path,
    page_range: range | None = None,
    dpi: int = 250,
    force: bool = False,
) -> None:
    """PDF → 페이지별 LLM 변환 → cache 저장 → 하나의 md 파일로 병합."""
    with fitz.open(pdf_path) as doc:
        total = len(doc)
    pages = list(page_range) if page_range is not None else list(range(total))

    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    state: dict = _empty_state()
    prev_page_md: str | None = None

    for i in pages:
        cp = page_cache_path(cache_dir, i)
        if cp.exists() and not force:
            content = cp.read_text(encoding="utf-8")
            state, _, _ = update_state(content, state)
            prev_page_md = content
            print(f"[{i + 1}/{total}] cached  state={_state_brief(state)}", flush=True)
            continue

        print(
            f"[{i + 1}/{total}] rendering @ {dpi}dpi → LLM\n"
            f"    in-state: {_state_brief(state)}"
            f" | prev_len={len(prev_page_md) if prev_page_md else 0}",
            flush=True,
        )
        img = render_page_png(pdf_path, i, dpi=dpi)
        data = parse_page_via_llm(img, state, prev_page_md=prev_page_md)
        choice = data["choices"][0]
        content = (choice["message"].get("content") or "").strip()
        usage = data.get("usage", {})
        print(
            f"  ↳ finish={choice.get('finish_reason')} "
            f"tokens={usage.get('completion_tokens')}/{usage.get('total_tokens')}",
            flush=True,
        )

        if not content:
            reasoning = (choice["message"].get("reasoning") or "").strip()
            print(
                f"  ⚠ content 빈 응답. skip. "
                f"(reasoning_len={len(reasoning)}, state 유지)",
                flush=True,
            )
            continue

        cp.write_text(content, encoding="utf-8")
        prev_page_md = content

        new_state, changed, is_toc = update_state(content, state)
        if is_toc:
            print(f"  · ToC(목차) 페이지 판정 — state 유지", flush=True)
        elif not changed:
            print(f"  · heading 갱신 없음 — state 유지", flush=True)
        else:
            print(f"  · state → {_state_brief(new_state)}", flush=True)
        state = new_state

    # 캐시 → 최종 합본
    merge_cache_to_output(cache_dir, pages, out_path, pdf_path)


def merge_cache_to_output(
    cache_dir: Path, pages: list[int], out_path: Path, pdf_path: Path
) -> None:
    with out_path.open("w", encoding="utf-8") as f:
        f.write(f"# {pdf_path.stem} — LLM parsed\n")
        for i in pages:
            cp = page_cache_path(cache_dir, i)
            if not cp.exists():
                f.write(f"\n\n<!-- page {i + 1} : MISSING -->\n\n")
                continue
            f.write(f"\n\n<!-- page {i + 1} -->\n\n")
            f.write(cp.read_text(encoding="utf-8").strip())
    print(f"\n✓ merged: {out_path}")


if __name__ == "__main__":
    pdf_path = Path("data/회계_sample.pdf")
    out_path = Path("data/llm_parsed/회계_sample.md")
    cache_dir = Path("data/llm_parsed/pages")

    convert_pdf_to_md(
        pdf_path,
        out_path,
        cache_dir,
        dpi=250,
        force=True,  
    )
