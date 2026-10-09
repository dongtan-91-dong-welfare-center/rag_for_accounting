import pytest

from src.utils import config
from src.utils.input_limits import check_feedback_length, check_length, check_query_length

pytestmark = pytest.mark.unit


def test_within_limit_passes():
    check_length("가" * 10, 10, "질의")


def test_over_limit_raises_with_guidance():
    with pytest.raises(ValueError, match=r"10자 이내.*현재 11자"):
        check_length("가" * 11, 10, "질의")


def test_query_and_feedback_use_config_limits():
    check_query_length("가" * config.MAX_QUERY_LENGTH)
    check_feedback_length("가" * config.MAX_FEEDBACK_LENGTH)
    with pytest.raises(ValueError):
        check_query_length("가" * (config.MAX_QUERY_LENGTH + 1))
    with pytest.raises(ValueError):
        check_feedback_length("가" * (config.MAX_FEEDBACK_LENGTH + 1))


def test_feedback_limit_is_not_larger_than_query_limit():
    assert config.MAX_FEEDBACK_LENGTH <= config.MAX_QUERY_LENGTH
