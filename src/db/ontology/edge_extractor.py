"""LLM(GPT-4o-mini)을 사용해 후보 문장에서 엣지를 추출한다.

edge_detector.py가 골라낸 후보 문장들을 LLM에 전달하면,
LLM은 각 문장의 엣지 타입·참조 대상·속성을 판별해 JSON으로 반환한다.
"""

import json
from pydantic import BaseModel, Field
from typing import Literal

from src.utils.config import OPENAI_MODEL
from src.utils.llm_client import client

_SYSTEM_PROMPT = """당신은 한국 회계기준서 텍스트에서 조항 간 관계(엣지)를 추출하는 전문가입니다.
주어진 후보 문장 각각에 대해 엣지를 판별하고 JSON으로 반환합니다.

엣지 타입:
- REFERENCES: 다른 장·절·문단을 참조 (제N절, 제N장, 문단 X.X 등)
- EXCLUDES: 적용범위에서 제외. include 배열에 제외 후 재포함되는 항목 기입
- HAS_CONDITION: 원칙은 A이나 특정 조건 충족 시 다른 처리(B)로 전환하며 B가 외부 조항인 경우
- IS_DEFAULT_FOR: 이 소절이 다른 절·장의 보충원칙(fallback)임을 선언하는 경우.
  "제N절~제M절에서 정하지 않은 사항은 이 절에서 적용한다"처럼 이 소절이 빈틈을 메워주는 관계.
  REFERENCES와 반대 방향 — target_ref에는 이 소절이 fallback이 되는 대상 절·장을 기입.
- NONE: 엣지 없음 (자기 소절 내 단순 언급, 일반 서술, 조건 목록 나열)

반환 형식:
{
  "edges": [
    {
      "edge_type": "REFERENCES|EXCLUDES|HAS_CONDITION|IS_DEFAULT_FOR|NONE",
      "paragraph": "출처 하위 항목 번호 (예: 6.14⑵㈏, 빈 문자열 가능)",
      "target_ref": "참조 대상 원문 (예: 제2절, 문단 6.4, 제8장 문단 8.2)",
      "source_text": "해당 원문 문장",
      "include": ["재포함 항목1"],
      "condition_text": "조건 원문 (HAS_CONDITION일 때만)"
    }
  ]
}"""


class EdgeCandidate(BaseModel):
    """LLM 응답을 파싱하는 임시 중간 객체. OntologyEdge와 유사하지만 역할이 다르다.

    OntologyEdge와의 차이:
      - from_id 없음 : LLM은 어느 노드에서 나온 참조인지 몰라도 됨.
                       builder.py가 node.id를 직접 알고 있어서 변환 시 주입한다.
      - to_id 없음   : 참조 대상은 target_ref(원문 텍스트)로만 존재.
                       resolver.py가 이를 실제 노드 ID로 변환한다.
      - 수명         : builder.py의 for 루프 안에서만 존재하고 OntologyEdge로 변환되어 사라진다.
    """

    edge_type: Literal["REFERENCES", "EXCLUDES", "HAS_CONDITION", "IS_DEFAULT_FOR", "NONE"]
    paragraph: str = ""      # 참조가 발생한 하위 항목 번호
    target_ref: str = ""     # 참조 대상 원문 텍스트 (아직 노드 ID가 아님)
    source_text: str = ""    # 해당 원문 문장
    include: list[str] = Field(default_factory=list)  # EXCLUDES 재포함 항목
    condition_text: str = "" # HAS_CONDITION 조건 원문


def extract_edges(
    subsection_id: str,   # 컨텍스트 제공용 (LLM 프롬프트에 포함)
    title: str,           # 컨텍스트 제공용
    content: str,         # Subsection 전체 텍스트 (LLM이 맥락 파악에 사용)
    candidates: list[str],  # edge_detector가 골라낸 후보 줄 목록
) -> list[EdgeCandidate]:
    """후보 문장을 LLM에 보내 엣지를 추출한다.

    NONE으로 판별된 항목은 제외하고 반환한다.
    candidates가 비어 있으면 LLM을 호출하지 않고 빈 목록을 반환한다.
    """
    if not candidates:
        return []

    # 소절 ID·제목·전체 내용을 함께 보내 LLM이 자기참조 여부를 판단할 수 있게 한다.
    user_prompt = (
        f"소절 ID: {subsection_id}\n소절 제목: {title}\n\n"
        f"전체 내용:\n{content}\n\n"
        f"다음 후보 문장들에서 엣지를 판별하세요:\n"
        + "\n".join(f"- {c}" for c in candidates)
    )

    # _client.chat.completions.create: OpenAI SDK 메서드 체인
    # .chat        : 채팅 기능 그룹
    # .completions : 텍스트 완성(completion) 기능
    # .create(...) : OpenAI 서버로 HTTP 요청 전송, LLM 응답 반환
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},  # JSON만 반환하도록 강제
        temperature=0,  # 0: 항상 확률 최高 토큰 선택 → 같은 입력이면 동일한 출력
                        # 1: 무작위성 개입 → 같은 입력이어도 매번 다른 표현 가능
    )

    # response.choices      : 응답 후보 목록 (n 파라미터로 여러 개 생성 가능, 기본값 1)
    # response.choices[0]   : 첫 번째 후보. n=1이므로 항상 [0]만 존재
    # .message.content      : LLM이 반환한 문자열 (JSON 형태)
    # response 자체는 리스트가 아닌 객체이므로 choices를 반드시 거쳐야 한다.
    # json.loads()          : JSON 문자열 → 파이썬 딕셔너리로 변환
    raw = json.loads(response.choices[0].message.content)
    # LLM 호출은 노드(Subsection) 단위로 수행되므로 하나의 응답에 엣지가 여러 개 포함될 수 있다.
    # raw.get("edges", [])  : 엣지 딕셔너리 목록. edges 키가 없으면 빈 리스트 반환
    # EdgeCandidate(**item) : 딕셔너리를 키워드 인자로 풀어서 Pydantic 객체로 변환
    #                         ** 없이 item을 통째로 넘기면 에러 발생
    return [
        EdgeCandidate(**item)
        for item in raw.get("edges", [])
        if item.get("edge_type") != "NONE"  # NONE은 그래프에 추가하지 않음
    ]
