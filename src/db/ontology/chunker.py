"""온톨로지 그래프 → 검색 청크 변환 모듈 (FUNC-002/003)

청킹(chunking)이란?
    - 긴 문서를 검색·임베딩에 적합한 작은 조각(청크)으로 나누는 작업입니다.
    - 이 프로젝트는 PDF를 파싱(FUNC-001)하고, 그 결과를 온톨로지 그래프로 구조화한 뒤, 그래프의 노드를 청크로 변환해 pgvector에 적재(FUNC-003)합니다.

설계 결정:
    1. 청킹 단위 — 온톨로지 노드 기반.
       `md_parser`가 Subsection을 "임베딩 단위"로 설계했고, 각 노드의 `content`가 이미 절·소절 경계로 분할되어 있다.
       content를 보유한 모든 노드(Subsection + 직속 문단이 있는 Section)를 청크화한다.
       content가 없는 Standard·Section 노드는 자연스럽게 제외된다.
       → 노드의 ontology_node_id가 그대로 청크 메타데이터에 실려, 고아 청크가 없다.
    2. chunk_id 규약 — 결정적 ID.
       분할되지 않은 노드는 chunk_id == node.id (노드 ↔ 청크 1:1).
       토큰 한도 초과로 분할되면 동일 node.id를 공유하며 "-0", "-1" 순번을 붙인다.
       실행 시각·랜덤을 쓰지 않으므로 동일 입력 재실행 시 동일 ID가 나와, `index_documents`의 ON CONFLICT upsert가 멱등하게 동작한다.
    3. 토큰 한도 초과 처리 — 인덱싱 단계는 EMBEDDING_MAX_TOKENS(8192) 초과 청크를 IX-201로 스킵(데이터 손실)한다.
        청킹 단계에서 문단→문장→문자 순으로 경계를 낮춰가며 분할해 손실을 막는다. 분할 조각들은 동일 ontology_node_id를 유지한다.
    4. metadata 전파 — standard_type·chapter는 Standard 노드 기준으로 모든 청크에 전파한다(Subsection·Section 노드 자체는 이 두 필드가 비어 있기 때문).
        source_path(파서 메타데이터)는 ChunkMetadata의 extra 필드로 싣는다.
"""
import re
from collections.abc import Callable

from src.db.ontology.models import OntologyGraph
from src.models.schemas import ChunkMetadata, RetrievedChunk
from src.utils.config import EMBEDDING_MAX_TOKENS
from src.utils.embedding import count_tokens
from src.utils.exception import OntologyParsingError
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 문장 경계 분할용 — 마침표·물음표·느낌표(한글/전각 포함) 뒤의 공백에서 끊는다.
_SENTENCE_RE = re.compile(r"(?<=[.。!?！？])\s+")


def _greedy_pack(units: list[str], sep: str, max_tokens: int, count: Callable[[str], int]) -> list[str]:
    """조각을 순서대로 이어붙이되, 토큰 한도를 넘기 직전까지 한 덩어리로 묶는다.

    그리디(greedy) 방식: 버퍼에 다음 조각을 더했을 때 한도를 넘으면, 현재 버퍼를 하나의 청크로 확정하고 새 버퍼를 시작한다.
    단일 조각이 이미 한도를 넘는 경우는 여기서 쪼개지 못하고 그대로 반환되므로, 호출측에서 더 작은 경계로 재분할한다.
    """
    packed: list[str] = []
    buffer = ""
    # 조각을 순서대로 이어붙인다.
    for unit in units:
        if not unit:
            continue
        candidate = f"{buffer}{sep}{unit}" if buffer else unit
        if buffer and count(candidate) > max_tokens:
            packed.append(buffer)
            buffer = unit
        else:
            buffer = candidate
    # 마지막 버퍼를 추가한다.
    if buffer:
        packed.append(buffer)
    return packed


def _hard_split(text: str, max_tokens: int, count: Callable[[str], int]) -> list[str]:
    """문장으로도 나눌 수 없는 한 덩어리를 문자 단위 이분탐색으로 강제 분할한다.

    토큰 한도 이하가 되는 최대 길이의 앞부분을 이분탐색으로 찾아 잘라내고, 남은 뒷부분을 재귀적으로 처리한다.
    의미 경계를 무시하는 최후의 fallback이므로 한 문단/문장이 단독으로 8192 토큰을 넘는 극단적 입력에서만 호출된다.
    """
    result: list[str] = []
    remaining = text
    while count(remaining) > max_tokens:    # 토큰 한도를 넘으면, 이분탐색으로 쪼갠다.
        lo, hi = 1, len(remaining)
        while lo < hi:  # 이분탐색
            mid = (lo + hi + 1) // 2
            if count(remaining[:mid]) <= max_tokens:  # 토큰 한도 이하이면 앞부분을 더 포함
                lo = mid
            else:
                hi = mid - 1
        result.append(remaining[:lo])
        remaining = remaining[lo:]
    # 마지막 버퍼를 추가한다.
    if remaining:
        result.append(remaining)
    return result


