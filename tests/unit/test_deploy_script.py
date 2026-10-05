"""
tests/unit/test_deploy_script.py: deploy.sh 스크립트 기능 및 동작 무결성 단위 테스트.

[테스트 목적]
이슈 #323 요구사항에 따라 신설된 deploy.sh의 동작을 검증합니다:
1. bash 문법 유효성 및 도움말(-h/--help)
2. .env 부재, 런타임 부재 시 안전한 실패 처리
3. DB 및 임베딩 인프라 미가동 또는 미준비 시 조기 중단 및 ./install.sh 안내
4. Docker Compose 및 Podman 환경별 증분 빌드·배포 호출 규약
5. --no-cache 플래그 전달 시 build --no-cache app 호출
6. 앱 헬스체크 실패 시 최근 50줄 컨테이너 로그(logs --tail=50 app) 출력
7. .dockerignore 필수 경로 제외 및 Dockerfile 패키지 캐시 마운트 정적 검증
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.utils.shell_test_helpers import (
    BASH_PATH as _BASH,
    make_bin as _make_bin,
    make_mock_env as _make_mock_env,
    run_shell as _run_shell,
    to_posix_path,
)

_ROOT = Path(__file__).resolve().parents[2]
_DEPLOY_SH = _ROOT / "deploy.sh"
_DOCKERIGNORE = _ROOT / ".dockerignore"
_DOCKERFILE = _ROOT / "Dockerfile"


@pytest.mark.unit
def test_deploy_bash_syntax():
    """deploy.sh의 bash 문법 오류 여부를 정적으로 검증합니다."""
    proc = subprocess.run([_BASH, "-n", str(_DEPLOY_SH)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0, f"deploy.sh 문법 오류: {proc.stderr}"


@pytest.mark.unit
@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_deploy_help(flag: str):
    """deploy.sh -h 및 --help 실행 시 사용법을 출력하고 0으로 정상 종료해야 합니다."""
    proc = subprocess.run([_BASH, str(_DEPLOY_SH), flag], cwd=_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0
    assert "사용법: " in proc.stdout
    assert "--no-cache" in proc.stdout
    assert "app 컨테이너" in proc.stdout
    assert "./install.sh" in proc.stdout


@pytest.mark.unit
def test_deploy_unknown_arg():
    """deploy.sh에 정의되지 않은 인자 전달 시 에러 메시지를 출력하고 종료 코드 1로 실패해야 합니다."""
    proc = subprocess.run(
        [_BASH, str(_DEPLOY_SH), "--invalid-option"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 1
    assert "오류: 알 수 없는 인자" in proc.stderr
    assert "사용법: " in proc.stderr


@pytest.mark.unit
def test_deploy_missing_curl(tmp_path: Path):
    """curl이 PATH에 없으면 에러 메시지를 출력하고 종료 코드 1로 실패해야 합니다."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")

    dirname_stub = """#!/bin/sh
case "$1" in
  */*) echo "${1%/*}" ;;
  *) echo "." ;;
esac
"""
    bash_stub = f"""#!/bin/sh
exec "{to_posix_path(_BASH)}" "$@"
"""
    bin_dir = _make_bin(
        tmp_path,
        {
            "bash": bash_stub,
            "dirname": dirname_stub,
            "docker": "#!/bin/sh\nexit 0\n",
        },
    )
    env = _make_mock_env(bin_dir, isolate=True, include_system_paths=False)

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 1
    assert "curl이 존재하지 않습니다" in proc.stderr





