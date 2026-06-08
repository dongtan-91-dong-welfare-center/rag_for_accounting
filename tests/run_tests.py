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

Phase 구조:
    Phase 0 (Unit Test)
        개별 함수 논리를 모킹 기반으로 검증합니다. 외부 의존성 없이
        메모리 내에서만 동작하므로 가장 빠르고 비용이 0입니다.

    Phase 1 (System Integration — Fast Fail)
        가짜 데이터를 이용해 노드 간 데이터 규격·예외 경로·라우팅 로직을
        검증합니다. Phase 0 통과 후에만 실행됩니다.

    Phase 2 (Benchmark — Business Quality)
        Benchmark 정답셋(K-GAAP 14개)을 투입하여 답변 품질·근거 인용·
        기준서 필터 정합성을 검증합니다. Phase 1 통과 후에만 실행됩니다.

설계 원칙:
    "통합 테스트는 벤치마크 데이터를 활용한 전체 파이프라인 검증을 원칙으로 하되,
     벤치마크 데이터가 커버하지 못하는 시스템 예외 케이스(네트워크 오류 등)는
     별도의 시나리오 기반 테스트로 보완하여 무결성을 증명한다."
"""
import subprocess
import sys
import time


def run_phase(
    phase_name: str,
    marker: str,
    test_path: str,
    extra_args: list[str] = None,
) -> bool:
    """단일 Phase를 실행하고 성공 여부를 반환한다."""
    args = [
        sys.executable, "-m", "pytest",
        test_path,
        "-m", marker,
        "-v",
        "--tb=short",
    ]
    if extra_args:
        args.extend(extra_args)

    print(f"\n{'='*70}")
    print(f"  {phase_name}")
    print(f"  대상: {test_path}  |  marker: -m {marker}")
    print(f"{'='*70}\n")

    start = time.time()
    result = subprocess.run(args)
    elapsed = time.time() - start

    status = "PASSED ✅" if result.returncode == 0 else "FAILED ❌"
    print(f"\n  {phase_name}: {status} ({elapsed:.2f}s)")

    return result.returncode == 0


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

    # ── Phase 0: Unit Test ──
    if not phase1_only and not phase2_only and not skip_unit:
        phase0_ok = run_phase(
            "Phase 0: Unit Test (함수 논리 검증)",
            "unit",
            "tests/unit/",
            extra_args,
        )

        if not phase0_ok:
            print("\n⛔ Phase 0 실패 — 단위 테스트를 먼저 해결하십시오.")
            print("   후속 Phase는 실행하지 않습니다.")
            sys.exit(1)

        if phase0_only:
            print("\n✅ Phase 0 단독 실행 완료.")
            sys.exit(0)

    # ── Phase 1: System Integration ──
    if not phase2_only:
        phase1_ok = run_phase(
            "Phase 1: System Integration (구조·예외 검증)",
            "system",
            "tests/integration/",
            extra_args,
        )

        if not phase1_ok:
            print("\n⛔ Phase 1 실패 — 시스템 워크플로우 결함이 발견되었습니다.")
            print("   Phase 2(Benchmark)는 실행하지 않습니다.")
            sys.exit(1)

        if phase1_only:
            print("\n✅ Phase 1 단독 실행 완료.")
            sys.exit(0)

    # ── Phase 2: Benchmark Quality ──
    phase2_ok = run_phase(
        "Phase 2: Benchmark Quality (비즈니스 품질 검증)",
        "benchmark",
        "tests/integration/",
        extra_args,
    )

    if not phase2_ok:
        print("\n⚠️  Phase 2 실패 — Benchmark 품질 기준을 충족하지 못합니다.")
        sys.exit(1)

    # ── 최종 결과 ──
    phases_run = []
    if not skip_unit and not phase1_only and not phase2_only:
        phases_run.append("Phase 0")
    if not phase2_only:
        phases_run.append("Phase 1")
    phases_run.append("Phase 2")

    print("\n" + "=" * 70)
    print(f"  ✅ 전체 테스트 통과 ({' + '.join(phases_run)})")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