def _split_content(content: str, max_tokens: int, count: Callable[[str], int]) -> list[str]:
    """노드 content를 토큰 한도 이하 조각들로 분할한다.

    경계 우선순위: 줄(문단) → 문장 → 문자.
    대부분의 노드는 한도 이하라 분할 없이 [content] 그대로 반환된다.
    """
    # 한도 이하이면 분할 없이 [content] 그대로 반환
    if count(content) <= max_tokens:
        return [content]

    pieces: list[str] = []
    # 1차: 줄 경계(회계 마크다운에서 각 H4 문단이 별도 줄)로 묶는다.
    for block in _greedy_pack(content.split("\n"), "\n", max_tokens, count):
        if count(block) <= max_tokens:
            pieces.append(block)
            continue
        # 2차: 한 줄이 여전히 한도를 넘으면 문장 경계로 묶는다.
        for sentence in _greedy_pack(_SENTENCE_RE.split(block), " ", max_tokens, count):
            if count(sentence) <= max_tokens:
                pieces.append(sentence)
            else:
                # 3차: 한 문장조차 한도를 넘으면 문자 단위로 강제 분할한다.
                pieces.extend(_hard_split(sentence, max_tokens, count))

    # 분할 과정에서 생긴 공백-only 조각은 버린다.
    return [p for p in pieces if p.strip()]


def chunk_graph(
    graph: OntologyGraph,
    *,
    document_id: str | None = None,
    source_path: str | None = None,
    max_tokens: int = EMBEDDING_MAX_TOKENS,
    token_counter: Callable[[str], int] = count_tokens,
) -> list[RetrievedChunk]:
    """온톨로지 그래프를 검색 청크 리스트로 변환한다.

    :param graph: build_graph(또는 parse_markdown) 결과 그래프
    :param document_id: 기준서 단위 식별자. None이면 Standard 노드의 id를 사용한다(장 단위).
    :param source_path: 원본 파일 경로(파서 메타데이터). 지정 시 ChunkMetadata extra 필드로 전파.
    :param max_tokens: 청크 1개의 토큰 상한. 초과 노드는 분할된다(기본 EMBEDDING_MAX_TOKENS).
    :param token_counter: 토큰 수 계산 함수. 기본은 KURE-v1 토크나이저. 테스트에서 모델 로드 없이 가벼운 함수를 주입할 수 있도록 인자로 노출한다.
    :return: RetrievedChunk 리스트. 각 청크는 metadata.ontology_node_id를 보유하고 score=0.0.
    :raises OntologyParsingError: content 노드가 있는데 document_id를 결정할 수 없을 때 (OT-103)
    """
    # content를 가진 노드만 청크화 대상. (Standard·직속 본문 없는 Section은 제외)
    content_nodes = [n for n in graph.nodes if (n.content or "").strip()]
    if not content_nodes:
        # 빈 문서·구조만 있는 그래프 → 적재할 청크 없음. 정상적으로 빈 리스트 반환.
        logger.info("청킹 대상 노드 없음 — 빈 청크 리스트 반환")
        return []

    # standard_type·chapter는 Standard 노드 기준으로 전 청크에 전파한다.
    standard = next((n for n in graph.nodes if n.node_type == "Standard"), None)
    # document_id가 지정되지 않았으면 Standard 노드의 id를 사용한다.
    if document_id is None:    
        # Standard 노드가 없으면 document_id를 결정할 수 없어 오류 발생
        if standard is None:
            raise OntologyParsingError(
                "document_id가 지정되지 않았고 그래프에 Standard 노드도 없어 식별자를 결정할 수 없습니다."
            )
        document_id = standard.id
    # standard_type, chapter는 Standard 노드 기준으로 전 청크에 전파한다.
    standard_type = (standard.standard_type or None) if standard else None
    chapter = (standard.chapter or None) if standard else None

    chunks: list[RetrievedChunk] = []
    for node in content_nodes:
        pieces = _split_content(node.content.strip(), max_tokens, token_counter)
        is_single = len(pieces) == 1
        for seq, piece in enumerate(pieces):
            # 분할되지 않은 노드는 chunk_id == node.id (노드 ↔ 청크 1:1).
            # 분할된 노드는 동일 node.id에 순번을 붙여 멱등성과 매핑을 동시에 만족한다.
            chunk_id = node.id if is_single else f"{node.id}-{seq}"
            metadata_kwargs: dict = {
                "ontology_node_id": node.id,
                "node_type": node.node_type,
                "standard_type": standard_type,
                "chapter": chapter,
            }
            if source_path:
                metadata_kwargs["source_path"] = source_path  # extra="allow" 비정형 필드
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    content=piece,
                    score=0.0,
                    metadata=ChunkMetadata(**metadata_kwargs),
                )
            )

    logger.info(
        f"청킹 완료: document_id={document_id}, 노드 {len(content_nodes)}개 → 청크 {len(chunks)}개"
    )
    return chunks
