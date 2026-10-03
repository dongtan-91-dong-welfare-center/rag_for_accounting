"""OpenAI LLM 클라이언트 — 지연 초기화(lazy initialization) 방식.

근거: import 시점에 클라이언트를 즉시 생성하면 OPENAI_API_KEY 환경변수가 없을 때
``--help``·테스트 로딩 시점에도 예외가 발생한다(#361). 첫 호출 시점에 초기화하도록
변경하여, 키 없이도 모듈 import와 CLI 진입점이 정상 동작하도록 한다.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

from src.utils.config import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS

if TYPE_CHECKING:
    from openai import OpenAI as _OpenAI

load_dotenv()

_client: Any = None


def _get_client() -> Any:
    """LLM 클라이언트를 반환한다. 첫 호출 시 초기화한다.

    OPENAI_API_KEY가 설정되지 않은 경우 명확한 오류 메시지와 함께 RuntimeError를 발생시킨다.
    """
    global _client
    if _client is None:
        from openai import OpenAI  # noqa: PLC0415 — 지연 import 의도적 사용

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY 환경변수가 설정되지 않았습니다. "
                ".env 파일 또는 환경변수로 API 키를 설정한 후 다시 실행하세요."
            )
        _client = OpenAI(
            api_key=api_key,
            timeout=LLM_TIMEOUT_SECONDS,
            max_retries=LLM_MAX_RETRIES,
        )
    return _client


class _LazyClient:
    """OpenAI 클라이언트를 첫 속성 접근 시 초기화하는 프록시 객체.

    기존 코드에서 ``client.chat.completions.create(...)`` 형태로 사용하던 부분을
    수정 없이 그대로 사용할 수 있도록 ``__getattr__``을 통해 위임한다.
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(_get_client(), name)


client: Any = _LazyClient()
