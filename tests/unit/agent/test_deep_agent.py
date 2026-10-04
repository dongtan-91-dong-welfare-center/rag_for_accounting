"""
src/agent/deep_agent.py 단위 테스트 (이슈 #402)

단일 검색 도구를 사용하는 자율 ReAct 딥에이전트의
도구 바인딩, 1턴/3턴/5턴 상한 제어, 인용구 파싱, max_turns 초과 폴백 동작을 검증합니다.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.models.test import TestModel

from src.agent.deep_agent import (
    DeepAgentDeps,
    create_deep_agent,
    extract_citations_from_collected_chunks,
    run_deep_agent,
)
from src.models.schemas import (
    ChunkMetadata,
    DeepAgentInternalResponse,
    FinalResponse,
    RetrievedChunk,
)

pytestmark = pytest.mark.unit


def _create_sample_chunk(chunk_id: str, content: str, score: float = 0.85, chapter: str = "10") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id="gaap-doc-1",
        content=content,
        score=score,
        metadata=ChunkMetadata(
            ontology_node_id=chunk_id,
            chapter=chapter,
            standard_type="GAAP",
        ),
    )


class TestExtractCitations:
    def test_extract_citations_valid(self):
        chunks = [
            _create_sample_chunk("gaap-ch10-1", "유형자산 감가상각 정의"),
            _create_sample_chunk("gaap-ch10-2", "내용연수 변경"),
        ]
        text = "유형자산 감가상각은 합리적으로 기간 배분합니다 [1]. 내용연수가 변동될 수 있습니다 [2]."
        citations = extract_citations_from_collected_chunks(text, chunks)

        assert len(citations) == 2
        assert citations[0].chunk_id == "gaap-ch10-1"
        assert citations[0].content == "유형자산 감가상각 정의"
        assert citations[1].chunk_id == "gaap-ch10-2"

    def test_extract_citations_out_of_bounds_and_duplicates(self):
        chunks = [
            _create_sample_chunk("gaap-ch10-1", "유형자산 감가상각 정의"),
        ]
        # [1] 중복 및 범위를 벗어난 [99] 인용
        text = "감가상각 정의 [1]. 추가 서술 [1]. 없는 인용 [99]."
        citations = extract_citations_from_collected_chunks(text, chunks)

        assert len(citations) == 1
        assert citations[0].chunk_id == "gaap-ch10-1"

    def test_extract_citations_multi_comma_and_range(self):
        chunks = [
            _create_sample_chunk("gaap-ch10-1", "청크 1"),
            _create_sample_chunk("gaap-ch10-2", "청크 2"),
            _create_sample_chunk("gaap-ch10-3", "청크 3"),
        ]
        text = "쉼표 인용 [1, 2] 및 범위 인용 [2-3]."
        citations = extract_citations_from_collected_chunks(text, chunks)

        assert len(citations) == 3
        assert [c.chunk_id for c in citations] == ["gaap-ch10-1", "gaap-ch10-2", "gaap-ch10-3"]


class TestDeepAgentExecution:
    @patch("src.agent.deep_agent.search_chunks")
    def test_deep_agent_single_turn_successful_tool_call(self, mock_search_chunks):
        mock_search_chunks.return_value = [
            _create_sample_chunk("gaap-ch10-10", "감가상각방법 변경 회계처리", score=0.92),
        ]

        # TestModel 설정: search_accounting_standards 도구를 1회 호출하고 구조화된 결과 생성
        model = TestModel(
            call_tools=["search_accounting_standards"],
            custom_output_args={
                "answer": "감가상각방법의 변경은 회계추정의 변경으로 처리합니다 [1].",
                "is_answerable": True,
                "llm_self_score": 0.95,
            },
        )
        agent = create_deep_agent()
        agent.model = model

        final_resp, chunks, meta = run_deep_agent(
            query="감가상각방법 변경 시 회계처리는?",
            standard_filter="GAAP",
            max_turns=3,
            top_k=5,
            agent=agent,
        )

        assert final_resp.is_answerable is True
        assert "회계추정의 변경" in final_resp.answer
        assert len(final_resp.citations) == 1
        assert final_resp.citations[0].chunk_id == "gaap-ch10-10"
        assert len(chunks) == 1
        assert meta["search_calls"] == 1
        assert meta["fallback_triggered"] is False
        mock_search_chunks.assert_called_once()
        call_kwargs = mock_search_chunks.call_args.kwargs
        assert call_kwargs["top_k"] == 5
        assert call_kwargs["metadata_filter"] == {"standard_type": "GAAP"}
        assert call_kwargs["include_sparse"] is True

    @patch("src.agent.deep_agent.search_chunks")
    def test_deep_agent_max_turns_exceeded_fallback(self, mock_search_chunks):
        mock_search_chunks.return_value = [
            _create_sample_chunk("gaap-ch10-10", "감가상각방법 내용", score=0.88),
        ]

        # request_limit=1인데 모델이 계속 도구만 호출하여 한도를 초과하도록 유도
        model = TestModel(
            call_tools=["search_accounting_standards"],
        )
        agent = create_deep_agent()
        agent.model = model

        final_resp, chunks, meta = run_deep_agent(
            query="무한 루프 유발 질의",
            standard_filter="GAAP",
            max_turns=1,
            top_k=5,
            agent=agent,
        )

        assert meta["fallback_triggered"] is True
        assert meta["fallback_reason"] == "MAX_TURNS_EXCEEDED"
        assert final_resp.is_answerable is False
        assert "최대 탐색 턴 수(1턴)를 초과" in final_resp.answer
        # 폴백 시 수집된 청크가 있으면 상위 청크를 보존
        assert len(final_resp.citations) == 1
        assert final_resp.citations[0].chunk_id == "gaap-ch10-10"

    def test_deep_agent_general_exception_handling(self):
        mock_agent = MagicMock()
        mock_agent.run_sync.side_effect = RuntimeError("예기치 않은 시스템 에러")

        final_resp, chunks, meta = run_deep_agent(
            query="에러 발생 질의",
            agent=mock_agent,
        )

        assert meta["fallback_triggered"] is True
        assert "RuntimeError" in meta["fallback_reason"]
        assert final_resp.is_answerable is False
        assert final_resp.confidence_score == 0.0

    @patch("src.agent.deep_agent.search_chunks")
    def test_deep_agent_ensemble_tool_call(self, mock_search_chunks):
        mock_search_chunks.return_value = [
            _create_sample_chunk("gaap-ch10-10.38", "감가상각 회계처리 앙상블 검색 결과", score=0.95),
        ]

        model = TestModel(
            call_tools=["search_accounting_standards"],
            custom_output_args={
                "answer": "감가상각방법에 관한 앙상블 결과입니다 [1].",
                "is_answerable": True,
                "llm_self_score": 0.98,
            },
        )
        agent = create_deep_agent(tool_type="ensemble")
        agent.model = model

        final_resp, chunks, meta = run_deep_agent(
            query="감가상각 기준",
            tool_type="ensemble",
            agent=agent,
        )

        assert final_resp.is_answerable is True
        assert "앙상블 결과" in final_resp.answer
        assert len(final_resp.citations) == 1
        assert final_resp.citations[0].chunk_id == "gaap-ch10-10.38"
        assert len(chunks) == 1
        assert meta["search_calls"] == 1
        mock_search_chunks.assert_called_once()

