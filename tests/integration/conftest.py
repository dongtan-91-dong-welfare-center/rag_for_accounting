import os

import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(autouse=True)
def require_openai_api_key():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY 없음 — 실제 LLM 호출이 필요한 통합 테스트 건너뜀")
