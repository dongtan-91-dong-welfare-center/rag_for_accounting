"""
조항 문단번호 추출 공용 모듈 단위 테스트

대상: src/utils/clause_paras.py
  - clause_header_re() : 문단 헤더 정규식 빌더(레벨 범위·접두 allowlist 파라미터)
  - content_paras()    : 청크 본문의 문단 헤더 → 번호 목록(등장 순서, 원형 보존)
  - node_id_para()     : chunk_id 꼬리 토큰 → 문단번호 (예: "gaap-ch2-실2.11" → "실2.11")
  - chunk_paras()      : content ∪ chunk_id 유니언

표본은 2026-07-25 운영 DB(chunks 1,507건·33장) 전수조사에서 실측한 실물 형태를 쓴다.
접두 allowlist(실=실무지침, 결=결론도출근거, 소=중소기업 특례)와 헤딩 레벨(H4 정규, H5는 ch12의 12.21~12.26 6건)이 그 조사 결과다.
열린 한글 패턴([가-힣]+)을 쓰지 않는 이유는 "사례"·"부록" 같은 비조항 제목이 오탐으로 섞이는 것을 구조적으로 막기 위해서다.
"""
import pytest

from src.utils.clause_paras import (
    chunk_paras,
    clause_header_re,
    content_paras,
    node_id_para,
)


@pytest.mark.unit
class TestContentParas:
    """content_paras() — 본문 헤더에서 문단번호를 등장 순서·원형 그대로 뽑는다"""

    def test_h4_plain_numbers_in_order(self):
        content = "#### 6.13\n금융자산은 …\n#### 6.14\n| 구분 | 측정기준 |\n#### 6.15\n…"
        assert content_paras(content) == ["6.13", "6.14", "6.15"]

    def test_branch_suffix_preserved_verbatim(self):
        """가지번호(의N)는 원형 보존 — 합치기(6.13의2→6.13)는 소비자(채점기)의 몫이다.

        화면은 '6.13의2'를 그대로 보여야 회계사가 그 조항을 찾을 수 있다.
        """
        assert content_paras("#### 21.5의2\n…\n#### 11.31의2\n…") == ["21.5의2", "11.31의2"]

    def test_practice_prefix_recognized(self):
        """실무지침 문단(실N.M) 인식 — #255의 발단. 운영 DB에 H4 실물 415건."""
        assert content_paras("#### 실12.1\n…\n#### 실12.10\n…") == ["실12.1", "실12.10"]

    def test_conclusion_and_sme_prefixes_recognized(self):
        """결(결론도출근거)·소(중소기업 특례) 접두 — 운영 DB에 각 107건·6건."""
        assert content_paras("#### 결21.6\n…\n#### 소21.1\n…") == ["결21.6", "소21.1"]

    def test_h5_header_recognized(self):
        """H5 문단(ch12의 ##### 12.21~12.26 실물 6건) — 현행 채점기가 비앵커 매칭으로
        잡고 있던 것이라, 새 규칙이 놓치면 채점 회귀가 된다."""
        assert content_paras("##### 12.21\n인식원칙의 예외 …") == ["12.21"]

    def test_h3_header_recognized(self):
        """H3 형태(### 실2.11) — 현행 청크 정본에는 H3이 0건이지만, 빌더가 레벨을 바꿔도 추출이 깨지지 않게 포함한다."""
        assert content_paras("### 실2.11\n…") == ["실2.11"]

    def test_h6_and_body_mentions_not_matched(self):
        """H6 제목과 본문 중간 언급은 문단 헤더가 아니다 — 잡으면 오탐."""
        assert content_paras("###### 미주 12.1\n본문에 결21.15 또는 실15.5를 인용") == []

    def test_unknown_prefix_not_matched(self):
        """allowlist 밖 한글 접두는 미매칭 — 열린 패턴 오탐 차단이 설계 의도다."""
        assert content_paras("#### 부록2.1\n…") == []

    def test_duplicates_removed_order_kept(self):
        assert content_paras("#### 6.13\n…\n#### 6.14\n…\n#### 6.13\n…") == ["6.13", "6.14"]

    def test_three_level_number(self):
        assert content_paras("#### 2.6.5\n…") == ["2.6.5"]


