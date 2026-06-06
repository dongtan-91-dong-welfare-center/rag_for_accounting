import pytest
from langgraph.graph.state import CompiledStateGraph
from unittest.mock import MagicMock, patch
from src.agent.workflow import (
    route_after_evaluate,
    route_after_rewrite,
    early_exit,
    search,
    run_workflow,
)
from src.models.state import GraphState
from src.utils.config import MAX_REWRITE_COUNT
from src.models.schemas import EvaluationResult, FinalResponse
from src.utils.exception import SearchTimeoutError, DatabaseQueryError, NoContextFoundError

@pytest.fixture(autouse=True)
def mock_searcher():
    """FUNC-005 반영으로 인해 외부 API 및 DB를 호출하는 searcher 모킹"""
    with patch("src.agent.workflow._search_impl") as mock_search:
        from src.models.schemas import RetrievedChunk
        mock_search.return_value = [
            RetrievedChunk(
                chunk_id="1", document_id="DOC-001",
                content="유형자산의 감가상각은...", score=0.9, metadata={}
            ),
            RetrievedChunk(
                chunk_id="2", document_id="DOC-002",
                content="전환사채를 투자목적으로...", score=0.8, metadata={}
            ),
        ]
        yield mock_search

@pytest.mark.unit
class TestWorkflowConstruction:
    """
    파이프라인 구축 검증. build_workflow()가 StateGraph를 정상적으로 구성했는지 확인
    """
    def test_workflow_builds_without_error(self, workflow_app):
        """build_workflow() 호출 성공 및 반환 타입 검증"""
        assert workflow_app is not None
        # CompiledStateGraph는 StateGraph.compile() 메서드가 반환하는 객체의 클래스
        assert isinstance(workflow_app, CompiledStateGraph)

    def test_workflow_has_required_nodes(self, workflow_app):
        """6개 노드(rewrite, early_exit, search, rerank, evaluate, generate) 등록 여부 검증"""
        # 추상화된 CompiledStateGraph에서 .get_graph()를 통해 독립적인 Graph 객체를 얻고, 노드 목록을 가져옴
        nodes = workflow_app.get_graph().nodes
        required_nodes = ["rewrite", "early_exit", "search", "rerank", "evaluate", "generate"]
        for node in required_nodes:
            assert node in nodes

    def test_workflow_has_edges(self, workflow_app):
        """직렬 엣지 및 조건부 라우팅 엣지 존재 및 연결 검증"""
        graph = workflow_app.get_graph()
        edges = [(edge.source, edge.target) for edge in graph.edges]
        conditional_edges = [(edge.source, edge.target) for edge in graph.edges if edge.conditional]

        # START/END 엣지 확인
        assert ("__start__", "rewrite") in edges    # start에서 rewrite로 시작
        assert ("generate", "__end__") in edges     # generate에서 종료
        assert ("early_exit", "__end__") in edges   # 비회계 조기 종료

        # 직렬 엣지 확인
        assert ("search", "rerank") in edges        # search에서 rerank로 이동
        assert ("rerank", "evaluate") in edges      # rerank에서 evaluate로 이동

        # rewrite 직후 조건부 라우팅 엣지 확인 (rewrite → search, rewrite → early_exit)
        assert ("rewrite", "search") in conditional_edges       # 회계 질의 → search
        assert ("rewrite", "early_exit") in conditional_edges   # 비회계 질의 → early_exit

        # 조건부 라우팅 엣지 확인 (evaluate → rewrite, evaluate → generate)
        assert ("evaluate", "rewrite") in conditional_edges # evaluate에서 evaluate로 재귀
        assert ("evaluate", "generate") in conditional_edges # evaluate에서 generate로 종료

    def test_workflow_initial_state_structure(self, initial_state):
        """초기 GraphState 구조 및 기본값 검증"""
        assert initial_state.original_query == "영업권 손상차손 인식 기준은?"   # 초기 쿼리 확인
        assert initial_state.rewrite_count == 0                    # 초기 재시도 횟수 확인
        assert initial_state.error_logs == []                      # 초기 에러 로그 확인
        assert initial_state.retrieved_chunks == []                # 초기 검색 결과 확인
        assert initial_state.reranked_chunks == []                 # 초기 재정렬 결과 확인
        assert initial_state.evaluation is None                    # 초기 평가 결과 확인
        assert initial_state.final_response is None                # 초기 최종 답변 확인

