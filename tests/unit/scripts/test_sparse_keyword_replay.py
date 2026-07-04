"""scripts/sparse_keyword_replay.py 순수부 테스트 — 불용어 제거·키워드 문자열·측정 arm 정의.

DB·LLM이 필요한 부분(키워드 추출·실측 실행)은 스크립트 내장 안전 점검·self-check와 실측 리포트로
검증하고, 여기서는 DB·LLM 없이 도는 순수 함수만 고정한다(test_sparse_predicate_replay와 동일 방침).
"""
import pytest

from scripts.sparse_keyword_replay import (
    ARMS,
    STOPWORDS,
    _arm_input_tokens,
    _kw_str,
    strip_stopwords,
)
from scripts.sparse_predicate_replay import PREDICATES

pytestmark = pytest.mark.unit


class _FakeCase:
    """ARMS의 input_fn이 참조하는 최소 케이스 — id와 query만 있으면 된다."""

    def __init__(self, case_id: str, query: str):
        self.id = case_id
        self.query = query


class TestStripStopwords:
    """strip_stopwords() — 불용어(일반어·의문사)만 걷어내고 나머지를 공백으로 잇는다.

    이 시스템의 토크나이저('simple')는 형태소 분석이 없어 조사가 붙은 채로 한 토큰이 된다.
    그래서 불용어 제거는 "때"·"및"처럼 홀로 선 일반어만 잡을 수 있고, "회사가"·"보유하고"처럼
    조사가 붙은 내용어는 잡지 못한다 — 이 천장을 그대로 드러내는 것이 이 대조군의 목적이다.
    """

    def test_removes_standalone_function_words(self):
        # "및"·"때"는 홀로 선 일반어라 제거되고, 시그널 명사는 남는다
        assert strip_stopwords("퇴직급여 및 인식 시점은 언제") == "퇴직급여 인식 시점은"

    def test_keeps_content_words_with_attached_josa(self):
        # "회사가"는 조사 부착 내용어라 불용어로 못 잡는다 — 형태소 천장의 실증
        assert "회사가" in strip_stopwords("회사가 자산을 보유")

    def test_empty_or_all_stopwords_returns_empty(self):
        assert strip_stopwords("") == ""
        assert strip_stopwords("무엇 및 또는") == ""


class TestKwStr:
    """_kw_str() — 케이스별 키워드 리스트를 검색식 입력용 공백 연결 문자열로 만든다"""

    def test_joins_keywords_with_space(self):
        kws = {"TEST-K-GAAP-001": ["퇴직급여충당부채", "인식"]}
        assert _kw_str(kws, "TEST-K-GAAP-001") == "퇴직급여충당부채 인식"

    def test_missing_case_returns_empty(self):
        # fixture에 없는 케이스는 빈 문자열 → sparse_search_predicate가 0건으로 처리
        assert _kw_str({}, "TEST-K-GAAP-999") == ""

    def test_empty_list_returns_empty(self):
        assert _kw_str({"c": []}, "c") == ""


class TestArms:
    """ARMS — 측정 arm 4종의 (술어, 입력 소스) 정의"""

    def test_registry_keys(self):
        assert set(ARMS) == {"plainto", "keyword_and", "keyword_or", "stopword_or"}

    def test_arms_reuse_existing_predicates(self):
        # 모든 arm은 1차에서 안전성이 실증된 술어(plainto/or)만 재사용한다 — 신규 raw 조립 없음
        for arm, (pred_key, _input_fn) in ARMS.items():
            assert pred_key in PREDICATES, arm
            assert pred_key in {"plainto", "or"}, arm

    def test_baseline_arm_is_current_behavior(self):
        # plainto arm = 원 질의 그대로 + plainto 술어 = 현행 sparse_search와 동일 (self-check 기준)
        pred_key, input_fn = ARMS["plainto"]
        assert pred_key == "plainto"
        assert input_fn(_FakeCase("c", "퇴직급여 인식은?"), {}) == "퇴직급여 인식은?"

    def test_keyword_arms_feed_keywords_not_query(self):
        # keyword_and/or arm의 입력은 원 질의가 아니라 fixture 키워드다
        kws = {"c": ["퇴직급여충당부채", "인식"]}
        case = _FakeCase("c", "회사가 퇴직급여를 어떻게 인식하나요?")
        for arm in ("keyword_and", "keyword_or"):
            _pred, input_fn = ARMS[arm]
            assert input_fn(case, kws) == "퇴직급여충당부채 인식"

    def test_keyword_and_uses_and_predicate_or_uses_or(self):
        assert ARMS["keyword_and"][0] == "plainto"  # plainto_tsquery = 전 단어 AND
        assert ARMS["keyword_or"][0] == "or"         # websearch_to_tsquery(or) = OR

    def test_stopword_arm_filters_query_and_uses_or(self):
        pred_key, input_fn = ARMS["stopword_or"]
        assert pred_key == "or"
        # 입력은 불용어를 걷어낸 원 질의
        assert input_fn(_FakeCase("c", "퇴직급여 및 인식"), {}) == "퇴직급여 인식"


class TestArmInputTokens:
    """_arm_input_tokens() — 정성 증거(어떤 토큰이 gold를 끌어올렸나)용 arm별 입력 토큰"""

    def test_keyword_arm_tokens_are_keywords(self):
        kws = {"c": ["퇴직급여충당부채", "인식"]}
        case = _FakeCase("c", "회사가 어떻게 인식하나요?")
        assert _arm_input_tokens("keyword_or", case, kws) == ["퇴직급여충당부채", "인식"]

    def test_plainto_arm_tokens_are_query_tokens(self):
        case = _FakeCase("c", "퇴직급여 인식은?")
        assert _arm_input_tokens("plainto", case, {}) == ["퇴직급여", "인식은"]
