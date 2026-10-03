"""
GitHub Actions 워크플로, 이슈·PR 템플릿, 코드 리뷰 룰 및 패키지 버전 정합성 검증 테스트
"""
import re
from pathlib import Path
import tomllib
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.unit
class TestGitHubWorkflows:
    """GitHub Actions CI/CD 워크플로 명세 및 보안 가드 검증"""

    def test_test_workflow_structure_and_security(self):
        """test.yml 워크플로의 트리거, 최소 권한 및 액션 SHA 핀을 검증합니다."""
        test_yml = REPO_ROOT / ".github" / "workflows" / "test.yml"
        assert test_yml.exists(), "test.yml 파일이 존재해야 합니다."

        content = yaml.safe_load(test_yml.read_text(encoding="utf-8"))
        assert content is not None

        # 트리거 검증
        on = content.get("on", {})
        assert "push" in on and "pull_request" in on
        assert set(on["push"]["branches"]) == {"dev", "main"}
        assert set(on["pull_request"]["branches"]) == {"dev", "main"}

        # 최소 권한 원칙 검증
        permissions = content.get("permissions", {})
        assert permissions.get("contents") == "read", "test.yml은 contents: read 권한만 가져야 합니다."

        # Job 및 스텝 검증
        jobs = content.get("jobs", {})
        assert "test" in jobs
        steps = jobs["test"]["steps"]

        sha_pattern = re.compile(r"^[a-zA-Z0-9_\-\./]+@[0-9a-f]{40}$")
        action_steps = [s["uses"] for s in steps if "uses" in s]
        for action in action_steps:
            assert sha_pattern.match(action), f"서드파티 액션은 40자리 커밋 SHA로 고정되어야 합니다: {action}"

        # 필수 액션 및 명령어 스텝 포함 여부 검증
        uses_str = " ".join(action_steps)
        assert "actions/checkout@" in uses_str
        assert "astral-sh/setup-uv@" in uses_str

        run_cmds = [s["run"] for s in steps if "run" in s]
        run_cmds_str = "\n".join(run_cmds)
        assert "uv sync" in run_cmds_str
        assert "--extra ingest" in run_cmds_str
        assert "ruff check" in run_cmds_str
        assert 'pytest -m "not benchmark"' in run_cmds_str

    def test_release_workflow_structure_and_security(self):
        """release.yml 워크플로의 태그 트리거, 쓰기 권한, 릴리즈 옵션을 검증합니다."""
        release_yml = REPO_ROOT / ".github" / "workflows" / "release.yml"
        assert release_yml.exists(), "release.yml 파일이 존재해야 합니다."

        content = yaml.safe_load(release_yml.read_text(encoding="utf-8"))
        assert content is not None

        # 태그 트리거 검증
        on = content.get("on", {})
        assert "push" in on and "tags" in on["push"]
        assert "v*.*.*" in on["push"]["tags"]

        # 릴리즈 생성을 위한 쓰기 권한 검증
        permissions = content.get("permissions", {})
        assert permissions.get("contents") == "write", "release.yml은 contents: write 권한이 필수적입니다."

        # 서드파티 액션 SHA 고정 및 옵션 검증
        jobs = content.get("jobs", {})
        assert "release" in jobs
        steps = jobs["release"]["steps"]

        sha_pattern = re.compile(r"^[a-zA-Z0-9_\-\./]+@[0-9a-f]{40}$")
        for step in steps:
            if "uses" in step:
                assert sha_pattern.match(step["uses"]), f"액션은 40자리 커밋 SHA로 고정되어야 합니다: {step['uses']}"

        checkout_step = next(s for s in steps if "actions/checkout@" in s.get("uses", ""))
        assert checkout_step.get("with", {}).get("fetch-depth") == 0, "전체 태그 및 히스토리 조회를 위해 fetch-depth는 0이어야 합니다."

        release_step = next(s for s in steps if "softprops/action-gh-release@" in s.get("uses", ""))
        release_with = release_step.get("with", {})
        assert release_with.get("generate_release_notes") is True


@pytest.mark.unit
class TestIssueAndPRTemplates:
    """이슈 및 PR 템플릿, CODEOWNERS, 기여 가이드 구조 검증"""

    def test_issue_templates_structure(self):
        """이슈 템플릿 4종 파일 및 필수 4개 섹션(배경, 해야 할 일, 종료 조건, 특이사항)을 검증합니다."""
        template_dir = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"
        assert template_dir.is_dir()

        config_file = template_dir / "config.yml"
        assert config_file.exists()
        config_data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert config_data.get("blank_issues_enabled") is True

        required_templates = ["task.md", "bug.md", "discuss.md"]
        required_sections = ["## 배경", "## 해야 할 일", "## 종료 조건", "## 특이사항"]

        for filename in required_templates:
            filepath = template_dir / filename
            assert filepath.exists(), f"{filename} 템플릿이 존재해야 합니다."
            text = filepath.read_text(encoding="utf-8")
            for sec in required_sections:
                assert sec in text, f"{filename}에 {sec} 섹션이 포함되어야 합니다."
            assert "BLUF" not in text and "한 줄 요약" not in text, f"{filename}에는 BLUF나 한 줄 요약이 포함되지 않아야 합니다."

    def test_pr_template_and_codeowners(self):
        """pull_request_template.md 및 CODEOWNERS 파일의 무결성을 검증합니다."""
        pr_template = REPO_ROOT / ".github" / "pull_request_template.md"
        assert pr_template.exists(), "pull_request_template.md가 존재해야 합니다."
        pr_text = pr_template.read_text(encoding="utf-8")
        assert "정확성" in pr_text
        assert "가독성" in pr_text
        assert "외부 의존" in pr_text

        codeowners = REPO_ROOT / ".github" / "CODEOWNERS"
        assert codeowners.exists(), "CODEOWNERS 파일이 존재해야 합니다."
        assert len(codeowners.read_text(encoding="utf-8").strip()) > 0

    def test_contributing_guide_contains_code_review_rules(self):
        """CONTRIBUTING.md에 함수 단위 코드 리뷰 룰 및 3축 기준이 명시되어 있는지 검증합니다."""
        contributing = REPO_ROOT / "CONTRIBUTING.md"
        assert contributing.exists(), "CONTRIBUTING.md가 존재해야 합니다."
        text = contributing.read_text(encoding="utf-8")
        assert "함수 단위 코드 리뷰" in text
        assert "정확성" in text
        assert "가독성" in text
        assert "외부 의존" in text


@pytest.mark.unit
class TestProjectVersionAndLinterConfig:
    """pyproject.toml 버전 및 ruff 린터 설정 검증"""

    def test_pyproject_version_and_ruff_settings(self):
        """pyproject.toml 버전이 1.1.0이며 ruff 의존성 및 설정이 올바르게 정의되어 있는지 검증합니다."""
        pyproject_file = REPO_ROOT / "pyproject.toml"
        assert pyproject_file.exists()

        data = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))
        assert data.get("project", {}).get("version") == "1.1.0", "패키지 버전은 1.1.0이어야 합니다."

        dev_deps = data.get("dependency-groups", {}).get("dev", [])
        assert any("ruff" in dep for dep in dev_deps), "dev 의존성 그룹에 ruff가 포함되어야 합니다."

        tool_ruff = data.get("tool", {}).get("ruff", {})
        assert tool_ruff.get("line-length") == 120
        lint_select = tool_ruff.get("lint", {}).get("select", [])
        assert set(lint_select) == {"E9", "F63", "F7", "F82"}
