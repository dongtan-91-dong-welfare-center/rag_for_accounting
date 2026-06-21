"""회계 기준서 RAG 시스템 실행 진입점

두 가지 실행 경로를 단일 CLI로 제공한다.

  1. ingest — 적재 경로
     온톨로지 그래프 → 청킹(FUNC-002/003) → pgvector 적재(FUNC-003)
     · 기본 소스: 미리 빌드된 온톨로지 JSON(data/ontology/*.json)
     · --pdf/--md 지정 시: 파싱(FUNC-001) → 온톨로지 빌드(FUNC-002) → 청킹 → 적재까지 전체 경로
     · 적재 대상 테이블은 검색기(searcher.py)가 조회하는 CHUNKS_TABLE("chunks")로 고정해
       적재와 검색이 동일 테이블을 공유하도록 한다.

  2. query — 질의 경로
     질의 → LangGraph 워크플로(rewrite→search→rerank→evaluate→generate, FUNC-004~009)
          → 답변/인용 출력
     · HIL(human_review) interrupt 발생 시 대화형으로 승인/재작성을 받아 재개한다.

사용 예:
  uv run python -m src.main ingest                       # data/ontology 전 장 적재
  uv run python -m src.main ingest --ontology-dir data/ontology --reset
  uv run python -m src.main ingest --pdf data/raw/제6장.pdf --standard-id gaap-ch6 --standard-type GAAP
  uv run python -m src.main query "금융자산의 최초 인식 시점은?"
  uv run python -m src.main query "리스 회계처리" --standard GAAP
"""
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.db.connection import close_pool, init_pool
from src.utils.config import CHUNKS_TABLE, EMBEDDING_MAX_TOKENS
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ───────────────────────────── ingest 경로 ─────────────────────────────


def _load_graph_from_json(path: Path):
    """저장된 온톨로지 그래프 JSON을 OntologyGraph로 역직렬화한다."""
    from src.db.ontology.models import OntologyGraph

    return OntologyGraph.model_validate_json(path.read_text(encoding="utf-8"))


def _build_graph_from_source(args):
    """--pdf/--md 입력으로부터 온톨로지 그래프를 새로 빌드한다(FUNC-001→002).

    PDF는 DoclingParser로 마크다운을 추출한 뒤 build_graph에 넘긴다.
    LLM 엣지 추출이 포함되므로 OPENAI_API_KEY와 실행 시간이 필요하다.
    """
    from src.db.ontology.builder import build_graph

    if args.md:
        md_path = Path(args.md)
    else:
        # PDF → 마크다운(FUNC-001). build_graph는 마크다운 파일 경로를 입력으로 받으므로
        # 파싱 결과 텍스트를 임시 .md로 저장해 전달한다.
        from src.parse.parser import DoclingParser

        pdf_path = Path(args.pdf)
        logger.info(f"PDF 파싱 시작: {pdf_path}")
        parsed = DoclingParser().parse(pdf_path)
        md_path = pdf_path.with_suffix(".md")
        md_path.write_text(parsed.text, encoding="utf-8")
        logger.info(f"파싱 결과 마크다운 저장: {md_path}")

    logger.info(f"온톨로지 빌드 시작(FUNC-002): {md_path}")
    graph = build_graph(md_path, args.standard_id, args.standard_type)
    return graph, str(md_path)


def _index_graph(
    graph, source_path: str | None, collection: str, *, clause_level: bool, max_tokens: int
) -> dict:
    """온톨로지 그래프 한 개를 청킹 후 적재하고 IndexingResult를 dict로 반환한다."""
    from src.db.ontology.chunker import chunk_graph
    from src.db.vector_store import index_documents

    chunks = chunk_graph(
        graph, source_path=source_path, clause_level=clause_level, max_tokens=max_tokens
    )
    if not chunks:
        logger.warning(f"청크가 비어 있어 적재를 건너뜁니다: source={source_path}")
        return {"document_id": "", "chunk_count": 0, "status": "failed"}

    result = index_documents(chunks, collection=collection)
    return result.model_dump()


def run_ingest(args) -> int:
    """적재 경로 실행. 성공 시 0, 적재된 청크가 하나도 없으면 1을 반환한다."""
    collection = args.collection
    init_pool()
    try:
        if args.reset:
            # 재적재 멱등성은 chunk_id 기반 upsert로도 보장되지만,
            # --reset은 컬렉션을 비워 삭제된 노드의 잔여 청크까지 정리한다.
            from src.db.vector_store import delete_collection

            logger.info(f"컬렉션 초기화: {collection}")
            delete_collection(collection)

        # 적재 대상 그래프 목록을 (graph, source_path) 형태로 모은다.
        targets: list[tuple[object, str | None]] = []
        if args.pdf or args.md:
            graph, source_path = _build_graph_from_source(args)
            targets.append((graph, source_path))
        else:
            ontology_dir = Path(args.ontology_dir)
            json_files = sorted(ontology_dir.glob("*.json"))
            if not json_files:
                logger.error(f"온톨로지 JSON을 찾지 못했습니다: {ontology_dir}")
                return 1
            logger.info(f"온톨로지 JSON {len(json_files)}개 적재 시작: {ontology_dir}")
            for jf in json_files:
                targets.append((_load_graph_from_json(jf), str(jf)))

        total_chunks = 0
        summaries: list[dict] = []
        for graph, source_path in targets:
            result = _index_graph(
                graph,
                source_path,
                collection,
                clause_level=args.clause_level,
                max_tokens=args.max_tokens,
            )
            total_chunks += result["chunk_count"]
            summaries.append(result)
            print(
                f"  - {result['document_id'] or source_path}: "
                f"{result['chunk_count']}청크 ({result['status']})"
            )

        print(
            f"\n적재 완료: 문서 {len(summaries)}건, 총 {total_chunks}청크 → 테이블 '{collection}'"
        )
        return 0 if total_chunks > 0 else 1
    finally:
        close_pool()


