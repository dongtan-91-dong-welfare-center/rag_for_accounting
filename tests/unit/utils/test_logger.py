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


@pytest.mark.unit
class TestStructuredLogging:
    """JSON Lines 포매터 및 구조화 로깅 단위 테스트"""

    def test_json_lines_formatter_output(self):
        """_JSONLinesFormatter가 유효한 단일 행 JSON 문자열을 생성하는지 검증"""
        import json
        from src.utils.logger import _JSONLinesFormatter

        formatter = _JSONLinesFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname=__file__,
            lineno=40,
            msg="테스트 경고 메시지",
            args=(),
            exc_info=None,
        )
        record.trace_id = "tr-12345"

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["level"] == "WARNING"
        assert data["logger"] == "test.logger"
        assert data["message"] == "테스트 경고 메시지"
        assert data["trace_id"] == "tr-12345"
        assert "timestamp" in data

    def test_log_execution_time_records_to_metadata(self):
        """log_execution_time 데코레이터가 state.metadata['execution_times']에 시간을 기록하는지 검증"""
        from src.models.state import GraphState
        from src.utils.logger import log_execution_time

        @log_execution_time
        def sample_node(state: GraphState) -> dict:
            return {"status": "ok"}

        state = GraphState(original_query="테스트 쿼리")
        sample_node(state)

        assert "execution_times" in state.metadata
        assert "sample_node" in state.metadata["execution_times"]
        assert state.metadata["execution_times"]["sample_node"] >= 0.0


@pytest.mark.unit
class TestLogKv:
    """log_kv() 표준 로그 헬퍼 단위 테스트 (#408)"""

    def _capture(self, level=logging.INFO):
        from src.utils.logger import _JSONLinesFormatter

        records: list[logging.LogRecord] = []

        class _H(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("test_log_kv_capture")
        logger.handlers = [_H()]
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        return logger, records, _JSONLinesFormatter()

    def test_text_message_format(self):
        """본문이 `[태그] 설명 | 키=값` 형식이고 소요는 소수점 4자리와 s 단위인지 검증"""
        from src.utils.logger import log_kv

        logger, records, _ = self._capture()
        log_kv(logger, logging.INFO, "search", "검색 완료", 건수=3, 소요=0.12345)

        assert records[0].getMessage() == "[search] 검색 완료 | 건수=3 | 소요=0.1235s"

    def test_json_mode_has_english_fields(self):
        """JSON 모드에서 extra 영어 키가 최상위 필드로 직렬화되는지 검증"""
        import json
        from src.utils.logger import log_kv

        logger, records, fmt = self._capture()
        log_kv(logger, logging.WARNING, "db", "실패", 오류="ValueError", 질의길이=12)
        entry = json.loads(fmt.format(records[0]))

        assert entry["tag"] == "db"
        assert entry["error"] == "ValueError"
        assert entry["query_len"] == 12

    def test_unregistered_tag_rejected(self):
        """허용 목록에 없는 태그는 거부되는지 검증"""
        from src.utils.logger import log_kv

        logger, _, _ = self._capture()
        with pytest.raises(ValueError):
            log_kv(logger, logging.INFO, "Unknown", "메시지")

    def test_unregistered_key_rejected(self):
        """대응표에 없는 키는 거부되는지 검증"""
        from src.utils.logger import log_kv

        logger, _, _ = self._capture()
        with pytest.raises(ValueError):
            log_kv(logger, logging.INFO, "search", "메시지", 임의키=1)
