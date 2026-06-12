from pydantic import BaseModel, Field
from typing import Literal

# BaseModel(Pydantic)을 상속하면 세 가지 기능이 자동으로 붙는다:
#   1. 타입 검증  : 객체 생성 시 잘못된 타입이 들어오면 즉시 ValidationError
#   2. 기본값 처리: Field(default_factory=list)는 인스턴스마다 새 리스트를 만들어
#                  리스트가 인스턴스 간에 공유되는 문제를 방지한다
#   3. JSON 변환 : model_dump_json() / model_validate_json()으로
#                  객체 ↔ JSON 파일 변환 (builder.py의 save_graph/load에서 사용)


class OntologyNode(BaseModel):
    """그래프의 노드(점). Standard → Section → Subsection 세 가지 타입이 있다.

    하나의 클래스에 세 타입의 필드가 섞여 있는데,
    타입별로 실제로 사용하는 필드가 다르다:
      - Standard : name, standard_type, chapter
      - Section  : title, order
      - Subsection: title, order, content, paragraphs
    """

    id: str                                              # 노드 고유 식별자. 예: "gaap-ch6-s1-최초인식"
    node_type: Literal["Standard", "Section", "Subsection"]

    # ── Standard 전용 ──────────────────────────────────────────
    name: str = ""                  # 기준서 전체 이름. 예: "제6장 금융자산·금융부채"
    standard_type: str = ""         # "GAAP" 또는 "KIFRS"
    chapter: str = ""               # 장 번호. 마크다운 헤딩에서 자동 추출됨. 예: "6"
    # ── Section / Subsection 공통 ──────────────────────────────
    title: str = ""                 # 절·소절 제목. 예: "제1절 공통사항"
    order: int = 0                  # 부모 노드 안에서의 순서 (1-based)
    content: str = ""               # 전체 텍스트. Section은 직속 문단만, Subsection은 소절 전체
    paragraphs: list[str] = Field(default_factory=list)
    # paragraphs: 포함된 문단 번호 목록. 예: ["6.4", "6.4의2"]
    # Section의 경우 직속 문단(예: 6.3)만 포함된다.



class OntologyEdge(BaseModel):
    """그래프의 엣지(선). 노드와 노드 사이의 관계를 나타낸다.

    엣지 타입별 의미:
      - CONTAINS     : 계층 포함. Standard→Section, Section→Subsection
      - REFERENCES   : 다른 절·장·문단을 참조
      - EXCLUDES     : 적용범위에서 제외 (일부 재포함 가능)
      - HAS_CONDITION: "원칙은 A, 조건 충족 시 B(외부 조항)"
    """

    from_id: str       # 엣지가 출발하는 노드 ID
    to_id: str = ""    # 엣지가 도착하는 노드 ID. 비어 있으면 아직 해소 안 된 참조.

    edge_type: Literal["CONTAINS", "REFERENCES", "EXCLUDES", "HAS_CONDITION", "IS_DEFAULT_FOR"]

    order: int = 0              # CONTAINS 전용: 자식 노드의 순서
    paragraph: str = ""         # REFERENCES·EXCLUDES·HAS_CONDITION 전용:
                                # 참조가 발생한 하위 항목 번호. 예: "6.14⑵㈏"
    source_text: str = ""       # 참조·제외·조건이 등장한 원문 문장

    include: list[str] = Field(default_factory=list)
    # include: EXCLUDES 전용. 제외 대상 중 다시 포함되는 항목 설명 목록.
    # 예: ["리스채권의 제거와 손상", "금융리스부채의 제거"]

    condition_text: str = ""    # HAS_CONDITION 전용: 조건 원문

    to_paragraph: str = ""
    # to_paragraph: REFERENCES·EXCLUDES·HAS_CONDITION 전용.
    # resolver가 target_ref에서 추출한 구체적 문단 번호. 예: "6.4", "6.A13", "실6.142"
    # to_id Subsection 안에서 어느 문단을 가리키는지 기록해 RAG 시 정밀 추출에 활용한다.

    unresolved_target: str = ""
    # unresolved_target: to_id가 빈 경우 LLM이 반환한 원문 참조 텍스트.
    # 예: "제8장 문단 8.2"
    # resolver가 노드 ID로 변환에 성공하면 to_id를 채우고 이 필드는 비워진다.


class OntologyGraph(BaseModel):
    """노드 목록과 엣지 목록으로 구성된 그래프 전체."""

    nodes: list[OntologyNode] = Field(default_factory=list)
    edges: list[OntologyEdge] = Field(default_factory=list)
