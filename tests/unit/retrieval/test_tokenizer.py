"""
형태소 토크나이저 단위 테스트 — 색인·질의가 공유하는 순수 함수의 계약 고정.

이 토크나이저의 존재 이유는 sparse 검색이 문장형 질의에서 0건을 반환하던 문제다
(to_tsvector('simple', …)가 조사를 못 떼어 "퇴직급여를"이 본문의 "퇴직급여"와 매칭 실패).
그래서 여기서 고정할 계약은 두 가지다:
  ① 조사·어미가 실제로 떨어지는가 (그래야 매칭이 산다)
  ② 화이트리스트별 차이가 의도대로 나는가 (ts_rank_cd에 IDF가 없어 노이즈 필터가 이것뿐)
"""
import pytest

from src.utils.config import MORPH_POS_TAGS_CORE, MORPH_POS_TAGS_WIDE

# kiwipiepy는 dev 의존성 그룹에 있다(운영 이미지는 --no-dev 슬림 빌드라 빠진다). 미설치 환경에서는 건너뛴다.
pytest.importorskip("kiwipiepy", reason="kiwipiepy 미설치 — uv sync(dev 그룹 포함 기본값)로 설치")

from src.retrieval.tokenizer import morph_text, tokenize_morph  # noqa: E402

# 실측에서 인용된 질의 — 조사(은/JX)·어미(나요/EF)·파생접미사가 모두 들어 있어 화이트리스트 차이를 한 문장으로 드러낸다.
SAMPLE = "대손충당금 환입액은 어떻게 회계처리하나요?"


@pytest.mark.unit
class TestTokenizeMorph:
    """품사 필터의 계약 — 무엇이 남고 무엇이 떨어지는가."""

    def test_particles_and_endings_removed(self):
        """조사·어미는 명사류 화이트리스트에서 제거된다 — 매칭 실패의 직접 원인이었다"""
        tokens = tokenize_morph(SAMPLE, MORPH_POS_TAGS_CORE)

        assert "은" not in tokens      # JX 보조사
        assert "나요" not in tokens    # EF 종결어미
        assert "어떻게" not in tokens  # MAG 부사

    def test_content_nouns_preserved(self):
        """복합어를 쪼갠 명사 조각은 남는다 — 이 조각들이 본문과의 매칭을 만든다"""
        tokens = tokenize_morph(SAMPLE, MORPH_POS_TAGS_CORE)

        for expected in ("대손", "충당금", "회계", "처리"):
            assert expected in tokens

    def test_wide_includes_stem_tags_core_excludes(self):
        """CORE↔WIDE 차이 — 어근(XR) 계열이 WIDE에서만 남는다.

        "환입액"은 환/XR + 입/NNG + 액/NNG으로 쪼개져, CORE는 "환"을 버린다.
        과분할 복합어의 신호를 어디까지 살릴지가 결과를 좌우하므로 실측 축으로 둔 차이다.
        """
        core = tokenize_morph(SAMPLE, MORPH_POS_TAGS_CORE)
        wide = tokenize_morph(SAMPLE, MORPH_POS_TAGS_WIDE)

        assert set(core) <= set(wide)      # WIDE는 CORE의 확장이다
        assert "환" in wide
        assert "환" not in core

    def test_no_tags_keeps_everything(self):
        """tags=None은 조사·어미까지 전부 남긴다 — IDF가 있는 오프라인 BM25용 경로"""
        unfiltered = tokenize_morph(SAMPLE, None)

        assert "은" in unfiltered
        assert len(unfiltered) > len(tokenize_morph(SAMPLE, MORPH_POS_TAGS_CORE))

    def test_single_character_tokens_kept(self):
        """1글자 형태소를 버리지 않는다 — 과분할 복합어의 신호를 지운다"""
        tokens = tokenize_morph(SAMPLE, MORPH_POS_TAGS_WIDE)

        assert [t for t in tokens if len(t) == 1]   # "환"·"입"·"액" 등이 남아 있어야 한다

    def test_empty_query_yields_no_tokens(self):
        """명사류가 없는 질의는 빈 리스트 — 호출자가 검색을 건너뛰는 신호다"""
        assert tokenize_morph("???", MORPH_POS_TAGS_CORE) == []


@pytest.mark.unit
class TestMorphText:
    """to_tsvector/plainto_tsquery('simple', …)에 넣을 문자열 형식."""

    def test_joins_tokens_with_space(self):
        """공백 결합 — 'simple' 설정이 이 공백을 토큰 경계로 받아 형태소 단위 매칭이 성립한다"""
        text = morph_text(SAMPLE, MORPH_POS_TAGS_CORE)

        assert text.split(" ") == tokenize_morph(SAMPLE, MORPH_POS_TAGS_CORE)

    def test_empty_when_no_tokens(self):
        """토큰이 없으면 빈 문자열 — 빈 tsquery로 질의하지 않도록 호출자가 분기한다"""
        assert morph_text("???", MORPH_POS_TAGS_CORE) == ""

    def test_index_and_query_share_the_same_function(self):
        """같은 입력·같은 tags면 항상 같은 출력 — 색인 토큰과 질의 토큰이 어긋나지 않는 근거"""
        assert morph_text(SAMPLE, MORPH_POS_TAGS_CORE) == morph_text(SAMPLE, MORPH_POS_TAGS_CORE)
