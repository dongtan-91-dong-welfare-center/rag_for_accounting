"""tests/unit/test_logging_standard.py — 로깅 표준(#408) 위반 검출 테스트.

src/ 하위에서 log_kv 헬퍼를 거치지 않은 `logger.*` 직접 호출을 AST로 검사한다.
헬퍼 정의 파일(src/utils/logger.py)은 예외로 둔다.
"""
import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
HELPER_FILE = SRC_DIR / "utils" / "logger.py"
LOG_METHODS = {"debug", "info", "warning", "error", "critical", "exception", "log"}


def _direct_logger_calls(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in LOG_METHODS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "logger"
    ]


def test_no_direct_logger_calls_outside_helper():
    """src/ 하위에 log_kv를 거치지 않은 logger.* 직접 호출이 없는지 검증한다."""
    violations = [
        f"{path.relative_to(SRC_DIR.parent).as_posix()}:{lineno}"
        for path in sorted(SRC_DIR.rglob("*.py"))
        if path != HELPER_FILE
        for lineno in _direct_logger_calls(path)
    ]

    assert not violations, "log_kv를 사용하지 않은 logger 직접 호출: " + ", ".join(violations)


def test_detector_flags_direct_call(tmp_path):
    """검출 로직이 직접 호출을 실제로 잡아내는지 검증한다."""
    sample = tmp_path / "sample.py"
    sample.write_text("logger.info('x')\nlog_kv(logger, 20, 'api', 'x')\n", encoding="utf-8")

    assert _direct_logger_calls(sample) == [1]
