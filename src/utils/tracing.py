"""OpenTelemetry 및 Logfire 기반 분산 트레이싱 초기화 모듈.

근거: #171. LangSmith에서 LangGraph 파이프라인의 각 노드 및 하위 PydanticAI
LLM 호출(프롬프트, 완성, 토큰 수, 소요시간)을 단일 run tree로 온전히 관찰할 수
있도록 배선한다.

- LANGSMITH_TRACING_ENABLED가 True이고 LANGSMITH_API_KEY가 설정되어 있을 때만 활성화된다.
- 비활성 상태이거나 키가 없을 때는 완벽하게 no-op으로 동작하여 테스트 및 CLI에 영향을 주지 않는다.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from src.utils.config import (
    LANGSMITH_ENDPOINT,
    LANGSMITH_TRACING_ENABLED,
)
from src.utils.logger import get_logger, log_kv

logger = get_logger(__name__)

_tracing_initialized: bool = False


def is_tracing_configured() -> bool:
    """트레이싱 활성화 요건(플래그 활성 및 API 키 존재)이 충족되었는지 확인한다."""
    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    return bool(LANGSMITH_TRACING_ENABLED and api_key)


def init_tracing(
    *,
    force: bool = False,
    additional_span_processors: list[Any] | None = None,
    send_to_logfire: bool = False,
) -> bool:
    """트레이싱 시스템 및 PydanticAI 계측을 1회 초기화한다.

    Args:
        force: 이미 초기화되었더라도 재초기화를 강제할지 여부(테스트용).
        additional_span_processors: OTel 스팬 프로세서 목록(예: 테스트용 SimpleSpanProcessor).
        send_to_logfire: Logfire 클라우드로 전송할지 여부(기본값 False).

    Returns:
        초기화가 수행되었으면 True, no-op 건너뛰었으면 False.
    """
    global _tracing_initialized
    if _tracing_initialized and not force:
        return False

    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    should_init = force or (LANGSMITH_TRACING_ENABLED and bool(api_key))

    if not should_init and not additional_span_processors:
        # 키나 프로세서가 없으면 계측을 구성하지 않는다.
        return False

    import logfire

    span_processors = list(additional_span_processors or [])

    # LangSmith OTLP 엔드포인트 연동을 위한 Exporter 구성 (실제 키가 있을 때)
    if api_key and not additional_span_processors:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            otlp_exporter = OTLPSpanExporter(
                endpoint=LANGSMITH_ENDPOINT,
                headers={"x-api-key": api_key},
            )
            span_processors.append(BatchSpanProcessor(otlp_exporter))
        except Exception as e:
            log_kv(logger, logging.WARNING, "tracing", "LangSmith OTLP SpanExporter 구성 실패", 대체동작="로깅만 유지", 오류=type(e).__name__, 상세=e)

    logfire.configure(
        send_to_logfire=send_to_logfire,
        inspect_arguments=False,
        additional_span_processors=span_processors,
    )
    logfire.instrument_pydantic_ai()

    _tracing_initialized = True
    log_kv(logger, logging.INFO, "tracing", "PydanticAI 트레이싱 계측 초기화 완료", 건수=len(span_processors))
    return True


def reset_tracing() -> None:
    """테스트 격리를 위해 트레이싱 초기화 플래그를 리셋한다."""
    global _tracing_initialized
    _tracing_initialized = False
