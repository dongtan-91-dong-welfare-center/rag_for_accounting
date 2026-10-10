import re
from pathlib import Path

import pytest

from src.utils.config import MAX_FEEDBACK_LENGTH

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_frontend_feedback_length_constant_matches_config():
    """frontend/src/api.ts의 MAX_FEEDBACK_LENGTH 상수가 src/utils/config.py와 일치해야 한다 (#447)."""
    api_ts = (REPO_ROOT / "frontend" / "src" / "api.ts").read_text(encoding="utf-8")
    match = re.search(r"export const MAX_FEEDBACK_LENGTH\s*=\s*(\d+);", api_ts)
    assert match is not None, "frontend/src/api.ts에 MAX_FEEDBACK_LENGTH 상수가 정의되어 있어야 합니다."
    assert int(match.group(1)) == MAX_FEEDBACK_LENGTH
