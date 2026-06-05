import logging

import pytest

from src.utils.logger import get_logger


@pytest.mark.unit
class TestGetLogger:
    """get_logger() 단위 테스트"""

    def test_first_init_sets_info_level(self):
        """최초 초기화 시 레벨이 INFO로 설정되는지 검증"""
        logger = get_logger("test_logger_first_init")

        assert logger.level == logging.INFO  # 최초 초기화 시 레벨이 INFO로 설정되는지 확인

    def test_no_duplicate_handlers_on_reinit(self):
        """동일 이름으로 재호출해도 핸들러가 중복 등록되지 않는지 검증"""
        name = "test_logger_no_dup_handlers"

        logger = get_logger(name)
        handler_count = len(logger.handlers)
        logger_again = get_logger(name)

        assert logger_again is logger   # 동일한 객체인지 확인
        assert len(logger_again.handlers) == handler_count  # 핸들러가 중복되지 않았는지 확인

    def test_external_level_preserved_on_reinit(self):
        """외부에서 설정한 레벨이 get_logger 재호출 후에도 유지되는지 검증"""
        name = "test_logger_level_preserved"

        logger = get_logger(name)
        logger.setLevel(logging.DEBUG)

        logger_again = get_logger(name)

        assert logger_again.level == logging.DEBUG  # 외부에서 설정한 레벨이 get_logger 재호출 후에도 유지되는지 확인
