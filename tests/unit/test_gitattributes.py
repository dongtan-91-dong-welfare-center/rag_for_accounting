"""tests/unit/test_gitattributes.py: .gitattributes 줄바꿈 정책 회귀 방지 테스트.

이슈 #427: Windows의 core.autocrlf 설정으로 셸 스크립트가 CRLF로 체크아웃되면
bash, WSL, 컨테이너에서 실행이 실패하므로 `*.sh`는 LF로 고정되어야 합니다.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_GITATTRIBUTES = _ROOT / ".gitattributes"


def _rules() -> dict[str, set[str]]:
    """`.gitattributes`의 패턴별 속성 집합을 반환합니다."""
    rules: dict[str, set[str]] = {}
    for line in _GITATTRIBUTES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pattern, *attrs = line.split()
        rules.setdefault(pattern, set()).update(attrs)
    return rules


def test_gitattributes_exists():
    """저장소 루트에 .gitattributes가 존재해야 합니다."""
    assert _GITATTRIBUTES.is_file()


@pytest.mark.parametrize("pattern", ["*.sh", "Dockerfile", "*.Dockerfile", "*.yml", "*.yaml"])
def test_lf_enforced_for_container_and_ci_files(pattern: str):
    """셸 스크립트와 컨테이너 및 CI 파일은 text와 eol=lf로 고정되어야 합니다."""
    attrs = _rules().get(pattern, set())
    assert {"text", "eol=lf"} <= attrs, f"{pattern} 규칙에 'text eol=lf'가 필요합니다: {attrs}"


@pytest.mark.skipif(shutil.which("git") is None, reason="git 실행 파일이 필요합니다")
def test_tracked_shell_scripts_resolve_to_eol_lf():
    """추적 중인 모든 *.sh 파일에 git이 eol=lf 속성을 실제로 적용해야 합니다."""
    listed = subprocess.run(
        ["git", "ls-files", "*.sh"], cwd=_ROOT, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout.split()
    if not listed:
        pytest.skip("추적 중인 셸 스크립트가 없습니다")
    out = subprocess.run(
        ["git", "check-attr", "eol", "--", *listed],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout.splitlines()
    bad = [line for line in out if not line.endswith(": eol: lf")]
    assert not bad, f"eol=lf가 적용되지 않은 파일: {bad}"
