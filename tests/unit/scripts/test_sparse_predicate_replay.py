"""scripts/sparse_predicate_replay.py 순수부 테스트 — 질의 토큰화·검색식 입력 빌더·후보 목록.

DB가 필요한 부분(실측 실행)은 스크립트에 내장된 특수문자 안전 점검·self-check와 실측 리포트로 검증하고,
여기서는 DB 없이 도는 순수 함수만 고정한다(test_rerank_replay와 동일 방침).
"""
import re

import pytest

from scripts.sparse_predicate_replay import (
    PREDICATES,
    build_or_input,
    build_or_prefix_input,
    tokenize,
)

pytestmark = pytest.mark.unit

# 후보②(or_prefix) 검색식의 안전한 형태: "'단어':*"를 |(OR)로 연결, 단어 안에 따옴표 없음.
# 이 형태를 벗어나지 않는 한 to_tsquery에서 SQL 문법 오류가 날 수 없다.
_SAFE_PREFIX_PATTERN = re.compile(r"^'[^']+':\*( \| '[^']+':\*)*$")


class TestTokenize:
    """tokenize() — 단어문자(한글·영숫자·밑줄) 연속만 토큰으로 남긴다"""

    def test_korean_query(self):
        assert tokenize("확정급여채무는 어떻게 인식하나요?") == ["확정급여채무는", "어떻게", "인식하나요"]

    def test_strips_tsquery_special_characters(self):
        # 따옴표·tsquery 연산자(& | ! : * 괄호)가 토큰에 남지 않는다 — 안전 조립의 전제
        assert tokenize("'; DROP TABLE chunks;-- & | ! ( ) :*") == ["DROP", "TABLE", "chunks"]

    def test_empty_or_punctuation_only_returns_empty(self):
        assert tokenize("") == []
        assert tokenize("??? !!! ...") == []


class TestBuildOrInput:
    """build_or_input() — 후보①: 단어들을 ' or '로 연결한 검색식 입력"""

    def test_joins_tokens_with_or(self):
        assert build_or_input("퇴직급여충당부채는 어떻게 인식하나요?") == "퇴직급여충당부채는 or 어떻게 or 인식하나요"

    def test_single_token_passes_through(self):
        assert build_or_input("퇴직연금운용자산") == "퇴직연금운용자산"

    def test_empty_returns_empty(self):
        assert build_or_input("???") == ""


class TestBuildOrPrefixInput:
    """build_or_prefix_input() — 후보②: 단어별 앞부분 일치("'단어':*")를 '|'로 연결한 검색식 입력"""

    def test_quoted_lexeme_prefix_shape(self):
        assert build_or_prefix_input("퇴직급여충당부채 인식") == "'퇴직급여충당부채':* | '인식':*"

    def test_arbitrary_special_input_is_always_safe_shape(self):
        # 어떤 악의적 입력이 와도 빈 문자열 또는 안전 형태만 나온다 — 문자열 이어붙이기 조립 금지 제약의 보장
        hostile = [
            "'; DROP TABLE chunks;--",
            "foo & bar | !baz:*",
            "(주)한국' OR '1'='1",
            "K-IFRS 제1019호",
            "   ",
        ]
        for q in hostile:
            built = build_or_prefix_input(q)
            assert built == "" or _SAFE_PREFIX_PATTERN.fullmatch(built), (q, built)

    def test_empty_returns_empty(self):
        assert build_or_prefix_input("") == ""


class TestPredicates:
    """PREDICATES — 비교 기준(현행 plainto) + 후보 3종의 목록"""

    def test_registry_keys(self):
        assert set(PREDICATES) == {"plainto", "or", "or_prefix", "websearch_control"}

    def test_plainto_is_current_baseline(self):
        # 현행 sparse_search와 동일: 원 질의를 그대로 plainto_tsquery에 바인딩
        spec = PREDICATES["plainto"]
        assert spec["tsquery"] == "plainto_tsquery('simple', %s)"
        assert spec["build_input"]("원 질의 그대로?") == "원 질의 그대로?"

    def test_candidates_never_assemble_raw_to_tsquery(self):
        # 문법 오류가 날 수 있는 to_tsquery를 쓰는 후보는 or_prefix뿐이고,
        # 그 입력은 안전 형태만 만드는 빌더 산출물로 한정된다
        for key, spec in PREDICATES.items():
            if spec["tsquery"].startswith("to_tsquery"):
                assert key == "or_prefix"
                assert spec["build_input"] is build_or_prefix_input