@pytest.mark.unit
def test_deploy_missing_env(tmp_path: Path):
    """.env 파일이 없으면 에러를 출력하고 ./install.sh 실행을 안내하며 종료해야 합니다."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")

    bin_dir = _make_bin(
        tmp_path,
        {
            "docker": "#!/bin/sh\nif [ \"$1\" = 'compose' ] && [ \"$2\" = 'version' ]; then echo 'Docker Compose version v2.39.0'; fi\nexit 0\n",
            "curl": "#!/bin/sh\nexit 0\n",
        },
    )
    env = _make_mock_env(bin_dir, isolate=True)

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 1
    assert ".env 파일이 존재하지 않습니다" in proc.stderr
    assert "./install.sh" in proc.stderr


@pytest.mark.unit
def test_deploy_missing_runtime(tmp_path: Path):
    """컨테이너 런타임(Docker/Podman)이 설치되어 있지 않으면 힌트를 출력하고 실패해야 합니다."""
    work = tmp_path / "repo"
    # shutil.copytree: 실제 저장소 루트의 scripts 폴더를 pytest 임시 격리 디렉터리(work/scripts)로 복사하여,
    # 실제 프로젝트 파일의 오염 없이 안전하게 독립 가상 환경에서 셸 스크립트 실행을 검증합니다.
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n")

    bin_dir = _make_bin(tmp_path, {"curl": "#!/bin/sh\nexit 0\n"})
    env = _make_mock_env(bin_dir, isolate=True)

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 1
    assert "compose를 지원하는 컨테이너 런타임을 찾을 수 없습니다" in proc.stderr


@pytest.mark.unit
def test_deploy_fails_if_db_not_running(tmp_path: Path):
    """database(accounting_db) 컨테이너가 실행 중이 아니면 조기 중단하고 ./install.sh를 안내해야 합니다."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n")

    docker_stub = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"; exit 0
fi
if [ "$1" = "inspect" ]; then
  case "$*" in
    *accounting_db*) echo "exited"; exit 0 ;;
    *) echo "running"; exit 0 ;;
  esac
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": docker_stub, "curl": "#!/bin/sh\nexit 0\n"})
    env = _make_mock_env(bin_dir, isolate=True)

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 1
    assert "필수 인프라 컨테이너(accounting_db)가 실행 중이지 않습니다" in proc.stderr
    assert "./install.sh" in proc.stderr


@pytest.mark.unit
def test_deploy_fails_if_embedding_not_running(tmp_path: Path):
    """embedding(accounting_embedding) 컨테이너가 실행 중이 아니면 조기 중단하고 ./install.sh를 안내해야 합니다."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n")

    docker_stub = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"; exit 0
fi
if [ "$1" = "inspect" ]; then
  case "$*" in
    *accounting_embedding*) echo "missing"; exit 1 ;;
    *) echo "running"; exit 0 ;;
  esac
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": docker_stub, "curl": "#!/bin/sh\nexit 0\n"})
    env = _make_mock_env(bin_dir, isolate=True)

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 1
    assert "필수 인프라 컨테이너(accounting_embedding)가 실행 중이지 않습니다" in proc.stderr
    assert "./install.sh" in proc.stderr


@pytest.mark.unit
def test_deploy_custom_embedding_container_name(tmp_path: Path):
    """EMBEDDING_CONTAINER 환경 변수로 지정된 커스텀 컨테이너명을 검사해야 합니다."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n")

    log_file = tmp_path / "docker_inspect.log"
    docker_stub = f"""#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"; exit 0
fi
if [ "$1" = "inspect" ]; then
  echo "$@" >> "{log_file}"
  case "$*" in
    *custom_embedding*) echo "missing"; exit 1 ;;
    *) echo "running"; exit 0 ;;
  esac
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": docker_stub, "curl": "#!/bin/sh\nexit 0\n"})
    env = _make_mock_env(bin_dir, isolate=True)
    env["EMBEDDING_CONTAINER"] = "custom_embedding"

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 1
    assert "필수 인프라 컨테이너(custom_embedding)가 실행 중이지 않습니다" in proc.stderr
    assert "./install.sh" in proc.stderr

    # custom_embedding 컨테이너를 실제로 검사했고, 기본값인 accounting_embedding은 검사하지 않았는지 확인
    calls = log_file.read_text().splitlines()
    assert any("custom_embedding" in c for c in calls)
    assert not any("accounting_embedding" in c for c in calls)


@pytest.mark.unit
def test_deploy_custom_embedding_container_name_success(tmp_path: Path):
    """EMBEDDING_CONTAINER 환경 변수로 지정된 커스텀 컨테이너가 정상 실행 중일 때 배포가 정상 통과하는지 검증합니다."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n")

    log_file = tmp_path / "docker_inspect.log"
    docker_stub = f"""#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"; exit 0
fi
if [ "$1" = "inspect" ]; then
  echo "$@" >> "{log_file}"
  echo "running"; exit 0
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": docker_stub, "curl": "#!/bin/sh\nexit 0\n"})
    env = _make_mock_env(bin_dir, isolate=True)
    env["EMBEDDING_CONTAINER"] = "custom_embedding"

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 0
    assert "배포 완료: app 컨테이너가 성공적으로 갱신되었습니다" in proc.stdout

    # custom_embedding 컨테이너를 실제로 검사했고, 기본값인 accounting_embedding은 검사하지 않았는지 확인
    calls = log_file.read_text().splitlines()
    assert any("custom_embedding" in c for c in calls)
    assert not any("accounting_embedding" in c for c in calls)


@pytest.mark.unit
def test_deploy_fails_if_embedding_health_fails(tmp_path: Path):
    """DB와 임베딩 컨테이너는 떠 있으나 TEI 웜업이 미완료되어 /health가 실패하면 조기 중단해야 합니다."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n")

    docker_stub = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"; exit 0
