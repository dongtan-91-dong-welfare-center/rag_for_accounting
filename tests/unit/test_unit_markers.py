"""tests/unit/test_unit_markers.py — tests/unit 하위 마커 누락 회귀 방지 테스트.

이슈 #407: tests/unit/ 디렉터리에 위치한 모든 단위 테스트는
`pytest -m unit` 필터링 시 누락 없이 정상 집계되어야 합니다.
"""
from pathlib import Path
import subprocess
import sys
import pytest

pytestmark = pytest.mark.unit


def test_all_unit_tests_have_unit_marker():
    """tests/unit 하위의 모든 단위 테스트가 unit 마커를 보유하고 있는지 검증한다."""
    repo_root = Path(__file__).resolve().parents[2]
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-m",
        "not unit",
        "tests/unit",
        "-q",
    ]
    res = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    # "not unit"으로 수집된 tests/unit 하위 테스트 항목이 없어야 함
    unmarked_tests = [
        line for line in res.stdout.splitlines()
        if line.startswith("tests/unit/") and "::" in line
    ]
    assert not unmarked_tests, (
        f"tests/unit/ 내에 @pytest.mark.unit 마커가 누락된 테스트가 {len(unmarked_tests)}건 발견되었습니다:\n"
        + "\n".join(unmarked_tests)
    )
