"""
GitHub Actions 워크플로, 이슈·PR 템플릿, 코드 리뷰 룰 및 패키지 버전 정합성 검증 테스트
"""
import os
import re
import subprocess
from pathlib import Path
import tomllib
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

pytestmark = pytest.mark.unit


class TestGitHubWorkflows:
    """GitHub Actions CI/CD 워크플로 명세 및 보안 가드 검증"""

    def test_test_workflow_structure_and_security(self):
        """test.yml 워크플로의 트리거, 최소 권한 및 액션 SHA 핀을 검증합니다."""
        test_yml = REPO_ROOT / ".github" / "workflows" / "test.yml"
        assert test_yml.exists(), "test.yml 파일이 존재해야 합니다."

        content = yaml.safe_load(test_yml.read_text(encoding="utf-8"))
        assert content is not None

        # 트리거 검증
        on = content.get("on") or content.get(True) or {}
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
        on = content.get("on") or content.get(True) or {}
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

    def test_deploy_workflow_structure_and_security(self):
        """deploy.yml 워크플로의 main 브랜치 트리거, 최소 권한, Tailscale 액션 SHA 핀 및 원격 명령을 검증합니다."""
        deploy_yml = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
        assert deploy_yml.exists(), "deploy.yml 파일이 존재해야 합니다."

        content = yaml.safe_load(deploy_yml.read_text(encoding="utf-8"))
        assert content is not None

        # 트리거 검증
        on = content.get("on") or content.get(True) or {}
        assert "push" in on
        assert set(on["push"]["branches"]) == {"main"}

        # 최소 권한 원칙 검증
        permissions = content.get("permissions", {})
        assert permissions.get("contents") == "read", "deploy.yml은 contents: read 권한만 가져야 합니다."

        # 동시성 제어 검증: 배포 도중 중단되어 서버가 불완전해지지 않도록 직렬 실행한다
        concurrency = content.get("concurrency", {})
        assert concurrency.get("cancel-in-progress") is False

        # Job 및 스텝 검증
        jobs = content.get("jobs", {})
        assert "deploy" in jobs
        steps = jobs["deploy"]["steps"]

        sha_pattern = re.compile(r"^[a-zA-Z0-9_\-\./]+@[0-9a-f]{40}$")
        for step in steps:
            if "uses" in step:
                assert sha_pattern.match(step["uses"]), f"액션은 40자리 커밋 SHA로 고정되어야 합니다: {step['uses']}"

        tailscale_step = next(s for s in steps if "tailscale/github-action@" in s.get("uses", ""))
        tailscale_with = tailscale_step.get("with", {})
        assert "TAILSCALE_AUTHKEY" in str(tailscale_with.get("authkey", ""))
        assert "tag:ci" in str(tailscale_with.get("tags", ""))

        # DEPLOY_PATH 시크릿 사전 검증 스텝 존재 여부 검증 (공백 및 누락 시 SSH 진입 차단)
        validate_step = next(
            (s for s in steps if "DEPLOY_PATH" in s.get("env", {}) and "tailscale ssh" not in s.get("run", "")),
            None,
        )
        assert validate_step is not None, "러너 단계에서 DEPLOY_PATH 사전 검증 스텝이 존재해야 합니다."
        validate_run = validate_step.get("run", "")
        assert "DEPLOY_PATH" in validate_run
        assert "exit 1" in validate_run

        ssh_step = next(s for s in steps if "tailscale ssh" in s.get("run", ""))
        ssh_run = ssh_step.get("run", "")
        # 원격 서버 배포 디렉터리 존재 검사 선행 확인
        assert "! -d" in ssh_run
        assert ssh_run.index("! -d") < ssh_run.index("git reset --hard")

        assert "git fetch origin main" in ssh_run
        assert "git reset --hard origin/main" in ssh_run
        # 서버의 로컬 수정이 경고 없이 사라지지 않도록 reset 이전에 변경 검사가 선행되어야 한다
        assert "git status --porcelain" in ssh_run
        assert ssh_run.index("git status --porcelain") < ssh_run.index("git reset --hard")
        assert "./deploy.sh" in ssh_run
        assert "./check.sh" in ssh_run

        # 직전 정상 커밋 보관 및 자동 롤백 로직 검증
        assert "PREV_COMMIT=$(git rev-parse HEAD)" in ssh_run.replace("\\$", "$")
        assert 'git reset --hard "$PREV_COMMIT" && ./deploy.sh' in (
            ssh_run.replace("\\$", "$").replace('\\"', '"').replace("\\'", "'")
        )
        assert "exit 1" in ssh_run

    @pytest.mark.parametrize(
        ("val", "should_pass"),
        [
            ("", False),
            ("   ", False),
            (" \t\n ", False),
            ("/var/app/rag_accounting", True),
        ],
    )
    def test_deploy_path_runner_validation_execution(self, val: str, should_pass: bool):
        """러너 단계의 DEPLOY_PATH 유효성 검사 스크립트가 빈 값 및 공백을 거부하고 유효 경로만 허용하는지 실제 셸로 검증합니다 (#397)."""
        deploy_yml = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
        content = yaml.safe_load(deploy_yml.read_text(encoding="utf-8"))
        steps = content["jobs"]["deploy"]["steps"]
        validate_step = next(
            s for s in steps if "DEPLOY_PATH" in s.get("env", {}) and "tailscale ssh" not in s.get("run", "")
        )
        validate_run = validate_step["run"]

        env = os.environ.copy()
        env["DEPLOY_PATH"] = val
        proc = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", validate_run],
            env=env,
            capture_output=True,
            text=True,
        )
        assert (proc.returncode == 0) is should_pass
        if not should_pass:
            assert "오류: DEPLOY_PATH" in proc.stderr

    def test_deploy_path_runner_validation_unset_fails(self):
        """러너 단계에서 DEPLOY_PATH 환경변수가 아예 설정되지 않은 경우 실패해야 합니다 (#397)."""
        deploy_yml = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
        content = yaml.safe_load(deploy_yml.read_text(encoding="utf-8"))
        steps = content["jobs"]["deploy"]["steps"]
        validate_step = next(
            s for s in steps if "DEPLOY_PATH" in s.get("env", {}) and "tailscale ssh" not in s.get("run", "")
        )
        validate_run = validate_step["run"]

        env = os.environ.copy()
        env.pop("DEPLOY_PATH", None)
        proc = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", validate_run],
            env=env,
            capture_output=True,
            text=True,
        )
        assert proc.returncode != 0
        assert "오류: DEPLOY_PATH" in proc.stderr

    def test_deploy_workflow_remote_ssh_rollback_on_deploy_failure(self, tmp_path: Path):
        """원격 배포 스크립트 실행 중 deploy.sh 실패 시 직전 커밋으로 롤백하고 exit 1로 종료해야 합니다 (#397)."""
        deploy_yml = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
        content = yaml.safe_load(deploy_yml.read_text(encoding="utf-8"))
        steps = content["jobs"]["deploy"]["steps"]
        ssh_step = next(s for s in steps if "tailscale ssh" in s.get("run", ""))
        ssh_run = ssh_step["run"]

        mock_tailscale = tmp_path / "tailscale"
        mock_tailscale.write_text(
            '#!/bin/sh\nif [ "$1" = "ssh" ]; then\n  exec /usr/bin/env bash -c "$3"\nfi\nexit 0\n'
        )
        mock_tailscale.chmod(0o755)

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
        (repo / "version.txt").write_text("v1")
        deploy_sh = repo / "deploy.sh"
        deploy_sh.write_text('#!/bin/sh\necho "DEPLOYING $(cat version.txt)"\nexit 0\n')
        deploy_sh.chmod(0o755)
        check_sh = repo / "check.sh"
        check_sh.write_text("#!/bin/sh\nexit 0\n")
        check_sh.chmod(0o755)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "commit 1"], cwd=repo, check=True)
        v1_hash = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
            .stdout.strip()
        )

        origin = tmp_path / "origin"
        subprocess.run(["git", "clone", "--bare", str(repo), str(origin)], check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", str(origin)], cwd=repo, check=True)

        work2 = tmp_path / "work2"
        subprocess.run(["git", "clone", str(origin), str(work2)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=work2, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=work2, check=True)
        (work2 / "version.txt").write_text("v2")
        (work2 / "deploy.sh").write_text('#!/bin/sh\necho "FAILING DEPLOY"\nexit 1\n')
        (work2 / "deploy.sh").chmod(0o755)
        subprocess.run(["git", "add", "."], cwd=work2, check=True)
        subprocess.run(["git", "commit", "-m", "commit 2"], cwd=work2, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=work2, check=True)

        env = os.environ.copy()
        cur_path = env["PATH"]
        env["PATH"] = f"{tmp_path}:{cur_path}"
        env["DEPLOY_USER"] = "root"
        env["DEPLOY_HOST"] = "testhost"
        env["DEPLOY_PATH"] = str(repo)

        proc = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", ssh_run],
            env=env,
            capture_output=True,
            text=True,
        )
        cur_hash = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
            .stdout.strip()
        )
        assert proc.returncode == 1
        assert cur_hash == v1_hash
        assert "배포 또는 점검 실패: 직전 커밋으로 자동 롤백을 수행합니다." in proc.stderr

    def test_deploy_workflow_remote_ssh_rollback_on_check_failure(self, tmp_path: Path):
        """원격 배포 스크립트 실행 중 check.sh 실패 시 직전 커밋으로 롤백하고 exit 1로 종료해야 합니다 (#397)."""
        deploy_yml = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
        content = yaml.safe_load(deploy_yml.read_text(encoding="utf-8"))
        steps = content["jobs"]["deploy"]["steps"]
        ssh_step = next(s for s in steps if "tailscale ssh" in s.get("run", ""))
        ssh_run = ssh_step["run"]

        mock_tailscale = tmp_path / "tailscale"
        mock_tailscale.write_text(
            '#!/bin/sh\nif [ "$1" = "ssh" ]; then\n  exec /usr/bin/env bash -c "$3"\nfi\nexit 0\n'
        )
        mock_tailscale.chmod(0o755)

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
        (repo / "version.txt").write_text("v1")
        deploy_sh = repo / "deploy.sh"
        deploy_sh.write_text('#!/bin/sh\necho "DEPLOYING $(cat version.txt)"\nexit 0\n')
        deploy_sh.chmod(0o755)
        check_sh = repo / "check.sh"
        check_sh.write_text("#!/bin/sh\nexit 0\n")
        check_sh.chmod(0o755)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "commit 1"], cwd=repo, check=True)
        v1_hash = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
            .stdout.strip()
        )

        origin = tmp_path / "origin"
        subprocess.run(["git", "clone", "--bare", str(repo), str(origin)], check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", str(origin)], cwd=repo, check=True)

        work2 = tmp_path / "work2"
        subprocess.run(["git", "clone", str(origin), str(work2)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=work2, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=work2, check=True)
        (work2 / "version.txt").write_text("v2")
        (work2 / "deploy.sh").write_text('#!/bin/sh\nexit 0\n')
        (work2 / "deploy.sh").chmod(0o755)
        (work2 / "check.sh").write_text('#!/bin/sh\necho "FAILING CHECK"\nexit 1\n')
        (work2 / "check.sh").chmod(0o755)
        subprocess.run(["git", "add", "."], cwd=work2, check=True)
        subprocess.run(["git", "commit", "-m", "commit 2"], cwd=work2, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=work2, check=True)

        env = os.environ.copy()
        cur_path = env["PATH"]
        env["PATH"] = f"{tmp_path}:{cur_path}"
        env["DEPLOY_USER"] = "root"
        env["DEPLOY_HOST"] = "testhost"
        env["DEPLOY_PATH"] = str(repo)

        proc = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", ssh_run],
            env=env,
            capture_output=True,
            text=True,
        )
        cur_hash = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
            .stdout.strip()
        )
        assert proc.returncode == 1
        assert cur_hash == v1_hash
        assert "배포 또는 점검 실패: 직전 커밋으로 자동 롤백을 수행합니다." in proc.stderr

    def test_deploy_workflow_remote_ssh_rollback_failure_warns_and_exits_one(self, tmp_path: Path):
        """원격 배포 스크립트 실행 중 배포 실패 후 자동 롤백 스크립트(deploy.sh) 실행마저 실패할 경우 경고를 출력하고 exit 1로 종료해야 합니다 (#397)."""
        deploy_yml = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
        content = yaml.safe_load(deploy_yml.read_text(encoding="utf-8"))
        steps = content["jobs"]["deploy"]["steps"]
        ssh_step = next(s for s in steps if "tailscale ssh" in s.get("run", ""))
        ssh_run = ssh_step["run"]

        mock_tailscale = tmp_path / "tailscale"
        mock_tailscale.write_text(
            '#!/bin/sh\nif [ "$1" = "ssh" ]; then\n  exec /usr/bin/env bash -c "$3"\nfi\nexit 0\n'
        )
        mock_tailscale.chmod(0o755)

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
        (repo / "version.txt").write_text("v1")
        deploy_sh = repo / "deploy.sh"
        deploy_sh.write_text('#!/bin/sh\necho "FAILING ROLLBACK DEPLOY" >&2\nexit 1\n')
        deploy_sh.chmod(0o755)
        check_sh = repo / "check.sh"
        check_sh.write_text("#!/bin/sh\nexit 0\n")
        check_sh.chmod(0o755)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "commit 1"], cwd=repo, check=True)
        v1_hash = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
            .stdout.strip()
        )

        origin = tmp_path / "origin"
        subprocess.run(["git", "clone", "--bare", str(repo), str(origin)], check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", str(origin)], cwd=repo, check=True)

        work2 = tmp_path / "work2"
        subprocess.run(["git", "clone", str(origin), str(work2)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=work2, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=work2, check=True)
        (work2 / "version.txt").write_text("v2")
        (work2 / "deploy.sh").write_text('#!/bin/sh\necho "FAILING NEW DEPLOY" >&2\nexit 1\n')
        (work2 / "deploy.sh").chmod(0o755)
        subprocess.run(["git", "add", "."], cwd=work2, check=True)
        subprocess.run(["git", "commit", "-m", "commit 2"], cwd=work2, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=work2, check=True)

        env = os.environ.copy()
        cur_path = env["PATH"]
        env["PATH"] = f"{tmp_path}:{cur_path}"
        env["DEPLOY_USER"] = "root"
        env["DEPLOY_HOST"] = "testhost"
        env["DEPLOY_PATH"] = str(repo)

        proc = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", ssh_run],
            env=env,
            capture_output=True,
            text=True,
        )
        cur_hash = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
            .stdout.strip()
        )
        assert proc.returncode == 1
        assert cur_hash == v1_hash
        assert "배포 또는 점검 실패: 직전 커밋으로 자동 롤백을 수행합니다." in proc.stderr
        assert "경고: 직전 커밋으로의 자동 롤백 스크립트 실행 중 오류가 발생했습니다." in proc.stderr

    def test_deploy_workflow_remote_ssh_success(self, tmp_path: Path):
        """원격 배포 스크립트 실행 중 deploy.sh와 check.sh 모두 성공 시 신규 커밋으로 정상 갱신되고 exit 0으로 종료해야 합니다 (#397)."""
        deploy_yml = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
        content = yaml.safe_load(deploy_yml.read_text(encoding="utf-8"))
        steps = content["jobs"]["deploy"]["steps"]
        ssh_step = next(s for s in steps if "tailscale ssh" in s.get("run", ""))
        ssh_run = ssh_step["run"]

        mock_tailscale = tmp_path / "tailscale"
        mock_tailscale.write_text(
            '#!/bin/sh\nif [ "$1" = "ssh" ]; then\n  exec /usr/bin/env bash -c "$3"\nfi\nexit 0\n'
        )
        mock_tailscale.chmod(0o755)

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
        (repo / "version.txt").write_text("v1")
        deploy_sh = repo / "deploy.sh"
        deploy_sh.write_text('#!/bin/sh\nexit 0\n')
        deploy_sh.chmod(0o755)
        check_sh = repo / "check.sh"
        check_sh.write_text("#!/bin/sh\nexit 0\n")
        check_sh.chmod(0o755)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "commit 1"], cwd=repo, check=True)

        origin = tmp_path / "origin"
        subprocess.run(["git", "clone", "--bare", str(repo), str(origin)], check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", str(origin)], cwd=repo, check=True)

        work2 = tmp_path / "work2"
        subprocess.run(["git", "clone", str(origin), str(work2)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=work2, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=work2, check=True)
        (work2 / "version.txt").write_text("v2")
        subprocess.run(["git", "add", "."], cwd=work2, check=True)
        subprocess.run(["git", "commit", "-m", "commit 2"], cwd=work2, check=True)
        v2_hash = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=work2, check=True, capture_output=True, text=True)
            .stdout.strip()
        )
        subprocess.run(["git", "push", "origin", "main"], cwd=work2, check=True)

        env = os.environ.copy()
        cur_path = env["PATH"]
        env["PATH"] = f"{tmp_path}:{cur_path}"
        env["DEPLOY_USER"] = "root"
        env["DEPLOY_HOST"] = "testhost"
        env["DEPLOY_PATH"] = str(repo)

        proc = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", ssh_run],
            env=env,
            capture_output=True,
            text=True,
        )
        cur_hash = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
            .stdout.strip()
        )
        assert proc.returncode == 0
        assert cur_hash == v2_hash
        assert "자동 롤백" not in proc.stderr

    def test_deploy_workflow_remote_ssh_directory_not_found(self, tmp_path: Path):
        """원격 서버에 배포 디렉터리가 존재하지 않는 경우 즉시 exit 1로 종료해야 합니다 (#397)."""
        deploy_yml = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
        content = yaml.safe_load(deploy_yml.read_text(encoding="utf-8"))
        steps = content["jobs"]["deploy"]["steps"]
        ssh_step = next(s for s in steps if "tailscale ssh" in s.get("run", ""))
        ssh_run = ssh_step["run"]

        mock_tailscale = tmp_path / "tailscale"
        mock_tailscale.write_text(
            '#!/bin/sh\nif [ "$1" = "ssh" ]; then\n  exec /usr/bin/env bash -c "$3"\nfi\nexit 0\n'
        )
        mock_tailscale.chmod(0o755)

        env = os.environ.copy()
        cur_path = env["PATH"]
        env["PATH"] = f"{tmp_path}:{cur_path}"
        env["DEPLOY_USER"] = "root"
        env["DEPLOY_HOST"] = "testhost"
        env["DEPLOY_PATH"] = str(tmp_path / "nonexistent_dir")

        proc = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", ssh_run],
            env=env,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 1
        assert "오류: 원격 서버에 배포 디렉터리가 존재하지 않습니다." in proc.stderr

    def test_deploy_workflow_remote_ssh_dirty_working_tree_aborts(self, tmp_path: Path):
        """원격 서버 체크아웃에 커밋되지 않은 변경이 있을 경우 작업 손실을 막기 위해 즉시 exit 1로 중단해야 합니다 (#397)."""
        deploy_yml = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
        content = yaml.safe_load(deploy_yml.read_text(encoding="utf-8"))
        steps = content["jobs"]["deploy"]["steps"]
        ssh_step = next(s for s in steps if "tailscale ssh" in s.get("run", ""))
        ssh_run = ssh_step["run"]

        mock_tailscale = tmp_path / "tailscale"
        mock_tailscale.write_text(
            '#!/bin/sh\nif [ "$1" = "ssh" ]; then\n  exec /usr/bin/env bash -c "$3"\nfi\nexit 0\n'
        )
        mock_tailscale.chmod(0o755)

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
        (repo / "version.txt").write_text("v1")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "commit 1"], cwd=repo, check=True)
        (repo / "version.txt").write_text("modified_locally")

        env = os.environ.copy()
        cur_path = env["PATH"]
        env["PATH"] = f"{tmp_path}:{cur_path}"
        env["DEPLOY_USER"] = "root"
        env["DEPLOY_HOST"] = "testhost"
        env["DEPLOY_PATH"] = str(repo)

        proc = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", ssh_run],
            env=env,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 1
        assert "서버 체크아웃에 커밋되지 않은 변경이 있어 배포를 중단합니다." in proc.stderr
        assert (repo / "version.txt").read_text() == "modified_locally"



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

    def test_contributing_guide_contains_code_naming_conventions(self):
        """CONTRIBUTING.md에 코드 네이밍 및 스타일 컨벤션 명세가 포함되어 있는지 검증합니다."""
        contributing = REPO_ROOT / "CONTRIBUTING.md"
        assert contributing.exists(), "CONTRIBUTING.md가 존재해야 합니다."
        text = contributing.read_text(encoding="utf-8")
        assert "코드 네이밍 및 스타일 컨벤션" in text
        assert "snake_case" in text
        assert "PascalCase" in text
        assert "SNAKE_CASE" in text


class TestProjectVersionAndLinterConfig:
    """pyproject.toml 버전 및 ruff 린터 설정 검증"""

    def test_pyproject_version_and_ruff_settings(self):
        """pyproject.toml 버전이 1.1.2이며 ruff 의존성 및 설정이 올바르게 정의되어 있는지 검증합니다."""
        pyproject_file = REPO_ROOT / "pyproject.toml"
        assert pyproject_file.exists()

        data = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))
        assert data.get("project", {}).get("version") == "1.1.2", "패키지 버전은 1.1.2이어야 합니다."

        dev_deps = data.get("dependency-groups", {}).get("dev", [])
        assert any("ruff" in dep for dep in dev_deps), "dev 의존성 그룹에 ruff가 포함되어야 합니다."

        tool_ruff = data.get("tool", {}).get("ruff", {})
        assert tool_ruff.get("line-length") == 120
        lint_select = tool_ruff.get("lint", {}).get("select", [])
        assert set(lint_select) == {"E9", "F63", "F7", "F82", "C901"}

