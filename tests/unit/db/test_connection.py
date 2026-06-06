"""
[FUNC-005] 커넥션 풀 초기화 단위 테스트

대상 모듈: src/db/connection.py
검증 범위:
    - init_pool(): 풀 초기화, 이중 호출 방지, 필수 환경변수 누락 시 조기 실패,
      특수문자 패스워드의 conninfo 이스케이프
    - get_pool(): init_pool() 미선행 시 RuntimeError
    - close_pool(): 종료 후 get_pool() 호출 시 RuntimeError

실제 DB에 접속하지 않도록 ConnectionPool을 mock한다.
"""
import pytest
from unittest.mock import patch, MagicMock

from src.db import connection
from src.utils.exception import ConfigNotFoundError


@pytest.fixture(autouse=True)
def reset_pool():
    """각 테스트가 깨끗한 전역 상태(_pool=None)에서 시작하고 끝나도록 보장한다."""
    connection._pool = None   # 테스트 시작 전 초기화
    yield
    connection._pool = None   # 테스트 끝난 후 초기화


@pytest.fixture
def mock_connection_pool():
    """실제 DB 접속을 차단하기 위해 ConnectionPool 생성자를 mock한다."""
    with patch("src.db.connection.ConnectionPool") as mock_pool_cls:
        mock_pool_cls.return_value = MagicMock()
        yield mock_pool_cls  # mock 객체 반환


@pytest.mark.unit
class TestGetPool:
    """get_pool() 인터페이스 규격 검증"""

    def test_get_pool_before_init_raises_runtime_error(self):
        """init_pool() 미호출 시 get_pool()은 RuntimeError를 발생시킨다."""
        with pytest.raises(RuntimeError, match="init_pool"):
            connection.get_pool()

    def test_get_pool_after_init_returns_pool(self, mock_connection_pool):
        """init_pool() 이후 get_pool()은 동일한 풀 인스턴스를 반환한다."""
        connection.init_pool()
        pool = connection.get_pool()
        assert pool is mock_connection_pool.return_value   # 동일 인스턴스 반환 확인


@pytest.mark.unit
class TestInitPool:
    """init_pool() 인터페이스 규격 검증"""

    def test_init_pool_missing_password_raises_config_error(
        self, mock_connection_pool, monkeypatch
    ):
        """POSTGRES_PASSWORD 미설정 시 ConfigNotFoundError로 조기 실패한다."""
        monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
        with pytest.raises(ConfigNotFoundError):
            connection.init_pool()
        # 풀이 생성되지 않아야 한다
        mock_connection_pool.assert_not_called()

    def test_init_pool_empty_password_raises_config_error(
        self, mock_connection_pool, monkeypatch
    ):
        """POSTGRES_PASSWORD가 빈 문자열이어도 조기 실패한다."""
        monkeypatch.setenv("POSTGRES_PASSWORD", "")
        with pytest.raises(ConfigNotFoundError):
            connection.init_pool()
        mock_connection_pool.assert_not_called()

    def test_init_pool_called_twice_creates_pool_once(self, mock_connection_pool):
        """init_pool() 이중 호출 시 풀은 단 한 번만 생성된다."""
        connection.init_pool()
        connection.init_pool()
        assert mock_connection_pool.call_count == 1   # 1회만 생성 확인

    def test_init_pool_escapes_special_char_password(
        self, mock_connection_pool, monkeypatch
    ):
        """특수문자(`=`, 공백)가 포함된 패스워드도 make_conninfo로 안전하게 이스케이프된다."""
        monkeypatch.setenv("POSTGRES_PASSWORD", "my pass=secret'\\x")
        connection.init_pool()

        # ConnectionPool에 전달된 첫 번째 인자(conninfo)를 검증한다
        conninfo = mock_connection_pool.call_args.args[0]
        # libpq 규칙상 공백·특수문자가 포함된 값은 작은따옴표로 감싸지고 이스케이프된다
        assert "password='my pass=secret\\'\\\\x'" in conninfo  # 특수문자 이스케이프 확인


@pytest.mark.unit
class TestClosePool:
    """close_pool() 인터페이스 규격 검증"""

    def test_close_pool_then_get_pool_raises_runtime_error(self, mock_connection_pool):
        """close_pool() 이후 get_pool() 호출 시 RuntimeError를 발생시킨다."""
        connection.init_pool()
        connection.close_pool()
        with pytest.raises(RuntimeError, match="init_pool"):
            connection.get_pool()

    def test_close_pool_calls_underlying_close(self, mock_connection_pool):
        """close_pool()은 실제 풀의 close()를 호출한다."""
        connection.init_pool()
        pool_instance = mock_connection_pool.return_value
        connection.close_pool()
        pool_instance.close.assert_called_once()

    def test_close_pool_without_init_is_noop(self, mock_connection_pool):
        """init_pool() 없이 close_pool()을 호출해도 예외가 발생하지 않는다."""
        connection.close_pool()  # 예외 없이 통과해야 한다
        mock_connection_pool.return_value.close.assert_not_called()
