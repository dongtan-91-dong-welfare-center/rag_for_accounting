"""
조항번호 정규화·매칭 단위 테스트

대상: tests/utils/benchmark_metrics.py 의 조항키 정규화/추출/매칭 로직
  - _normalize_para()      : 가지번호(의N) 접미사 제거
  - _expand_range()        : 'N.a'~'N.b' 동일 prefix 연속 범위 펼침
  - parse_gold_clauses()   : gold 라벨('제N장 N.M조') → (chapter, 문단집합), K-IFRS 제외
  - gold_para_set()        : gold 문단 정규화 집합
  - extract_chunk_paras()  : 청크 본문('#### N.M') → 정규화 문단집합
  - _paras_match()         : exact/prefix 매칭
  - rank_hit()             : 순위별 첫 hit·커버리지

핵심 계약: gold 표기('제18장 18.7조')와 청크 헤더 표기('#### 18.7')가 동일한 정규형 문단키로 변환돼 매칭된다.
"""
import pytest

from tests.utils.benchmark_metrics import (
    _expand_range,
    _normalize_para,
    _paras_match,
    extract_chunk_paras,
    gold_para_set,
    parse_gold_clauses,
    rank_hit,
)


@pytest.mark.unit
class TestNormalizePara:
    """_normalize_para() — 가지번호(의N) 정규화"""

    def test_plain_two_level(self):
        assert _normalize_para("21.8") == "21.8"
        assert _normalize_para("2.65") == "2.65"

    def test_strips_branch_suffix(self):
        """'N.M의K'의 가지번호 접미사를 제거한다"""
        assert _normalize_para("21.5의2") == "21.5"
        assert _normalize_para("6.13의2") == "6.13"

    def test_three_level_preserved(self):
        """3단계 표기는 보존하고 접미사만 제거한다"""
        assert _normalize_para("2.6.5") == "2.6.5"
        assert _normalize_para("2.6.5의3") == "2.6.5"


@pytest.mark.unit
class TestExpandRange:
    """_expand_range() — 동일 prefix 연속 범위 펼침"""

    def test_same_prefix_range(self):
        assert _expand_range("15.15", "15.16") == {"15.15", "15.16"}
        assert _expand_range("18.4", "18.7") == {"18.4", "18.5", "18.6", "18.7"}

    def test_different_prefix_no_expand(self):
        """prefix(장)가 다르면 펼치지 않고 끝점만 반환한다"""
        assert _expand_range("15.16", "16.1") == {"15.16", "16.1"}


@pytest.mark.unit
class TestParseGoldClauses:
    """parse_gold_clauses() — gold 라벨 파싱 + K-IFRS 제외"""

    def test_single_clause(self):
        clauses = parse_gold_clauses(["일반기업회계기준 제18장 18.4조"])
        assert len(clauses) == 1
        assert clauses[0].chapter == "18"
        assert clauses[0].paras == {"18.4"}

    def test_multi_clause(self):
        clauses = parse_gold_clauses(["일반기업회계기준 제21장 21.8조, 21.9조, 21.10조"])
        assert clauses[0].chapter == "21"
        assert clauses[0].paras == {"21.8", "21.9", "21.10"}

    def test_jeol_suffix(self):
        """'절' 접미사도 '조'와 동일하게 문단 토큰을 추출한다"""
        clauses = parse_gold_clauses(["일반기업회계기준 제2장 2.65절"])
        assert clauses[0].chapter == "2"
        assert clauses[0].paras == {"2.65"}

    def test_kifrs_excluded(self):
        """K-IFRS 라벨은 채점 대상에서 제외한다(적재 데이터가 GAAP뿐)"""
        assert parse_gold_clauses(["K-IFRS 제1007호 20절"]) == []

    def test_mixed_keeps_only_gaap(self):
        clauses = parse_gold_clauses([
            "일반기업회계기준 제6장 6.29조, 6.31조",
            "K-IFRS 제1109호 5.7절",
        ])
        assert len(clauses) == 1
        assert clauses[0].paras == {"6.29", "6.31"}

    def test_range_expansion(self):
        """'N.a조~N.b조' 범위는 끝점 포함으로 펼쳐 파싱한다"""
        clauses = parse_gold_clauses(["일반기업회계기준 제15장 15.15조~15.16조"])
        assert clauses[0].paras == {"15.15", "15.16"}

    def test_gold_para_set_normalized(self):
        clauses = parse_gold_clauses(["일반기업회계기준 제15장 15.18조, 15.20조"])
        assert gold_para_set(clauses) == {"15.18", "15.20"}


