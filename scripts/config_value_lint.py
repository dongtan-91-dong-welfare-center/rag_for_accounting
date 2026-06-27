"""docs/ 설정값 == src/utils/config.py 일치 검사 — 온디맨드 유틸 (path_lint 동류).

CLAUDE.md SSoT 규칙("문서에 수치를 복제하지 말고 코드를 가리킨다 … 수치를 문서에 박으면 드리프트가 생긴다")을 기계로 강제한다.
문서가 핵심 상수를 `NAME=값` 형태로 박아두면, 그 값이 config.py와 어긋났는지 검사해 드리프트를 잡는다.
손-스냅샷을 금지하는 대신 이 검사로 안전망을 둔다.

테스트 스위트에는 묶지 않는다(수동 실행). 
문서나 config.py를 손댄 뒤 uv run python scripts/config_value_lint.py로 불일치가 0인지 확인하는 용도.
스캔 범위·제외 규칙은 path_lint와 공유한다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from scripts.path_lint import iter_doc_files  # noqa: E402  (스캔 범위·제외 규칙 공유)
from src.utils import config  # noqa: E402

# 문서에 `NAME=값`으로 박힐 만한, 드리프트 위험이 큰 핵심 상수.
TRACKED = (
    "RRF_K",
    "MAX_REWRITE_COUNT",
    "MAX_HIL_COUNT",
    "TOP_K_RETRIEVAL",
    "EMBEDDING_DIM",
    "RERANK_THRESHOLD",
    "CHUNK_MAX_TOKENS",
    "EMBEDDING_MAX_TOKENS",
    "SEARCH_TIMEOUT_SECONDS",
    "BATCH_SIZE",
)


def actual_values() -> dict:
    """추적 대상 상수의 현재 config.py 값."""
    return {name: getattr(config, name) for name in TRACKED}


def _eq(stated: str, actual) -> bool:
    """숫자는 정규화 비교(60==60, 0.50==0.5), 그 외는 문자열 비교."""
    try:
        return float(stated) == float(actual)
    except (TypeError, ValueError):
        return stated == str(actual)


def find_mismatches(text: str, values: dict) -> list[tuple[int, str, str, str]]:
    """문서 텍스트에서 `NAME=리터럴`을 찾아 values(실제 config 값)와 다른 것만 반환.

    반환: [(lineno, name, 문서값, 실제값), ...]
    """
    if not values:
        return []
    pat = re.compile(r"\b(" + "|".join(map(re.escape, values)) + r")\s*=\s*([0-9]+(?:\.[0-9]+)?)")
    out: list[tuple[int, str, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in pat.finditer(line):
            name, stated = m.group(1), m.group(2)
            if not _eq(stated, values[name]):
                out.append((lineno, name, stated, str(values[name])))
    return out


def lint_docs(repo_root: Path = _ROOT) -> list[tuple[str, int, str, str, str]]:
    values = actual_values()
    broken: list[tuple[str, int, str, str, str]] = []
    for p in iter_doc_files(repo_root):
        text = p.read_text(encoding="utf-8")
        for lineno, name, stated, actual in find_mismatches(text, values):
            broken.append((str(p.relative_to(repo_root)), lineno, name, stated, actual))
    return broken


if __name__ == "__main__":
    result = lint_docs()
    for rel, ln, name, stated, actual in result:
        print(f"  {rel}:{ln}  문서 {name}={stated}  ↔  config.py {actual}")
    print(f"\nTOTAL: {len(result)}")
