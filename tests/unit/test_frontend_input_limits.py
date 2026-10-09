# 프런트엔드 입력 길이 상수가 서버 SSoT(src/utils/config.py)와 일치하는지 검증한다(#445).
import re
from pathlib import Path

import pytest

from src.utils import config

pytestmark = pytest.mark.unit

API_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api.ts"


def _frontend_limit(name: str) -> int:
    match = re.search(rf"export const {name} = (\d+);", API_TS.read_text(encoding="utf-8"))
    assert match, f"frontend/src/api.ts에 {name} 상수가 없습니다."
    return int(match.group(1))


@pytest.mark.parametrize("name", ["MAX_QUERY_LENGTH", "MAX_FEEDBACK_LENGTH"])
def test_frontend_limit_matches_config(name):
    assert _frontend_limit(name) == getattr(config, name)
