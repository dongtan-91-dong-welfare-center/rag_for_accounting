"""
Benchmark 데이터 로더 유틸리티

Benchmark JSONL 파일을 파싱하여 pytest.mark.parametrize에 투입 가능한 형태로 변환합니다.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

# Benchmark 데이터 파일 경로 (프로젝트 루트 기준)
BENCHMARK_PATH = Path(__file__).parent.parent / "fixtures" / "benchmark.jsonl"


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


def load_benchmark(path: Path = BENCHMARK_PATH) -> list[BenchmarkCase]:
    """JSONL 파일을 읽어 BenchmarkCase 리스트로 반환한다."""
    cases: list[BenchmarkCase] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            cases.append(BenchmarkCase(**data))
    return cases
