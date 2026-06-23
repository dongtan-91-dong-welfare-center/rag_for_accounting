from datetime import datetime
from typing import Literal

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
        error_type: str
    ):
        """
        :param message: 에러 상세 내용
        :param node: 에러가 발생한 노드명 ("rewrite", "search", "rerank", "evaluate", "generate", "parse", "ontology", "index")
        :param error_type: 예외 식별 ID (예: "SE-101", "GN-401")
        """
        super().__init__(message) # 부모 생성자를 호출하여 Exception 클래스의 message 속성을 초기화한다.
        self.message = message
        self.node = node
        self.error_type = error_type

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
        super().__init__(message=message, node=node, error_type="CM-001")

class LLMAPIConnectionError(AccountingRAGError):
    """
    [CM-002] LLM API 호출에 실패했을 때(네트워크/인증 오류) 발생하는 예외입니다.
    """
    def __init__(self, message: str, node: NodeType):
        super().__init__(message=message, node=node, error_type="CM-002")

class DocumentParseError(AccountingRAGError):
    """
    [CM-003] 문서 파일 파싱에 실패했을 때 발생하는 예외입니다.
    착지점: src/parse/parser.py DoclingParser.parse() (converter.convert() /
    export_to_markdown() 실패 변환). raise 사이트 도입 전까지는 미배선 상태.
    """
    def __init__(self, message: str, node: NodeType):
        super().__init__(message=message, node=node, error_type="CM-003")


# ==========================================
# 2. Parse Exceptions (PS) -> node: "parse"
# ==========================================
# PS-001(DocumentNotFoundError) / PS-002(UnsupportedFormatError)는 검증 로직
# 미구현·사용처 0건으로 제거. 파서가 파일 부재/포맷 검증을 실제로 구현하는 시점에 필요한 것만 raise 사이트와 함께 재도입한다(YAGNI).


# ==========================================
# 3. Ontology Exceptions (OT) -> node: "ontology"
# ==========================================
# OT-101(CircularReferenceError, 순환참조) / OT-102(DuplicateNodeError, 중복노드)는 청커에 해당 검증이 없고 사용처 0건이라 #139에서 제거
# 순환/중복 검증 구현 시 검증 로직과 함께 재정의한다. 실사용은 OT-103뿐이다.

class OntologyParsingError(AccountingRAGError):
    """
    [OT-103] 비정형 텍스트의 구조를 파악할 수 없을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="ontology", error_type="OT-103")


# ==========================================
# 4. Search Exceptions (SE) -> node: "search"
# ==========================================

class SearchTimeoutError(AccountingRAGError):
    """
    [SE-101] pgvector 쿼리 응답 시간을 초과했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="search", error_type="SE-101")

class DatabaseQueryError(AccountingRAGError):
    """
    [SE-102] 데이터베이스 연결 실패 또는 쿼리 실행 중 오류가 발생했을 때 발생하는 예외입니다.
    검색(search) 외에 인덱싱(index) 경로에서도 발생하므로 node를 주입받을 수 있습니다.
    """
    def __init__(self, message: str, node: NodeType = "search"):
        super().__init__(message=message, node=node, error_type="SE-102")

class NoContextFoundError(AccountingRAGError):
    """
    [SE-103] 검색 결과가 없거나 임계값을 만족하는 결과가 없을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="search", error_type="SE-103")


# ==========================================
# 5. Rerank Exceptions (RR) -> node: "rerank"
# ==========================================

class RerankFailureError(AccountingRAGError):
    """
    [RR-201] 리랭킹 모델 호출 또는 점수 계산에 실패했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="rerank", error_type="RR-201")

class ScoreThresholdError(AccountingRAGError):
    """
    [RR-202] 리랭킹 후 임계값을 초과하는 청크가 하나도 없을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="rerank", error_type="RR-202")


# ==========================================
# 6. Index Exceptions (IX) -> node: "index"
# ==========================================

class EmbeddingTokenLimitError(AccountingRAGError):
    """
    [IX-201] 임베딩 생성 시 토큰 한도를 초과했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="index", error_type="IX-201")


# ==========================================
# 7. Evaluate Exceptions (EV) -> node: "evaluate"
# ==========================================

class EvaluationParsingError(AccountingRAGError):
    """
    [EV-301] LLM 평가 응답을 지정된 스키마로 파싱하는 데 실패했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="evaluate", error_type="EV-301")

class InconsistentVerdictError(AccountingRAGError):
    """
    [EV-302] 평가 결과가 내부 일관성을 위반했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="evaluate", error_type="EV-302")

class HallucinationDetectedError(AccountingRAGError):
    """
    [EV-303] 검색된 컨텍스트에 근거하지 않은 주장이 감지되었을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="evaluate", error_type="EV-303")


# ==========================================
# 8. Generate Exceptions (GN) -> node: "generate"
# ==========================================

class LLMResponseFormatError(AccountingRAGError):
    """
    [GN-401] Generate 단계에서 LLM 응답이 예상된 스키마/포맷과 일치하지 않을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="generate", error_type="GN-401")

class ContextLengthExceededError(AccountingRAGError):
    """
    [GN-402] 입력 컨텍스트의 길이가 모델의 최대 토큰 한도를 초과했을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        super().__init__(message=message, node="generate", error_type="GN-402")
