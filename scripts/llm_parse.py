"""정본 마크다운(`data/llm_parsed/*.md`) 생성기: PDF를 비전 LLM으로 페이지별 변환한다.

동작 순서는 다음과 같다.

1. PDF를 페이지별 PNG로 렌더한다(PyMuPDF).
2. OpenAI 호환 비전 LLM 서버에 이미지와 프롬프트를 보내 마크다운으로 변환한다.
3. 페이지별 결과를 캐시 디렉터리(`pages/`)에 저장한다. 이미 있으면 재사용한다.
4. 페이지 마커(`<!-- page N -->`)를 끼워 한 파일로 병합한다.

산출물 구조의 규칙은 `docs/guides/document_parsing_guide.md`가 정의한다.
코퍼스를 만들 때 한 번 실행하는 도구이므로 운영 경로에서는 임포트하지 않는다.
PyMuPDF는 `ingest` 옵션 그룹에 있으므로 `uv sync --extra ingest`가 필요하다.

사용 예:
    uv run python scripts/llm_parse.py data/회계_sample.pdf --pages 1-10
"""
from __future__ import annotations

import argparse
import base64
import re
from pathlib import Path

import httpx

DEFAULT_BASE_URL = "http://localhost:8000/v1"
# 정본 생성에 사용한 모델명이다. 모델을 바꾸면 파싱 가이드의 기록도 함께 갱신한다.
DEFAULT_MODEL = "qwen3.6-35b"
DEFAULT_DPI = 250
DEFAULT_OUT_DIR = Path("data/llm_parsed")


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


def render_page_png(pdf_path: Path, page_index: int, dpi: int = DEFAULT_DPI) -> bytes:
    """PDF의 특정 페이지를 PNG bytes로 렌더링한다."""
    import fitz  # PyMuPDF: 코퍼스 생성 전용 의존성이라 호출 시점에 임포트한다.

    with fitz.open(pdf_path) as doc:
        pix = doc[page_index].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
        return pix.tobytes("png")


def count_pdf_pages(pdf_path: Path) -> int:
    import fitz

    with fitz.open(pdf_path) as doc:
        return len(doc)


def parse_page_via_llm(
    image_bytes: bytes,
    state: dict,
    prev_page_md: str | None = None,
    *,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 8192,
) -> dict:
    """페이지 PNG를 비전 LLM에 넘겨 chat completion 응답을 받는다."""
    b64 = base64.b64encode(image_bytes).decode()
    resp = httpx.post(
        f"{base_url}/chat/completions",
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        {"type": "text", "text": build_page_prompt(state, prev_page_md)},
                    ],
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
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




def _apply_heading(state: dict, level: int, title: str) -> bool:
    """heading 한 줄을 state에 반영하고 갱신 여부를 돌려준다. 상위가 바뀌면 하위는 리셋한다."""
    if level == 1 and _JANG_PAT.search(title):
        state.update(jang=title, jeol=None, sojemok=None, last_article=None, last_item=None, last_ho=None)
    elif level == 2 and _JEOL_PAT.search(title):
        state.update(jeol=title, sojemok=None, last_article=None, last_item=None, last_ho=None)
    elif level == 3 and not _SOJEMOK_EXCLUDE.search(title):
        state.update(sojemok=title, last_article=None, last_item=None, last_ho=None)
    elif level == 4 and (am := _ARTICLE_PAT.match(title)):
        state.update(last_article=am.group(1), last_item=None, last_ho=None)
    elif level == 5 and (im := _ITEM_PAT.match(title)):
        state.update(last_item=f"({im.group(1)})", last_ho=None)
    elif level == 6 and (hm := _HO_PAT.match(title)):
        state["last_ho"] = f"({hm.group(1)})"
    else:
        return False
    return True


def update_state(md_text: str, state: dict) -> tuple[dict, bool, bool]:
    """페이지 md를 순서대로 훑으며 6단계 state를 갱신한다.

    장(#), 절(##), 소제목(###), 조(####), 항(#####), 호(######) 순이며
    상위 단계가 바뀌면 하위 단계는 모두 초기화한다.

    Returns:
        (new_state, changed, is_toc)
    """
    if is_toc_page(md_text):
        return dict(state), False, True

    new_state = dict(state)
    changed = False
    for m in _HEADING_LINE_RE.finditer(md_text):
        if _apply_heading(new_state, len(m.group(1)), m.group(2).strip()):
            changed = True
    return new_state, changed, False


def page_cache_path(cache_dir: Path, page_idx: int) -> Path:
    return cache_dir / f"page_{page_idx + 1:03d}.md"