@pytest.mark.unit
class TestNodeIdPara:
    """
    node_id_para() — 단일 조항 노드는 번호가 content에 없고 chunk_id에만 있다.

    운영 DB 실측: 이런 청크가 435건이고, 실2.11(TEST-K-GAAP-011의 '상계' 조항)이 정확히 이 형태다.
    content 정규식만 고쳐서는 영구 miss로 남는다.
    """

    def test_single_clause_node_ids(self):
        assert node_id_para("gaap-ch2-실2.11") == "실2.11"
        assert node_id_para("gaap-ch3-결3.2") == "결3.2"
        assert node_id_para("gaap-ch22-실22.17") == "실22.17"

    def test_plain_number_tail(self):
        assert node_id_para("gaap-ch6-6.13") == "6.13"

    def test_split_suffix_stripped(self):
        """토큰 상한 분할 뒷조각(-N 접미사)은 벗겨내고 판정한다."""
        assert node_id_para("gaap-ch2-실2.11-2") == "실2.11"

    def test_non_clause_tails_are_none(self):
        assert node_id_para("gaap-ch6-s1-최초인식") is None
        assert node_id_para("gaap-ch6-s1-최초인식-2") is None
        assert node_id_para("gaap-ch10-용어의_정의-원가") is None
        assert node_id_para("gaap-ch29-사례_4._재고자산평가손실") is None
        assert node_id_para("gaap-ch12") is None
        assert node_id_para("") is None


@pytest.mark.unit
class TestChunkParas:
    """chunk_paras() — content 헤더 ∪ chunk_id 유니언(중복 제거)"""

    def test_bundle_chunk_uses_content_headers(self):
        assert chunk_paras("#### 6.13\n…\n#### 6.14\n…", "gaap-ch6-s1-최초인식") == ["6.13", "6.14"]

    def test_single_clause_chunk_falls_back_to_id(self):
        """실2.11 실물 재현: content에 헤더가 전혀 없어도 chunk_id에서 번호가 나온다."""
        body = "동일 또는 유사한 거래나 회계사건에서 발생한 차익, 차손 등은 총액으로 표시하지만 …"
        assert chunk_paras(body, "gaap-ch2-실2.11") == ["실2.11"]

    def test_id_para_not_duplicated(self):
        assert chunk_paras("#### 실2.11\n…", "gaap-ch2-실2.11") == ["실2.11"]

    def test_no_number_anywhere(self):
        assert chunk_paras("합리적인 판단력과 거래의사가 있는 …", "gaap-ch10-용어의_정의-공정가치") == []


@pytest.mark.unit
class TestClauseHeaderReBuilder:
    """
    clause_header_re() — 소비자별 변형을 한 곳에서 생성한다(사본 0).

    chunker는 분할 경계로 현행 의미(H4·숫자 전용)를 고정해 소비한다.
    경계를 넓히면 다음 재적재부터 청크 구성이 달라져 검색 회귀·벤치마크 플로어 재시드가 필요해진다.
    """

    def test_chunker_variant_h4_numeric_only(self):
        """levels=(4,4)·prefixes=() 변형은 실·결·소와 H5를 경계로 잡지 않는다."""
        rx = clause_header_re(levels=(4, 4), prefixes=())
        text = "#### 2.10\n…\n#### 실2.11\n…\n##### 12.21\n…"
        assert [m.group(1) for m in rx.finditer(text)] == ["2.10"]

    def test_default_variant_is_extraction_spec(self):
        rx = clause_header_re()
        text = "### 실2.11\n#### 결21.6\n##### 12.21\n###### 각주"
        assert [m.group(1) for m in rx.finditer(text)] == ["실2.11", "결21.6", "12.21"]
