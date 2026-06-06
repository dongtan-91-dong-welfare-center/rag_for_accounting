"""
회계 RAG 시스템 - 통합 테스트 마스터 스크립트

이 스크립트는 `ingestion/` (데이터 축적) 과 `inference/` (질의 응답) 하위의
모든 통합 테스트 시나리오를 순차적으로 실행하여 시스템의 전체 데이터 흐름과 예외 상황 대처를 검증합니다.

실행:
    uv run python tests/integration/run_integration_tests.py
"""
import subprocess
import sys
import time
from pathlib import Path

def run_test_suite(suite_name: str, path: str) -> bool:
    """지정된 경로의 테스트 스위트를 실행하고 성공 여부를 반환합니다."""
    args = [
        sys.executable, "-m", "pytest",
        path,
        "-v",
        "--tb=short"
    ]
    
    print(f"\n{'='*60}")
    print(f"  실행 중: {suite_name}")
    print(f"  경로: {path}")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    result = subprocess.run(args)
    elapsed = time.time() - start_time
    
    status = "성공 ✅" if result.returncode == 0 else "실패 ❌"
    print(f"\n  [결과] {suite_name}: {status} ({elapsed:.2f}초)")
    
    return result.returncode == 0

def main():
    print("\n" + "=" * 60)
    print("  RAG 시스템 통합 테스트")
    print("=" * 60)
    
    base_dir = Path(__file__).parent
    
    suites = [
        ("데이터 수집 및 축적 파이프라인 (Ingestion)", str(base_dir / "ingestion")),
        ("질의 응답 및 라우팅 시나리오 (Inference)", str(base_dir / "inference")),
    ]
    
    all_passed = True
    
    for name, path in suites:
        if not Path(path).exists():
            print(f"\n⚠️  경고: {path} 경로를 찾을 수 없습니다.")
            continue
            
        success = run_test_suite(name, path)
        if not success:
            all_passed = False
            print(f"\n⛔ {name} 테스트 스위트에서 실패가 발생했습니다.")
            # Fail-fast 옵션: 하나의 스위트가 실패하면 전체 중단
            # break 
            
    print("\n" + "=" * 60)
    if all_passed:
        print("  🎉 모든 통합 테스트 시나리오를 성공적으로 통과했습니다!")
        sys.exit(0)
    else:
        print("  ⚠️ 통합 테스트 중 일부 시나리오가 실패했습니다.")
        sys.exit(1)

if __name__ == "__main__":
    main()
