"""
케이스별 회계사 검토 대조 리포트 단위 테스트

대상: tests/utils/benchmark_metrics.py write_markdown_report()
  - 평가 자산(질문·예상정답·실제답변·판정사유)이 마크다운 보고서에서 안전하게 제외되는지
  - 회계사 검토란(③) 및 검색통과(retrieval_pass) 노출 여부
"""
import pytest

from tests.utils.benchmark_metrics import CaseResult, aggregate, write_markdown_report


def _result():
    return CaseResult(
        case_id="TEST-K-GAAP-001",
        chapter="2",
        measurable=True,
        gold_paras=["2.65"],
        metrics={
            "retrieval_pass": True,
            "generation_exact_hit@1": True,
            "retrieval_exact_hit@10": True,
            "is_answerable": True,
        },
        diag={
            "query": "간접법으로 영업활동현금흐름을 어떻게 가감하나요?",
            "expected_answer": "당기순이익에 비현금항목을 가감한다.",
            "answer": "실제 답변 전문입니다. " * 30,  # 200자 초과 — 절단 없이 들어가야 함
            "eval_reasoning": "판정 사유 전문입니다. " * 30,
            "citation_paras": ["2.65"],
            "retrieval_chapters": ["2"],
            "rewrite_count": 1,
        },
    )


@pytest.mark.unit
class TestReviewReport:
    """write_markdown_report() — 회계사 대조표 렌더링"""

    def test_review_section_and_full_text(self, tmp_path):
        r = _result()
        summary = aggregate([r], 10)
        path = write_markdown_report(
            [r], summary, k=10, indexed_chapters=["2"],
            n_chunks=1042, use_reranker=False, out_dir=tmp_path,
        )
        text = path.read_text(encoding="utf-8")

        # 대조표 섹션·케이스·각 항목
        assert "## 케이스별 회계사 검토 대조표" in text
        assert "TEST-K-GAAP-001" in text
        # 평가 자산 보호를 위해 질문과 예상 정답, 실제 답변 및 판정 사유 전문은 마크다운 보고서에 포함되지 않아야 합니다.
        assert "간접법으로 영업활동현금흐름을 어떻게 가감하나요?" not in text
        assert "당기순이익에 비현금항목을 가감한다." not in text
        assert r.diag["answer"] not in text
        assert r.diag["eval_reasoning"] not in text
        # 근거와 판정 정보 및 회계사 체크란 노출을 검증합니다.
        assert "**① 예상 근거(gold)**: 2.65" in text
        assert "**② 실제 근거(인용 문단)**: 2.65" in text
        assert "③ 회계사 검토" in text
        assert "☐적절" in text
        assert "검색 통과(핵심 Top-5)" in text  # 요약표 행

    def test_skip_and_error_cases_excluded_from_review(self, tmp_path):
        ok = _result()
        skipped = CaseResult(case_id="SKIP-1", chapter="9", measurable=False, gold_paras=["9.1"])
        errored = CaseResult(
            case_id="ERR-1", chapter="9", measurable=True, gold_paras=["9.1"],
            error="RuntimeError: boom",
        )
        summary = aggregate([ok, skipped, errored], 10)
        path = write_markdown_report(
            [ok, skipped, errored], summary, k=10, indexed_chapters=["2", "9"],
            n_chunks=1042, use_reranker=False, out_dir=tmp_path,
        )
        text = path.read_text(encoding="utf-8")
        # 대조표에는 측정 성공 케이스만 ### 헤더로 등장
        assert "### TEST-K-GAAP-001" in text
        assert "### SKIP-1" not in text
        assert "### ERR-1" not in text
