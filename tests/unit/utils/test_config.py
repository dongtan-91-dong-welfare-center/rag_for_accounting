import pytest

from src.utils.config import _env_bool, _env_float

# 모듈 상수(config.USE_RERANKER 등)의 ambient 값은 단언하지 않는다:
# config는 import 시 load_dotenv()로 로컬 .env를 읽으므로 머신마다 상수 값이 달라질 수 있다.
# 대신 파싱 헬퍼를 monkeypatch 환경에서 직접 검증한다.


@pytest.mark.unit
class TestEnvBool:
    """_env_bool() 단위 테스트 — USE_RERANKER 환경변수 파싱"""

    @pytest.mark.parametrize("raw", ["true", "True", "TRUE", "1", "yes", "YES"])
    def test_truthy_values(self, monkeypatch, raw):
        """대소문자 무관 true/1/yes 계열은 True로 파싱된다"""
        monkeypatch.setenv("USE_RERANKER", raw)

        assert _env_bool("USE_RERANKER", False) is True

    @pytest.mark.parametrize("raw", ["false", "False", "FALSE", "0", "no", "", "abc"])
    def test_non_truthy_values(self, monkeypatch, raw):
        """truthy 집합 밖의 값(false/0/빈 문자열/오타 등)은 False다 — bool("false") == True 함정 방지"""
        monkeypatch.setenv("USE_RERANKER", raw)

        assert _env_bool("USE_RERANKER", True) is False

    def test_unset_returns_default(self, monkeypatch):
        """환경변수 미설정 시 기본값을 그대로 반환한다 — 기본값 false 회귀 보장"""
        monkeypatch.delenv("USE_RERANKER", raising=False)

        assert _env_bool("USE_RERANKER", False) is False
        assert _env_bool("USE_RERANKER", True) is True


@pytest.mark.unit
class TestEnvFloat:
    """_env_float() 단위 테스트 — RERANK_THRESHOLD 환경변수 파싱"""

    def test_parses_float(self, monkeypatch):
        """설정된 값을 float으로 파싱한다"""
        monkeypatch.setenv("RERANK_THRESHOLD", "0.7")

        assert _env_float("RERANK_THRESHOLD", 0.5) == 0.7

    def test_unset_returns_default(self, monkeypatch):
        """환경변수 미설정 시 기본값을 그대로 반환한다"""
        monkeypatch.delenv("RERANK_THRESHOLD", raising=False)

        assert _env_float("RERANK_THRESHOLD", 0.5) == 0.5

    def test_invalid_value_raises(self, monkeypatch):
        """숫자가 아닌 값은 ValueError로 즉시 실패한다"""
        monkeypatch.setenv("RERANK_THRESHOLD", "not-a-number")

        with pytest.raises(ValueError):
            _env_float("RERANK_THRESHOLD", 0.5)