@pytest.mark.unit
class TestNormalFlowPath:
    """정상적인 상황에서 파이프라인이 의도된 순서대로 실행되는지 확인"""

    def test_rewrite_count_increments(self, workflow_app, initial_state):
        """rewrite 노드 진입 시 카운트 증가 검증"""
        final_state = workflow_app.invoke(initial_state)
        assert final_state["rewrite_count"] == 1    # 기본적으로 1번 실행

    def test_search_returns_chunks(self, workflow_app, initial_state):
        """search 노드에서 retrieved_chunks 생성 검증"""
        final_state = workflow_app.invoke(initial_state)
        assert len(final_state["retrieved_chunks"]) >= 2  # 기본적으로 2개의 청크 반환

    def test_rerank_transforms_chunks(self, workflow_app, initial_state):
        """rerank 노드에서 RerankingResult로 변환 검증"""
        final_state = workflow_app.invoke(initial_state)
        assert len(final_state["reranked_chunks"]) == len(final_state["retrieved_chunks"])  # 개수 일치
        assert hasattr(final_state["reranked_chunks"][0], "rerank_score")  # 점수 속성 확인

    def test_evaluate_returns_result(self, workflow_app, initial_state):
        """evaluate 노드에서 EvaluationResult 생성 검증"""
        final_state = workflow_app.invoke(initial_state)
        assert final_state["evaluation"] is not None  # 평가 결과 확인
        assert final_state["evaluation"].is_relevant is True    # 평가 결과 확인

    def test_generate_response_created(self, workflow_app, initial_state):
        """generate 노드에서 FinalResponse 생성 검증"""
        final_state = workflow_app.invoke(initial_state)
        assert final_state["final_response"] is not None    # 최종 답변 확인
        # Mock 답변 내용 포함 여부 확인
        assert "채권형 매도가능증권" in final_state["final_response"].answer  # Mock 답변 내용 포함 여부 확인

