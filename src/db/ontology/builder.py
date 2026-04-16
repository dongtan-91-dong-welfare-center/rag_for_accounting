"""온톨로지 구축 파이프라인 + CLI

파이프라인 4단계:
  1. parse_markdown    → Standard/Section/Subsection 노드 + CONTAINS 엣지
  2. detect_candidates → 엣지가 있을 법한 후보 문장 (정규식 필터)
  3. extract_edges     → 후보 문장 → EdgeCandidate 목록 (LLM 판별)
  4. resolve_edges     → EdgeCandidate의 target_ref(원문) → 노드 ID 변환

CLI 사용법:
  uv run python -m src.db.ontology.builder \\
      --input data/회계_sample.md \\
      --output data/ontology/gaap-ch6.json \\
      --standard-id gaap-ch6 \\
      --standard-type GAAP
"""
import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from src.db.ontology.edge_detector import detect_candidates
from src.db.ontology.edge_extractor import extract_edges
from src.db.ontology.md_parser import parse_markdown
from src.db.ontology.models import OntologyEdge, OntologyGraph
from src.db.ontology.resolver import resolve_edges


def build_graph(
    md_path: str | Path,
    standard_id: str,    # 예: "gaap-ch6"
    standard_type: str,  # "GAAP" 또는 "KIFRS"
    effective_date: str = "",
) -> OntologyGraph:
    """마크다운 파일 하나를 받아 완성된 OntologyGraph를 반환한다.

    내부적으로 파이프라인 4단계를 순서대로 실행한다.
    LLM 호출(3단계)이 포함되므로 실행 시간이 길 수 있다.
    """
    text = Path(md_path).read_text(encoding="utf-8")

    # 1단계: 마크다운 파싱 → 노드·CONTAINS 엣지 생성
    graph = parse_markdown(text, standard_id, standard_type, effective_date)

    # 2·3단계: Subsection마다 후보 탐지 → LLM 엣지 추출
    for node in graph.nodes:
        if node.node_type != "Subsection" or not node.content:
            continue  # 내용이 없는 노드는 건너뜀

        candidates = detect_candidates(node.content)
        for ec in extract_edges(node.id, node.title, node.content, candidates):
            # LLM이 반환한 EdgeCandidate를 OntologyEdge로 변환.
            # to_id는 아직 모르므로 빈 문자열로 두고,
            # target_ref(원문)를 unresolved_target에 저장한다.
            graph.edges.append(OntologyEdge(
                from_id=node.id,
                to_id="",                        # 4단계에서 채워짐
                edge_type=ec.edge_type,
                paragraph=ec.paragraph,
                source_text=ec.source_text,
                include=ec.include,
                condition_text=ec.condition_text,
                unresolved_target=ec.target_ref, # 예: "제2절", "문단 6.4"
            ))

    # 4단계: unresolved_target → 노드 ID 변환
    return resolve_edges(graph)


def save_graph(graph: OntologyGraph, output_path: str | Path) -> None:
    """그래프를 JSON 파일로 저장한다."""
    Path(output_path).write_text(graph.model_dump_json(indent=2), encoding="utf-8")


def main() -> None:
    load_dotenv()  # .env 파일에서 OPENAI_API_KEY 로드
    parser = argparse.ArgumentParser(description="회계기준서 온톨로지 그래프 구축")
    parser.add_argument("--input", required=True, help="파싱된 마크다운 파일 경로")
    parser.add_argument("--output", required=True, help="출력 JSON 파일 경로")
    parser.add_argument("--standard-id", required=True, help="예: gaap-ch6")
    parser.add_argument("--standard-type", required=True, choices=["GAAP", "KIFRS"])
    parser.add_argument("--effective-date", default="")
    args = parser.parse_args()

    # args.output 예: "data/ontology/gaap-ch6.json"
    # .parent → "data/ontology" (파일이 들어갈 디렉토리)
    # mkdir(parents=True)  : 중간 경로(data/ 등)가 없어도 한 번에 생성
    # mkdir(exist_ok=True) : 이미 존재하면 에러 없이 넘어감
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    print(f"파싱 중: {args.input}")
    graph = build_graph(args.input, args.standard_id, args.standard_type,
                        args.effective_date)
    save_graph(graph, args.output)

    nodes = len(graph.nodes)
    edges = len(graph.edges)
    unresolved = sum(1 for e in graph.edges if not e.to_id)
    print(f"완료: 노드 {nodes}개, 엣지 {edges}개 (미해소 참조: {unresolved}개)")
    print(f"저장: {args.output}")


if __name__ == "__main__":
    main()
