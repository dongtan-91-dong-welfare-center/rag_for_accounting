"""정규식으로 엣지 후보 문장을 필터링한다.

전체 텍스트를 LLM에 바로 던지면 비용이 크고 노이즈도 많다.
이 모듈은 "엣지가 있을 가능성이 있는 줄"만 골라내는 1차 필터 역할을 한다.
실제로 엣지 타입을 판별하는 것은 LLM(edge_extractor.py)이 담당한다.
"""

import re

# 이 패턴 중 하나라도 줄에 포함되면 엣지 후보로 본다.
# 오탐(false positive)이 있어도 괜찮다 — LLM이 NONE으로 걸러낸다.
_PATTERNS = [
    re.compile(r'다만'),          # 예외 조항 시작 신호
    re.compile(r'제외'),          # 적용범위 제외
    re.compile(r'제\s*\d+\s*장'), # 장 참조. 예: "제8장"
    re.compile(r'제\s*\d+\s*절'), # 절 참조. 예: "제 2 절"
    re.compile(r'문단\s*[가-힣]*\d+'),  # 문단 번호 참조. 예: "문단 6.4", "문단 실6.72", "문단 6.5~6.7"
    re.compile(r'불구하고'),       # 원칙의 예외 신호
    re.compile(r'한하여'),         # 조건부 적용 신호
]


def detect_candidates(content: str) -> list[str]:
    """Subsection의 전체 텍스트에서 엣지 후보 줄만 골라 반환한다.

    반환값은 줄 단위 문자열 목록이며, 빈 줄은 포함하지 않는다.
    """
    return [
        line.strip()
        for line in content.split('\n')
        if line.strip() and any(p.search(line) for p in _PATTERNS)
    ]
