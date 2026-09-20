"""
셸 스크립트(*.sh) 테스트 공통 유틸리티


[목적]
install.sh, check.sh, db_dump.sh, db_restore.sh 등 
프로젝트 내 셸 스크립트를 테스트할 때 필요한 가짜 CLI 바이너리 생성, 
PATH 환경 격리 및 셸 명령 실행을 한 곳에서 관리하여 테스트 코드 중복을 해소하고 가독성을 높인다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

# 시스템 bash 절대 경로 (PATH를 가짜 디렉터리로 좁혀도 bash를 안전하게 실행 가능)
BASH_PATH: str = shutil.which("bash") or "/bin/bash"


def make_bin(tmp_path: Path, files: dict[str, str]) -> Path:
    """
    가짜 실행 파일들을 담은 bin 디렉터리를 만들고 실행 권한(0o755)을 부여하여 반환한다.

    :param tmp_path: pytest 임시 디렉터리
    :param files: 실행 파일명과 본문 매핑 (예: {"docker": "#!/bin/sh\\nexit 0"})
    :return: 생성된 bin 디렉터리 경로 (Path)
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        target = bin_dir / name
        target.write_text(body)
        target.chmod(0o755)
    return bin_dir


def make_mock_env(
    bin_dir: Path,
    *,
    base_env: dict[str, str] | None = None,
    isolate: bool = False,
    include_system_paths: bool = True,
) -> dict[str, str]:
    """
    Mock bin_dir을 포함하는 환경 변수 사전을 생성한다.

    :param bin_dir: make_bin()으로 생성한 Mock bin 디렉터리 경로
    :param base_env: 복사할 기본 환경 변수 dict (None일 경우 os.environ 복사)
    :param isolate: True일 경우 기존 PATH를 배제하고 격리된 PATH 구성
    :param include_system_paths: isolate=True일 때 기본 시스템 도구(/bin:/usr/bin) 포함 여부
    :return: 갱신된 환경 변수 dict
    """
    env = dict(base_env if base_env is not None else os.environ)
    if isolate:
        # 테스트 환경을 깨끗하게 격리하면서도 스크립트 실행에 필요한 필수 쉘 명령어만 최소한으로 제공
        if include_system_paths:
            env["PATH"] = f"{bin_dir}:/bin:/usr/bin"
        else:
            env["PATH"] = str(bin_dir)
    else:
        existing_path = env.get("PATH", "")
        # 기존 PATH를 유지하면서 bin_dir을 앞에 추가
        env["PATH"] = f"{bin_dir}:{existing_path}" if existing_path else str(bin_dir)
    return env


def run_shell(
    cmd: str | list[str],
    *,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """
    BASH_PATH를 사용하여 명령을 실행하고 결과(문자열)를 캡처한다.

    :param cmd: 실행할 셸 커맨드 문자열 또는 인자 리스트
    :param cwd: 작업 디렉터리
    :param env: 환경 변수 dict
    :param input_text: 표준 입력으로 주입할 문자열
    :return: subprocess.CompletedProcess[str]
    """
    if isinstance(cmd, str):
        # -c 옵션: 문자열 형태의 셸 커맨드를 실행
        args = [BASH_PATH, "-c", cmd]
    else:
        # 문자열이 아니면 리스트로 전달받은 인자로 취급
        args = [BASH_PATH] + list(cmd)

    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
    )
