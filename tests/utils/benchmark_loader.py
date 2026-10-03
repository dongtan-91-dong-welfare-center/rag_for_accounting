"""
Benchmark 데이터 로더 유틸리티

Benchmark JSONL 파일을 파싱하여 pytest.mark.parametrize에 투입 가능한 형태로 변환합니다.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

# Benchmark 데이터 파일 경로 — 이 파일 기준 세 단계 위인 프로젝트 루트를 기준으로 data/test_data/benchmark.jsonl을 가리킨다.
BENCHMARK_PATH = Path(__file__).parent.parent.parent / "data" / "test_data" / "benchmark.jsonl"
BENCHMARK_SAMPLE_PATH = Path(__file__).parent.parent.parent / "data" / "test_data" / "benchmark_sample.jsonl"


@dataclass
class BenchmarkCase:
    """단일 Benchmark 테스트 케이스"""
    id: str
    category: str
    standard: str               # "GAAP" | "KIFRS"
    query: str                  # 사용자 질의
    expected_answer: str        # 기대 정답 요약
    references: list[str] = field(default_factory=list)  # 근거 문헌 목록
    # 핵심(core) 조항 문단번호. 비어 있으면 references 전체를 핵심으로 간주한다.
    # 멀티조항 gold에서 '핵심⊊전체'인 경우에만 명시하여 검색 적합도 판정에 사용한다.
    core_paras: list[str] = field(default_factory=list)


def load_benchmark(path: Path | None = None) -> list[BenchmarkCase]:
    """JSONL 파일을 읽어 BenchmarkCase 리스트로 반환한다.
    
    경로가 주어지지 않으면 BENCHMARK_PATH를 우선 확인하고, 부재 시 BENCHMARK_SAMPLE_PATH로 대체합니다.
    둘 다 존재하지 않는 경우 빈 리스트를 반환합니다.
    """
    if path is None:
        if BENCHMARK_PATH.exists():
            target_path = BENCHMARK_PATH
        elif BENCHMARK_SAMPLE_PATH.exists():
            target_path = BENCHMARK_SAMPLE_PATH
        else:
            return []
    else:
        target_path = path

    if not target_path.exists():
        return []

    cases: list[BenchmarkCase] = []
    with open(target_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            cases.append(BenchmarkCase(**data))
    return cases
