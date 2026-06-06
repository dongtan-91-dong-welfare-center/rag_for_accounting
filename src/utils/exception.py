from datetime import datetime
from typing import Literal
from pathlib import Path

# src.models.state의 ErrorLog 타입 참조 (타입 힌팅용)
from src.models.state import ErrorLog
from src.utils.config import KST

# 허용되는 노드 타입 (LangGraph의 각 노드)
NodeType = Literal["rewrite", "search", "rerank", "evaluate", "generate", "parse", "ontology", "index"]

class AccountingRAGError(Exception):
    """
    AccountingRAG 시스템의 최상위 커스텀 예외 클래스입니다.
    모든 커스텀 예외는 이 클래스를 상속받아야 하며, LangGraph의 ErrorLog 구조와 호환되도록 설계되었습니다.
    """
    def __init__(
        self, 
        message: str, 
        node: NodeType, 
        error_type: str, 
        is_retryable: bool
    ):
        """
        :param message: 에러 상세 내용
        :param node: 에러가 발생한 노드명 ("rewrite", "search", "rerank", "evaluate", "generate", "parse", "ontology", "index")
        :param error_type: 예외 식별 ID (예: "SE-101", "GN-401")
        :param is_retryable: LangGraph 제어 로직에서 재시도 가능 여부
        """
        super().__init__(message) # 부모 생성자를 호출하여 Exception 클래스의 message 속성을 초기화한다.
        self.message = message
        self.node = node
        self.error_type = error_type
        self.is_retryable = is_retryable

    def to_error_log(self) -> ErrorLog:
        """
        예외 객체를 LangGraph 상태 관리를 위한 ErrorLog 딕셔너리로 변환합니다.
        
        :return: ErrorLog 타입의 딕셔너리
        """
        return {
            "timestamp": datetime.now(KST).isoformat(), # datetime 객체를 ISO 8601 국제 표준 형식의 문자열로 변환
            "node": self.node,
            "error_type": self.error_type,
            "message": self.message
        }


# ==========================================
# 1. Common Exceptions (CM)
# 전체 프로세스에서 발생 가능. 노드명 동적 주입.
# ==========================================

class ConfigNotFoundError(AccountingRAGError):
    """
    [CM-001] 환경 변수 또는 설정 파일이 누락되었을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str, node: NodeType):
        super().__init__(message=message, node=node, error_type="CM-001", is_retryable=False)

class LLMAPIConnectionError(AccountingRAGError):
    """
    [CM-002] LLM API 호출에 실패했을 때(네트워크/인증 오류) 발생하는 예외입니다.
    """
    def __init__(self, message: str, node: NodeType):
        super().__init__(message=message, node=node, error_type="CM-002", is_retryable=True)

class DocumentParseError(AccountingRAGError):
    """
    [CM-003] 문서 파일 파싱에 실패했을 때 발생하는 예외입니다.
    Windows 파일 경로 호환을 위해 pathlib.Path를 사용한 추가 정보를 지원합니다.
    """
    def __init__(self, message: str, node: NodeType, file_path: Path | None = None):
        msg = f"{message} (File: {file_path})" if file_path else message
        super().__init__(message=msg, node=node, error_type="CM-003", is_retryable=False)


# ==========================================
# 2. Parse Exceptions (PS) -> node: "parse"
# ==========================================

class DocumentNotFoundError(AccountingRAGError):
    """
    [PS-001] 지정된 경로에 문서 파일이 존재하지 않을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="parse", error_type="PS-001", is_retryable=False)

class UnsupportedFormatError(AccountingRAGError):
    """
    [PS-002] 시스템에서 지원하지 않는 파일 형식일 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="parse", error_type="PS-002", is_retryable=False)


# ==========================================
# 3. Ontology Exceptions (OT) -> node: "ontology"
# ==========================================

class CircularReferenceError(AccountingRAGError):
    """
    [OT-101] 조항 간의 참조 관계가 순환을 형성했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="ontology", error_type="OT-101", is_retryable=False)

class DuplicateNodeError(AccountingRAGError):
    """
    [OT-102] 동일한 조항 번호가 중복으로 정의되었을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="ontology", error_type="OT-102", is_retryable=False)

class OntologyParsingError(AccountingRAGError):
    """
    [OT-103] 비정형 텍스트의 구조를 파악할 수 없을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="ontology", error_type="OT-103", is_retryable=False)


# ==========================================
# 4. Search Exceptions (SE) -> node: "search"
# ==========================================

class SearchTimeoutError(AccountingRAGError):
    """
    [SE-101] pgvector 쿼리 응답 시간을 초과했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="search", error_type="SE-101", is_retryable=True)

class DatabaseQueryError(AccountingRAGError):
    """
    [SE-102] 데이터베이스 연결 실패 또는 쿼리 실행 중 오류가 발생했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="search", error_type="SE-102", is_retryable=True)

class NoContextFoundError(AccountingRAGError):
    """
    [SE-103] 검색 결과가 없거나 임계값을 만족하는 결과가 없을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="search", error_type="SE-103", is_retryable=False)


# ==========================================
# 5. Rerank Exceptions (RR) -> node: "rerank"
# ==========================================

class RerankFailureError(AccountingRAGError):
    """
    [RR-201] 리랭킹 모델 호출 또는 점수 계산에 실패했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="rerank", error_type="RR-201", is_retryable=True)

class ScoreThresholdError(AccountingRAGError):
    """
    [RR-202] 리랭킹 후 임계값을 초과하는 청크가 하나도 없을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="rerank", error_type="RR-202", is_retryable=False)


# ==========================================
# 6. Index Exceptions (IX) -> node: "index"
# ==========================================

class EmbeddingTokenLimitError(AccountingRAGError):
    """
    [IX-201] 임베딩 생성 시 토큰 한도를 초과했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="index", error_type="IX-201", is_retryable=False)


# ==========================================
# 7. Evaluate Exceptions (EV) -> node: "evaluate"
# ==========================================

class EvaluationParsingError(AccountingRAGError):
    """
    [EV-301] LLM 평가 응답을 지정된 스키마로 파싱하는 데 실패했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="evaluate", error_type="EV-301", is_retryable=True)

class InconsistentVerdictError(AccountingRAGError):
    """
    [EV-302] 평가 결과가 내부 일관성을 위반했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="evaluate", error_type="EV-302", is_retryable=False)

class HallucinationDetectedError(AccountingRAGError):
    """
    [EV-303] 검색된 컨텍스트에 근거하지 않은 주장이 감지되었을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="evaluate", error_type="EV-303", is_retryable=False)


# ==========================================
# 8. Generate Exceptions (GN) -> node: "generate"
# ==========================================

class LLMResponseFormatError(AccountingRAGError):
    """
    [GN-401] Generate 단계에서 LLM 응답이 예상된 스키마/포맷과 일치하지 않을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="generate", error_type="GN-401", is_retryable=True)

class ContextLengthExceededError(AccountingRAGError):
    """
    [GN-402] 입력 컨텍스트의 길이가 모델의 최대 토큰 한도를 초과했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="generate", error_type="GN-402", is_retryable=False)
