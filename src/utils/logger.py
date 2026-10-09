import json
import logging
import time
from datetime import datetime
from functools import wraps
from src.utils.config import KST, LOG_FIELD_KEYS, LOG_FORMAT, LOG_TAGS


class _KSTFormatter(logging.Formatter):
    """%(asctime)s를 한국 표준시(KST, UTC+9)로 출력하는 일반 텍스트 포매터"""
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=KST)
        return dt.strftime(datefmt) if datefmt else dt.isoformat(timespec="seconds")


class _JSONLinesFormatter(logging.Formatter):
    """로그 레코드를 JSON Lines (NDJSON) 규격의 단일 행 JSON으로 직렬화하는 구조화 포매터"""
    def format(self, record: logging.LogRecord) -> str:
        dt = datetime.fromtimestamp(record.created, tz=KST)
        log_entry = {
            "timestamp": dt.isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        # extra로 전달된 커스텀 필드(예: trace_id, elapsed_sec, node 등)가 있으면 병합
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "taskName"
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_entry[key] = value

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def get_logger(name: str) -> logging.Logger:
    """표준 로거 반환. 핸들러가 없으면 LOG_FORMAT 설정에 따라 StreamHandler를 자동 추가"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        if LOG_FORMAT == "json":
            handler.setFormatter(_JSONLinesFormatter())
        else:
            handler.setFormatter(_KSTFormatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_kv(logger: logging.Logger, level: int, tag: str, message: str, *, exc_info=False, **fields) -> None:
    """표준 로그 형식 `[태그] 설명 | 키=값`으로 기록하고 동일 값을 extra 영어 키로 함께 전달하는 헬퍼.

    tag는 config.LOG_TAGS, fields의 키는 config.LOG_FIELD_KEYS(한국어 키)에 등록된 값만 허용한다.
    근거: 오타와 표기 불일치를 구조적으로 막고, JSON 모드에서 필드 단위 검색을 가능하게 하기 위함이다.
    """
    if tag not in LOG_TAGS:
        raise ValueError(f"등록되지 않은 로그 태그입니다: {tag}")
    parts = [f"[{tag}] {message}"]
    extra: dict = {"tag": tag}
    for key, value in fields.items():
        if key not in LOG_FIELD_KEYS:
            raise ValueError(f"등록되지 않은 로그 키입니다: {key}")
        en_key = LOG_FIELD_KEYS[key]
        if key == "소요":
            value = round(float(value), 4)
            parts.append(f"{key}={value:.4f}s")
        else:
            parts.append(f"{key}={value}")
        extra[en_key] = value
    logger.log(level, " | ".join(parts), extra=extra, exc_info=exc_info)


def log_execution_time(func):
    """함수 실행 시간을 측정하고 로거에 기록하며, 첫 번째 인자가 GraphState인 경우 metadata에 기록하는 데코레이터."""
    logger = get_logger(func.__module__)

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            # GraphState 객체이거나 metadata dict를 가진 객체일 경우 실행 시간 기록
            if args:
                first_arg = args[0]
                if hasattr(first_arg, "metadata") and isinstance(first_arg.metadata, dict):
                    first_arg.metadata.setdefault("execution_times", {})[func.__name__] = elapsed
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start
            try:
                log_kv(logger, logging.ERROR, "workflow", "실행 오류", 함수=func.__name__, 소요=elapsed, 오류=type(e).__name__, 상세=e)
            except Exception:
                pass  # 근거: 로깅 실패가 원래 예외를 가리지 않도록 삼킨다.
            raise
    return wrapper
