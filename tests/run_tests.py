"""
회계 RAG 시스템

단위 테스트부터 비즈니스 품질 검증까지 3단계 순차 실행을 통해 비용 효율적이면서도 완전한 품질 검증을 수행합니다.

실행 방법:
    uv run python tests/run_tests.py [옵션]

옵션:
    --phase0-only     Phase 0(Unit)만 실행
    --phase1-only     Phase 1(System)만 실행
    --phase2-only     Phase 2(Benchmark)만 실행
    --skip-unit       Phase 0를 건너뛰고 Phase 1부터 시작
    --durations=N     느린 테스트 N개 출력

판정 읽는 법:
    Phase마다 PASSED / NOT VERIFIED / FAILED 중 하나로 판정한다.
    NOT VERIFIED는 "실패는 없었지만 한 건도 실행되지 않았다"는 뜻이다.
    예를 들어 API 키나 DB가 없으면 Phase 2의 벤치마크가 전부 건너뛰어지는데,
    이때 실패가 0건이라고 품질이 검증된 것은 아니다. 두 상태를 구분해 표시한다.

Phase 구조:
    Phase 0 (Unit Test)
        개별 함수 논리를 모킹 기반으로 검증합니다. 외부 의존성 없이
        메모리 내에서만 동작하므로 가장 빠르고 비용이 0입니다.

    Phase 1 (System Integration — Fast Fail)
        가짜 데이터를 이용해 노드 간 데이터 규격·예외 경로·라우팅 로직을
        검증합니다. 기본 실행에는 Phase 0 통과 후에만 실행되며, --phase1-only 옵션을 쓰면 Phase 0 없이 단독으로 실행할 수 있습니다.

    Phase 2 (Benchmark — Business Quality)
        Benchmark 정답셋(K-GAAP 14개)을 투입하여 답변 품질·근거 인용·
        기준서 필터 정합성을 검증합니다. 기본 실행에는 Phase 1 통과 후에만 실행되며, --phase2-only 옵션을 쓰면 이전 단계 없이 단독으로 실행할 수 있습니다.

설계 원칙:
    "통합 테스트는 벤치마크 데이터를 활용한 전체 파이프라인 검증을 원칙으로 하되,
     벤치마크 데이터가 커버하지 못하는 시스템 예외 케이스(네트워크 오류 등)는
     별도의 시나리오 기반 테스트로 보완하여 무결성을 증명한다."
"""
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# ── Phase 판정 세 가지 ──
#
# 왜 "통과/실패" 두 가지로는 부족한가:
#     pytest는 "수집은 했지만 전부 건너뛴" 경우에도 종료 코드 0을 준다.
#     실패가 없으니 형식상 맞는 값이다.
#     그래서 종료 코드만 보면, API 키나 DB가 없어 벤치마크 114건이 통째로 건너뛴 실행도
#     "통과"로 보고된다. 정확도 게이트가 조용히 꺼진 채 초록불이 켜지는 것이다.
#     실제로 그런 실행이 `✅ 전체 테스트 통과`를 출력한 사례가 있었다.
#     그래서 "실패는 없었다"와 "검증했다"를 구분한다.
PASSED = "passed"              # 실패 0건이고, 실제로 1건 이상 실행됐다 — 검증된 상태
NOT_VERIFIED = "not_verified"  # 실패 0건이지만 실행 0건 — 아무것도 검증하지 못했다
FAILED = "failed"              # 실패나 오류가 있었다

_VERDICT_LABEL = {
    PASSED: "PASSED ✅",
    NOT_VERIFIED: "NOT VERIFIED ⚠️  (전부 건너뜀 — 검증되지 않았습니다)",
    FAILED: "FAILED ❌",
}


@dataclass
class PhaseResult:
    """한 Phase의 판정과 실행 건수.

    executed는 실제로 몸통이 돌아간 건수(건너뛴 것 제외)다.
    이 값이 0이면 초록불이어도 검증된 것이 없다.
    """
    verdict: str
    executed: int
    skipped: int

    @property
    def blocking(self) -> bool:
        """후속 Phase를 중단시켜야 하는 상태인가.

        검증 안 됨(NOT_VERIFIED)은 중단시키지 않는다.
        라이브 인프라가 없는 개발 환경에서는 정상적으로 일어나는 일이고,
        여기서 멈추면 API 과금과 Docker 상시 기동을 사실상 강제하게 된다.
        지금 필요한 것은 검증을 강제하는 게 아니라, 검증되지 않았음을 숨기지 않는 것이다.
        """
        return self.verdict == FAILED


def _read_counts(report_path: Path) -> tuple[int, int] | None:
    """pytest가 남긴 JUnit XML 리포트에서 (실행 건수, 건너뜀 건수)를 읽는다.

    JUnit XML의 tests 속성은 건너뛴 것까지 포함한 총 건수라서,
    실제로 돌아간 건수는 tests에서 skipped를 뺀 값이다.
    예: tests=121, skipped=121 → 실행 0건, 즉 아무것도 검증하지 못한 실행이다.

    화면 출력을 긁는 대신 이 파일을 읽는 이유는, 출력 문구가 pytest 버전에 따라 바뀌어도
    이 XML의 속성 이름은 그대로이기 때문이다. 표준 라이브러리만 쓰므로 의존성도 늘지 않는다.
    리포트를 못 읽으면 판단을 꾸며내지 않고 None을 반환한다.
    """
    try:
        root = ET.parse(report_path).getroot()
    except (OSError, ET.ParseError):
        return None

    # pytest는 <testsuites> 안에 <testsuite>를 하나 넣는다. 두 형태 모두 받아들인다.
    suites = root.findall("testsuite") or ([root] if root.tag == "testsuite" else [])
    if not suites:
        return None

    total = sum(int(s.get("tests", 0)) for s in suites)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    return total - skipped, skipped