@pytest.mark.unit
class TestCRAGLoopPath:
    """조건부 라우팅이 정확히 작동하여 재검색 루프를 형성하는지 확인"""

    def test_route_after_evaluate_to_rewrite(self):
        """needs_external=True이고 카운트 미달일 때 rewrite 반환 검증"""
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            evaluation=EvaluationResult(
                is_relevant=True, 
                needs_external=True, 
                confidence=0.8, 
                reasoning="추가 검색 필요"
            ),
            rewrite_count=1
        )
        assert route_after_evaluate(state) == "rewrite" # evaluate에서 evaluate로 재귀

    def test_route_after_evaluate_to_generate_on_max_count(self):
        """MAX_REWRITE_COUNT 도달 시 needs_external=True라도 generate 반환 검증"""
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            evaluation=EvaluationResult(
                is_relevant=True, 
                needs_external=True, 
                confidence=0.8, 
                reasoning="한계 도달"
            ),
            rewrite_count=MAX_REWRITE_COUNT
        )
        assert route_after_evaluate(state) == "generate"    # evaluate에서 generate로 종료

    def test_route_after_evaluate_to_generate_on_needs_external_false(self):
        """needs_external=False일 때 generate 반환 검증"""
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            evaluation=EvaluationResult(
                is_relevant=True,
                needs_external=False,
                confidence=0.8,
                reasoning="검색 충분함"
            ),
            rewrite_count=1
        )
        assert route_after_evaluate(state) == "generate"    # evaluate에서 generate로 종료

    def test_route_after_evaluate_needs_reretrieval_true(self):
        """rerank가 needs_reretrieval=True를 세팅했고 횟수 미달이면 rewrite로 라우팅"""
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            needs_reretrieval=True,
            rewrite_count=1,
        )
        assert route_after_evaluate(state) == "rewrite" # 라우팅이 rewrite인지 확인

    def test_route_after_evaluate_needs_reretrieval_max_exceeded(self):
        """needs_reretrieval=True이라도 MAX_REWRITE_COUNT 도달 시 generate로 강제 진입"""
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            needs_reretrieval=True,
            rewrite_count=MAX_REWRITE_COUNT,
        )
        assert route_after_evaluate(state) == "generate" # 라우팅이 generate인지 확인

    def test_route_after_evaluate_prioritizes_needs_reretrieval_over_error(self):
        """needs_reretrieval=True와 evaluate 에러가 동시에 존재할 때 rewrite로 라우팅

        rerank가 빈 컨텍스트를 evaluate에 넘겨 evaluate 노드 자체 에러를 유발한 시나리오
        evaluate 안전장치보다 needs_reretrieval(rewrite)이 우선해야 한다.
        이 테스트가 깨지면 CRAG 루프가 잘못된 답변 생성으로 직행하는 버그가 재발한 것이다.
        """
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            needs_reretrieval=True,
            rewrite_count=1,
            error_logs=[{
                "timestamp": "2026-05-17T10:00:00+09:00",
                "node": "evaluate",
                "error_type": "EV-301",
                "message": "빈 컨텍스트로 인한 평가 실패",
            }],
        )
        assert route_after_evaluate(state) == "rewrite" # 라우팅이 rewrite인지 확인

    def test_route_after_evaluate_with_none_evaluation(self):
        """evaluation=None 엣지 케이스에서 에러 없이 generate를 반환하는지 검증
        (needs_reretrieval=False, error_logs=[], evaluation=None 조합)"""
        state = GraphState(
            original_query="영업권 손상차손 인식 기준은?",
            evaluation=None,
            rewrite_count=1,
        )
        assert route_after_evaluate(state) == "generate"    # generate로 라우팅되어야 함

    def test_recursion_limit_fallback(self, workflow_app, initial_state):
        """rewrite-retrieve 루프가 MAX_REWRITE_COUNT에 도달했을 때 루프를 종료하고 최선의 답변을 반환하는지 검증

        evaluate 노드가 항상 needs_external=True를 반환하도록 패치하여 루프를 강제 유도한다.
        MAX_REWRITE_COUNT 도달 시 route_after_evaluate가 generate로 라우팅하여 파이프라인이 종료된다.
        """
        mock_evaluator_instance = MagicMock()
        mock_evaluator_result = MagicMock()
        mock_evaluator_result.output = EvaluationResult(
            is_relevant=False,
            needs_external=True,
            confidence=0.3,
            reasoning="항상 외부 데이터 필요"
        )
        mock_evaluator_instance.run_sync.return_value = mock_evaluator_result

        with patch("src.agent.nodes.evaluate.Agent", return_value=mock_evaluator_instance):
            final_state = workflow_app.invoke(initial_state)

        assert final_state["rewrite_count"] == MAX_REWRITE_COUNT    # 최대 재시도 횟수에 도달했는지 확인
        assert final_state["final_response"] is not None            # 루프 종료 후 최선의 답변이 반환됐는지 확인
        assert final_state["evaluation"].needs_external is True     # 루프 종료 사유가 max count임을 간접 검증


