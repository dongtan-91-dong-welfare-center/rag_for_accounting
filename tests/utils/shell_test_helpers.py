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

def _find_bash() -> str:
    """시스템 환경에 적합한 bash 실행 파일의 절대 경로를 탐색합니다."""
    # os.name == "nt": 'nt'는 'New Technology'의 약어로 파이썬 표준 os 모듈에서 Windows NT 커널 기반 운영체제를 식별하는 고유 문자열입니다 (Linux/macOS는 'posix').
    if os.name == "nt":
        # [WSL bash 대신 Git for Windows의 bash를 선택하는 이유]
        # Windows 환경에서 WSL bash(C:\Windows\System32\bash.exe)는 가상화된 리눅스 서브시스템 파일 경로를 바라보므로,
        # 파이썬 테스트 러너가 Windows 호스트에 생성한 pytest 임시 디렉터리(C:\...)를 인식하지 못해 테스트가 깨집니다.
        # 반면 Git for Windows의 bash는 호스트 파일 시스템 드라이브를 /c/... 형태로 직접 마운트하여 다룰 수 있으므로 최우선으로 탐색합니다.
        candidates = [
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files\Git\usr\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
        ]
        for candidate in candidates:
            if Path(candidate).is_file():
                return candidate
    return shutil.which("bash") or "/bin/bash"


# 시스템 bash 절대 경로 (PATH를 가짜 디렉터리로 좁혀도 bash를 안전하게 실행 가능)
BASH_PATH: str = _find_bash()


def to_posix_path(path: Path | str) -> str:
    """Windows 환경의 절대 경로(C:\\...)를 Git Bash 호환 POSIX 경로(/c/...)로 변환합니다."""
    # resolve(): 상대 경로를 절대 경로로 정규화하고 심볼릭 링크 및 '.'이나 '..' 경로 세그먼트를 모두 물리적 정규 절대 경로(canonical path)로 치환합니다.
    p = Path(path).resolve()
    if os.name == "nt" and p.drive:
        drive = p.drive.rstrip(":").lower()
        return f"/{drive}{p.as_posix()[2:]}"
    return p.as_posix()


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
    posix_bin = to_posix_path(bin_dir)
    if isolate:
        # 테스트 환경을 깨끗하게 격리하면서도 스크립트 실행에 필요한 필수 쉘 명령어만 최소한으로 제공
        if include_system_paths:
            env["PATH"] = f"{posix_bin}:/bin:/usr/bin"
        else:
            env["PATH"] = posix_bin
    else:
        existing_path = env.get("PATH", "")
        # 기존 PATH를 유지하면서 bin_dir을 앞에 추가
        system_extra = ":/usr/bin:/bin" if os.name == "nt" else ""
        env["PATH"] = f"{posix_bin}{system_extra}:{existing_path}" if existing_path else f"{posix_bin}{system_extra}"
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
    path_export = ""
    if env and "PATH" in env:
        # Git Bash 등 서브프로세스 기동 시 시스템 PATH가 우선되는 현상을 방지하기 위해 셸 내부에서 PATH를 최우선으로 재정의합니다.
        path_export = f'export PATH="{env["PATH"]}"; '

    if isinstance(cmd, str):
        full_cmd = f"{path_export}{cmd}" if path_export else cmd
        args = [BASH_PATH, "--noprofile", "--norc", "-c", full_cmd]
    else:
        # 리스트 인자의 Windows 역슬래시(\)가 bash -c 파싱 시 이스케이프 문자로 소실되지 않도록 변환
        sanitized_args = [to_posix_path(arg) if ("\\" in str(arg) or (os.name == "nt" and ":" in str(arg))) else str(arg) for arg in cmd]
        # [인자 결합 시 큰따옴표를 감싸는 이유]
        # 인자 내부에 공백(예: 경로명 'Program Files')이 포함되어 있는 경우, 큰따옴표 없이 공백으로 결합하면
        # bash -c 전달 시 셸이 공백을 기준으로 인자를 쪼개어 각각 별개의 명령어나 플래그로 잘못 파싱하므로 단일 인자 보존을 위해 따옴표를 감쌉니다.
        cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in sanitized_args)
        full_cmd = f"{path_export}{cmd_str}" if path_export else cmd_str
        args = [BASH_PATH, "--noprofile", "--norc", "-c", full_cmd]

    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
        # encoding="utf-8": 서브프로세스의 stdout/stderr 바이트 스트림을 UTF-8 문자열로 디코딩합니다.
        # errors="replace": 디코딩 불가능한 비정상 바이트가 포함되어 있어도 UnicodeDecodeError 예외로 중단되지 않고 대체 문자(\ufffd)로 안전하게 치환합니다.
        encoding="utf-8",
        errors="replace",
    )
