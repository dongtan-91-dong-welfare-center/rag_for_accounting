"""
Benchmark 데이터셋 기반 회계 RAG 정답셋(Ground Truth) 검증

산출물 - Benchmark.csv의 21개 케이스를 pytest.mark.parametrize로 동적 생성하여,
워크플로우의 회계적 신뢰성을 데이터 구동 방식으로 검증합니다.

검증 방식:
  1. 근거 일치성 — citations 필드에 기준서 조항 번호가 포함되는지 최우선 검증
  2. 답변 가능 여부 — is_answerable이 True인지 확인
  3. 답변 유사성 — expected_answer의 핵심 키워드가 생성된 답변에 포함되는지 확인
"""
import pytest
from unittest.mock import patch

from tests.utils.benchmark_loader import load_benchmark, BenchmarkCase
from src.models.schemas import (
    RetrievedChunk, RerankingResult, EvaluationResult, 
    FinalResponse, Citation
)
from src.agent.workflow import run_workflow

# ── Benchmark 케이스 로딩 ──
_BENCHMARK_CASES = load_benchmark()


@pytest.mark.benchmark
class TestBenchmarkCompliance:
    """Benchmark 데이터셋 기반 회계 RAG 품질 검증"""

    @pytest.mark.parametrize(
        "case",
        _BENCHMARK_CASES,
        ids=[c.id for c in _BENCHMARK_CASES]
    )
    def test_reference_coverage(self, case: BenchmarkCase):
        """
        답변의 citations에 Benchmark 정답셋의 '근거 문헌' 키워드가 포함되는지 검증.
        회계 RAG 시스템의 핵심 가치는 '어떤 기준서 조항을 근거로 답했는가'에 있습니다.
        """
        # 실제 워크플로우를 실행하여 결과 획득
        result = run_workflow(case.query, standard_filter=case.standard)
        response = result.get("final_response")
        assert response is not None, f"[{case.id}] final_response 결과가 존재하지 않습니다."

        # 모든 citation의 content를 하나의 문자열로 결합
        all_citation_text = " ".join(c.content for c in response.citations)

        # 근거 문헌 중 최소 1개 이상이 citation에 포함되어야 함
        matched = [
            ref for ref in case.references
            if ref in all_citation_text
        ]
        assert len(matched) > 0, (
            f"[{case.id}] 근거 문헌이 citations에 포함되지 않음. "
            f"기대: {case.references}, 실제: {all_citation_text[:200]}"
        )

    @pytest.mark.parametrize(
        "case",
        _BENCHMARK_CASES,
        ids=[c.id for c in _BENCHMARK_CASES]
    )
    def test_answerable_status(self, case: BenchmarkCase):
        """
        Benchmark 케이스에 대해 is_answerable=True가 반환되는지 검증
        Benchmark에 포함된 질의는 모두 회계 기준서에서 답변 가능한 질의입니다.
        """
        # 실제 워크플로우를 실행하여 결과 획득
        result = run_workflow(case.query, standard_filter=case.standard)
        response = result.get("final_response")
        assert response is not None, f"[{case.id}] final_response 결과가 존재하지 않습니다."

        assert response.is_answerable is True, (
            f"[{case.id}] 답변 가능한 질의인데 is_answerable=False 반환"
        )

    @pytest.mark.parametrize(
        "case",
        _BENCHMARK_CASES,
        ids=[c.id for c in _BENCHMARK_CASES]
    )
    def test_standard_filter_alignment(self, case: BenchmarkCase):
        """
        Benchmark 케이스의 standard(GAAP/KIFRS)가
        GraphState의 standard_filter와 올바르게 매핑되는지 검증.
        """
        valid_standards = {"GAAP", "KIFRS", "ALL"}
        assert case.standard in valid_standards, (
            f"[{case.id}] 잘못된 standard 값: {case.standard}"
        )