@pytest.mark.unit
class TestEarlyExitRouting:
    """비회계 질문 조기 종료 라우팅(route_after_rewrite, early_exit) 검증"""

    def test_route_after_rewrite_non_accounting_to_early_exit(self):
        """is_accounting_query=False → early_exit 반환"""
        state = GraphState(original_query="대한민국 수도는 어디야?", is_accounting_query=False)
        assert route_after_rewrite(state) == "early_exit"   # route_after_rewrite가 early_exit로 라우팅되는지 확인

    def test_route_after_rewrite_accounting_to_search(self):
        """is_accounting_query=True → search 반환"""
        state = GraphState(original_query="영업권 손상차손 인식 기준은?", is_accounting_query=True)
        assert route_after_rewrite(state) == "search"   # route_after_rewrite가 search로 라우팅되는지 확인

    def test_early_exit_builds_final_response_with_confidence(self):
        """early_exit 노드가 안내 응답과 분류 신뢰도를 담은 FinalResponse를 생성"""
        state = GraphState(
            original_query="대한민국 수도는 어디야?",
            is_accounting_query=False,
            classification_confidence=0.88,
        )
        result = early_exit(state)
        fr = result["final_response"]
        assert isinstance(fr, FinalResponse)   # early_exit가 FinalResponse를 생성하는지 확인
        assert fr.answer == "죄송합니다. 회계 관련 질문을 해 주세요."   # early_exit가 안내 응답을 생성하는지 확인
        assert fr.is_answerable is False   # early_exit가 is_answerable=False를 설정하는지 확인
        assert fr.citations == []   # early_exit가 citations=[]로 설정하는지 확인
        # 고정값이 아니라 rewrite가 기록한 실제 분류 신뢰도가 전달되어야 함
        assert fr.confidence_score == 0.88   # early_exit가 confidence_score를 설정하는지 확인

    def test_non_accounting_query_skips_pipeline_e2e(self, workflow_app, initial_state, mock_searcher):
        """비회계 질의는 search/rerank/evaluate/generate를 거치지 않고 즉시 종료된다 (E2E)"""
        with patch(
            "src.agent.nodes.rewrite.classify_and_select",
            return_value=(False, "bypass", 0.9),
        ):
            final_state = workflow_app.invoke(initial_state)

        # 하위 검색 파이프라인이 호출되지 않았는지 확인
        # (조기 종료 경로에서는 해당 채널이 한 번도 갱신되지 않으므로 .get으로 안전하게 조회)
        mock_searcher.assert_not_called()
        assert final_state.get("retrieved_chunks", []) == []    # retrieved_chunks가 []인지 확인
        assert final_state.get("reranked_chunks", []) == []    # reranked_chunks가 []인지 확인
        assert final_state.get("evaluation") is None    # evaluation이 None인지 확인

        # 조기 종료 응답 검증
        fr = final_state["final_response"]
        assert fr is not None    # early_exit가 FinalResponse를 생성하는지 확인
        assert fr.is_answerable is False    # early_exit가 is_answerable=False를 설정하는지 확인
        assert fr.confidence_score == 0.9    # early_exit가 confidence_score를 설정하는지 확인
        assert "회계 관련 질문" in fr.answer    # early_exit가 안내 응답을 생성하는지 확인


