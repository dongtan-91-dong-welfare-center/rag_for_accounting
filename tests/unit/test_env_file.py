"""
scripts/env_file.sh — .env에서 값을 꺼내 오는 방식 테스트.

[배경]
`.env`는 Compose가 읽는 데이터 파일이지 셸 스크립트가 아니다. 그런데 셸에서 값을 꺼낼 때
`source .env`를 쓰면 파일 내용이 명령으로 실행된다. 그래서 값에 특별한 글자가 들어가면
값을 읽으려던 스크립트가 엉뚱한 이유로 죽는다.

    POSTGRES_PASSWORD=Str0ng$Pass   → `$Pass`를 변수로 보고 "unbound variable"로 즉사한다
    POSTGRES_PASSWORD=my secret pw  → `secret`을 명령으로 보고 "command not found"로 즉사한다
    POSTGRES_PASSWORD=a`id -un`b    → 백틱 안의 명령이 실제로 실행되어 값이 뒤바뀐다

Compose는 세 경우 모두 글자 그대로 읽는다. 그래서 스택은 멀쩡한데 스크립트만 죽는,
원인을 짐작하기 어려운 상황이 만들어진다. 비밀번호에 `$`를 넣는 것은 아주 흔한 일이다.

[목적]
이 테스트는 값을 꺼내는 함수가 파일을 실행하지 않는다는 것과, Compose가 읽는 값과 같은 값을
돌려준다는 것을 고정한다.
"""
from __future__ import annotations

import shutil   # 고수준 파일 및 디렉터리 조작 (Shell Utility)
import subprocess   # 외부 프로세스 실행 및 관리 (Shell Execution)
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_LIB = _ROOT / "scripts" / "env_file.sh"
_BASH = shutil.which("bash") or "/bin/bash"


def _read_env(tmp_path: Path, env_body: str, key: str) -> tuple[int, str, str]:
    """
    임시 디렉터리에 .env를 놓고 read_env를 부른 결과를 돌려준다.
    `read_env`는 `.env`의 변수를 읽어 표준 출력으로 내보내는 작은 셸 함수다.

    스크립트들이 저장소 루트로 이동한 뒤 `.env`를 읽으므로, 테스트도 같은 방식으로 현재 디렉터리를 옮겨 놓고 부른다.

    :param tmp_path: 임시 디렉터리
    :param env_body: .env 파일 내용
    :param key: 읽어 올 키
    :return: 종료 코드, 표준 출력, 표준 에러
    """
    # write_text: 문자열 데이터를 지정한 파일에 한 번에 쓰고 저장하는 간결한 파일 쓰기 함수
    # with open(...) 구문을 한 줄로 축약한 형태
    (tmp_path / ".env").write_text(env_body)
    proc = subprocess.run(
        # set -uo pipefail:
            # -u: 정의되지 않은 변수를 참조하면 즉시 에러를 발생시킨다.
            # -o pipefail: 파이프(|)로 연결된 명령어 중 하나라도 실패하면 전체 파이프라인 실패로 간주한다.
        [_BASH, "-c", f'set -uo pipefail\nsource "{_LIB}"\nread_env {key}\n'],
        cwd=tmp_path,   # 프로세스의 현재 작업 디렉터리를 방금 만든 임시 폴더로 지정한다.
        capture_output=True,    # 프로세스가 터미널에 찍는 표준 출력과 표준 에러를 화면에 띄우지 않고 메모리에 캡처
        text=True,  # 캡처한 출력을 바이트가 아닌 문자열로 변환
    )
    return proc.returncode, proc.stdout.rstrip("\n"), proc.stderr


