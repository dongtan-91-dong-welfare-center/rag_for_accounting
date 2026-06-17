"""
HIL auto-resume 라이브 스모크

단위 테스트(test_workflow_to_completion.py, test_hil_workflow.py)가 닿지 않는 경로만 라이브로 검증한다
실제 LLM이 decompose/stepback으로 분류 → human_review에서 interrupt() → approve resume으로 끝까지 완료.

@pytest.mark.benchmark 게이트(라이브 LLM+Docker). tests/integration/conftest.py의
check_integration_env autouse 픽스처가 키/인프라 부재 시 세션 skip 한다.
inference/ 하위는 conftest가 LLM을 모킹하므로(자식 conftest), 이 스모크는 integration 직속에 둔다.

정확도 게이트(Hit@1/MRR/answerable)는 test_benchmark_accuracy.py의 책임이며, 본 스모크는
benchmark.jsonl/benchmark_floor.json을 건드리지 않는다(전용 인라인 케이스).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from src.agent.workflow import run_workflow, resume_workflow
from src.db.connection import init_pool, close_pool
from src.utils.embedding import embed_texts
from src.utils.logger import get_logger
from tests.utils.benchmark_metrics import (
    extract_chunk_paras,
    get_indexed_chapters,
    gold_para_set,
    parse_gold_clauses,
)

_log = get_logger(__name__)


@dataclass
class HILSmokeCase:
    id: str
    query: str
    expected_strategy: str          # "decompose" | "stepback"
    standard: str = "GAAP"
    gold_refs: list[str] = field(default_factory=list)


# HIL 트리거 케이스 — 분류 정의(src/agent/prompts.py)에 명백히 부합하도록 설계해
# 라이브 분류의 hard fail 오탐을 줄인다. gold_refs는 soft 진단(로그)에만 쓰인다.
_HIL_CASES = [
    HILSmokeCase(
        id="HIL-DECOMPOSE-001",
        query="K-GAAP에서 유형자산 재평가잉여금을 처분할 때의 회계처리와, 매도가능증권 중 지분상품을 처분할 때 평가손익 처리 방법을 각각 알려주세요.",
        expected_strategy="decompose",   # 두 개의 독립적 회계 주제 → 분해
        gold_refs=["일반기업회계기준 제10장 10.42조", "일반기업회계기준 제6장 6.31조"],
    ),
    HILSmokeCase(
        id="HIL-STEPBACK-001",
        query="2020년 12월 말 ㈜한빛이 12억원에 취득한 토지를 재평가모형으로 평가 중인데, 5년이 지난 2025년에 재평가를 반드시 다시 수행해야 하나요?",
        expected_strategy="stepback",    # 회사명·금액·날짜가 포함된 과도하게 구체적 질의 → 추상화
        gold_refs=["일반기업회계기준 제10장 10.22조"],
    ),
]


@pytest.fixture(scope="module")
def live_corpus():
    """라이브 풀을 열고 chunks 적재를 확인한다.

    interrupt/strategy 단언은 search 이전(human_review)에서 끝나 코퍼스와 무관하지만,
    approve resume 이후 search가 chunks 테이블을 읽으므로 미적재 시 UndefinedTable로 죽는다.
    따라서 적재되지 않았으면 resume 경로를 검증할 수 없어 skip 한다.
    """
    try:
        init_pool()
    except Exception as e:
        pytest.skip(f"커넥션 풀 초기화 불가 — 라이브 스모크 skip ({e})")
    try:
        if not get_indexed_chapters():
            pytest.skip("chunks 미적재 — 수동 ingest 선행 필요")
        # 임베딩 모델(KURE-v1) 콜드 로드를 setup으로 분리한다.
        # 첫 검색에서 모델을 처음 로드하면 search 노드가 step_timeout(30s)을 넘겨 TimeoutError로
        # 죽으므로(HIL 로직과 무관한 인프라 콜드 스타트), 케이스 실행 전에 미리 warm up 한다.
        embed_texts(["워밍업"], node="search")
        yield
    finally:
        close_pool()


def _citation_paras(final_response) -> set[str]:
    """final_response 인용 본문에서 조항 문단번호를 모은다(soft 진단용)."""
    paras: set[str] = set()
    for c in final_response.citations:
        paras |= extract_chunk_paras(c.content)
    return paras


@pytest.mark.benchmark
@pytest.mark.parametrize("case", _HIL_CASES, ids=[c.id for c in _HIL_CASES])
def test_hil_live_resume(case: HILSmokeCase, live_corpus):
    """라이브 분류 → interrupt → approve resume → 완료를 단언한다."""
    # 1) 최초 실행: decompose/stepback로 분류되면 human_review에서 interrupt
    result = run_workflow(case.query, standard_filter=case.standard)

    interrupts = result.get("__interrupt__")
    assert interrupts, (
        f"[{case.id}] interrupt 미발생 — 전략 유도 실패. "
        f"strategy={getattr(result.get('rewritten_query'), 'strategy', None)}"
    )
    assert result.get("thread_id"), f"[{case.id}] interrupt 상태에 thread_id 없음"

    strategy = result["__interrupt__"][0].value["strategy"]
    assert strategy == case.expected_strategy, (
        f"[{case.id}] 기대 {case.expected_strategy} ≠ 실제 {strategy} "
        f"— 분류 회귀 또는 케이스 경계 모호"
    )

    # 2) approve로 재개: interrupt 소거 + 최종 응답 생성
    resumed = resume_workflow(result["thread_id"], {"action": "approve"})
    assert "__interrupt__" not in resumed, f"[{case.id}] resume 후에도 interrupt 잔존"
    final_response = resumed.get("final_response")
    assert final_response is not None, f"[{case.id}] resume 후 final_response가 None"

    # 3) soft 진단(로그 전용, 게이트 아님): gold 조항이 인용에 포함됐는지
    gold = gold_para_set(parse_gold_clauses(case.gold_refs))
    cited = _citation_paras(final_response)
    _log.info(
        "[%s] strategy=%s gold=%s cited=%s covered=%s",
        case.id, strategy, sorted(gold), sorted(cited), sorted(gold & cited),
    )
