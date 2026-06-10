# FUNC-003/FUNC-005 공유 임베딩 모듈 — KURE-v1 자체호스팅 (이슈 #93 설계 확정)
#
# 인덱싱(index_documents)과 검색(embed_query)이 이 모듈의 embed_texts()를 공유하여
# "인덱싱 모델 = 검색 모델" 일치를 구조적으로 보장한다.
# KURE-v1은 BAAI/bge-m3를 한국어 검색에 파인튜닝한 모델로, 1024차원 벡터를 출력한다.
# normalize_embeddings=True로 단위 벡터를 생성해 pgvector의 코사인 거리(<=>)와 정합을 맞춘다.

import threading

from src.utils.config import EMBEDDING_MODEL
from src.utils.exception import LLMAPIConnectionError, NodeType
from src.utils.logger import get_logger

logger = get_logger(__name__)

_model = None               # SentenceTransformer 싱글톤 (최초 호출 시 1회 로드)
_lock = threading.Lock()    # 멀티스레드 환경에서 모델 이중 로드 방지


def _get_model():
    """SentenceTransformer 모델을 lazy 싱글톤으로 반환한다.

    - 지연 임포트: sentence_transformers는 torch를 끌고 오므로 모듈 import 시점이 아닌
      최초 임베딩 시점에 로드하여, DB 전용 경로(예: sparse 검색)의 기동 비용을 막는다.
    - _lock으로 보호해 동시 호출 시 모델이 두 번 로드되지 않도록 한다.
    """
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                logger.info(f"임베딩 모델 로드 시작: {EMBEDDING_MODEL}")
                _model = SentenceTransformer(EMBEDDING_MODEL)
                logger.info("임베딩 모델 로드 완료")
    return _model


def embed_texts(texts: list[str], node: NodeType = "index") -> list[list[float]]:
    """텍스트 목록을 KURE-v1로 임베딩하여 벡터 목록을 반환한다.

    :param texts: 임베딩할 텍스트 목록 (빈 리스트면 빈 리스트 반환)
    :param node: 실패 시 ErrorLog에 기록할 노드명 (인덱싱="index", 검색="search")
    :raises LLMAPIConnectionError: 모델 로드(최초 다운로드 포함) 또는 인코딩 실패 시.
        임베딩 실패는 DB 오류(SE-102)가 아니라 임베딩 모델 호출 문제이므로 CM-002로 분류한다.
        ① 로그상 원인이 'DB 쿼리 실패'로 둔갑하지 않고
        ② 검색 노드의 DatabaseQueryError 핸들러가 무의미한 CRAG 재탐색을 트리거하지 않는다.
    """
    if not texts:
        return []
    try:
        model = _get_model()
        vectors = model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]
    except Exception as e:
        logger.error(f"임베딩 생성 실패: {e}")
        raise LLMAPIConnectionError(f"임베딩 모델 호출 실패: {e}", node=node)


def count_tokens(text: str, node: NodeType = "index") -> int:
    """KURE-v1 토크나이저 기준 토큰 수를 반환한다.

    인덱싱 시 EMBEDDING_MAX_TOKENS(8192) 초과 청크를 IX-201로 스킵하기 위한 사전 검사에 쓰인다.
    sentence-transformers는 한도 초과 입력을 조용히 잘라내므로(silent truncation),
    잘린 벡터가 저장되는 것을 막으려면 인코딩 전에 이 함수로 길이를 확인해야 한다.

    :raises LLMAPIConnectionError: 모델(토크나이저) 로드 실패 시 CM-002로 분류
    """
    try:
        model = _get_model()
        return len(model.tokenizer.encode(text))
    except Exception as e:
        logger.error(f"토큰 수 계산 실패: {e}")
        raise LLMAPIConnectionError(f"임베딩 모델 호출 실패: {e}", node=node)
