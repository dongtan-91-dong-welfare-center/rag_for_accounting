"""scripts/llm_parse.py 순수 로직 검증.

PyMuPDF와 LLM 서버 없이 확인할 수 있는 부분(state 추적, 프롬프트, 병합, 인자 처리)만 다룬다.
"""
import httpx
import pytest

from scripts import llm_parse as lp

pytestmark = pytest.mark.unit


def test_update_state_resets_lower_levels():
    s = lp._empty_state()
    md = "# 제6장 금융자산\n## 제1절 공통사항\n### 대손충당금\n#### 6.4의2\n##### (3)\n###### (가)\n"
    s, changed, is_toc = lp.update_state(md, s)
    assert changed and not is_toc
    assert (s["jang"], s["last_article"], s["last_item"], s["last_ho"]) == ("제6장 금융자산", "6.4의2", "(3)", "(가)")
    s, _, _ = lp.update_state("## 제2절 측정\n", s)
    assert s["jeol"] == "제2절 측정" and s["sojemok"] is None and s["last_article"] is None
    assert s["jang"] == "제6장 금융자산"


def test_update_state_ignores_non_matching_headings():
    s, changed, _ = lp.update_state("#### 본문 제목\n", lp._empty_state())
    assert not changed and s == lp._empty_state()


def test_toc_page_keeps_state():
    md = "## 제1절 가\n## 제2절 나\n## 제3절 다\n"
    prev = {**lp._empty_state(), "jang": "제1장"}
    s, changed, is_toc = lp.update_state(md, prev)
    assert is_toc and not changed and s == prev


def test_build_page_prompt_injects_state_and_prev_page():
    state = {**lp._empty_state(), "jang": "제6장", "last_article": "6.1"}
    prompt = lp.build_page_prompt(state, "이전 본문")
    assert "제6장" in prompt and "6.1" in prompt and "이전 본문" in prompt
    assert "(아직 확인되지 않음)" in prompt
    assert "직전 페이지 markdown" not in lp.build_page_prompt(state)


def test_parse_page_range():
    assert lp.parse_page_range(None, 3) == [0, 1, 2]
    assert lp.parse_page_range("1-2,5", 5) == [0, 1, 4]
    with pytest.raises(ValueError):
        lp.parse_page_range("4", 3)


def test_merge_cache_marks_pages_and_missing(tmp_path):
    cache = tmp_path / "pages"
    cache.mkdir()
    lp.page_cache_path(cache, 0).write_text("본문1\n", encoding="utf-8")
    out = tmp_path / "out.md"
    lp.merge_cache_to_output(cache, [0, 1], out, tmp_path / "기준서.pdf")
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# 기준서 — LLM parsed")
    assert "<!-- page 1 -->\n\n본문1" in text
    assert "<!-- page 2 : MISSING -->" in text


def test_page_cache_path_is_one_based():
    assert lp.page_cache_path(lp.Path("c"), 0).name == "page_001.md"


def test_parse_page_via_llm_uses_configured_endpoint(monkeypatch):
    seen = {}

    class R:
        def raise_for_status(self): ...
        def json(self): return {"choices": []}

    def fake_post(url, json, timeout):
        seen.update(url=url, model=json["model"])
        return R()

    monkeypatch.setattr(httpx, "post", fake_post)
    lp.parse_page_via_llm(b"x", lp._empty_state(), base_url="http://h:1/v1", model="m")
    assert seen == {"url": "http://h:1/v1/chat/completions", "model": "m"}


def test_arg_parser_defaults():
    a = lp.build_arg_parser().parse_args(["a.pdf"])
    assert a.base_url == lp.DEFAULT_BASE_URL and a.model == lp.DEFAULT_MODEL and not a.force