# ───────────────────────────── query 경로 ─────────────────────────────


def _prompt_human_decision(payload: dict) -> dict:
    """human_review interrupt 페이로드를 보여주고 사용자 결정을 받는다.

    비대화형(파이프 입력 등) 환경에서는 자동 승인하여 워크플로가 멈추지 않게 한다.
    """
    strategy = payload.get("strategy", "?")
    queries = payload.get("search_queries", [])
    print("\n[확인 요청] 재작성 전략이 사용자 확인을 요구합니다.")
    print(f"  전략: {strategy}")
    print(f"  원질의: {payload.get('original_query', '')}")
    for i, q in enumerate(queries, 1):
        print(f"  검색쿼리 {i}: {q}")

    if not sys.stdin.isatty():
        print("  (비대화형 환경 → 자동 승인)")
        return {"action": "approve"}

    choice = input("  진행할까요? [Enter=승인 / r=재작성 요청]: ").strip().lower()
    if choice == "r":
        feedback = input("  재작성 피드백을 입력하세요: ").strip()
        return {"action": "rewrite", "feedback": feedback}
    return {"action": "approve"}


def _extract_interrupt_payload(result: dict) -> dict:
    """invoke 결과의 __interrupt__ 값을 dict 페이로드로 정규화한다."""
    intr = result["__interrupt__"]
    item = intr[0] if isinstance(intr, (list, tuple)) and intr else intr
    payload = getattr(item, "value", item)
    return payload if isinstance(payload, dict) else {}


def _print_response(result: dict) -> None:
    """워크플로 결과의 FinalResponse를 사람이 읽기 좋게 출력한다."""
    response = result.get("final_response")
    print("\n" + "=" * 60)
    if response is None:
        print("답변을 생성하지 못했습니다.")
        return

    print(f"답변:\n{response.answer}\n")
    print(f"답변 가능 여부: {response.is_answerable}")
    print(f"신뢰도: {response.confidence_score:.2%}")

    if response.citations:
        print(f"\n인용 ({len(response.citations)}건):")
        for c in response.citations:
            snippet = c.content.replace("\n", " ")[:80]
            print(f"  - [{c.document_id} / {c.chunk_id}] (rel={c.relevance_score:.2f}) {snippet}...")
    else:
        print("\n인용: 없음")
    print("=" * 60)


def run_query(args) -> int:
    """질의 경로 실행. HIL interrupt가 발생하면 결정을 받아 재개한다."""
    from src.agent.workflow import resume_workflow, run_workflow

    init_pool()
    try:
        logger.info(f"질의 실행: '{args.query}' (standard={args.standard})")
        result = run_workflow(args.query, standard_filter=args.standard)

        # human_review interrupt 루프: __interrupt__가 사라질 때까지 결정을 주입해 재개
        while "__interrupt__" in result:
            decision = _prompt_human_decision(_extract_interrupt_payload(result))
            result = resume_workflow(result["thread_id"], decision)

        _print_response(result)
        return 0
    finally:
        close_pool()


# ───────────────────────────── CLI 구성 ─────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rag-for-accounting",
        description="회계 기준서 RAG — 적재(ingest)/질의(query) 진입점",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = sub.add_parser("ingest", help="문서를 청킹·임베딩하여 pgvector에 적재")
    p_ingest.add_argument(
        "--ontology-dir",
        default="data/ontology",
        help="적재할 온톨로지 JSON 디렉토리 (기본: data/ontology). --pdf/--md 미지정 시 사용",
    )
    p_ingest.add_argument("--pdf", help="단일 PDF에서 파싱→온톨로지→적재까지 전체 경로 실행")
    p_ingest.add_argument("--md", help="단일 마크다운에서 온톨로지→적재 실행")
    p_ingest.add_argument("--standard-id", help="--pdf/--md 사용 시 기준서 ID (예: gaap-ch6)")
    p_ingest.add_argument(
        "--standard-type",
        choices=["GAAP", "KIFRS"],
        help="--pdf/--md 사용 시 기준 유형",
    )
    p_ingest.add_argument(
        "--collection",
        default=CHUNKS_TABLE,
        help=f"적재 대상 테이블 (기본: {CHUNKS_TABLE} — 검색기와 동일 테이블)",
    )
    p_ingest.add_argument("--reset", action="store_true", help="적재 전 컬렉션을 비운다")
    p_ingest.add_argument(
        "--clause-level",
        action="store_true",
        help="조항 헤더(#### N.N) 경계로 분할하여 적재. 기본: 온톨로지 노드 단위",
    )
    p_ingest.add_argument(
        "--max-tokens",
        type=int,
        default=EMBEDDING_MAX_TOKENS,
        help=f"청크 1개의 토큰 상한 (기본: {EMBEDDING_MAX_TOKENS})",
    )
    p_ingest.set_defaults(func=run_ingest)

    # query
    p_query = sub.add_parser("query", help="질의에 대해 워크플로를 실행하고 답변을 출력")
    p_query.add_argument("query", help="질의 문장")
    p_query.add_argument(
        "--standard",
        choices=["GAAP", "KIFRS", "ALL"],
        default="ALL",
        help="검색 대상 기준 필터 (기본: ALL)",
    )
    p_query.set_defaults(func=run_query)

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    # --pdf/--md 사용 시 standard-id/type은 필수
    if args.command == "ingest" and (args.pdf or args.md):
        if not args.standard_id or not args.standard_type:
            parser.error("--pdf/--md 사용 시 --standard-id 와 --standard-type 이 필요합니다.")

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
