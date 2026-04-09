"""DTO 정의"""
import re
from dataclasses import dataclass, field

# Docling의 레이아웃 후처리에서 사용하는 임계값 정리
OVERLAP_THRESHOLD = 0.15
CONTAINMENT_THRESHOLD = 0.15

# 리스트 마커 패턴 확인(추가적으로 업데이트 나중에 진행)
_MARKER_RE = re.compile(
    r"^[⑴⑵⑶⑷⑸⑹⑺⑻⑼⑽⑾⑿㈎㈏㈐㈑㈒㈓㈔㈕"
    r"①②③④⑤⑥⑦⑧⑨⑩⑪⑫"
    r"\(\d+\)\d+\.\d+\.]\s*$"
)

# 일차적인 문서를 처리하기 위한 DTO
@dataclass
class ParsedDocument:
    title: str
    text: str
    tables: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

