# rewrite 노드 통합 테스트 — 실제 LLM 호출
# 실행: uv run pytest tests/integration/test_rewrite_integration.py -v

from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

from src.agent.nodes.rewrite import rewrite_query
from src.models.state import GraphState

QUERIES = [
    (1,  "K-GAAP이랑 K-IFRS 적용 시 현금흐름표의 영업활동현금흐름 계산 방법이 어떻게 다른가요? "
         "간접법으로 구할 때 대손상각비나 대손충당금 환입액 처리가 헷갈립니다. "
         "전기 조서를 보니까 비현금흐름으로 다 가감해 주던데 정확한 기준이 뭔가요?"),
    (2,  "K-GAAP에서 차입원가를 자본화할 때, 특정차입금과 일반차입금 각각에 대해 "
         "자본화가 강제사항인지 선택사항인지 규정이 어떻게 되나요?"),
    (3,  "K-GAAP 적용 기업인데, 기말 퇴직금추계액을 산정해 보니 전년도보다 금액이 감소했습니다. "
         "이 감소분을 퇴직급여 환입(수익)으로 회계처리해도 기준서상 문제가 없을까요?"),
    (4,  "회사가 전환사채(CB)를 발행했는데, K-GAAP 상에서 이를 사채(장기성부채)와 "
         "전환권대가(자본)로 분리해서 인식하는 것이 맞는지 확인 부탁드립니다."),
    (5,  "당사가 전환사채(CB)를 발행한 게 아니라 '투자(취득)'한 경우입니다. "
         "K-GAAP에서는 내재된 전환권을 주계약인 채권과 분리하여 별도의 파생금융상품(자산)으로 "
         "분류 및 표시해야 하나요?"),
    (6,  "중소기업 임의감사를 나갔는데, 회사가 유형자산 감가상각비를 세법상 산식(정률법 등)으로 "
         "그대로 계산해 두었습니다. 이거 K-GAAP 상으로 허용되나요?"),
    (7,  "K-GAAP 기업이 채권형 매도가능증권을 보유하고 있습니다. "
         "K-IFRS의 FVOCI 금융자산처럼 유효이자율법으로 상각을 먼저 한 다음, "
         "기말 상각후원가와 공정가치의 차액을 매도가능증권평가손익(자본)으로 잡는 절차가 맞나요?"),
    (8,  "과거 20년 말에 토지 재평가를 수행한 K-GAAP 기업입니다. "
         "일반기업회계기준서에 '매 3년이나 5년마다' 재평가를 수행한다는 문구가 있던데, "
         "이게 5년이 지나면 무조건 의무적으로 재평가를 다시 해야 한다는 뜻인가요?"),
    (9,  "K-GAAP 하에서 재평가모형을 적용 중인 토지/건물 등 유형자산을 처분할 때, "
         "기존에 자본으로 인식해 둔 재평가잉여금은 당기손익으로 재분류조정(Recycling) 하는 것이 맞습니까?"),
    (10, "K-GAAP에서 매도가능증권 중 지분상품을 처분할 때의 구체적인 회계처리가 궁금합니다. "
         "기존에 인식했던 평가손익은 어떻게 처리하나요?"),
    (11, "회사가 기말에 외화환산손익을 계산한 후, 외화환산이익에서 손실을 뺀 순액으로만 "
         "손익계산서에 표시해 두었습니다. "
         "K-GAAP 상 외화환산손익을 이렇게 상계하여 순액 표시하는 것이 규정상 허용되나요?"),
    (12, "확정급여형(DB) 퇴직연금 제도를 운용 중인 K-GAAP 기업입니다. "
         "K-IFRS처럼 별도의 계리평가보고서 없이, 사외적립자산 내역만 기록하고 "
         "퇴직급여충당부채는 기말 일시퇴직기준 추계액으로 설정하면 올바른 회계처리인가요?"),
    (13, "K-GAAP 기업이 만기보유증권이나 장기성 채권을 보유하고 있을 때, "
         "K-IFRS와 동일하게 유효이자율법을 적용하여 이자수익을 인식해야 합니까?"),
    (14, "회사가 퇴직연금운용자산을 재무상태표에 계상할 때, 일부는 장기금융상품으로 잡고 "
         "일부는 퇴직급여충당부채의 차감 항목으로 쪼개서 표시했습니다. "
         "퇴직급여충당부채 총액이 운용자산보다 더 큰 상황인데, "
         "운용자산을 이렇게 두 가지로 나누어 분류하는 명확한 기준이 무엇인가요?"),
    # stepback 예상 — 특정 회사명·금액·날짜 포함
    (15, "저희 A사가 2024년 1월에 건물을 취득원가 50억원, 잔존가치 5억원, 내용연수 20년으로 "
         "취득했는데 2024년 말 정액법 감가상각비를 K-GAAP 기준으로 어떻게 계산하나요?"),
    (16, "삼성전자가 2023년 12월 31일 기준으로 영업권 손상검사를 수행했는데 "
         "장부금액 300억원, 회수가능액 200억원으로 산정됐습니다. "
         "K-GAAP 상 손상차손 인식 금액과 회계처리 방법은 무엇인가요?"),
    # decompose 예상 — 두 가지 이상의 독립적인 주제 포함
    (17, "K-GAAP에서 유형자산 감가상각 방법과 무형자산 상각 방법의 차이점, "
         "그리고 리스자산의 사용권자산 상각 처리 방법을 각각 설명해 주세요."),
    (18, "전환사채 발행자의 K-GAAP 회계처리 방법과 "
         "매도가능증권 평가손익의 처분 시 재분류조정 방법을 함께 설명해 주세요."),
]

VALID_STRATEGIES = {"hyde", "decompose", "stepback"}
OUTPUT_PATH = Path(__file__).parents[2] / "docs" / "superpowers" / "plans" / "llm_rewrite.md"


def _write_md(results: list[dict]) -> None:
    lines = ["# rewrite 노드 LLM 실행 결과\n"]
    for r in results:
        # 알파벳 정렬 시 Q1과 Q10이 뒤섞이지 않도록 자릿수를 맞춤
        lines.append(f"## Q{r['num']:02d}")
        lines.append(f"**원문**")
        # > — 마크다운 blockquote, 렌더링 시 회색 블록으로 표시되어 원문 질의를 다른 내용과 시각적으로 구분
        lines.append(f"> {r['query']}\n")
        lines.append(f"**전략:** `{r['strategy']}`\n")
        lines.append("**search_queries**")
        for i, sq in enumerate(r["search_queries"], start=1):
            lines.append(f"{i}. {sq}")
        lines.append("")
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")


def test_rewrite_all_queries():
    results = []

    for num, query in QUERIES:
        state = rewrite_query(GraphState(query=query))
        rq = state.rewritten_query
        results.append({
            "num": num,
            "query": query,
            "is_accounting": state.is_accounting_query,
            "strategy": rq.strategy,
            "search_queries": rq.search_queries,
            "original": rq.original,
        })

    _write_md(results)

    for r in results:
        assert r["is_accounting"] is True, f"Q{r['num']}: 회계 질의로 분류되지 않음"
        assert r["strategy"] in VALID_STRATEGIES, f"Q{r['num']}: 유효하지 않은 전략 '{r['strategy']}'"
        assert r["search_queries"][0] == r["query"], f"Q{r['num']}: search_queries[0]이 원문과 다름"
        assert r["original"] == r["query"], f"Q{r['num']}: rewritten_query.original이 원문과 다름"
