"""
조항 문단번호 추출 공용 모듈 — 채점기·chunker·UI가 함께 쓰는 단일 정본.

[배경] 기준서 청크 본문은 마크다운이고, 조항 문단은 "#### 6.13"처럼 헤딩으로 표시된다.
문단에는 일반 번호 외에 한글 접두가 붙는 종류가 있다. 실(실무지침), 결(결론도출근거), 소(중소기업 특례). 
또 온톨로지 노드가 조항 하나인 청크는 번호가 본문에 없고 chunk_id 꼬리에만 있다(예: "gaap-ch2-실2.11")
2026-07-25 운영 DB 전수조사(1,507청크)
실측: 접두 헤더 실 415·결 107·소 6건, 번호가 chunk_id에만 있는 청크 435건.

[목적] 문단번호를 뽑는 규칙을 이 모듈 한 곳에 두어, 벤치마크 채점기·조항 chunker·화면(조항 카드 칩)이 같은 규칙을 소비하게 한다.
규칙이 두 벌로 복사되면 수정이 한쪽만 반영돼 "채점은 맞는데 화면은 틀린" 상태가 구조적으로 생긴다.

[제약] 추출 결과는 원형 보존이다. "6.13의2"는 "6.13의2"로 돌려준다. 가지번호를
"6.13"으로 합치는 정규화는 통계를 내는 채점기의 요구이고, 화면은 원형을 그대로 보여야 회계사가 그 조항을 찾을 수 있어 요구가 반대다.
정규화는 각 소비자가 한다.
접두는 명시 allowlist만 허용한다.
열린 한글 패턴([가-힣]+)을 쓰면 "사례"·"부록" 같은 비조항 제목이 오탐으로 섞인다.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

# 접두 allowlist. 운영 코퍼스 전수조사에서 실재가 확인된 세 종류만 허용한다.
PARA_PREFIXES: tuple[str, ...] = ("실", "결", "소")

# 문단번호의 구성 조각. 예: "6.13" / "2.6.5" / "6.13의2" → NUM_CORE + BRANCH.
# 채점기의 범위 표기("15.15조~15.16조") 파싱처럼 가지번호 없는 꼴이 필요한 소비자가 있어 본체와 가지를 분리해 둔다.
NUM_CORE_PATTERN = r"\d+\.\d+(?:\.\d+)?"
BRANCH_PATTERN = r"(?:의\d+)?"
PREFIX_PATTERN = rf"(?:{'|'.join(PARA_PREFIXES)})"

# 문단번호 토큰 한 개(접두 선택 + 본체 + 가지). gold 라벨의 "실2.11조"에서 "실2.11"을 잡는 데 쓴다
# 접두를 버리면 같은 장의 일반 문단 2.11과 구분되지 않는다.
TOKEN_PATTERN = rf"{PREFIX_PATTERN}?{NUM_CORE_PATTERN}{BRANCH_PATTERN}"
PARA_TOKEN_RE = re.compile(TOKEN_PATTERN)

_TOKEN_FULL_RE = re.compile(TOKEN_PATTERN)


def clause_header_re(
    *,
    levels: tuple[int, int] = (3, 5),
    prefixes: Sequence[str] = PARA_PREFIXES,
) -> re.Pattern[str]:
    """
    문단 헤더 정규식을 소비자별 변형으로 생성한다(사본 0의 실현 수단).
    levels는 허용 헤딩 레벨 범위다. 추출 기본값 (3, 5)는 실물 기준이다.
    청크 정본은 H4가 정규이고 H5는 ch12의 12.21~12.26 6건이 실재하며,
    H3은 이슈 #255가 지목한 소스 마크다운 표기라 빌더가 레벨을 바꿔도 깨지지 않게 포함한다.
    H6은 각주·미주 제목이라 제외한다.

    chunker는 분할 경계용으로 levels=(4, 4)·prefixes=()를 넘겨 현행 의미를 고정한다 —
    경계를 넓히면 다음 재적재부터 청크 구성이 달라져 검색 회귀 검증과 벤치마크 플로어
    재시드가 필요해지기 때문이다. 경계 확장은 별도 이슈에서 A/B로 판단한다.
    """
    lo, hi = levels
    hashes = f"#{{{lo}}}" if lo == hi else f"#{{{lo},{hi}}}"
    prefix = f"(?:{'|'.join(prefixes)})?" if prefixes else ""
    return re.compile(
        rf"^{hashes}\s+({prefix}{NUM_CORE_PATTERN}{BRANCH_PATTERN})", re.MULTILINE
    )


# 추출 정본 정규식. 줄 시작 앵커라 본문 중간 언급("본문에 결21.15를 인용")은 잡지 않는다.
CONTENT_PARA_RE = clause_header_re()


def content_paras(content: str) -> list[str]:
    """본문 헤더에서 문단번호를 등장 순서대로, 중복 없이, 원형 그대로 뽑는다.

    예: "#### 6.13\\n…\\n#### 실2.24\\n…" → ["6.13", "실2.24"].
    """
    seen: set[str] = set()
    out: list[str] = []
    for p in CONTENT_PARA_RE.findall(content):
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def node_id_para(chunk_id: str) -> str | None:
    """
    chunk_id 꼬리 토큰이 문단번호면 돌려준다. 예: "gaap-ch2-실2.11" → "실2.11".

    단일 조항 노드는 온톨로지 빌더가 조항 번호를 노드 id로 쓰고 본문에는 헤더를 남기지 않으므로, 여기서 못 읽으면 그 조항은 채점·칩 표시 어디에서도 번호가 없는 것이 된다.
    토큰 상한 분할 뒷조각의 "-N" 접미사(예: "…-실2.11-2")는 벗겨내고 판정한다.
    """
    if not chunk_id:
        return None
    segments = chunk_id.split("-")
    if len(segments) >= 2 and segments[-1].isdigit():  # 분할 뒷조각 접미사(-2, -3 …)
        segments = segments[:-1]
    tail = segments[-1]
    return tail if _TOKEN_FULL_RE.fullmatch(tail) else None


def chunk_paras(content: str, chunk_id: str = "") -> list[str]:
    """
    청크 한 건의 문단번호 = content 헤더 ∪ chunk_id 꼬리 토큰(중복 제거).

    다발 청크는 content 헤더에서, 단일 조항 청크는 chunk_id에서 번호가 나온다.
    id 토큰은 대개 content에 없을 때만 존재하므로 목록 끝에 보탠다.
    """
    paras = content_paras(content)
    id_para = node_id_para(chunk_id)
    if id_para and id_para not in paras:
        paras.append(id_para)
    return paras
