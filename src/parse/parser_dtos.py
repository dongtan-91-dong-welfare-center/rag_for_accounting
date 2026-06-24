"""
DTO(Data Transfer Object) 정의 모듈

DTO란?
    - 데이터를 담아서 여러 함수/클래스 사이에 전달하기 위한 "그릇" 역할의 객체입니다.
    - 예를 들어, PDF에서 추출한 텍스트·표·메타데이터를 하나로 묶어서 다른 모듈에
      전달할 때 딕셔너리(dict) 대신 DTO를 쓰면 어떤 필드가 있는지 명확해집니다.

이 모듈에서 정의하는 것들:
    1. 레이아웃 후처리에 사용하는 임계값(threshold) 상수
    2. 리스트 마커(번호 매기기 기호)를 인식하기 위한 정규표현식 패턴
    3. ParsedDocument — 파싱 결과 DTO (정본은 src/models/schemas.py, 여기서 재노출)
"""
import re
from dataclasses import dataclass
from docling_core.types.doc.document import RefItem

# ParsedDocument의 단일 정본은 src/models/schemas.py. 
# 기존 import 경로(src.parse.parser_dtos) 호환을 위해 재노출한다. 
# schemas는 parse를 import하지 않으므로 순환 의존은 없다.
from src.models.schemas import ParsedDocument  # noqa: F401

# ──────────────────────────────────────────────────────────────────
# 레이아웃 후처리 임계값 (Docling 내부 레이아웃 분석에서 사용)
# ──────────────────────────────────────────────────────────────────
# Docling은 PDF를 분석할 때 페이지 안의 텍스트 블록(클러스터)들이 서로 겹치는지 판단합니다.
# 아래 두 값은 "어느 정도 겹쳐야 같은 블록으로 볼 것인가"를 결정하는 비율(0~1)입니다.
#
# - OVERLAP_THRESHOLD  : 두 클러스터의 겹침 면적 비율이 이 값 이상이면 "겹친다"고 판단
# - CONTAINMENT_THRESHOLD : 한 클러스터가 다른 클러스터에 포함되는 비율이 이 값 이상이면
#                           "포함된다"고 판단
#
# 값이 낮을수록(예: 0.15) 조금만 겹쳐도 병합 대상이 되고,
# 값이 높을수록(예: 0.80) 많이 겹쳐야 병합 대상이 됩니다.
# 회계 문서처럼 빽빽한 레이아웃에서는 낮은 값이 더 정확한 결과를 줍니다.
OVERLAP_THRESHOLD = 0.15
CONTAINMENT_THRESHOLD = 0.15

# ──────────────────────────────────────────────────────────────────
# 리스트 마커 패턴 (정규표현식)
# ──────────────────────────────────────────────────────────────────
# 한국어 회계/법률 문서에서 자주 쓰이는 번호 매기기 기호를 인식하기 위한 패턴입니다.
#
# 매칭 대상 예시:
#   ⑴ ⑵ ⑶ ...  → 괄호 숫자 기호 (유니코드)
#   ㈎ ㈏ ㈐ ... → 괄호 한글 기호 (유니코드)
#   ① ② ③ ...  → 원 숫자 기호 (유니코드)
#   (1) (2) ... → 일반 괄호+숫자 형식
#   1. 2. 3. ...→ 숫자+마침표 형식
#
# re.compile()은 패턴을 미리 컴파일(준비)해두어 반복 사용 시 성능을 높입니다.
# ^ : 문자열의 시작, $ : 문자열의 끝, \s* : 0개 이상의 공백
_MARKER_RE = re.compile(
    r"^(?:"
    r"[⑴⑵⑶⑷⑸⑹⑺⑻⑼⑽⑾⑿㈎㈏㈐㈑㈒㈓㈔㈕①②③④⑤⑥⑦⑧⑨⑩⑪⑫]"
    r"|\(\d+\)"
    r"|[가-힣]*\d+\.[A-Za-z]?\d*(?:의\d+)?"
    r")\s*$"
)


@dataclass
class _ItemInfo:
    """정렬을 위한 아이템 메타 정보."""
    ref: RefItem
    page_no: int
    left: float
    top: float
    right: float
    bottom: float
    width: float

# 두 아이템의 수직 겹침이 이 비율 이상이면 "같은 라인"으로 간주
SAME_LINE_OVERLAP_RATIO = 0.5
# XY-Cut에서 gap이 이 값(평균 아이템 높이 대비 비율) 이상이면 분할
MIN_GAP_RATIO = 0.3
# 클러스터링: 아이템 간 거리가 이 값(평균 아이템 높이 배수) 이내면 같은 클러스터
CLUSTER_DISTANCE_FACTOR = 1.5

# ── 페이지 걸침 테이블 병합 임계값 ──
_PAGE_TOP_THRESHOLD = 700   # PDF t좌표가 이 이상이면 페이지 상단
_PAGE_BOT_THRESHOLD = 150   # PDF b좌표가 이 이하이면 페이지 하단

# 두 아이템의 top y 차이가 (작은 쪽 높이 × 이 비율) 이내면 같은 라인
SAME_LINE_RATIO = 0.5