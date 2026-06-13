"""
Phase 2: 조항정확도 벤치마크 — 비회귀 플로어

항키 기반 측정(Hit@1/@10/MRR/answerable)을 관리 테스트(run_tests.py Phase 2)로 편입한다.
실제 파이프라인으로 K-GAAP 14건을 **케이스당 1회만** 관통시켜 전 지표를 산출하고,
사람이 읽는 .md 리포트를 생성한 뒤 **비회귀 플로어**를 단언한다.

단언 정책 (결정됨):
  - 검색단계(retrieval_exact_hit@k)만 게이트한다. 생성단계 인용 Hit은 generate 노드 temperature 미지정 + CRAG 경로 변동으로 비결정적이므로 단언하지 않고 리포트에만 싣는다.
  - is_answerable은 가드레일 플로어로 함께 단언한다(레거시 하드 assert 대체).
  - 비교는 rate가 아닌 hit 카운트 + 허용밴드: hits >= floor - tolerance.
  - 코퍼스(적재 장 집합/청크 수)가 floor 파일의 baseline과 불일치하면 단언을 skip한다
    (데이터 상태 차이는 코드 회귀가 아니므로). 코퍼스 재적재 시 benchmark_floor.json을 재시드할 것.
  - NFR-002 90% 목표는 리포트에 갭으로 표기하되 하드게이트로 쓰지 않는다.

라이브(DB+OPENAI) 부재 시 tests/integration/conftest.py 의 autouse 픽스처가 세션 skip 한다.
"""
import json
from pathlib import Path

import pytest

from src.db.connection import init_pool, close_pool
from src.utils.config import TOP_K_RETRIEVAL, USE_RERANKER
from tests.utils.benchmark_loader import load_benchmark
from tests.utils.benchmark_metrics import (
    CaseResult,
    aggregate,
    get_chunk_count,
    get_indexed_chapters,
    measure_case,
    parse_gold_clauses,
    write_markdown_report,
)

_FLOOR_PATH = Path(__file__).parent / "benchmark_floor.json"


def _load_floor() -> dict:
    return json.loads(_FLOOR_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def benchmark_measurement():
    """K-GAAP 벤치마크를 실제 파이프라인으로 1회 측정하고 리포트까지 생성한다.

    측정은 모듈당 1회만 수행하여(케이스당 워크플로우 1회) 비용·비결정성을 최소화하고, 같은 결과로 검색 플로어·answerable 플로어를 함께 단언한다.
    각 케이스는 measure_case 내부에서 격리되므로 한 건이 실패해도 나머지 집계는 진행된다.
    """
    # 라이브 테스트는 main.py와 달리 풀 초기화가 자동으로 일어나지 않으므로 직접 연다.
    try:
        init_pool()
    except Exception as e:
        pytest.skip(f"벤치마크 측정 건너뜀: 커넥션 풀 초기화 불가 ({e})")

    k = TOP_K_RETRIEVAL
    try:
        indexed = get_indexed_chapters()
        if not indexed:
            pytest.skip("chunks 미적재 — 측정 불가 (수동 ingest 선행 필요)")
        n_chunks = get_chunk_count()

        # 적재된 장의 K-GAAP 케이스만 측정 대상(미적재 장은 채점 제외)
        cases = load_benchmark()
        results: list[CaseResult] = []
        for case in cases:
            clauses = parse_gold_clauses(case.references)
            chapter = clauses[0].chapter if clauses else "?"
            if chapter not in indexed:
                continue
            results.append(measure_case(case, k))

        summary = aggregate(results, k)

        # 사람이 읽는 리포트 생성(라이브 가용 시에만 도달하는 경로)
        report_path = write_markdown_report(
            results,
            summary,
            k=k,
            indexed_chapters=sorted(indexed, key=lambda x: int(x)),
            n_chunks=n_chunks,
            use_reranker=USE_RERANKER,
        )

        yield {
            "k": k,
            "results": results,
            "summary": summary,
            "indexed_chapters": sorted(indexed, key=lambda x: int(x)),
            "n_chunks": n_chunks,
            "report_path": report_path,
        }
    finally:
        close_pool()


@pytest.mark.benchmark
class TestBenchmarkAccuracy:
    """조항정확도 비회귀 플로어 (검색단계 게이트 + answerable 가드레일)"""

    def _guard_corpus(self, measurement: dict, floor: dict) -> None:
        """측정 코퍼스가 floor baseline과 다르면 단언을 skip한다(데이터 상태 != 코드 회귀)."""
        corpus = floor.get("corpus", {})
        exp_chapters = set(corpus.get("indexed_chapters", []))
        act_chapters = set(measurement["indexed_chapters"])
        if exp_chapters and exp_chapters != act_chapters:
            pytest.skip(
                f"코퍼스 불일치 → 플로어 단언 skip. "
                f"적재 장 baseline={sorted(exp_chapters, key=int)} vs 현재={sorted(act_chapters, key=int)}. "
                f"재적재했다면 benchmark_floor.json을 재시드하십시오."
            )
        exp_chunks = corpus.get("n_chunks")
        if exp_chunks is not None and exp_chunks != measurement["n_chunks"]:
            pytest.skip(
                f"코퍼스 불일치 → 플로어 단언 skip. "
                f"청크 수 baseline={exp_chunks} vs 현재={measurement['n_chunks']}. "
                f"재적재했다면 benchmark_floor.json을 재시드하십시오."
            )

    def test_report_generated(self, benchmark_measurement):
        """측정 리포트(.md)가 생성되고 측정 케이스가 1건 이상이어야 한다."""
        assert benchmark_measurement["report_path"].exists(), "벤치마크 리포트가 생성되지 않았습니다."
        assert benchmark_measurement["summary"]["n_measured"] > 0, "측정 가능 케이스가 0건입니다."

    def test_retrieval_floor(self, benchmark_measurement):
        """검색단계 조항 Hit@k 가 비회귀 플로어(허용밴드 포함) 이상이어야 한다."""
        floor = _load_floor()
        self._guard_corpus(benchmark_measurement, floor)

        k = benchmark_measurement["k"]
        key = f"retrieval_exact_hit@{k}"
        floor_hits = floor["floors"][key]
        tolerance = floor.get("tolerance", 0)
        actual = benchmark_measurement["summary"][key]["hits"]
        n = benchmark_measurement["summary"]["n_measured"]

        assert actual >= floor_hits - tolerance, (
            f"검색 조항 정확도 회귀: {key}={actual}/{n} < 플로어 {floor_hits}-{tolerance}. "
            f"리포트: {benchmark_measurement['report_path']}"
        )

    def test_answerable_floor(self, benchmark_measurement):
        """is_answerable 적중이 비회귀 플로어(허용밴드 포함) 이상이어야 한다(가드레일)."""
        floor = _load_floor()
        self._guard_corpus(benchmark_measurement, floor)

        floor_hits = floor["floors"]["is_answerable"]
        tolerance = floor.get("tolerance", 0)
        actual = benchmark_measurement["summary"]["is_answerable"]["hits"]
        n = benchmark_measurement["summary"]["n_measured"]

        assert actual >= floor_hits - tolerance, (
            f"answerable 가드레일 회귀: is_answerable={actual}/{n} < 플로어 {floor_hits}-{tolerance}. "
            f"리포트: {benchmark_measurement['report_path']}"
        )
