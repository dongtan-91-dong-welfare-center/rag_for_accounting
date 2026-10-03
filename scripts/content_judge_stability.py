"""답변 내용 판정(content_pass)의 반복 안정성 측정 및 케이스별 분석표 생성 (#183).

[목적] 라이브 벤치마크가 저장한 케이스별 답변(baseline_*.json)을 같은 판정 LLM으로 여러 번 다시 판정하여,
같은 답변에 대한 판정이 얼마나 흔들리는지 잰다. 파이프라인(검색·생성)은 다시 돌리지 않으므로 비용이 판정 호출분으로 한정된다.
근거: 전수 재실행은 생성 변동까지 섞여 판정 자체의 흔들림을 분리할 수 없다.

사용법: uv run python scripts/content_judge_stability.py <baseline.json> [--repeats 3] [--out docs/benchmark/xxx.md]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PASS = "pass"


def summarize_stability(verdicts_by_case: dict[str, list[str]]) -> dict:
    """케이스별 판정 목록으로 안정성 지표를 집계한다.

    - n_unstable: 반복 판정 값이 하나라도 다른 케이스 수
    - n_pass_boundary_flips: pass와 비pass가 섞인 케이스 수(content_pass 값이 실제로 뒤집히는 경우)
    """
    unstable = sorted(c for c, v in verdicts_by_case.items() if len(set(v)) > 1)
    boundary = sorted(c for c, v in verdicts_by_case.items() if len({x == PASS for x in v}) > 1)
    n = len(verdicts_by_case)
    return {
        "n_cases": n,
        "n_unstable": len(unstable),
        "unstable_ids": unstable,
        "n_pass_boundary_flips": len(boundary),
        "pass_boundary_ids": boundary,
        "agreement_rate": (n - len(unstable)) / n if n else 0.0,
    }


def _rejudge(cases: list[dict], repeats: int) -> dict[str, list[str]]:
    from tests.utils.benchmark_metrics import judge_content

    out: dict[str, list[str]] = {}
    for c in cases:
        d = c["diag"]
        vs = [d["content_verdict"]]  # 원 실행의 판정이 첫 번째 표본
        for _ in range(repeats):
            vs.append(judge_content(query=d["query"], expected_answer=d["expected_answer"], answer=d["answer"]).verdict)
        out[c["case_id"]] = vs
    return out


def _render(cases: list[dict], verdicts: dict[str, list[str]], stab: dict, src: str, repeats: int) -> str:
    lines = [
        "# 답변 내용 판정 안정성 및 케이스별 분석 (#183)",
        "",
        f"원자료: `{src}` (원 실행 판정 1회 + 재판정 {repeats}회, 총 {repeats + 1}회/케이스)",
        "",
        "## 안정성",
        "",
        f"- 케이스 수: {stab['n_cases']}",
        f"- 판정 전부 일치: {stab['n_cases'] - stab['n_unstable']}/{stab['n_cases']} ({stab['agreement_rate']:.1%})",
        f"- content_pass가 뒤집힌 케이스(pass와 비pass 혼재): {stab['n_pass_boundary_flips']}건 {stab['pass_boundary_ids']}",
        f"- 판정 값이 하나라도 달라진 케이스: {stab['n_unstable']}건 {stab['unstable_ids']}",
        "",
        "## 케이스별 표",
        "",
        "| 케이스 | 장 | 검색통과 | 핵심 판정 | 반복 판정 | 첫 판정 사유(비pass만) |",
        "|---|---|---|---|---|---|",
    ]
    for c in cases:
        d, m = c["diag"], c["metrics"]
        rep = "/".join(verdicts[c["case_id"]])
        reason = "" if d["content_verdict"] == PASS else d.get("content_reasoning", "").replace("|", "/").replace("\n", " ")
        lines.append(
            f"| {c['case_id'].replace('TEST-K-GAAP-', '')} | {c['chapter']} | "
            f"{'O' if m.get('retrieval_pass') else 'X'} | {d['content_verdict']} | {rep} | {reason} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("baseline")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--out", default=None)
    a = p.parse_args(argv)
    data = json.loads(Path(a.baseline).read_text(encoding="utf-8"))
    cases = [c for c in data["cases"] if c.get("measurable") and c.get("diag", {}).get("content_verdict")]
    verdicts = _rejudge(cases, a.repeats)
    stab = summarize_stability(verdicts)
    md = _render(cases, verdicts, stab, Path(a.baseline).name, a.repeats)
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")
    print(json.dumps({k: v for k, v in stab.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