fi
if [ "$1" = "inspect" ]; then
  echo "running"; exit 0
fi
exit 0
"""
    curl_stub = """#!/bin/sh
# 임베딩 서버 헬스체크 주소이면 실패(exit 1) 반환
for arg in "$@"; do
  case "$arg" in
    *8080/health*) exit 1 ;;
  esac
done
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": docker_stub, "curl": curl_stub})
    env = _make_mock_env(bin_dir, isolate=True)
    env["DEPLOY_EMBEDDING_WAIT_SECONDS"] = "0"

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 1
    assert "임베딩 서버(http://localhost:8080)가 정상 응답하지 않습니다" in proc.stderr
    assert "TEI 웜업이 완료될 때까지 대기하거나 ./install.sh" in proc.stderr


@pytest.mark.unit
def test_deploy_docker_compose_flow(tmp_path: Path):
    """Docker 환경에서 deploy.sh 실행 시 build app -> up -d --no-deps app 순으로 호출해야 합니다."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=3000\nEMBEDDING_HOST_PORT=8080\n")

    log_file = tmp_path / "docker_calls.log"
    docker_stub = f"""#!/bin/sh
echo "$@" >> "{log_file}"
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"; exit 0
fi
if [ "$1" = "inspect" ]; then
  echo "running"; exit 0
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": docker_stub, "curl": "#!/bin/sh\nexit 0\n"})
    env = _make_mock_env(bin_dir, isolate=True)
    env.pop("APP_HOST_PORT", None)
    env.pop("EMBEDDING_HOST_PORT", None)

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 0
    assert "배포 완료: app 컨테이너가 성공적으로 갱신되었습니다" in proc.stdout
    assert "http://localhost:3000" in proc.stdout

    calls = log_file.read_text().splitlines()
    # compose build app 호출 검증
    assert any("compose build app" in c for c in calls)
    # compose up -d --no-deps app 호출 검증
    assert any("compose up -d --no-deps app" in c for c in calls)

    # compose build app이 compose up보다 먼저 실행되었는지 호출 순서 검증
    build_idx = next(i for i, c in enumerate(calls) if "compose build app" in c)
    up_idx = next(i for i, c in enumerate(calls) if "compose up -d --no-deps app" in c)
    assert build_idx < up_idx, "compose build app이 compose up -d --no-deps app보다 먼저 실행되어야 합니다."

    # database나 embedding이 build나 up 대상에 포함되지 않았는지 검증
    assert not any("build database" in c or "build embedding" in c for c in calls)


