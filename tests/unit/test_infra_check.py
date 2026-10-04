"""
tests/utils/infra_check.py에 대한 단위 테스트
"""
import os
import subprocess
from unittest.mock import MagicMock, patch
import pytest

from tests.utils.infra_check import check_docker_infrastructure

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_subprocess_run():
    with patch("subprocess.run") as mock_run:
        yield mock_run


def test_infra_check_separates_container_and_db_name(monkeypatch):
    """
    POSTGRES_DB가 기본값이 아닌 custom_db로 설정되어도,
    컨테이너 검사는 POSTGRES_CONTAINER_NAME(accounting_db)을 대상으로 수행하고,
    psql -d 옵션에는 custom_db가 전달되는지 검증합니다.
    """
    monkeypatch.setenv("POSTGRES_DB", "custom_db")
    monkeypatch.setenv("POSTGRES_CONTAINER_NAME", "accounting_db")
    monkeypatch.setenv("POSTGRES_USER", "custom_user")

    executed_commands = []

    def fake_run(command, *args, **kwargs):
        cmd_str = command if isinstance(command, str) else " ".join(command)
        executed_commands.append(cmd_str)
        res = MagicMock()
        res.returncode = 0
        res.stdout = "true\n"
        res.stderr = ""
        return res

    with patch("subprocess.run", side_effect=fake_run):
        err = check_docker_infrastructure(require_app=False)
        assert err is None

    # 검증: docker inspect 대상은 accounting_db여야 하며 custom_db여서는 안 됨
    inspect_db_cmds = [cmd for cmd in executed_commands if "docker inspect" in cmd]
    assert any("accounting_db" in cmd for cmd in inspect_db_cmds)
    assert not any("custom_db" in cmd for cmd in inspect_db_cmds)

    # 검증: docker exec 대상 컨테이너는 accounting_db이고 -d 옵션은 custom_db여야 함
    exec_cmds = [cmd for cmd in executed_commands if "docker exec" in cmd]
    assert len(exec_cmds) == 1
    assert "docker exec accounting_db" in exec_cmds[0]
    assert "-d custom_db" in exec_cmds[0]
    assert "-U custom_user" in exec_cmds[0]


def test_infra_check_docker_daemon_down():
    """Docker 데몬이 비정상일 때 적절한 에러 메시지를 반환하는지 검증합니다."""
    def fake_run(command, *args, **kwargs):
        res = MagicMock()
        if "docker version" in command:
            res.returncode = 1
            res.stdout = ""
            res.stderr = "Cannot connect to the Docker daemon"
        else:
            res.returncode = 0
            res.stdout = "true"
        return res

    with patch("subprocess.run", side_effect=fake_run):
        err = check_docker_infrastructure()
        assert err == "Docker 데몬이 실행 중이지 않습니다."


def test_infra_check_container_not_running(monkeypatch):
    """DB 컨테이너가 실행 중이지 않을 때 컨테이너 이름을 포함한 에러 메시지를 반환하는지 검증합니다."""
    monkeypatch.setenv("POSTGRES_CONTAINER_NAME", "my_custom_container")

    def fake_run(command, *args, **kwargs):
        res = MagicMock()
        if "docker version" in command:
            res.returncode = 0
            res.stdout = "Client: Docker Engine"
        elif "docker inspect" in command:
            res.returncode = 0
            res.stdout = "false"
        else:
            res.returncode = 0
            res.stdout = ""
        return res

    with patch("subprocess.run", side_effect=fake_run):
        err = check_docker_infrastructure()
        assert err == "my_custom_container 컨테이너가 실행 중이 아닙니다."
