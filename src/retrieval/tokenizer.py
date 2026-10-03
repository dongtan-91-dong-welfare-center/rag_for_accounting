# FUNC-003·FUNC-005 공유: sparse 검색용 한국어 형태소 토큰화

"""
형태소 토큰화 — 적재(색인)와 검색(질의)이 공유하는 단일 진실.

[왜 필요한가] PostgreSQL 'simple' 설정은 형태소 분석을 하지 않아 띄어쓰기로만 자른다.
그래서 "퇴직급여를"이 한 덩어리로 남고 본문의 "퇴직급여"와 매칭조차 못 하며,
plainto_tsquery는 전 토큰 AND이므로 문장형 질의는 전 케이스 0건을 반환한다.
하이브리드 검색이 이름만 하이브리드였던 구조적 원인이다.

[해법] 본문과 질의를 같은 형태소 분석기로 미리 쪼개 공백으로 이어 붙인 뒤
to_tsvector('simple', …)에 넣는다. 'simple'은 이미 쪼개진 토큰을 그대로 받으므로
ParadeDB 같은 추가 인프라 없이 형태소 단위 매칭이 된다.

[핵심 규약] 색인과 질의가 같은 함수를 통과해야 한다. 
색인은 명사류만 남기고 질의는 전체 형태소를 넣으면 매칭이 조용히 깨진다.
인덱싱과 검색이 embedding.embed_texts()를 공유해 모델·차원 불일치를 구조적으로 막는 것과 같은 이유로, 토크나이저도 여기 한 곳에 둔다.
태그 화이트리스트는 config.py(MORPH_POS_TAGS_*)가 정본이다.
"""
from __future__ import annotations

from src.utils.config import MORPH_POS_TAGS

# kiwipiepy Kiwi 싱글턴 — 로드가 무거워(초 단위) 최초 1회만 만든다.
# 적재는 전 청크를, 검색은 질의마다 이 인스턴스를 재사용한다.
_kiwi = None


def _get_kiwi():
    """
    Kiwi 인스턴스를 지연 로드해 재사용한다.
    import 시점에 로드하지 않는 이유: 형태소 분석이 필요 없는 진입점(API 서버 기동 등)까지 수 초의 초기화 비용을 물지 않게 하기 위함이다.
    """
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi

        _kiwi = Kiwi()
    return _kiwi


def tokenize_morph(text: str, tags: tuple[str, ...] | None = MORPH_POS_TAGS) -> list[str]:
    """
    형태소 표면형 리스트로 쪼갠다. tags를 주면 그 품사만 남긴다.

    예(tags=MORPH_POS_TAGS_CORE):
        "대손충당금 환입액은 어떻게 회계처리하나요?"
        → ["대손", "충당금", "입", "액", "회계", "처리"]
        (은/JX·하/XSV·나요/EF 같은 조사·어미는 태그로 걸러지고, "환"은 XR이라 CORE에서는 빠진다)

    tags=None이면 조사·어미까지 전부 남긴다
    IDF가 흔한 형태소를 자동 감쇠하는 오프라인 BM25에서만 타당한 선택지다.
    운영 sparse가 쓰는 ts_rank_cd에는 IDF가 없어 저IDF 매칭이 누적되면 순위가 흔들리므로, 기본값은 필터를 켠다.
    """
    tokens = _get_kiwi().tokenize(text)
    if tags is None:
        return [t.form for t in tokens]
    return [t.form for t in tokens if t.tag in tags]


def morph_text(text: str, tags: tuple[str, ...] | None = MORPH_POS_TAGS) -> str:
    """
    형태소를 공백으로 이어 붙인 문자열 — 색인 컬럼에 저장할 본문 입력용.

    색인은 본문을 이 함수로 변환해 저장하고, 검색은 질의를 같은 tokenize_morph로 쪼갠 뒤 OR로 연결해 질의한다
    결합 방식은 달라도 토큰화가 같으므로 색인 토큰과 질의 토큰이 어긋나지 않는다.
    'simple' 설정은 이 공백을 토큰 경계로 그대로 받아들이므로 형태소 단위 매칭이 성립한다.

    토큰이 하나도 남지 않으면 빈 문자열을 반환한다. 호출자는 이때 검색을 건너뛰어야 한다.
    """
    return " ".join(tokenize_morph(text, tags))