@pytest.mark.unit
def test_deploy_podman_compose_flow(tmp_path: Path):
    """Podman 환경에서 deploy.sh 실행 시 accounting_app 단독 stop/rm 및 up -d --no-deps app을 호출해야 합니다 (#399)."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n")

    compose_log = tmp_path / "podman_compose_calls.log"
    podman_log = tmp_path / "podman_calls.log"
    podman_compose_stub = f"""#!/bin/sh
echo "$@" >> "{compose_log}"
exit 0
"""
    podman_stub = f"""#!/bin/sh
echo "$@" >> "{podman_log}"
if [ "$1" = "inspect" ]; then
  echo "running"; exit 0
fi
exit 0
"""
    bin_dir = _make_bin(
        tmp_path,
        {
            "podman-compose": podman_compose_stub,
            "podman": podman_stub,
            "curl": "#!/bin/sh\nexit 0\n",
        },
    )
    env = _make_mock_env(bin_dir, isolate=True)

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 0

    compose_calls = compose_log.read_text().splitlines()
    podman_calls = podman_log.read_text().splitlines()

    assert any("build app" in c for c in compose_calls)
    assert any("up -d --no-deps app" in c for c in compose_calls)
    assert not any("--force-recreate" in c for c in compose_calls)

    # accounting_app 컨테이너 단독 stop 및 rm 호출 검증
    assert any("stop accounting_app" in c for c in podman_calls)
    assert any("rm accounting_app" in c for c in podman_calls)

    # accounting_db 및 accounting_embedding은 stop/rm 대상에서 제외되어야 함
    assert not any("stop accounting_db" in c or "stop accounting_embedding" in c for c in podman_calls)
    assert not any("rm accounting_db" in c or "rm accounting_embedding" in c for c in podman_calls)


@pytest.mark.unit
def test_deploy_podman_custom_app_container(tmp_path: Path):
    """APP_CONTAINER 환경변수 지정 시 해당 컨테이너명을 대상으로 stop/rm을 수행해야 합니다 (#399)."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n")

    podman_log = tmp_path / "podman_calls.log"
    podman_compose_stub = """#!/bin/sh
exit 0
"""
    podman_stub = f"""#!/bin/sh
echo "$@" >> "{podman_log}"
if [ "$1" = "inspect" ]; then
  echo "running"; exit 0
fi
exit 0
"""
    bin_dir = _make_bin(
        tmp_path,
        {
            "podman-compose": podman_compose_stub,
            "podman": podman_stub,
            "curl": "#!/bin/sh\nexit 0\n",
        },
    )
    env = _make_mock_env(bin_dir, isolate=True)
    env["APP_CONTAINER"] = "custom_accounting_app"

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 0

    podman_calls = podman_log.read_text().splitlines()
    assert any("stop custom_accounting_app" in c for c in podman_calls)
    assert any("rm custom_accounting_app" in c for c in podman_calls)
    assert not any("stop accounting_app" in c for c in podman_calls)


@pytest.mark.unit
def test_deploy_docker_does_not_stop_rm_app(tmp_path: Path):
    """Docker 환경에서는 compose up이 직접 컨테이너 교체를 관장하므로 별도 stop/rm을 호출하지 않아야 합니다."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n")

    docker_log = tmp_path / "docker_calls.log"
    docker_stub = f"""#!/bin/sh
echo "$@" >> "{docker_log}"
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"; exit 0
fi
if [ "$1" = "inspect" ]; then
  echo "running"; exit 0
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": docker_stub, "curl": "#!/bin/sh\nexit 0\n"})
    env = _make_mock_env(bin_dir, isolate=True)

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 0

    docker_calls = docker_log.read_text().splitlines()
    assert not any("stop" in c or "rm" in c for c in docker_calls)


@pytest.mark.unit
def test_deploy_delegating_podman_without_podman_cli_stops_rms_app(tmp_path: Path):
    """Podman 4.7+ 위임 환경에서 podman CLI가 없더라도 docker 래퍼를 통해 accounting_app 단독 stop/rm을 수행해야 합니다 (#399)."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n")

    docker_log = tmp_path / "docker_calls.log"
    docker_stub = f"""#!/bin/sh
echo "$@" >> "{docker_log}"
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo '>>>> 외부 compose 제공자 "/usr/bin/podman-compose" 실행 중' >&2
  echo "podman-compose version 1.0.6"
  exit 0
fi
if [ "$1" = "inspect" ]; then
  echo "running"; exit 0
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": docker_stub, "curl": "#!/bin/sh\nexit 0\n"})
    env = _make_mock_env(bin_dir, isolate=True)

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 0

    docker_calls = docker_log.read_text().splitlines()
    assert any("stop accounting_app" in c for c in docker_calls)
    assert any("rm accounting_app" in c for c in docker_calls)
    assert not any("stop accounting_db" in c or "stop accounting_embedding" in c for c in docker_calls)
    assert not any("rm accounting_db" in c or "rm accounting_embedding" in c for c in docker_calls)


@pytest.mark.unit
def test_deploy_no_cache_flag(tmp_path: Path):
    """--no-cache 플래그 전달 시 compose build에 --no-cache 옵션이 전달되어야 합니다."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n")

    log_file = tmp_path / "docker_calls.log"
    docker_stub = f"""#!/bin/sh
echo "$@" >> "{log_file}"
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"; exit 0
fi
if [ "$1" = "inspect" ]; then
  echo "running"; exit 0
fi
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": docker_stub, "curl": "#!/bin/sh\nexit 0\n"})
    env = _make_mock_env(bin_dir, isolate=True)

    proc = _run_shell("./deploy.sh --no-cache", cwd=work, env=env)
    assert proc.returncode == 0

    calls = log_file.read_text().splitlines()
    assert any("compose build --no-cache app" in c for c in calls)


@pytest.mark.unit
def test_deploy_healthcheck_timeout_outputs_tail_logs(tmp_path: Path):
    """앱 서버 준비 상태(/ready) 점검이 타임아웃되면 compose logs --tail=50 app을 출력하고 exit 1로 종료해야 합니다 (#399)."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n", encoding="utf-8")

    docker_stub = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"; exit 0
fi
if [ "$1" = "inspect" ]; then
  echo "running"; exit 0
fi
if [ "$1" = "compose" ] && [ "$2" = "logs" ]; then
  echo "Mock Container Log: Traceback (most recent call last)..."; exit 0
fi
exit 0
"""
    curl_stub = """#!/bin/sh
# 8000(앱 서버) /ready 호출은 실패시킴
for arg in "$@"; do
  case "$arg" in
    *8000/ready*) exit 1 ;;
  esac
done
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": docker_stub, "curl": curl_stub})
    env = _make_mock_env(bin_dir, isolate=True)
    env["DEPLOY_READY_WAIT_SECONDS"] = "0"

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 1
    assert "오류: 앱 서버가 준비되지 않았습니다" in proc.stderr
    assert "최근 app 컨테이너 로그" in proc.stderr
    assert "Mock Container Log: Traceback" in proc.stderr


@pytest.mark.unit
def test_deploy_ready_check_polling_success(tmp_path: Path):
    """앱 서버 /ready 엔드포인트를 정상 폴링하여 200 OK를 수신하면 배포 성공을 보고해야 합니다 (#399)."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_DEPLOY_SH, work / "deploy.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n", encoding="utf-8")

    log_file = tmp_path / "curl_calls.log"
    docker_stub = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"; exit 0
fi
if [ "$1" = "inspect" ]; then
  echo "running"; exit 0
fi
exit 0
"""
    curl_stub = f"""#!/bin/sh
echo "$@" >> "{log_file}"
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": docker_stub, "curl": curl_stub})
    env = _make_mock_env(bin_dir, isolate=True)

    proc = _run_shell("./deploy.sh", cwd=work, env=env)
    assert proc.returncode == 0
    assert "배포 완료: app 컨테이너가 성공적으로 갱신되었습니다" in proc.stdout

    curl_calls = log_file.read_text().splitlines()
    assert any("http://localhost:8000/ready" in c for c in curl_calls)


@pytest.mark.unit
def test_check_script_fails_when_ready_fails(tmp_path: Path):
    """check.sh 실행 시 /ready 엔드포인트가 실패하면 [FAIL]을 출력하고 exit 1로 종료해야 합니다 (#399)."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_ROOT / "check.sh", work / "check.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n", encoding="utf-8")

    docker_stub = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"; exit 0
fi
if [ "$1" = "inspect" ]; then
  echo "running"; exit 0
fi
if [ "$1" = "exec" ]; then
  echo "1"; exit 0
fi
exit 0
"""
    curl_stub = """#!/bin/sh
for arg in "$@"; do
  case "$arg" in
    *8000/ready*) exit 1 ;;
  esac
done
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": docker_stub, "curl": curl_stub})
    env = _make_mock_env(bin_dir, isolate=True)

    proc = _run_shell("./check.sh", cwd=work, env=env)
    assert proc.returncode == 1
    assert "[FAIL] app이 준비 상태가 아닙니다" in proc.stdout
    assert "확인 완료: 심각한 문제가 발견되었습니다" in proc.stdout


@pytest.mark.unit
def test_check_script_passes_when_ready_succeeds(tmp_path: Path):
    """check.sh 실행 시 /ready 엔드포인트가 정상이면 [PASS]를 출력하고 exit 0으로 종료해야 합니다 (#399)."""
    work = tmp_path / "repo"
    shutil.copytree(_ROOT / "scripts", work / "scripts")
    shutil.copy(_ROOT / "check.sh", work / "check.sh")
    (work / ".env").write_text("APP_HOST_PORT=8000\nEMBEDDING_HOST_PORT=8080\n", encoding="utf-8")

    docker_stub = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"; exit 0
fi
if [ "$1" = "inspect" ]; then
  echo "running"; exit 0
fi
if [ "$1" = "exec" ]; then
  echo "1"; exit 0
fi
exit 0
"""
    curl_stub = """#!/bin/sh
exit 0
"""
    bin_dir = _make_bin(tmp_path, {"docker": docker_stub, "curl": curl_stub})
    env = _make_mock_env(bin_dir, isolate=True)

    proc = _run_shell("./check.sh", cwd=work, env=env)
    assert proc.returncode == 0
    assert "[PASS] app이 준비 상태입니다" in proc.stdout
    assert "확인 완료: 심각한 문제는 발견되지 않았습니다" in proc.stdout


@pytest.mark.unit
def test_dockerignore_completeness():
    """.dockerignore 파일에 대용량 및 불필요 파일 제외 경로가 누락 없이 정의되어 있는지 정적 검증합니다."""
    content = _DOCKERIGNORE.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]

    required_entries = [
        "data/raw_data/",
        "data/benchmarks/",
        "data/test_data/",
        "backups/",
        "frontend/node_modules/",
        "frontend/dist/",
        "docs/",
        "tests/",
    ]
    for req in required_entries:
        assert req in lines, f".dockerignore에 필수 제외 항목 '{req}'이(가) 누락되었습니다."


@pytest.mark.unit
def test_dockerfile_cache_mounts():
    """Dockerfile에 syntax 선언 및 npm, uv 패키지 캐시 마운트 구문이 올바르게 선언되어 있는지 정적 검증합니다."""
    content = _DOCKERFILE.read_text(encoding="utf-8")
    assert "# syntax=docker/dockerfile:1" in content
    assert "--mount=type=cache,target=/root/.npm" in content
    assert "--mount=type=cache,target=/root/.cache/uv" in content