@pytest.mark.unit
class TestSearchNode:
    """search() 워크플로우 노드 예외 처리 단위 테스트

    searcher.search_chunks()에서 발생하는 예외가 노드 레벨에서 올바르게
    분기되어 CRAG 신호(needs_reretrieval)와 error_logs에 반영되는지 검증한다.
    """

    def _make_state(self) -> GraphState:
        return GraphState(original_query="영업권 손상차손 인식 기준은?", error_logs=[])

    @patch("src.agent.workflow._search_impl")
    def test_search_timeout_triggers_reretrieval(self, mock_search):
        """SE-101: SearchTimeoutError → needs_reretrieval=True, retrieved_chunks=[], error_logs 기록"""
        mock_search.side_effect = SearchTimeoutError("pgvector 쿼리 타임아웃")

        result = search(self._make_state())

        assert result["retrieved_chunks"] == []         # 빈 결과 반환
        assert result["needs_reretrieval"] is True      # CRAG 루프 재진입 신호
        assert result["error_logs"][-1]["error_type"] == "SE-101"   # 에러 타입 기록

    @patch("src.agent.workflow._search_impl")
    def test_db_error_triggers_reretrieval(self, mock_search):
        """SE-102: DatabaseQueryError → needs_reretrieval=True, retrieved_chunks=[], error_logs 기록"""
        mock_search.side_effect = DatabaseQueryError("DB 연결 실패")

        result = search(self._make_state())

        assert result["retrieved_chunks"] == []         # 빈 결과 반환
        assert result["needs_reretrieval"] is True      # CRAG 루프 재진입 신호
        assert result["error_logs"][-1]["error_type"] == "SE-102"   # 에러 타입 기록

    @patch("src.agent.workflow._search_impl")
    def test_no_context_found_no_reretrieval(self, mock_search):
        """SE-103: NoContextFoundError → needs_reretrieval=False, retrieved_chunks=[], error_logs 기록

        검색 자체는 성공했으나 결과가 없으므로 재시도해도 같은 결과가 예상된다.
        CRAG 루프 재진입 없이 빈 컨텍스트로 하위 노드에 전달한다.
        """
        mock_search.side_effect = NoContextFoundError("검색 결과 없음")

        result = search(self._make_state())

        assert result["retrieved_chunks"] == []         # 빈 결과 반환
        assert result["needs_reretrieval"] is False     # 재시도 무의미 → 루프 재진입 없음
        assert result["error_logs"][-1]["error_type"] == "SE-103"   # 에러 타입 기록

    @patch("src.agent.workflow._search_impl")
    def test_system_exception_propagates(self, mock_search):
        """시스템 예외는 AccountingRAGError로 래핑되지 않고 원본 그대로 전파된다"""
        mock_search.side_effect = RuntimeError("예상치 못한 시스템 오류")

        with pytest.raises(RuntimeError, match="예상치 못한 시스템 오류"):
            search(self._make_state())


@pytest.mark.unit
class TestRunWorkflow:
    """run_workflow() 실행기 단위 테스트"""

    @patch("src.agent.workflow.build_workflow")
    def test_run_workflow_normal(self, mock_build_workflow):
        """정상 흐름 호출 시 invoke 결과 반환 검증"""
        mock_app = MagicMock()
        mock_app.invoke.return_value = {"original_query": "영업권 손상차손 인식 기준은?", "final_response": "영업권의 장부금액이 배분된 현금창출단위(CGU)의 회수가능액에 미달할 때..."}
        mock_build_workflow.return_value = mock_app

        result = run_workflow("영업권 손상차손 인식 기준은?")
        assert result["original_query"] == "영업권 손상차손 인식 기준은?"
        assert result["final_response"] == "영업권의 장부금액이 배분된 현금창출단위(CGU)의 회수가능액에 미달할 때..."
        assert mock_app.step_timeout == 30

    @patch("src.agent.workflow.build_workflow")
    def test_run_workflow_recursion_fallback(self, mock_build_workflow):
        """GraphRecursionError 발생 시 fallback 딕셔너리 반환 검증"""
        from langgraph.errors import GraphRecursionError
        from src.models.schemas import FinalResponse

        mock_app = MagicMock()
        mock_app.invoke.side_effect = GraphRecursionError("최대 재귀 횟수 초과")
        mock_build_workflow.return_value = mock_app

        result = run_workflow("영업권 손상차손 인식 기준은?")
        
        assert isinstance(result["final_response"], FinalResponse)
        assert result["final_response"].is_answerable is False
        assert "재시도" in result["final_response"].answer

    @patch("src.agent.workflow.build_workflow")
    def test_run_workflow_timeout_propagates(self, mock_build_workflow):
        """TimeoutError 발생 시 예외가 그대로 상위로 전파(raise)되는지 검증"""
        mock_app = MagicMock()
        mock_app.invoke.side_effect = TimeoutError("시간 초과")
        mock_build_workflow.return_value = mock_app

        with pytest.raises(TimeoutError):
            run_workflow("영업권 손상차손 인식 기준은?")

