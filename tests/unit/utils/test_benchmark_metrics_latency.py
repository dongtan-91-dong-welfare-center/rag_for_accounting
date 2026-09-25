"""
NFR-001 성능 지연 시간 계측 및 집계 단위 테스트

대상:
  - tests/utils/benchmark_metrics.py _percentile()
  - tests/utils/benchmark_metrics.py measure_case()
  - tests/utils/benchmark_metrics.py aggregate()
  - tests/utils/benchmark_metrics.py write_markdown_report()
"""
import time
from unittest.mock import patch

import pytest
from scripts.benchmark_baseline import _load_checkpoint, _save_checkpoint
from src.utils.config import TARGET_LATENCY_TOTAL_SEC
from tests.utils.benchmark_loader import BenchmarkCase
from tests.utils.benchmark_metrics import (
    CaseResult,
    _percentile,
    aggregate,
    measure_case,
    sort_chapters,
    write_markdown_report,
)


@pytest.mark.unit
class TestPercentileInterpolation:
    """_percentile(): 선형 보간 백분위수 산출을 검증합니다."""

    def test_empty_and_single_element(self):
        assert _percentile([], 50.0) == 0.0
        assert _percentile([12.5], 0.0) == 12.5
        assert _percentile([12.5], 50.0) == 12.5
        assert _percentile([12.5], 100.0) == 12.5

    def test_two_elements_linear_interpolation(self):
        data = [10.0, 20.0]
        assert _percentile(data, 0.0) == 10.0
        assert _percentile(data, 50.0) == 15.0
        assert _percentile(data, 100.0) == 20.0
        assert _percentile(data, 25.0) == 12.5

    def test_multi_elements_p50_p95(self):
        # 1부터 100까지 균등 분포
        data = [float(i) for i in range(1, 101)]
        # p50은 50.5 (선형 보간)
        assert _percentile(data, 50.0) == 50.5
        # p95는 95.05 (k = 99 * 0.95 = 94.05 -> 95 + 0.05 * 1 = 95.05)
        assert round(_percentile(data, 95.0), 2) == 95.05


@pytest.mark.unit
class TestMeasureCaseLatency:
    """measure_case(): time.perf_counter() 기반 소요 시간 계측을 검증합니다."""

    def test_measure_case_records_elapsed_sec(self):
        case = BenchmarkCase(
            id="TEST-LAT-001",
            category="일반회계",
            standard="GAAP",
            query="재무제표 작성 원칙은?",
            references=["일반기업회계기준 제2장 재무제표의 작성과 표시 2.10"],
            expected_answer="재무제표는 계속기업을 전제로 작성한다.",
            core_paras=["2.10"],
        )

        mock_state = {
            "final_response": None,
            "reranked_chunks": [],
            "retrieved_chunks": [],
            "rewrite_count": 0,
        }

        def _fake_run(*args, **kwargs):
            time.sleep(0.02)  # 20ms 지연
            return mock_state

        with patch("tests.integration.helpers.run_workflow_to_completion", side_effect=_fake_run):
            res = measure_case(case, k=10)

        assert res.elapsed_sec is not None
        assert res.elapsed_sec >= 0.01
        assert res.diag.get("elapsed_sec") == res.elapsed_sec
        assert res.error is None

    def test_measure_case_records_elapsed_sec_on_exception(self):
        case = BenchmarkCase(
            id="TEST-LAT-ERR",
            category="일반회계",
            standard="GAAP",
            query="오류 발생 질의",
            references=["일반기업회계기준 제2장 2.1"],
            expected_answer="테스트",
        )

        def _boom(*args, **kwargs):
            time.sleep(0.01)
            raise RuntimeError("DB 연결 오류")

        with patch("tests.integration.helpers.run_workflow_to_completion", side_effect=_boom):
            res = measure_case(case, k=10)

        assert res.elapsed_sec is not None
        assert res.elapsed_sec >= 0.005
        assert res.error is not None
        assert "RuntimeError" in res.error
        assert res.diag.get("elapsed_sec") == res.elapsed_sec


