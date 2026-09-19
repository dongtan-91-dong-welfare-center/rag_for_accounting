"""
scripts/container_runtime.sh — 컨테이너 런타임 판정 로직 테스트.

[배경]
install.sh·check.sh·db_dump.sh·db_restore.sh 네 스크립트는 컨테이너를 띄우고 들여다보기 위해 compose 명령을 부른다. 
그런데 Rocky·RHEL 계열 서버의 기본 런타임은 Docker가 아니라 Podman이고,
Podman에는 `docker compose`에 해당하는 하위 명령이 없다. 
`podman-docker`가 깔려 있어도 `docker compose up -d`는
`podman compose up -d`로 넘어가면서 `-d`를 최상위 플래그로 오인해 즉시 죽는다.

[목적]
그래서 네 스크립트가 공유하는 판정 함수를 한 곳에 두었다. 
이 테스트는 그 함수가 어떤 환경에서 무엇을 고르는지를 고정한다.

[판정 규칙]
`docker compose`가 되면 그것을 쓰고, 안 되면 `podman-compose`를 쓰고, 둘 다 없으면 실패를 알린다.
Docker를 쓰던 사람의 동작이 그대로 유지되어야 하므로 Docker를 먼저 확인한다.

[검증 방법]
진짜 Docker나 Podman을 깔 수는 없으므로, 임시 디렉터리에 이름만 같은 가짜 실행 파일을 만들고 
PATH를 그 디렉터리 하나로 좁힌 뒤 판정 함수를 돌린다. 
예를 들어 `podman-compose` 파일만 있으면 "Podman만 있는 서버"가 재현된다.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_LIB = _ROOT / "scripts" / "container_runtime.sh"
# PATH를 가짜 디렉터리로 좁히면 bash 자체도 찾지 못하므로, 좁히기 전에 절대 경로로 붙잡아 둔다.
_BASH = shutil.which("bash") or "/bin/bash"

# `docker compose version`이 성공하는 가짜 docker — Docker Compose v2가 깔린 환경을 흉내 낸다.
_DOCKER_WITH_COMPOSE = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo "Docker Compose version v2.39.0"
  exit 0
fi
exit 0
"""

# `docker compose`가 깨지는 가짜 docker — podman-docker 래퍼가 깔린 Podman 환경을 흉내 낸다.
# 실제 증상과 같은 메시지와 종료 코드를 낸다.
_DOCKER_PODMAN_WRAPPER = """#!/bin/sh
if [ "$1" = "compose" ]; then
  echo "Error: unknown shorthand flag: 'd' in -d" >&2
  exit 125
fi
exit 0
"""

# `docker compose`가 성공하지만 실제로는 podman이 podman-compose에 넘겨서 처리하는 가짜 docker.
# Podman 4.7부터 생긴 compose 하위 명령이 이렇게 동작한다. 겉모습만 Docker다.
_DOCKER_DELEGATING_TO_PODMAN = """#!/bin/sh
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  echo '>>>> Executing external compose provider "/usr/bin/podman-compose"' >&2
  echo "podman-compose version 1.0.6"
  exit 0
fi
exit 0
"""

_STUB = """#!/bin/sh
exit 0
"""


