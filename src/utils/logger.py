import logging
from datetime import datetime
from src.utils.config import KST


class _KSTFormatter(logging.Formatter):
    """%(asctime)s를 한국 표준시(KST, UTC+9)로 출력하는 포매터"""
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=KST)
        return dt.strftime(datefmt) if datefmt else dt.isoformat(timespec="seconds")


def get_logger(name: str) -> logging.Logger:
    """표준 로거 반환. 핸들러가 없으면 StreamHandler를 자동 추가"""
    # 동일한 이름의 로거를 재상용함으로써 핸들러 중복 등록을 방지
    # 외부 로그 시스템과 연동할 때, 로거 이름을 지정하여 로그를 분류할 수 있음
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_KSTFormatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

def log_execution_time(func):
    """함수 실행 시간을 측정하여 GraphState.metadata에 기록하는 데코레이터"""
    # Pseudo:
    # @wraps(func)  # 내부 wrapper 함수의 메타데이터를 원래 함수의 것으로 복사
    # async def wrapper(*args, **kwargs):   # 경우에 따라서는 비동기 처리 추가
    # def wrapper(*args, **kwargs):
    #     start = time.perf_counter()
    #     try:
    #         result = func(*args, **kwargs)
    #         elapsed = time.perf_counter() - start
    #
    #         [GraphState가 첫 번째 인자인 경우에만 metadata 기록]
    #         # LangGraph의 노드 함수는 기본적으로 def node_func(state: GraphState) 형태이므로 적용하기 매우 좋다.
    #         if args and isinstance(args[0], GraphState):
    #             state = args[0]
    #             # 실행 시간뿐만 아니라 에러 정보, 토큰 사용량, 모델 버전 등을 기록하는 용도로 확장 가능
    #             state.metadata.setdefault("execution_times", {})[func.__name__] = elapsed
    #
    #         return result
    #     except Exception as e:
    #         logger.error(f"[{func.__name__}] 실행 오류: {e}")
    #         raise
    # return wrapper
    raise NotImplementedError
