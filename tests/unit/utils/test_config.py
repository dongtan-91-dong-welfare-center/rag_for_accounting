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


@pytest.mark.unit
class TestTimeoutMarginInvariant:
    """타임아웃 마진 불변식 단위 테스트 — #310

    재시도 포함 최악 시나리오에서 LangGraph step_timeout이 먼저 발동하는
    오발동을 방지하기 위한 불변식을 검증한다.

    불변식: LLM_TIMEOUT_SECONDS * (1 + LLM_MAX_RETRIES) + backoff_buffer < GRAPH_STEP_TIMEOUT_SECONDS
    """

    # OpenAI SDK 지수 백오프(초기 0.5s, 최대 8s) 1회 발생 시 여유 추정값
    BACKOFF_BUFFER_SECONDS: float = 5.0

    def test_retry_margin_invariant_holds_with_defaults(self, monkeypatch):
        """기본값 기준으로 재시도 마진 불변식이 성립한다.

        LLM_TIMEOUT_SECONDS * (1 + LLM_MAX_RETRIES) + backoff_buffer < GRAPH_STEP_TIMEOUT_SECONDS
        를 검증하여, 환경변수 미설정 기본 상태에서 step_timeout 오발동이 발생하지 않음을 보장한다.
        """
        monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
        monkeypatch.delenv("LLM_MAX_RETRIES", raising=False)
        monkeypatch.delenv("GRAPH_STEP_TIMEOUT_SECONDS", raising=False)

        llm_timeout = _env_float("LLM_TIMEOUT_SECONDS", 45.0)
        llm_max_retries = int(_env_float("LLM_MAX_RETRIES", 1.0))
        graph_step_timeout = int(_env_float("GRAPH_STEP_TIMEOUT_SECONDS", 120.0))

        worst_case = llm_timeout * (1 + llm_max_retries) + self.BACKOFF_BUFFER_SECONDS

        assert worst_case < graph_step_timeout, (
            f"재시도 마진 불변식 위반: "
            f"LLM_TIMEOUT({llm_timeout}) * (1 + LLM_MAX_RETRIES({llm_max_retries})) "
            f"+ backoff_buffer({self.BACKOFF_BUFFER_SECONDS}) = {worst_case} "
            f">= GRAPH_STEP_TIMEOUT({graph_step_timeout}). "
            f"step_timeout 오발동 위험이 있습니다."
        )

    def test_llm_timeout_less_than_graph_step_timeout(self, monkeypatch):
        """단일 LLM 요청 타임아웃이 step_timeout보다 짧다 — Inside-Out 원칙 기본 조건.

        재시도 없이 단순 요청 하나가 step_timeout 내에 Fast-Fail 되어야 한다.
        """
        monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
        monkeypatch.delenv("GRAPH_STEP_TIMEOUT_SECONDS", raising=False)

        llm_timeout = _env_float("LLM_TIMEOUT_SECONDS", 45.0)
        graph_step_timeout = int(_env_float("GRAPH_STEP_TIMEOUT_SECONDS", 120.0))

        assert llm_timeout < graph_step_timeout, (
            f"단일 LLM 타임아웃({llm_timeout}s)이 step_timeout({graph_step_timeout}s) 이상입니다. "
            f"Inside-Out 원칙에 위배됩니다."
        )