@pytest.mark.unit
class TestReadEnv:
    def test_value_containing_dollar_sign_is_returned_literally(self, tmp_path):
        """비밀번호에 흔히 쓰이는 `$`가 값을 죽이지 않아야 한다."""
        rc, value, stderr = _read_env(
            tmp_path, "POSTGRES_PASSWORD=Str0ng$Pass\n", "POSTGRES_PASSWORD"
        )

        assert rc == 0  # 성공적으로 종료됨을 확인
        assert value == "Str0ng$Pass"   # Bash의 특별한 문자열로 해석되지 않고 문자 그대로 반환되는지 확인
        assert "unbound variable" not in stderr  # 에러 메시지에 "unbound variable"이 포함되어 있지 않은지 확인

    def test_unquoted_spaces_are_kept(self, tmp_path):
        """따옴표 없이 공백이 들어간 값도 Compose와 같게 줄 끝까지 읽어야 한다."""
        rc, value, stderr = _read_env(
            tmp_path, "POSTGRES_PASSWORD=my secret pw\n", "POSTGRES_PASSWORD"
        )

        assert rc == 0  # 성공적으로 종료됨을 확인
        assert value == "my secret pw"  # 공백이 포함된 값을 문자 그대로 반환하는지 확인
        assert "command not found" not in stderr  # 에러 메시지에 "command not found"가 포함되어 있지 않은지 확인

    def test_backticks_are_not_executed(self, tmp_path):
        """`.env`에 적힌 명령이 실행되면 안 된다. 실행되면 값이 바뀔 뿐 아니라 보안 문제가 된다."""
        rc, value, _ = _read_env(
            tmp_path, "POSTGRES_PASSWORD=a`id -un`b\n", "POSTGRES_PASSWORD"
        )

        assert rc == 0  # 성공적으로 종료됨을 확인
        assert value == "a`id -un`b"  # Bash의 특수 문자(명령 치환)로 해석되지 않고 문자 그대로 반환되는지 확인

    def test_dollar_parens_are_not_executed(self, tmp_path):
        """`$(...)` 형태도 마찬가지로 글자 그대로 남아야 한다."""
        rc, value, _ = _read_env(tmp_path, "TOKEN=x$(id -un)y\n", "TOKEN")

        assert rc == 0  # 성공적으로 종료됨을 확인
        assert value == "x$(id -un)y"  # Bash의 특수 문자(명령 치환)로 해석되지 않고 문자 그대로 반환되는지 확인

    @pytest.mark.parametrize(
        "line,expected",
        [
            ('APP_HOST_PORT="3000"', "3000"),
            ("APP_HOST_PORT='3000'", "3000"),
            ("APP_HOST_PORT=3000   ", "3000"),
        ],
    )
    def test_surrounding_quotes_and_trailing_spaces_are_trimmed(
        self, tmp_path, line, expected
    ):
        """Compose는 감싼 따옴표를 벗기고 읽는다. 포트 번호에 따옴표가 남으면 주소가 깨진다."""
        rc, value, _ = _read_env(tmp_path, line + "\n", "APP_HOST_PORT")

        assert rc == 0  # 성공적으로 종료됨을 확인
        assert value == expected  # 감싼 따옴표가 벗겨지고 공백이 제거되었는지 확인

    def test_commented_out_key_is_ignored(self, tmp_path):
        """주석 처리된 줄은 값이 아니다. .env.example은 선택 항목을 주석으로 두고 있다."""
        rc, value, _ = _read_env(tmp_path, "# APP_HOST_PORT=9999\n", "APP_HOST_PORT")

        assert rc == 0  # 성공적으로 종료됨을 확인
        assert value == ""  # 주석 처리된 줄은 값을 반환하지 않음

    def test_last_definition_wins(self, tmp_path):
        """같은 키가 여러 번 나오면 마지막 것을 쓴다. 셸에서 파일을 읽을 때와 같은 규칙이다."""
        rc, value, _ = _read_env(
            tmp_path, "APP_HOST_PORT=8000\nAPP_HOST_PORT=3000\n", "APP_HOST_PORT"
        )

        assert rc == 0  # 성공적으로 종료됨을 확인
        assert value == "3000"  # 동일한 키가 여러 번 나오면 마지막 값을 사용

    def test_missing_key_returns_empty(self, tmp_path):
        """파일에 존재하지 않는 키를 읽으려고 하면 빈 값을 반환한다."""
        rc, value, _ = _read_env(tmp_path, "OTHER=1\n", "APP_HOST_PORT")

        assert rc == 0  # 성공적으로 종료됨을 확인
        assert value == ""  # 존재하지 않는 키는 빈 값을 반환

    def test_missing_env_file_returns_empty_without_error(self, tmp_path):
        """.env가 아직 없는 상태에서도 조용히 빈 값을 준다. check.sh는 그 상태에서도 돌아야 한다."""
        proc = subprocess.run(
            [_BASH, "-c", f'set -uo pipefail\nsource "{_LIB}"\nread_env APP_HOST_PORT\n'],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert proc.returncode == 0  # 성공적으로 종료됨을 확인
        assert proc.stdout.strip() == ""  # 표준 출력 없음
        assert proc.stderr.strip() == ""  # 표준 에러 없음


@pytest.mark.unit
class TestEntryScriptsSurviveHostileEnv:
    """
    install.sh와 check.sh가 특별한 글자가 든 .env를 만나도 죽지 않아야 한다.

    이 두 스크립트는 사용자가 저장소를 받은 직후 처음 실행하는 진입점이다.
    여기서 죽으면 사용자에게 남는 단서는 `Pass: unbound variable` 한 줄뿐이라,
    .env가 원인이라는 것도 install.sh가 죽었다는 것도 알기 어렵다.
    """

    HOSTILE_ENV = (
        "OPENAI_API_KEY=sk-test\n"
        "POSTGRES_PASSWORD=Str0ng$Pass\n"
        "APP_HOST_PORT=3000\n"
    )

    def _stub_bin(self, tmp_path: Path) -> Path:
        """스택을 실제로 띄우지 않도록 컨테이너 명령을 가짜로 바꾼 PATH 디렉터리를 만든다."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "docker").write_text(
            '#!/bin/sh\n'
            'if [ "$1" = "compose" ] && [ "$2" = "version" ]; then\n'
            '  echo "Docker Compose version v2.39.0"; exit 0\n'
            'fi\n'
            'exit 0\n'
        )
        # curl이 성공을 돌려주면 install.sh의 대기 루프가 곧바로 통과한다.
        # (bin_dir / "curl"): curl이라는 이름의 스크립트를 만들고 write_text()의 인자로 들어간 값을 내용으로 한다.
        (bin_dir / "curl").write_text("#!/bin/sh\nexit 0\n")
        # bin_dir.iterdir(): bin 폴더 내의 파일들(docker, curl)을 하나씩 순회
        for f in bin_dir.iterdir():
            f.chmod(0o755) # 파일의 권한을 실행 가능하게 변경
        return bin_dir

    def _run(self, script: str, tmp_path: Path) -> subprocess.CompletedProcess:
        """실행할 스크립트 경로와 임시 경로를 받아서 스크립트를 실행하고 결과를 반환"""
        work = tmp_path / "repo"
        # shutil.copytree: 프로젝트 루트(_ROOT)의 scripts/ 폴더 전체를 통째로 복사
        shutil.copytree(_ROOT / "scripts", work / "scripts")
        # install.sh, check.sh, .env.example 복사
        for name in ("install.sh", "check.sh", ".env.example"):
            shutil.copy(_ROOT / name, work / name)
        # 위험한 특수문자가 포함된 self.HOSTILE_ENV 문자열을 .env 파일로 직접 생성
        (work / ".env").write_text(self.HOSTILE_ENV)
        # stub bin
        bin_dir = self._stub_bin(tmp_path)
        # 스크립트 실행
        return subprocess.run(
            [_BASH, f"./{script}"], # 실행할 명령어 배열
            cwd=work,   # 현재 작업 디렉터리
            env={"PATH": f"{bin_dir}:/usr/bin:/bin"},   # 프로세스에 전달할 환경 변수 딕셔너리
            capture_output=True,    # 표준 출력과 표준 에러를 캡처
            text=True,  # 캡처한 출력을 문자열로 디코딩
        )

    def test_install_reaches_the_container_build_step(self, tmp_path):
        """install.sh가 특별한 글자가 든 .env를 만나도 죽지 않고 빌드 단계까지 진행해야 한다."""
        proc = self._run("install.sh", tmp_path)

        assert "unbound variable" not in proc.stderr    # 실행중에 바인드되지 않는 변수 에러 확인
        assert "Building and starting containers" in proc.stdout    # 빌드 단계 확인

    def test_install_uses_the_port_from_env(self, tmp_path):
        """.env의 APP_HOST_PORT가 안내 문구에 반영되어야 한다."""
        proc = self._run("install.sh", tmp_path)

        assert "http://localhost:3000" in proc.stdout   # curl 포트 반영 확인

    def test_check_still_prints_its_report(self, tmp_path):
        """check.sh도 특별한 글자가 든 .env를 만나도 죽지 않고 평소처럼 점검 결과를 출력해야 한다."""
        proc = self._run("check.sh", tmp_path)

        assert "unbound variable" not in proc.stderr    # 실행중에 바인드되지 않는 변수 에러 확인
        assert "1. Required tools" in proc.stdout   # bash 실행 확인
        assert "Check complete" in proc.stdout    # 점검 완료 확인
