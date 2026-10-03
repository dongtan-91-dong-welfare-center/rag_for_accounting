"""
코드 복잡도(McCabe C901) 및 정적 분석 품질 설정 검증 단위 테스트.

Issue #306 (SlopCodeBench 침식도 통제 및 ruff C901 순환 복잡도 가드레일 도입) 검증.
"""
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.unit
class TestCodeComplexityConfig:
    """pyproject.toml의 ruff McCabe 복잡도 설정 및 베이스라인 무결성 검증"""

    @pytest.fixture(scope="class")
    def pyproject_data(self) -> dict:
        pyproject_path = REPO_ROOT / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml 파일이 존재해야 합니다."
        return tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    def test_mccabe_max_complexity_is_set_to_ten(self, pyproject_data: dict):
        """McCabe 순환 복잡도 임계값이 10으로 명시되어 있는지 검증합니다."""
        tool_ruff = pyproject_data.get("tool", {}).get("ruff", {})
        lint_config = tool_ruff.get("lint", {})

        select_rules = lint_config.get("select", [])
        assert "C901" in select_rules, "tool.ruff.lint.select에 'C901'이 포함되어야 합니다."

        mccabe_config = lint_config.get("mccabe", {})
        assert mccabe_config.get("max-complexity") == 10, "max-complexity 임계값은 10이어야 합니다."

    def test_per_file_ignores_paths_exist_in_repository(self, pyproject_data: dict):
        """per-file-ignores에 등록된 베이스라인 예외 파일들이 저장소에 실제로 존재하는지 검증합니다."""
        tool_ruff = pyproject_data.get("tool", {}).get("ruff", {})
        per_file_ignores = tool_ruff.get("lint", {}).get("per-file-ignores", {})

        assert len(per_file_ignores) > 0, "베이스라인 예외 파일 목록이 존재해야 합니다."

        for rel_path, rules in per_file_ignores.items():
            full_path = REPO_ROOT / rel_path
            assert full_path.exists(), f"예외 등록된 파일이 실제로 존재해야 합니다: {rel_path}"
            assert rules == ["C901"], f"예외 규칙은 C901로만 국한되어야 합니다: {rel_path} -> {rules}"

    def test_ruff_check_passes_on_current_codebase(self):
        """현재 코드베이스 전체에 대해 ruff check가 0개의 오류로 통과하는지 검증합니다."""
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "src", "tests"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"ruff check 실행이 성공해야 합니다:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"

    def test_c901_detects_overly_complex_function(self, tmp_path: Path):
        """복잡도 10을 초과하는 고복잡도 함수에 대해 ruff C901이 위반을 정확히 탐지하는지 검증합니다."""
        # 11개의 독립적인 조건 분기를 가진 복잡도 11 함수 생성
        complex_code = '''
def complex_function(x: int) -> int:
    if x == 1:
        return 1
    elif x == 2:
        return 2
    elif x == 3:
        return 3
    elif x == 4:
        return 4
    elif x == 5:
        return 5
    elif x == 6:
        return 6
    elif x == 7:
        return 7
    elif x == 8:
        return 8
    elif x == 9:
        return 9
    elif x == 10:
        return 10
    return 0
'''
        test_file = tmp_path / "complex_sample.py"
        test_file.write_text(complex_code, encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", str(test_file), "--select", "C901", "--config", "lint.mccabe.max-complexity=10"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "복잡도 11인 함수에 대해 ruff check가 실패를 반환해야 합니다."
        assert "C901" in result.stdout or "C901" in result.stderr, "C901 위반 코드가 출력되어야 합니다."
