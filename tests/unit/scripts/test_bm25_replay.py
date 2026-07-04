"""
scripts/bm25_replay.py 순수부 테스트 — 토크나이저 3종·BM25 오프라인 스코어러.

DB·코퍼스 적재가 필요한 실측 실행부는 스크립트 내장 self-check와 실측 리포트로 검증하고,
여기서는 DB 없이 도는 순수 함수·클래스만 고정한다(test_sparse_*_replay와 동일 방침).
kiwipiepy 형태소 분석은 로컬 모델 로드만 필요하므로 단위 테스트에 포함한다.
"""
import pytest

from scripts.bm25_replay import (
    Bm25Index,
    TOKENIZERS,
    _bm25_sparse,
    _passes_filter,
    tokenize_morph,
    tokenize_ngram,
)
from src.models.schemas import RetrievedChunk

pytestmark = pytest.mark.unit


def _chunk(chunk_id: str, content: str, standard_type: str) -> RetrievedChunk:
    """BM25 arm은 content로 검색하고 standard_type으로 필터한다."""
    return RetrievedChunk(
        chunk_id=chunk_id, document_id="doc", content=content, score=0.0,
        metadata={"standard_type": standard_type},
    )


class TestTokenizeNgram:
    """단어별 문자 3-gram. 단어 내 부분일치를 만들어 형태소 미지원 한계를 우회한다."""

    def test_long_word_split_into_char_ngrams(self):
        # 4글자 "외화환산" → 3-gram 2개 (외화환, 화환산)
        assert tokenize_ngram("외화환산") == ["외화환", "화환산"]

    def test_short_word_kept_whole(self):
        # n(3)보다 짧은 단어는 쪼갤 수 없어 통째로 한 토큰
        assert tokenize_ngram("인식") == ["인식"]

    def test_query_and_corpus_share_ngrams(self):
        # 질의 "외화환산손익"과 청크 "외화환산"이 3-gram을 공유 → 부분일치 성립(현행 simple은 불가)
        assert set(tokenize_ngram("외화환산손익")) & set(tokenize_ngram("외화환산"))


class TestTokenizeMorph:
    """복합어를 쪼개 정답 조항 표현과 매칭시킨다."""

    def test_splits_compound_noun(self):
        # 현행 'simple'은 "외화환산손익"이 한 덩어리라 청크의 "외화환산"과 매칭 불가(#81).
        # 형태소는 이를 쪼개 매칭 가능하게 만든다 — 이 트랙이 토큰화를 1급 축으로 올린 이유.
        assert tokenize_morph("외화환산손익") == ["외화", "환산", "손익"]

    def test_single_term_unchanged(self):
        assert tokenize_morph("상계") == ["상계"]


class TestBm25Index:
    """ts_rank_cd에 없는 IDF로 흔한 단어를 감쇠한다."""

    def test_idf_downweights_common_term(self):
        # "손익"은 전 문서 공통(IDF↓), "상계"는 1문서만(IDF↑) → 상계 든 문서가 1위.
        # ts_rank_cd라면 흔한 "손익"이 순위를 지배해 이 변별이 안 된다(#211 병목).
        docs = ["손익 상계", "손익 인식", "손익 평가", "손익 측정"]
        idx = Bm25Index(docs, str.split)
        ranked = idx.rank("손익 상계", n=4)
        assert docs[ranked[0][0]] == "손익 상계"

    def test_zero_score_docs_excluded(self):
        # 질의 토큰이 하나도 없는 문서는 sparse 결과로 부적절 → 제외(dense와 공정 병합).
        # "상계"는 4문서 중 1개에만 등장 → IDF 양수, 매칭 문서만 남는다.
        docs = ["손익 상계", "퇴직 급여", "자산 평가", "부채 인식"]
        idx = Bm25Index(docs, str.split)
        ranked = idx.rank("상계", n=10)
        assert [i for i, _ in ranked] == [0]
        assert all(s > 0 for _, s in ranked)

    def test_respects_top_n(self):
        # 질의 3개어가 각기 다른 문서에 매칭(3건) → n=2로 자르면 상위 2건만.
        docs = ["상계", "인식", "평가", "측정"]
        idx = Bm25Index(docs, str.split)
        assert len(idx.rank("상계 인식 평가", n=2)) == 2


class TestTokenizerRegistry:
    def test_registry_keys(self):
        # arm이 참조하는 토큰화 축 3종(whitespace / 문자 3-gram / 형태소)
        assert set(TOKENIZERS) == {"ws", "ngram", "morph"}


class TestPassesFilter:
    """_passes_filter() — BM25 결과를 dense와 같은 후보 풀로 맞추는 metadata 필터."""

    def test_none_filter_passes_all(self):
        assert _passes_filter(_chunk("1", "상계", "GAAP"), None) is True

    def test_matching_standard_passes(self):
        assert _passes_filter(_chunk("1", "상계", "GAAP"), {"standard_type": "GAAP"}) is True

    def test_mismatching_standard_blocked(self):
        assert _passes_filter(_chunk("1", "상계", "KIFRS"), {"standard_type": "GAAP"}) is False


class TestBm25Sparse:
    """_bm25_sparse() — 오프라인 BM25 순위에서 필터 통과 상위 top_n을 RetrievedChunk로 만든다."""

    def test_applies_metadata_filter(self):
        # dense가 GAAP만 보므로 BM25도 GAAP만 후보에 남겨야 병합이 공정하다
        corpus = [_chunk("1", "상계 손익", "GAAP"), _chunk("2", "상계 자산", "KIFRS")]
        idx = Bm25Index([c.content for c in corpus], str.split)
        out = _bm25_sparse(idx, corpus, "상계", top_n=10, metadata_filter={"standard_type": "GAAP"})
        assert [c.chunk_id for c in out] == ["1"]

    def test_score_replaced_by_bm25(self):
        # 코퍼스 청크의 score(0)를 실제 BM25 점수로 갱신한 복사본을 돌려준다
        corpus = [_chunk("1", "상계 손익", "GAAP"), _chunk("2", "퇴직 급여", "GAAP")]
        idx = Bm25Index([c.content for c in corpus], str.split)
        out = _bm25_sparse(idx, corpus, "상계", top_n=10, metadata_filter=None)
        assert [c.chunk_id for c in out] == ["1"]
        assert out[0].score > 0
        assert corpus[0].score == 0.0  # 원본 코퍼스는 불변

    def test_respects_top_n_after_filter(self):
        # "상계"가 10문서 중 4개(<절반)에만 등장 → IDF 양수, 매칭 4건을 top_n=3으로 자른다
        corpus = [_chunk(str(i), "상계 항목", "GAAP") for i in range(4)] + \
                 [_chunk(f"x{i}", "무관 문서", "GAAP") for i in range(6)]
        idx = Bm25Index([c.content for c in corpus], str.split)
        out = _bm25_sparse(idx, corpus, "상계", top_n=3, metadata_filter=None)
        assert len(out) == 3