def parse_page_range(spec: str | None, total: int) -> list[int]:
    """1부터 시작하는 페이지 지정('3', '1-10', '1-3,7')을 0부터 시작하는 인덱스 목록으로 바꾼다."""
    if not spec:
        return list(range(total))
    pages: list[int] = []
    for part in spec.split(","):
        lo, _, hi = part.strip().partition("-")
        start, end = int(lo), int(hi or lo)
        if start < 1 or end < start or end > total:
            raise ValueError(f"페이지 범위가 올바르지 않습니다: {part!r} (전체 {total}쪽)")
        pages.extend(range(start - 1, end))
    return pages


def merge_cache_to_output(cache_dir: Path, pages: list[int], out_path: Path, pdf_path: Path) -> None:
    """캐시된 페이지를 마커로 구분해 한 파일로 병합한다. 캐시가 없는 페이지는 MISSING으로 표시한다."""
    with out_path.open("w", encoding="utf-8") as f:
        f.write(f"# {pdf_path.stem} — LLM parsed\n")
        for i in pages:
            cp = page_cache_path(cache_dir, i)
            if not cp.exists():
                f.write(f"\n\n<!-- page {i + 1} : MISSING -->\n\n")
                continue
            f.write(f"\n\n<!-- page {i + 1} -->\n\n")
            f.write(cp.read_text(encoding="utf-8").strip())
    print(f"\n병합 완료: {out_path}")


def convert_pdf_to_md(
    pdf_path: Path,
    out_path: Path,
    cache_dir: Path,
    page_range: list[int] | None = None,
    dpi: int = DEFAULT_DPI,
    force: bool = False,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
) -> None:
    """PDF를 페이지별로 LLM 변환하고 캐시에 저장한 뒤 하나의 md 파일로 병합한다."""
    total = count_pdf_pages(pdf_path)
    pages = page_range if page_range is not None else list(range(total))

    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    state: dict = _empty_state()
    prev_page_md: str | None = None

    for i in pages:
        cp = page_cache_path(cache_dir, i)
        if cp.exists() and not force:
            prev_page_md = cp.read_text(encoding="utf-8")
            state, _, _ = update_state(prev_page_md, state)
            print(f"[{i + 1}/{total}] cached  state={_state_brief(state)}", flush=True)
            continue

        print(f"[{i + 1}/{total}] {dpi}dpi 렌더 후 LLM 호출, 입력 state: {_state_brief(state)}", flush=True)
        data = parse_page_via_llm(
            render_page_png(pdf_path, i, dpi=dpi), state, prev_page_md, base_url=base_url, model=model
        )
        choice = data["choices"][0]
        content = (choice["message"].get("content") or "").strip()
        if not content:
            print("  경고: 빈 응답이라 건너뜁니다(state 유지).", flush=True)
            continue

        cp.write_text(content, encoding="utf-8")
        prev_page_md = content
        state, _, is_toc = update_state(content, state)
        if is_toc:
            print("  목차 페이지로 판정해 state를 유지합니다.", flush=True)

    merge_cache_to_output(cache_dir, pages, out_path, pdf_path)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PDF를 비전 LLM으로 변환해 정본 마크다운(data/llm_parsed)을 생성한다.")
    p.add_argument("pdf", type=Path, help="입력 PDF 경로")
    p.add_argument("--out", type=Path, help="출력 md 경로(기본: data/llm_parsed/<PDF 이름>.md)")
    p.add_argument("--cache-dir", type=Path, help="페이지 캐시 경로(기본: data/llm_parsed/pages/<PDF 이름>)")
    p.add_argument("--pages", help="변환할 페이지(1부터). 예: 3, 1-10, 1-3,7 (기본: 전체)")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI 호환 서버 주소")
    p.add_argument("--model", default=DEFAULT_MODEL, help="비전 LLM 모델명")
    p.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    p.add_argument("--force", action="store_true", help="캐시를 무시하고 다시 변환")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    stem = args.pdf.stem
    out_path = args.out or DEFAULT_OUT_DIR / f"{stem}.md"
    cache_dir = args.cache_dir or DEFAULT_OUT_DIR / "pages" / stem
    page_range = parse_page_range(args.pages, count_pdf_pages(args.pdf)) if args.pages else None
    convert_pdf_to_md(
        args.pdf, out_path, cache_dir, page_range,
        dpi=args.dpi, force=args.force, base_url=args.base_url, model=args.model,
    )


if __name__ == "__main__":
    main()
