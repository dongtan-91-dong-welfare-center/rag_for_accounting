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

    def test_h5_header_scoring_preserved(self):
        """
        ch12의 '##### 12.21~12.26'(실물 6건)은 현행 비앵커 정규식이 잡던 형태
        새 규칙이 놓치면 채점 회귀가 되므로 고정한다.
        """
        assert extract_chunk_paras("##### 12.21\n인식원칙의 예외...") == {"12.21"}


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


@pytest.mark.unit
class TestPrefixedParaScoring:
    """#255: 실·결·소 접두 문단을 gold·청크 양쪽에서 키의 일부로 보존한다.

    운영 DB 실측(2026-07-25, 1,507청크): 실(실무지침) 415·결(결론도출근거) 107·
    소(중소기업 특례) 6건의 H4 헤더가 실재한다. 접두를 벗기면 같은 장의 일반 문단과
    구분되지 않아(실2.11 → 2.11) 오탐 매칭이 생긴다.
    """

    def test_gold_preserves_practice_prefix(self):
        clauses = parse_gold_clauses(["일반기업회계기준 제2장 실2.11조"])
        assert clauses[0].chapter == "2"
        assert clauses[0].paras == {"실2.11"}

    def test_gold_conclusion_prefix_and_plain_mixed(self):
        clauses = parse_gold_clauses(["일반기업회계기준 제21장 21.13조, 결21.6조, 결21.7조"])
        assert clauses[0].paras == {"21.13", "결21.6", "결21.7"}

    def test_gold_prefixed_range_expansion(self):
        """'실2.46조~실2.47조' 범위는 접두를 유지한 채 끝점 포함으로 펼친다."""
        clauses = parse_gold_clauses(["일반기업회계기준 제2장 실2.46조~실2.47조"])
        assert clauses[0].paras == {"실2.46", "실2.47"}

    def test_prefixed_and_plain_do_not_cross_match(self):
        """실2.11 ≠ 2.11 — exact·prefix 어느 모드에서도 서로 매칭되지 않는다."""
        assert _paras_match({"실2.11"}, {"2.11"}, "exact") == set()
        assert _paras_match({"실2.11"}, {"2.11"}, "prefix") == set()
        assert _paras_match({"2.11"}, {"실2.11"}, "prefix") == set()

    def test_chunk_header_with_prefix_matches_gold(self):
        gold = gold_para_set(parse_gold_clauses(["일반기업회계기준 제12장 실12.1조"]))
        chunk = extract_chunk_paras("#### 실12.1\n주식기준보상거래에서...")
        assert _paras_match(gold, chunk, "exact") == {"실12.1"}

    def test_normalize_keeps_prefix_strips_branch(self):
        assert _normalize_para("실21.5의2") == "실21.5"


@pytest.mark.unit
class TestChunkIdUnionScoring:
    """#255: 추출을 content 헤더 ∪ chunk_id 유니언으로 확장한다.

    운영 DB 실측: 단일 조항 노드 435건은 번호가 content에 없고 chunk_id에만 있다
    (예: gaap-ch2-실2.11). content 정규식만 고치면 이들은 여전히 영구 miss다.
    """

    def test_extract_falls_back_to_chunk_id(self):
        """TEST-K-GAAP-011 실물 재현: 실2.11 청크는 content에 헤더가 전혀 없다."""
        body = "동일 또는 유사한 거래나 회계사건에서 발생한 차익, 차손 등은 총액으로 표시하지만..."
        assert extract_chunk_paras(body, "gaap-ch2-실2.11") == {"실2.11"}

    def test_rank_hit_accepts_content_id_pairs(self):
        items = [
            ("#### 2.10\n...", "gaap-ch2-회계정책"),
            ("동일 또는 유사한 거래나 회계사건에서...", "gaap-ch2-실2.11"),
        ]
        first, covered = rank_hit(items, {"실2.11"}, "exact")
        assert first == 2
        assert covered == {"실2.11"}

    def test_rank_hit_plain_strings_still_work(self):
        """재현 하니스(scripts/*_replay.py 7종)의 기존 호출 형태(list[str]) 하위호환."""
        first, _ = rank_hit(["#### 18.4\n..."], {"18.4"}, "exact")
        assert first == 1
