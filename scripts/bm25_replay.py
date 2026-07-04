"""BM25 오프라인 실측 하니스 — 진짜 BM25(IDF 내장)가 조항 검색을 개선하는지 반증.

[배경] 이 시스템의 sparse 검색이 쓰는 PostgreSQL ts_rank_cd는 BM25가 아니라 IDF 흔한 단어일수록 가중치를 자동으로 낮추는 값)가 없다.
  그래서 "손익계산서"처럼 흔한 용어가 순위를 지배하고 #211에서 query 쪽 레버(술어·키워드·불용어)를 다 바꿔 봐도 이 병목을 못 넘어 전부 기각됐다. 
  남은 레버는 IDF를 내장한 진짜 BM25다.

[목적] BM25 랭킹(IDF)과 한국어 토큰화는 곱셈 관계인 두 축이다. 
  무거운 인프라(ParadeDB 등)를 들이기 전에, 운영 코퍼스를 오프라인으로 꺼내 rank_bm25로 BM25 점수를 매기고,
  토크나이저를 whitespace·문자 3-gram·형태소으로 갈아끼워 "IDF 순효과"와 "토큰화 순효과"를 분리 측정한다.

[제약] 운영 스키마·프롬프트·검색 경로는 건드리지 않는다. rank_bm25·kiwipiepy는 하니스 전용 dev 의존성이다.
판정이 아래 게이트를 통과한 (토크나이저 × IDF) 조합이 있을 때만 Phase 1로 간다.

[판정 기준] Hit@1(정답 조항이 검색 1위인 질의 수) 순증 ≥ +2 · 기존 1위 회귀 0 · MRR(정답 순위 역수 평균) Δ>0 ·
sparse 지연 p50(중앙값) ≤ 1s · RRF k=60 고정 · 판정 모집단은 gold(정답 라벨) 확정 대기 3건을 뺀 11건.

이 파일은 아직 토크나이저·BM25 인덱스만 담는다 — 실측 실행부는 다음 커밋에서 추가한다.
"""
from __future__ import annotations

from collections.abc import Callable

from rank_bm25 import BM25Okapi

from scripts.sparse_predicate_replay import tokenize as tokenize_whitespace

# n-gram 크기 — 한국어 부분일치를 만드는 최소 단위. 3이면 "외화환산"과 "외화환산손익"이
# {"외화환","화환산"}을 공유해 매칭된다(2면 흔한 조각이 많아 노이즈↑, 4면 부분일치 범위↓).
NGRAM_N = 3

_kiwi = None  # kiwipiepy Kiwi 싱글턴 — 로드가 무거워(초 단위) 최초 1회만 만든다.


def tokenize_ngram(text: str, n: int = NGRAM_N) -> list[str]:
    """
    단어별 문자 n-gram으로 쪼갠다. n자보다 짧은 단어는 통째로 한 토큰으로 둔다.

    예: "외화환산손익" → ["외화환","화환산","환산손","산손익"], "인식" → ["인식"].
    현행 'simple' 토크나이저는 "외화환산손익"을 한 덩어리로 둬 청크의 "외화환산"과 매칭조차 못 하지만
    3-gram은 겹치는 조각으로 이 간극을 우회한다.
    """
    grams: list[str] = []
    for word in tokenize_whitespace(text):
        if len(word) <= n:
            grams.append(word)
        else:
            grams.extend(word[i:i + n] for i in range(len(word) - n + 1))
    return grams


def tokenize_morph(text: str) -> list[str]:
    """
    kiwipiepy 형태소 분석으로 토큰화한다(각 형태소의 표면형 form만 취함).

    예: "외화환산손익 인식" → ["외화","환산","손익","인식"].
    조사·어미도 토큰에 남기되 품사 필터를 걸지 않는다
    흔한 형태소(조사 등)는 BM25의 IDF가 자동으로 감쇠하므로, 여기서 걸러 규칙을 늘리는 것은 불필요하다.
    """
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return [t.form for t in _kiwi.tokenize(text)]


# 토큰화 축 — 표시키 → 토크나이저. arm이 (토크나이저 × BM25) 조합을 만들 때 참조한다.
#   ws    : 단어(\w+) 분리 — 현행 'simple'과 근사, IDF 순효과를 재는 기준 토큰화
#   ngram : 문자 3-gram — 단어 내 부분일치 회복
#   morph : 형태소 분석 — 복합어를 표준 용어 단위로 분해
TOKENIZERS: dict[str, Callable[[str], list[str]]] = {
    "ws": tokenize_whitespace,
    "ngram": tokenize_ngram,
    "morph": tokenize_morph,
}


class Bm25Index:
    """
    오프라인 BM25 인덱스 — 문서 리스트와 토크나이저로 구축하고, 질의별 top-n을 돌려준다.

    운영 DB에는 BM25가 없어 ts_rank_cd(IDF 부재)만 쓸 수 있다. 
    이 클래스는 코퍼스를 메모리에서 BM25Okapi로 인덱싱해, IDF가 있을 때 순위가 어떻게 달라지는지를 인프라 도입 없이 측정한다.
    """

    def __init__(self, docs: list[str], tokenizer: Callable[[str], list[str]]):
        self.tokenizer = tokenizer
        self.bm25 = BM25Okapi([tokenizer(d) for d in docs])

    def rank(self, query: str, n: int) -> list[tuple[int, float]]:
        """
        질의 상위 n개를 (문서 인덱스, 점수) 리스트로 반환한다(점수 내림차순).

        질의 토큰이 하나도 없어 점수가 0 이하인 문서는 sparse 결과로 부적절하므로 제외한다 —
        현행 sparse가 매칭된 문서만 돌려주는 규약과 같아, dense와의 RRF 병합이 공정해진다.
        """
        scores = self.bm25.get_scores(self.tokenizer(query))
        ranked = sorted(enumerate(scores), key=lambda pair: pair[1], reverse=True)
        return [(i, float(s)) for i, s in ranked[:n] if s > 0]