@pytest.mark.unit
class TestExtractChunkParas:
    """extract_chunk_paras() — 청크 '#### N.M' 헤더 추출"""

    def test_single_header(self):
        assert extract_chunk_paras("#### 18.7\n특정차입금에 대한 차입원가...") == {"18.7"}

    def test_multiple_headers(self):
        content = "#### 6.29\n만기보유증권...\n#### 6.31\n매도가능증권..."
        assert extract_chunk_paras(content) == {"6.29", "6.31"}

    def test_branch_suffix_header(self):
        assert extract_chunk_paras("#### 6.13의2\n내재파생...") == {"6.13"}

    def test_inline_non_header_ignored(self):
        """'결21.15'·'실15.5'처럼 #### 헤더가 아닌 인라인 표기는 추출하지 않는다"""
        assert extract_chunk_paras("본문에 결21.15 또는 실15.5를 인용") == set()


@pytest.mark.unit
class TestParasMatch:
    """_paras_match() — exact/prefix 매칭"""

    def test_exact_hit(self):
        assert _paras_match({"18.4"}, {"18.4", "18.5"}, "exact") == {"18.4"}

    def test_exact_miss_wrong_para(self):
        """같은 장의 다른 문단은 exact에서 불일치 (오라벨 검출의 근거)"""
        assert _paras_match({"18.4"}, {"18.7"}, "exact") == set()

    def test_prefix_hierarchical(self):
        """gold '2.6.5' ↔ 청크 '2.6' 계층 포함을 prefix로 인정"""
        assert _paras_match({"2.6.5"}, {"2.6"}, "prefix") == {"2.6.5"}

    def test_prefix_equal(self):
        assert _paras_match({"21.8"}, {"21.8"}, "prefix") == {"21.8"}


@pytest.mark.unit
class TestCrossFormatEquivalence:
    """#163 핵심 계약: gold 표기와 청크 헤더 표기가 동일 정규키로 매칭된다"""

    def test_gold_label_matches_chunk_header(self):
        gold = gold_para_set(parse_gold_clauses(["일반기업회계기준 제18장 18.4조"]))
        chunk = extract_chunk_paras("#### 18.4\n차입원가는 기간비용으로 처리함을 원칙으로 한다...")
        assert _paras_match(gold, chunk, "exact") == {"18.4"}

    def test_mislabel_does_not_match(self):
        """교정 전 오라벨(18.7)은 정답 청크(18.4)와 매칭되지 않음을 회귀로 고정"""
        gold_wrong = gold_para_set(parse_gold_clauses(["일반기업회계기준 제18장 18.7조"]))
        chunk = extract_chunk_paras("#### 18.4\n차입원가는 기간비용으로 처리함을 원칙으로 한다...")
        assert _paras_match(gold_wrong, chunk, "exact") == set()


@pytest.mark.unit
class TestRankHit:
    """rank_hit() — 순위별 첫 hit·누적 커버리지"""

    def test_first_hit_rank_and_coverage(self):
        contents = ["#### 6.27\n...", "#### 6.29\n...", "#### 6.31\n..."]
        first, covered = rank_hit(contents, {"6.29", "6.31"}, "exact")
        assert first == 2
        assert covered == {"6.29", "6.31"}

    def test_no_hit(self):
        first, covered = rank_hit(["#### 10.1\n...", "#### 10.2\n..."], {"21.8"}, "exact")
        assert first is None
        assert covered == set()

    def test_empty_gold(self):
        first, covered = rank_hit(["#### 1.1\n..."], set(), "exact")
        assert first is None
        assert covered == set()
