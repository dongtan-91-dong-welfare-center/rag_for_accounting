# 벡터 검색 결과(RetrievedChunk)와 온톨로지 그래프(OntologyNode) 사이를 잇는 어댑터.
#
# 청크와 온톨로지 노드는 ChunkNode를 OntologyNode 하위에 두지 않기로 한 결정에 따라 독립적으로 운영되며
# 둘의 연결은 청크 메타데이터의 ontology_node_id 필드를 통한 외부 매핑으로만 이뤄진다.
# 단일 책임 원칙을 위해 searcher.py가 아닌 별도 모듈로 분리한다.
from src.models.schemas import RetrievedChunk


def chunks_to_node_ids(chunks: list[RetrievedChunk]) -> list[str]:
    """RetrievedChunk 목록에서 그래프 탐색 진입점이 될 온톨로지 노드 ID를 추출한다.

    반환되는 ID는 `ChunkMetadata.ontology_node_id`이며, 이는
    `src/db/ontology/models.py`의 `OntologyNode.id`(예: "gaap-ch6-s1-최초인식")에 대응한다.
    즉 이 함수의 출력은 곧 그래프 탐색(graph.traverse_from(node_id=...))의 진입점 목록이 된다.

    설계 정책:
      - Silent Skip: ontology_node_id가 없는(None/빈 문자열) 청크는 조용히 무시하고 유효한 ID만 추출한다.
        그래프 탐색이 불가한 청크를 텍스트 단독으로 LLM에 제공하는 등의 처리는 이 함수가 아닌 호출자(워크플로우)의 책임이다.
      - 순서 유지 중복 제거: 동일한 노드를 가리키는 여러 청크가 있을 수 있으므로 첫 등장 순서를 유지하며 중복 ID를 제거한다.

    Args:
        chunks: 벡터 검색 결과 청크 목록.

    Returns:
        중복이 제거된 온톨로지 노드 ID 목록 (입력 순서 유지).
    """
    node_ids: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        nid = chunk.metadata.ontology_node_id
        if nid and nid not in seen:
            node_ids.append(nid)
            seen.add(nid)
    return node_ids
