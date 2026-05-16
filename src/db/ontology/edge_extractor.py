"""LLM(GPT-5.4-mini)을 사용해 후보 문장에서 엣지를 추출한다.

edge_detector.py가 골라낸 후보 문장들을 LLM에 전달하면,
LLM은 각 문장의 엣지 타입·참조 대상·속성을 판별해 JSON으로 반환한다.
"""

import json
from pydantic import BaseModel, Field
from typing import Literal

from src.utils.config import OPENAI_MODEL
from src.utils.llm_client import client

_SYSTEM_PROMPT = """당신은 한국 회계기준서 텍스트에서 조항 간 관계(엣지)를 추출하는 전문가입니다.
후보 문장 각각을 독립적으로 판별해 JSON으로 반환합니다.

엣지 타입:
판별 우선순위: 문장에 "제외한다"·"적용하지 않는다"가 있으면 EXCLUDES를 먼저 검토한다.
  절·문단 번호가 함께 등장하더라도 그 번호가 제외 대상이면 REFERENCES가 아니라 EXCLUDES다.

- EXCLUDES: 특정 조건·항목을 이 소절의 적용범위에서 제외하는 경우.
  패턴: "A는 제외한다", "A에 대하여는 적용하지 않는다", "A는 이 절/장을 적용하지 않는다"
  → 문장에서 "제외"·"적용하지 않는다" 앞에 오는 A가 target_ref다.
  A에 절·문단 번호(예: 제4절, 문단 6.9)가 있으면 그 번호를, 없으면 원문 그대로 기입한다.
  절·문단 번호 없이 "이 절을 적용하지 않는다" 형태이면 target_ref에 "이 절"을 기입한다.
  제외 대상이 이거나/또는/및으로 연결된 경우 반드시 각각 별도 엣지로 반환한다.
  예: "A이거나 B 또는 C는 제외한다" → A, B, C 각각 EXCLUDES 엣지 (절대 하나로 합치지 말 것)
- REFERENCES: 독자가 해당 장·절·문단으로 이동해 규정을 확인하거나 적용해야 하는 경우.
  EXCLUDES 패턴("제외", "적용하지 않는다")이 없는 문장에만 적용한다.
  target_ref는 반드시 "제N절", "문단 X.X", "제N장" 형식의 탐색 가능한 참조여야 한다.
  한 문장에 참조가 여러 개이면(이거나/또는/및/과 등으로 연결) 반드시 각각 별도 엣지로 반환한다.
  예: "문단 6.4 또는 문단 6.9를 적용한다" → 문단 6.4, 문단 6.9 각각 REFERENCES 엣지
- HAS_CONDITION: 원칙은 A이나 특정 조건 충족 시 다른 처리(B)로 전환하며 B가 외부 조항인 경우
- IS_DEFAULT_FOR: 이 소절이 다른 절·장의 보충원칙(fallback)임을 선언하는 경우.
  "제N절~제M절에서 정하지 않은 사항은 이 절에서 적용한다"처럼 이 소절이 빈틈을 메워주는 관계.
  REFERENCES와 반대 방향 — target_ref에는 이 소절이 fallback이 되는 대상 절·장을 기입.
- NONE: 해당 문장이 다음에 해당하면 NONE으로 판별한다:
  ① 괄호 안 부연 설명이나 예시 (예: "금융상품(최초인식 이후 공정가치로 측정하며...)")
  ② 이 소절 내 개념·용어를 정의하거나 조건을 나열하는 문장
  ③ 절·장·문단 번호 없이 다른 항목의 이름만 언급하는 문장
  ④ 자기 소절의 규정을 풀어쓰거나 예시를 제시하는 문장

include 필드 사용 규칙 (EXCLUDES 전용):
  제외(EXCLUDES) 대상 안에서 예외적으로 '재포함(적용)'이 선언된 항목을 기입한다.
  주로 다음 두 가지 패턴으로 나타난다:
  패턴 1 (접속사형): "A는 제외한다. 단, B에 대하여는 적용한다" / "다만, B는 이 절을 적용한다"
  패턴 2 (괄호형): "A(B인 경우는 제외)" → A 전체가 제외 대상일 때, 괄호 안의 B는 예외적으로
    제외되지 않고 '재포함'됨을 의미한다.
  → 위 두 패턴에서 재포함되는 대상인 B만 추출하여 배열로 기입한다. A(제외 대상 자체)는 기입하지 않는다.
  예1 (접속사형): "리스에 따른 권리와 의무는 이 장을 적용하지 않는다. 다만,
       ㈎ 리스채권의 제거와 손상, ㈏ 금융리스부채의 제거 및
       ㈐ 리스에 내재된 파생상품에 대하여는 이 장을 적용한다."
  → include: ["리스채권의 제거와 손상", "금융리스부채의 제거", "리스에 내재된 파생상품"]
  예2 (괄호형): "자산의 매입계약(금융상품 또는 파생상품인 경우는 제외)"
  → target_ref: "자산의 매입계약", include: ["금융상품 또는 파생상품인 경우"]

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
    # content가 너무 길면 출력 토큰 한계를 초과해 JSON이 잘리므로 앞부분만 전달한다.
    MAX_CONTENT_CHARS = 12000
    content_ctx = content[:MAX_CONTENT_CHARS] + ("..." if len(content) > MAX_CONTENT_CHARS else "")
    user_prompt = (
        f"소절 ID: {subsection_id}\n소절 제목: {title}\n\n"
        f"전체 내용:\n{content_ctx}\n\n"
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