def _make_bin(tmp_path: Path, files: dict[str, str]) -> Path:
    """가짜 실행 파일들을 담은 디렉터리를 만들어 그 경로를 돌려준다."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in files.items():
        target = bin_dir / name
        target.write_text(body)
        target.chmod(0o755)
    return bin_dir


def _detect(bin_dir: Path) -> tuple[int, str, str, str]:
    """
    param:
      bin_dir (Path): 가짜 실행 파일들을 담은 디렉터리 경로.
    return: 
      tuple[int, str, str, str]: (반환코드, COMPOSE, CONTAINER, COMPOSE_UP_FLAGS)

    PATH를 가짜 디렉터리 하나로 좁혀서, 호스트에 실제로 깔린 Docker가 결과에 섞이지 않게 한다.
    """
    script = (
        f'source "{_LIB}"\n'
        "detect_container_runtime\n"
        'rc=$?\n'
        'echo "rc=$rc"\n'
        'echo "compose=${COMPOSE[*]}"\n'
        'echo "container=${CONTAINER[*]}"\n'
        'echo "upflags=${COMPOSE_UP_FLAGS[*]}"\n'
    )
    proc = subprocess.run(
        [_BASH, "-c", script],
        env={"PATH": str(bin_dir)},
        capture_output=True,
        text=True,
    )
    values = dict(
        line.split("=", 1)  # "key=value"를 (key, value)로 분할한다.
        for line in proc.stdout.splitlines()
        if "=" in line
    )
    return int(values["rc"]), values["compose"], values["container"], values["upflags"]


@pytest.mark.unit
class TestDetectContainerRuntime:
    def test_docker_compose_wins_when_available(self, tmp_path):
        """Docker Compose v2가 있으면 그것을 고른다 — 기존 Docker 사용자에게 회귀가 없어야 한다."""
        bin_dir = _make_bin(tmp_path, {"docker": _DOCKER_WITH_COMPOSE})

        rc, compose, container, up_flags = _detect(bin_dir)

        assert rc == 0  # 성공
        assert compose == "docker compose"  # docker compose를 선택
        assert container == "docker"  # docker를 선택
        assert up_flags == "-d --build"  # -d --build 플래그를 선택

    def test_falls_back_to_podman_compose_when_docker_absent(self, tmp_path):
        """docker 명령 자체가 없는 서버에서는 podman-compose를 고른다."""
        bin_dir = _make_bin(tmp_path, {"podman-compose": _STUB, "podman": _STUB})

        rc, compose, container, up_flags = _detect(bin_dir)

        assert rc == 0  # 성공
        assert compose == "podman-compose"  # podman-compose를 선택
        assert container == "podman"  # podman을 선택
        assert "--force-recreate" in up_flags  # --force-recreate 플래그를 선택

    def test_falls_back_when_docker_wrapper_cannot_run_compose(self, tmp_path):
        """
        podman-docker 래퍼 때문에 docker 명령은 있지만 `docker compose`가 깨지는 환경.
        실제로 `docker compose version`을 돌려 보고 판정해야 한다.
        """
        bin_dir = _make_bin(
            tmp_path,
            {"docker": _DOCKER_PODMAN_WRAPPER, "podman-compose": _STUB, "podman": _STUB},
        )

        rc, compose, container, up_flags = _detect(bin_dir)

        assert rc == 0  # 성공
        assert compose == "podman-compose"  # podman-compose를 선택
        assert container == "podman"  # podman을 선택
        assert "--force-recreate" in up_flags  # --force-recreate 플래그를 선택

    def test_prefers_podman_cli_but_accepts_docker_wrapper(self, tmp_path):
        """podman-compose는 있는데 podman 실행 파일이 없으면 래퍼(docker)로 컨테이너를 다룬다."""
        bin_dir = _make_bin(
            tmp_path, {"docker": _DOCKER_PODMAN_WRAPPER, "podman-compose": _STUB}
        )

        rc, compose, container, up_flags = _detect(bin_dir)

        assert rc == 0  # 성공
        assert compose == "podman-compose"  # podman-compose를 선택
        assert container == "docker"  # docker를 선택
        assert "--force-recreate" in up_flags  # --force-recreate 플래그를 선택

    def test_delegating_docker_compose_is_treated_as_podman(self, tmp_path):
        """
        `docker compose`가 되긴 하는데 실제로는 podman이 podman-compose에 넘겨 처리하는 환경.

        Podman 4.7부터 compose 하위 명령이 생겨서, 겉으로는 `docker compose version`이 성공한다.
        그러나 실제로 일하는 것은 podman-compose이므로 아래 재생성 문제를 똑같이 안고 있다.
        버전 출력에 podman이라는 이름이 남으므로 그것으로 가려낸다.
        """
        bin_dir = _make_bin(
            tmp_path, {"docker": _DOCKER_DELEGATING_TO_PODMAN, "podman": _STUB}
        )

        rc, compose, container, up_flags = _detect(bin_dir)

        assert rc == 0  # 성공
        assert compose == "docker compose"  # docker compose를 선택
        assert "--force-recreate" in up_flags  # --force-recreate 플래그를 선택

    def test_reports_failure_when_no_runtime_found(self, tmp_path):
        """compose 계열이 하나도 없으면 실패를 알린다."""
        bin_dir = _make_bin(tmp_path, {})

        rc, compose, container, up_flags = _detect(bin_dir)

        assert rc != 0  # 실패
        # 판정에 실패해도 두 배열은 비우지 않는다. 빈 배열을 `set -u`가 켜진 bash에서
        # "${COMPOSE[@]}"로 펼치면 오래된 bash(4.4 미만, macOS 기본 3.2 포함)가 오류를 낸다.
        # 호출한 스크립트가 실패를 보고하고 나머지 점검을 이어 갈 수 있도록 안전한 기본값을 남긴다.
        assert compose == "docker compose"  # 안전한 기본값을 남긴다
        assert container == "docker"  # 안전한 기본값을 남긴다


@pytest.mark.unit
class TestInstallHint:
    def test_hint_names_both_install_paths(self, tmp_path):
        """
        설치 안내는 Docker와 podman-compose 두 경로를 모두 알려 줘야 한다.

        Rocky·RHEL에서 podman-compose는 기본 저장소에 없고 EPEL을 켜야 설치되므로 그 사실도 담는다.
        """
        bin_dir = _make_bin(tmp_path, {})
        proc = subprocess.run(
            [_BASH, "-c", f'source "{_LIB}"\ncontainer_runtime_hint\n'],
            env={"PATH": str(bin_dir)},
            capture_output=True,
            text=True,
        )

        # 안내는 표준 출력이 아니라 표준 오류로 나가야 한다.
        assert proc.stdout.strip() == ""    # 표준 출력이 비어 있는지 확인
        hint = proc.stderr
        assert "podman-compose" in hint   # podman-compose가 안내에 포함되어 있는지 확인
        assert "epel" in hint.lower()    # epel이 안내에 포함되어 있는지 확인
        assert "docker" in hint.lower()    # docker가 안내에 포함되어 있는지 확인
