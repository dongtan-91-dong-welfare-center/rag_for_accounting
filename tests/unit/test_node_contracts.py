import pytest
from unittest.mock import patch, MagicMock
from src.agent.workflow import rewrite, search
from src.models.state import GraphState
from src.models.schemas import RewrittenQuery, RetrievedChunk
from src.utils.exception import SearchTimeoutError, NoContextFoundError

# 헬퍼 함수: 모델 응답 mock
def create_mock_completion_response(json_content: str):
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = json_content
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    return mock_response


@pytest.mark.unit
class TestRewriteNodeContract:
    """rewrite 노드의 입출력 계약 단위 테스트"""

    @patch("src.agent.nodes.rewrite.client.chat.completions.create")
    def test_rewrite_normal_contract(self, mock_create):
        """정상 케이스:
        1. client.chat.completions.create side_effect로 첫 호출 시 분류 결과, 두 번째 호출 시 전략 결과 반환.
        2. 상태 변이 검증 (rewrite_count == 1).
        3. 타입 및 원문 보장 (rewritten_query 인스턴스 및 search_queries[0] == state.original_query).
        """
        mock_create.side_effect = [
            create_mock_completion_response('{"is_accounting": true, "strategy": "hyde"}'),
            create_mock_completion_response('{"hypothetical_answer": "영업권의 장부금액이 배분된 현금창출단위(CGU)의 회수가능액에 미달할 때..."}')
        ]

        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            rewrite_count=0,
            error_logs=[]
        )

        result = rewrite(state)

        # 반환 타입이 dict인지 검증
        assert isinstance(result, dict) 

        # 상태 변이 검증 (rewrite_count == 1)
        assert result["rewrite_count"] == 1

        # 타입 및 원문 보장
        assert isinstance(result["rewritten_query"], RewrittenQuery)    # rewritten_query 타입 검증
        assert result["is_accounting_query"] is True    # 회계 관련 질의 검증
        assert result["rewritten_query"].search_queries[0] == "영업권 손상차손 인식 기준은?"    # 첫 번째 search_query 검증
        assert len(result["rewritten_query"].search_queries) == 2    # search_queries 개수 검증
        assert result["rewritten_query"].search_queries[1] == "영업권의 장부금액이 배분된 현금창출단위(CGU)의 회수가능액에 미달할 때..."    # 두 번째 search_query 검증

    @patch("src.agent.nodes.rewrite.classify_and_select")
    def test_rewrite_fallback_contract(self, mock_classify):
        """Fallback 동작 검증:
        1. classify_and_select 패치를 통해 (True, "invalid_strategy", 0.7) 반환.
        2. 미정의 전략 명시 검증의 ValueError를 통해 strategy="bypass"로 폴백 및 error_logs 기록 검증.
        """
        mock_classify.return_value = (True, "invalid_strategy", 0.7)

        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            rewrite_count=0,
            error_logs=[]
        )

        result = rewrite(state)

        # Fallback 동작 검증: strategy="bypass"
        assert isinstance(result["rewritten_query"], RewrittenQuery)    # rewritten_query 타입 검증
        assert result["rewritten_query"].strategy == "bypass"           # strategy=bypass 검증
        assert result["rewritten_query"].search_queries == ["영업권 손상차손 인식 기준은?"]    # search_queries 검증

        # error_logs 기록 검증
        assert len(result["error_logs"]) > 0    # 에러 로그 기록
        assert any(log["node"] == "rewrite" and "ValueError" in log["error_type"] for log in result["error_logs"]) # ValueError 검증


@pytest.mark.unit
class TestSearchNodeContract:
    """search 노드의 입출력 계약 단위 테스트"""

    @patch("src.agent.workflow._search_impl")
    def test_search_normal_contract(self, mock_search):
        """정상 케이스:
        1. 단일 쿼리 입력 통제 (search_queries를 단일 원소로 고정).
        2. 반환된 retrieved_chunks 리스트 타입 검증.
        """
        # 검색 구현을 모킹하여 단일 청크 반환
        mock_search.return_value = [
            RetrievedChunk(
                chunk_id="c1",
                document_id="d1",
                content="정상 검색된 컨텍스트",
                score=0.95,
                metadata={"ontology_node_id": "test_node_123"}
            )
        ]

        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            rewritten_query=RewrittenQuery(
                original_query="영업권 손상차손 인식 기준은?",
                strategy="hyde",
                search_queries=["영업권 손상차손 인식 기준은?"]
            ),
            error_logs=[]
        )

        result = search(state)

        # 반환 타입 및 retrieved_chunks 리스트 검증
        assert isinstance(result, dict) # 반환 타입 검증
        assert isinstance(result["retrieved_chunks"], list) # retrieved_chunks 리스트 타입 검증
        assert len(result["retrieved_chunks"]) == 1 # retrieved_chunks 길이 검증
        assert result["retrieved_chunks"][0].chunk_id == "c1" # retrieved_chunks 첫 번째 원소 검증
        # metadata가 ChunkMetadata로 변환되어 ontology_node_id가 명시 필드로 보존되는지 검증 (#80)
        assert result["retrieved_chunks"][0].metadata.ontology_node_id == "test_node_123"   # metadata.ontology_node_id 명시 필드 검증
        mock_search.assert_called_once() # search 함수 호출 검증
        assert mock_search.call_args[0][0] == "영업권 손상차손 인식 기준은?" # search 함수 첫 번째 인자 검증

    @patch("src.agent.workflow._search_impl")
    def test_search_no_context_found_contract(self, mock_search):
        """에러 케이스 분기 및 에러 로그 검증 - NoContextFoundError:
        NoContextFoundError 발생 시 retrieved_chunks=[], needs_reretrieval=False, 그리고 len(error_logs) > 0 검증.
        """
        mock_search.side_effect = NoContextFoundError("검색 컨텍스트 없음")

        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            rewritten_query=RewrittenQuery(
                original_query="영업권 손상차손 인식 기준은?",
                strategy="hyde",
                search_queries=["영업권 손상차손 인식 기준은?"]
            ),
            error_logs=[]
        )

        result = search(state)

        assert result["retrieved_chunks"] == [] # 검색 실패 시 반환되는 값
        assert result["needs_reretrieval"] is False # 재검색 불필요
        assert len(result["error_logs"]) > 0    # 에러 로그 기록
        assert result["error_logs"][0]["error_type"] == "SE-103" # SE-103 에러 검증

    @patch("src.agent.workflow._search_impl")
    def test_search_timeout_error_contract(self, mock_search):
        """에러 케이스 분기 및 에러 로그 검증 - SearchTimeoutError:
        SearchTimeoutError 발생 시 retrieved_chunks=[], needs_reretrieval=True, 그리고 len(error_logs) > 0 검증.
        """
        mock_search.side_effect = SearchTimeoutError("타임아웃 발생")

        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            rewritten_query=RewrittenQuery(
                original_query="영업권 손상차손 인식 기준은?",
                strategy="hyde",
                search_queries=["영업권 손상차손 인식 기준은?"]
            ),
            error_logs=[]
        )

        result = search(state)

        assert result["retrieved_chunks"] == [] # 검색 실패 시 반환되는 값
        assert result["needs_reretrieval"] is True # 재검색 필요
        assert len(result["error_logs"]) > 0    # 에러 로그 기록
        assert result["error_logs"][0]["error_type"] == "SE-101" # SE-101 에러 검증