@pytest.mark.unit
class TestAggregateLatency:
    """aggregate(): NFR-001 지연 시간 통계 산출을 검증합니다."""

    def test_aggregate_computes_latency_metrics(self):
        results = [
            CaseResult(case_id=f"C-{i}", chapter="2", measurable=True, gold_paras=["2.1"], elapsed_sec=val)
            for i, val in enumerate([10.0, 20.0, 30.0, 40.0, 50.0], 1)
        ]
        summary = aggregate(results, k=10)

        assert "latency" in summary
        lat = summary["latency"]
        assert lat["p50"] == 30.0
        assert lat["min"] == 10.0
        assert lat["max"] == 50.0
        assert lat["avg"] == 30.0
        assert lat["target_sec"] == TARGET_LATENCY_TOTAL_SEC
        # k = 4 * 0.95 = 3.8 -> 40 + 0.8 * 10 = 48.0
        assert lat["p95"] == 48.0

    def test_aggregate_ignores_none_elapsed_sec(self):
        results = [
            CaseResult(case_id="C-1", chapter="2", measurable=True, gold_paras=["2.1"], elapsed_sec=None),
            CaseResult(case_id="C-2", chapter="2", measurable=True, gold_paras=["2.1"], elapsed_sec=15.0),
        ]
        summary = aggregate(results, k=10)

        assert "latency" in summary
        lat = summary["latency"]
        assert lat["p50"] == 15.0
        assert lat["avg"] == 15.0
        assert lat["max"] == 15.0

    def test_aggregate_without_any_elapsed_sec(self):
        results = [
            CaseResult(case_id="C-1", chapter="2", measurable=True, gold_paras=["2.1"], elapsed_sec=None),
        ]
        summary = aggregate(results, k=10)
        assert "latency" not in summary

    def test_aggregate_includes_latency_from_error_cases(self):
        """에러가 발생한 케이스라도 유효한 소요 시간이 계측되었다면 지연 시간 통계에 포함합니다."""
        results = [
            CaseResult(case_id="C-1", chapter="2", measurable=True, gold_paras=["2.1"], elapsed_sec=10.0),
            CaseResult(case_id="C-2", chapter="2", measurable=True, gold_paras=["2.1"], elapsed_sec=20.0),
            CaseResult(
                case_id="C-ERR",
                chapter="2",
                measurable=True,
                gold_paras=["2.1"],
                elapsed_sec=120.0,
                error="TimeoutError: 120초 제한 초과",
            ),
        ]
        summary = aggregate(results, k=10)

        assert "latency" in summary
        lat = summary["latency"]
        assert lat["max"] == 120.0
        assert lat["min"] == 10.0
        assert lat["p50"] == 20.0
        # n_measured는 채점 가능한 정상 케이스 수(2건)여야 함
        assert summary["n_measured"] == 2


