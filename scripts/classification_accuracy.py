"""is_accounting_query 분류 정확도 측정 하니스 (#341).

[목적] 회계 질의와 비회계 질의의 경계에 놓인 표본으로 분류 노드의 정확도를 측정한다.
표본은 `data/test_data/boundary_queries.json`이며 정답 레이블은 CLASSIFY_STRATEGY_PROMPT 기준으로 작성되었다.

[비용 주의] 실행하면 표본 수만큼 LLM(classify_and_select)을 호출하므로 외부 API 비용이 발생한다.
따라서 `--run` 플래그를 명시하지 않으면 표본 검증만 수행하고 LLM은 호출하지 않는다.

사용:
  uv run python scripts/classification_accuracy.py         # 표본 규격 검증만(무비용)
  uv run python scripts/classification_accuracy.py --run   # 실측 후 docs/benchmark에 리포트 저장(비용 발생, 사전 승인 필요)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

DEFAULT_SAMPLE_PATH = _ROOT / "data" / "test_data" / "boundary_queries.json"
REPORT_DIR = _ROOT / "docs" / "benchmark"
_CATEGORIES = ("clear_accounting", "clear_non_accounting", "boundary")


def load_samples(path: Path = DEFAULT_SAMPLE_PATH) -> list[dict]:
    """표본 JSON을 읽고 규격(질의 비어있지 않음, 불리언 레이블, 유효 category)을 검증한다."""
    samples = json.loads(Path(path).read_text(encoding="utf-8"))["samples"]
    for s in samples:
        if not str(s.get("query", "")).strip():
            raise ValueError(f"{s.get('id')}: query가 비어 있습니다.")
        if not isinstance(s.get("expected_is_accounting"), bool):
            raise ValueError(f"{s.get('id')}: expected_is_accounting는 bool이어야 합니다.")
        if s.get("category") not in _CATEGORIES:
            raise ValueError(f"{s.get('id')}: category가 유효하지 않습니다.")
    return samples


def evaluate(samples: list[dict], classifier: Callable[[str], tuple[bool, float]]) -> list[dict]:
    """각 표본에 분류기를 적용하여 예측값과 정오 여부를 기록한다."""
    results = []
    for s in samples:
        predicted, confidence = classifier(s["query"])
        results.append({**s, "predicted": predicted, "confidence": confidence,
                        "correct": predicted == s["expected_is_accounting"]})
    return results


def _ratio(num: int, den: int) -> float:
    return num / den if den else 0.0


def compute_metrics(results: list[dict]) -> dict:
    """정확도, 회계(positive) 기준 정밀도·재현율, 범주별 정확도를 계산한다."""
    tp = sum(r["predicted"] and r["expected_is_accounting"] for r in results)
    fp = sum(r["predicted"] and not r["expected_is_accounting"] for r in results)
    fn = sum((not r["predicted"]) and r["expected_is_accounting"] for r in results)
    tn = sum((not r["predicted"]) and not r["expected_is_accounting"] for r in results)
    by_category = {}
    for cat in _CATEGORIES:
        rows = [r for r in results if r["category"] == cat]
        correct = sum(r["correct"] for r in rows)
        by_category[cat] = {"total": len(rows), "correct": correct, "accuracy": _ratio(correct, len(rows))}
    return {
        "total": len(results), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": _ratio(tp + tn, len(results)),
        "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn),
        "by_category": by_category,
    }


def render_markdown(metrics: dict, results: list[dict], model: str) -> str:
    """측정 결과를 기록용 마크다운으로 렌더링한다."""
    lines = [
        "# 비회계 질의 분류 정확도 측정 (#341)", "",
        f"- 측정 일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 모델: {model}",
        f"- 표본 수: {metrics['total']}", "",
        "## 요약", "",
        f"- 정확도: {metrics['accuracy']:.1%}",
        f"- 정밀도(회계 기준): {metrics['precision']:.1%}",
        f"- 재현율(회계 기준): {metrics['recall']:.1%}",
        f"- 혼동행렬: TP={metrics['tp']} FP={metrics['fp']} FN={metrics['fn']} TN={metrics['tn']}", "",
        "## 범주별 정확도", "", "| 범주 | 표본 | 정답 | 정확도 |", "|---|---|---|---|",
    ]
    for cat, v in metrics["by_category"].items():
        lines.append(f"| {cat} | {v['total']} | {v['correct']} | {v['accuracy']:.1%} |")
    wrong = [r for r in results if not r["correct"]]
    lines += ["", "## 오분류 목록", ""]
    if not wrong:
        lines.append("오분류가 없습니다.")
    else:
        lines += ["| ID | 질의 | 정답 | 예측 | 신뢰도 |", "|---|---|---|---|---|"]
        lines += [f"| {r['id']} | {r['query']} | {r['expected_is_accounting']} | {r['predicted']} | {r['confidence']:.2f} |"
                  for r in wrong]
    return "\n".join(lines) + "\n"


def _live_classifier(query: str) -> tuple[bool, float]:
    """실제 분류 노드 함수를 호출한다. 외부 API 비용이 발생한다."""
    from src.agent.nodes.rewrite import classify_and_select
    errors: list = []
    is_accounting, _strategy, confidence, _scope = classify_and_select(query, errors)
    if errors:
        # LLM 실패 시 폴백(True)이 정확도를 오염시키므로 측정을 중단한다.
        raise RuntimeError(f"분류 LLM 호출 실패: {query!r}")
    return is_accounting, confidence


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true", help="실제 LLM을 호출하여 측정한다(비용 발생)")
    ap.add_argument("--samples", type=Path, default=DEFAULT_SAMPLE_PATH)
    args = ap.parse_args(argv)

    samples = load_samples(args.samples)
    print(f"표본 {len(samples)}건 규격 검증 통과")
    if not args.run:
        print("--run이 없으므로 LLM 호출 없이 종료합니다.")
        return 0

    from src.utils.config import OPENAI_MODEL
    results = evaluate(samples, _live_classifier)
    report = render_markdown(compute_metrics(results), results, model=OPENAI_MODEL)
    out = REPORT_DIR / f"classification_accuracy_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    out.write_text(report, encoding="utf-8")
    print(f"리포트 저장: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
