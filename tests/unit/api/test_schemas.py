"""src/api/schemas.py — 워크플로 결과 → API 유니언 스키마 변환 단위테스트 (순수 — DB·FastAPI 불필요).

#195 계약: status(done|interrupted) 유니언 · GraphState 통째 직렬화 금지 ·
error_code("TIMEOUT"|null)는 error_logs에서 서버가 파생 · interrupt 노출 필드는 4종.
"""
from langgraph.types import Interrupt

from src.api.schemas import (
    QueryDoneResponse,
    QueryInterruptedResponse,
    to_api_response,
)
from src.models.schemas import (
    ChunkMetadata,
    Citation,
    FinalResponse,
    RerankingResult,
    RetrievedChunk,
)


def _rr(chunk_id, score, chapter="6", node_id="gaap-ch6-s1", content="조항 본문"):
    """reranked chunk 생성 헬퍼 함수"""
    return RerankingResult(
        chunk=RetrievedChunk(
            chunk_id=chunk_id,
            document_id="doc",
            content=content,
            score=score,
            metadata=ChunkMetadata(chapter=chapter, ontology_node_id=node_id),
        ),
        rerank_score=1.0,
    )


def _done_result(**overrides) -> dict:
    """run_workflow 완료 반환 dict의 최소 형태 (GraphState 필드 + thread_id)."""
    result = {
        "thread_id": "t1",
        "final_response": FinalResponse(
            answer="재고자산은 취득원가로 측정한다.",
            citations=[
                Citation(
                    document_id="gaap-ch7",
                    chunk_id="c1",
                    content="제7장 재고자산 …",
                    relevance_score=0.83,
                )
            ],
            is_answerable=True,
            confidence_score=0.91,
        ),
        "reranked_chunks": [_rr("a", 0.9), _rr("b", 0.8)],
        "retrieved_chunks": [],
        "error_logs": [],
    }
    result.update(overrides)
    return result


TIMEOUT_LOG = {
    "timestamp": "2026-07-04T21:00:00+09:00",
    "node": "workflow",
    "error_type": "TIMEOUT",
    "message": "노드 실행이 step_timeout을 초과했습니다.",
}


class TestDoneResponse:
    def test_maps_final_response_to_contract_fields(self):
        """FinalResponse → answer·is_answerable·confidence(=confidence_score) 매핑"""
        res = to_api_response(_done_result())
        assert isinstance(res, QueryDoneResponse)
        assert res.status == "done"
        assert res.thread_id == "t1"
        assert res.answer == "재고자산은 취득원가로 측정한다."
        assert res.is_answerable is True
        assert res.confidence == 0.91
        assert res.error_code is None

    def test_clauses_follow_build_clause_rows_contract(self):
        """clauses[]는 build_clause_rows 재사용 — 1-based rank·chunk.score 노출"""
        res = to_api_response(_done_result())
        assert [c.rank for c in res.clauses] == [1, 2]
        assert res.clauses[0].score == 0.9
        assert res.clauses[0].chapter == "6"
        assert res.clauses[0].node_id == "gaap-ch6-s1"
        assert res.clauses[0].content == "조항 본문"

    def test_citations_are_mapped(self):
        res = to_api_response(_done_result())
        assert len(res.citations) == 1
        c = res.citations[0]
        assert (c.document_id, c.chunk_id, c.relevance_score) == ("gaap-ch7", "c1", 0.83)

    def test_empty_reranked_chunks_yield_empty_clauses(self):
        """폴백·조기종료 결과처럼 reranked_chunks가 비어도 안전하게 빈 리스트"""
        res = to_api_response(_done_result(reranked_chunks=[]))
        assert res.clauses == []

    def test_internal_state_is_not_exposed(self):
        """GraphState 통째 직렬화 금지 — retrieved_chunks·error_logs 등 내부 키 부재"""
        dumped = to_api_response(_done_result()).model_dump()
        assert set(dumped) == {
            "status",
            "thread_id",
            "answer",
            "is_answerable",
            "confidence",
            "error_code",
            "clauses",
            "citations",
        }


class TestErrorCode:
    def test_timeout_fallback_sets_error_code(self):
        """#131 타임아웃 폴백(error_logs의 TIMEOUT) → error_code="TIMEOUT" 파생"""
        fallback = _done_result(
            final_response=FinalResponse(
                answer="처리 시간이 초과되어 답변을 생성하지 못했습니다. 잠시 후 다시 시도해주세요.",
                citations=[],
                is_answerable=False,
                confidence_score=0.0,
            ),
            reranked_chunks=[],
            error_logs=[TIMEOUT_LOG],
        )
        res = to_api_response(fallback)
        assert res.error_code == "TIMEOUT"
        assert res.is_answerable is False

    def test_node_level_errors_do_not_set_error_code(self):
        """노드 레벨 에러(CM-002 등)는 폴백 구분자가 아니다 — TIMEOUT만 매핑"""
        node_error = {**TIMEOUT_LOG, "node": "search", "error_type": "CM-002"}
        res = to_api_response(_done_result(error_logs=[node_error]))
        assert res.error_code is None


class TestInterruptedResponse:
    PAYLOAD = {
        "type": "human_review",
        "strategy": "decompose",
        "original_query": "리스 회계처리",
        "search_queries": ["리스 인식", "리스 측정"],
        "hil_count": 0,
        "max_hil_count": 5,
        "options": [
            {"action": "approve", "label": "이대로 검색을 진행합니다"},
            {"action": "rewrite", "label": "재작성을 요청합니다 (피드백 입력)"},
        ],
    }

    def _interrupted_result(self) -> dict:
        return {"thread_id": "t9", "__interrupt__": [Interrupt(value=self.PAYLOAD)]}

    def test_maps_interrupt_payload(self):
        res = to_api_response(self._interrupted_result())
        assert isinstance(res, QueryInterruptedResponse)
        assert res.status == "interrupted"
        assert res.thread_id == "t9"
        assert res.interrupt.strategy == "decompose"
        assert res.interrupt.original_query == "리스 회계처리"
        assert res.interrupt.search_queries == ["리스 인식", "리스 측정"]
        assert [o.action for o in res.interrupt.options] == ["approve", "rewrite"]

    def test_exposes_only_contract_fields(self):
        """계약 4종(strategy·original_query·search_queries·options)만 노출 — hil_count 등 비노출(7/4 결정)"""
        dumped = to_api_response(self._interrupted_result()).interrupt.model_dump()
        assert set(dumped) == {"strategy", "original_query", "search_queries", "options"}