@pytest.mark.unit
class TestWriteMarkdownReportLatency:
    """write_markdown_report(): 지연 시간 요약 및 컬럼 렌더링을 검증합니다."""

    def test_report_includes_latency_section_and_columns(self, tmp_path):
        results = [
            CaseResult(
                case_id="TEST-001",
                chapter="2",
                measurable=True,
                gold_paras=["2.10"],
                elapsed_sec=12.34,
                metrics={"retrieval_exact_hit@10": True, "generation_exact_hit@1": True},
                diag={"rewrite_count": 1, "strategy": "rewrite", "n_citations": 2, "n_retrieved": 5},
            ),
            CaseResult(
                case_id="TEST-002",
                chapter="2",
                measurable=True,
                gold_paras=["2.20"],
                elapsed_sec=None,  # 결측치 방어 검증
                metrics={"retrieval_exact_hit@10": False, "generation_exact_hit@1": False},
                diag={"rewrite_count": 0},
            ),
        ]
        summary = aggregate(results, k=10)

        report_path = write_markdown_report(
            results,
            summary,
            k=10,
            indexed_chapters=["2"],
            n_chunks=500,
            use_reranker=False,
            out_dir=tmp_path,
        )

        content = report_path.read_text(encoding="utf-8")

        # NFR-001 및 NFR-002 헤더
        assert "# 벤치마크 평가 리포트 (NFR-001 성능 / NFR-002 정확도)" in content
        assert "## 지연 시간 요약 (NFR-001 목표 120.0초)" in content
        assert "중위 지연 시간 (p50)" in content
        assert "95 백분위수 (p95)" in content
        assert "최대 지연 시간 (Max)" in content

        # 케이스별 결과 표의 소요(초) 컬럼 및 결측치 방어
        assert "| 소요(초) |" in content
        assert "12.34s" in content
        assert "—" in content

        # 최악 지연 시간 상위 진단 섹션
        assert "## 최악 지연 시간 진단 (상위 1건)" in content
        assert "TEST-001" in content
        assert "소요 12.34s" in content

    def test_write_markdown_report_includes_slowest_with_error(self, tmp_path):
        """최악 지연 시간 진단 표에 에러 발생 케이스가 에러 메시지와 함께 정상 렌더링되는지 검증합니다."""
        results = [
            CaseResult(
                case_id="TEST-SLOW-ERR",
                chapter="2",
                measurable=True,
                gold_paras=["2.10"],
                elapsed_sec=95.5,
                error="Database timeout occurred\nConnection reset by peer",
            ),
            CaseResult(
                case_id="TEST-FAST-OK",
                chapter="2",
                measurable=True,
                gold_paras=["2.20"],
                elapsed_sec=5.0,
                metrics={"retrieval_exact_hit@10": True, "generation_exact_hit@1": True},
                diag={"rewrite_count": 0, "strategy": "direct", "n_citations": 1, "n_retrieved": 5},
            ),
        ]
        summary = aggregate(results, k=10)
        report_path = write_markdown_report(
            results,
            summary,
            k=10,
            indexed_chapters=["2"],
            n_chunks=500,
            use_reranker=False,
            out_dir=tmp_path,
        )
        content = report_path.read_text(encoding="utf-8")

        assert "## 최악 지연 시간 진단 (상위 2건)" in content
        assert "TEST-SLOW-ERR" in content
        assert "소요 95.50s" in content
        # 줄바꿈이 공백으로 치환되어 마크다운 리스트 문법이 유지되는지 검증
        assert "에러=Database timeout occurred Connection reset by peer" in content


@pytest.mark.unit
class TestSortChapters:
    """sort_chapters(): 장 번호 목록을 숫자 장 오름차순, 비정수 장 문자열 오름차순으로 정렬합니다."""

    def test_sort_chapters_supports_non_numeric(self):
        chapters = ["10", "2", "부록", "1", "부록2", "33"]
        sorted_ch = sort_chapters(chapters)
        assert sorted_ch == ["1", "2", "10", "33", "부록", "부록2"]

    def test_sort_chapters_empty_and_single(self):
        assert sort_chapters([]) == []
        assert sort_chapters(["부록"]) == ["부록"]
        assert sort_chapters(["2"]) == ["2"]


@pytest.mark.unit
class TestCheckpointParameterGuard:
    """_load_checkpoint(): k 불일치 시 ValueError 발생 및 동일 k 시 정상 복구를 검증합니다."""

    def test_load_checkpoint_mismatched_k_raises_error(self, tmp_path):
        chk_file = tmp_path / "checkpoint_benchmark.json"
        sample_results = [
            CaseResult(case_id="C-1", chapter="2", measurable=True, gold_paras=["2.1"], elapsed_sec=5.0)
        ]
        _save_checkpoint(chk_file, sample_results, k=5, indexed=["2"])

        with pytest.raises(ValueError) as excinfo:
            _load_checkpoint(chk_file, expected_k=10)

        assert "k(5)" in str(excinfo.value)
        assert "k(10)" in str(excinfo.value)

    def test_load_checkpoint_matching_k_loads_results(self, tmp_path):
        chk_file = tmp_path / "checkpoint_benchmark.json"
        sample_results = [
            CaseResult(case_id="C-1", chapter="2", measurable=True, gold_paras=["2.1"], elapsed_sec=5.0)
        ]
        _save_checkpoint(chk_file, sample_results, k=10, indexed=["2"])

        loaded = _load_checkpoint(chk_file, expected_k=10)
        assert len(loaded) == 1
        assert loaded[0].case_id == "C-1"
        assert loaded[0].elapsed_sec == 5.0

    def test_load_checkpoint_non_existent_file_returns_empty(self, tmp_path):
        chk_file = tmp_path / "non_existent.json"
        assert _load_checkpoint(chk_file, expected_k=10) == []
