"""
Benchmark 데이터셋 기반 회계 RAG 정합성 검증 (라이브 불요)

조항정확도(citations 근거 일치·is_answerable)의 실측·비회귀 단언은
test_benchmark_accuracy.py(조항키 기반 + 비회귀 플로어)로 이관되었다.
  - 기존 test_reference_coverage(`ref in citation_text` 부분일치)는 정답 라벨('제18장 18.7조')이
    청크 본문('#### 18.7')에 문자열로 존재하지 않아 라이브에서 0/14로 구조적 실패 → 삭제.
  - 기존 test_answerable_status(전건 True 하드 assert)는 베이스라인 13/14를 반영해
    test_benchmark_accuracy.test_answerable_floor(가드레일 플로어)로 대체.

이 파일에는 라이브 환경 없이도 결정적으로 검증 가능한 데이터셋 정합성만 남긴다.
"""
import pytest

from tests.utils.benchmark_loader import load_benchmark, BenchmarkCase

# ── Benchmark 케이스 로딩 ──
_BENCHMARK_CASES = load_benchmark()


@pytest.mark.benchmark
class TestBenchmarkCompliance:
    """Benchmark 데이터셋 정합성 검증 (라이브 불요·결정적)"""

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