def run_phase(
    phase_name: str,
    marker: str,
    test_path: str,
    extra_args: list[str] = None,
) -> PhaseResult:
    """단일 Phase를 실행하고 판정과 실행 건수를 반환한다."""
    print(f"\n{'='*70}")
    print(f"  {phase_name}")
    print(f"  대상: {test_path}  |  marker: -m {marker}")
    print(f"{'='*70}\n")

    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "report.xml"
        args = [
            sys.executable, "-m", "pytest",
            test_path,
            "-m", marker,
            "-v",
            "--tb=short",
            f"--junitxml={report_path}",
        ]
        if extra_args:
            args.extend(extra_args)

        start = time.time()
        completed = subprocess.run(args)
        elapsed = time.time() - start

        counts = _read_counts(report_path)

    executed, skipped = counts if counts else (0, 0)
    if completed.returncode != 0:
        verdict = FAILED
    elif counts is None:
        # 실패는 없었지만 건수를 확인할 수 없다. 검증했다고 단정하지 않는다.
        verdict = NOT_VERIFIED
    else:
        verdict = PASSED if executed > 0 else NOT_VERIFIED

    print(f"\n  {phase_name}: {_VERDICT_LABEL[verdict]} ({elapsed:.2f}s)")
    print(f"  실행 {executed}건 · 건너뜀 {skipped}건")

    return PhaseResult(verdict=verdict, executed=executed, skipped=skipped)


def main():
    args_set = set(sys.argv[1:])
    extra_args = [a for a in sys.argv[1:] if a.startswith("--durations")]

    phase0_only = "--phase0-only" in args_set
    phase1_only = "--phase1-only" in args_set
    phase2_only = "--phase2-only" in args_set
    skip_unit = "--skip-unit" in args_set

    print("\n" + "=" * 70)
    print("  회계 RAG 시스템 — 통합 테스트")
    print("=" * 70)

    # 실행한 Phase의 판정을 순서대로 모아, 마지막에 어디까지 실제로 검증됐는지 요약한다.
    results: list[tuple[str, PhaseResult]] = []

    # ── Phase 0: Unit Test ──
    if not phase1_only and not phase2_only and not skip_unit:
        phase0 = run_phase(
            "Phase 0: Unit Test (함수 논리 검증)",
            "unit",
            "tests/unit/",
            extra_args,
        )
        results.append(("Phase 0", phase0))

        if phase0.blocking:
            print("\n⛔ Phase 0 실패 — 단위 테스트를 먼저 해결하십시오.")
            print("   후속 Phase는 실행하지 않습니다.")
            sys.exit(1)

        if phase0_only:
            print_summary(results)
            sys.exit(0)

    # ── Phase 1: System Integration ──
    if not phase2_only:
        phase1 = run_phase(
            "Phase 1: System Integration (구조·예외 검증)",
            "system",
            "tests/integration/",
            extra_args,
        )
        results.append(("Phase 1", phase1))

        if phase1.blocking:
            print("\n⛔ Phase 1 실패 — 시스템 워크플로우 결함이 발견되었습니다.")
            print("   Phase 2(Benchmark)는 실행하지 않습니다.")
            sys.exit(1)

        if phase1_only:
            print_summary(results)
            sys.exit(0)

    # ── Phase 2: Benchmark Quality ──
    phase2 = run_phase(
        "Phase 2: Benchmark Quality (비즈니스 품질 검증)",
        "benchmark",
        "tests/integration/",
        extra_args,
    )
    results.append(("Phase 2", phase2))

    if phase2.blocking:
        print("\n⚠️  Phase 2 실패 — Benchmark 품질 기준을 충족하지 못합니다.")
        sys.exit(1)

    print_summary(results)


def print_summary(results: list[tuple[str, "PhaseResult"]]) -> None:
    """Phase별 판정을 한자리에 모아 출력한다.

    실행한 Phase가 하나라도 검증되지 않았다면 "전체 통과"라고 쓰지 않는다.
    두 상태를 같은 문장으로 뭉개면, 읽는 사람이 검증되지 않은 것을 검증됐다고 믿는다.
    """
    print("\n" + "=" * 70)

    not_verified = [name for name, r in results if r.verdict == NOT_VERIFIED]
    if not_verified:
        print("  ⚠️  일부 Phase가 검증되지 않았습니다 — 실패는 없었지만 실행 건수가 0입니다.")
    else:
        print("  ✅ 실행한 Phase 전부 통과")

    for name, r in results:
        print(f"     {name}: {_VERDICT_LABEL[r.verdict]}  (실행 {r.executed}건 · 건너뜀 {r.skipped}건)")

    if not_verified:
        print(f"\n  {', '.join(not_verified)}는 품질을 보증하지 않습니다.")
        print("  라이브 인프라(DB·API 키)를 갖추고 다시 실행하면 실제로 검증됩니다.")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
