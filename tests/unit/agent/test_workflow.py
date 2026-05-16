import pytest
from langgraph.graph.state import CompiledStateGraph
from unittest.mock import MagicMock, patch
from src.agent.workflow import build_workflow, route_after_evaluate
from src.models.state import GraphState
from src.utils.config import MAX_REWRITE_COUNT
from src.models.schemas import EvaluationResult

@pytest.fixture
def initial_state():
    """기본 GraphState 객체 생성 피처"""
    return GraphState(original_query="영업권 손상차손 인식 기준은?")

@pytest.fixture
def workflow_app():
    """컴파일된 LangGraph 워크플로우 앱 피처"""
    return build_workflow()

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
        """5개 노드(rewrite, search, rerank, evaluate, generate) 등록 여부 검증"""
        # 추상화된 CompiledStateGraph에서 .get_graph()를 통해 독립적인 Graph 객체를 얻고, 노드 목록을 가져옴
        nodes = workflow_app.get_graph().nodes
        required_nodes = ["rewrite", "search", "rerank", "evaluate", "generate"]
        for node in required_nodes:
            assert node in nodes

    def test_workflow_has_edges(self, workflow_app):
        """START 및 END 엣지의 존재 및 연결 검증"""
        graph = workflow_app.get_graph()
        edges = [(edge.source, edge.target) for edge in graph.edges]
        
        # 현재 node와 edge를 확실하게 정의하지 않았으므로 시작과 종료에 대해서만 검증합니다.
        # START 엣지 확인 (__start__ -> rewrite)
        assert any(src == "__start__" and tgt == "rewrite" for src, tgt in edges)
        # END 엣지 확인 (generate -> __end__)
        assert any(src == "generate" and tgt == "__end__" for src, tgt in edges)

    def test_workflow_initial_state_structure(self, initial_state):
        """초기 GraphState 구조 및 기본값 검증"""
        assert initial_state.original_query == "영업권 손상차손 인식 기준은?"
        assert initial_state.rewrite_count == 0
        assert initial_state.error_logs == []
        assert initial_state.retrieved_chunks == []
        assert initial_state.reranked_chunks == []
        assert initial_state.evaluation is None
        assert initial_state.final_response is None

@pytest.mark.unit
class TestNormalFlowPath:
    """정상적인 상황에서 파이프라인이 의도된 순서대로 실행되는지 확인"""

    def test_normal_path_complete_flow(self, workflow_app, initial_state):
        """표준 쿼리에 대해 모든 노드가 순서대로 실행되는지 검증"""
        # invoke 호출(사전에 정의한 순서대로 상태를 전달하며 노드를 실행하도록 설정)
        final_state: dict = workflow_app.invoke(initial_state)
        
        # TODO: 현재는 workflow.py에 정의한 Mock을 대상으로 하지만, 로직 구현 이후에는 LLM의 API를 호출하므로 테스트 항목을 적절하게 변경하여야 함
        # 검증 항목
        assert final_state["final_response"] is not None
        assert final_state["final_response"].is_answerable is True
        assert len(final_state["error_logs"]) == 0
        
        # 각 단계별 데이터 적재 확인
        assert final_state["rewrite_count"] == 1
        assert len(final_state["retrieved_chunks"]) == 2  # Mock에서 2개 반환
        assert len(final_state["reranked_chunks"]) == 2
        assert final_state["evaluation"] is not None
        assert final_state["evaluation"].needs_external is False

    def test_rewrite_count_increments(self, workflow_app, initial_state):
        """rewrite 노드 진입 시 카운트 증가 검증"""
        final_state = workflow_app.invoke(initial_state)
        assert final_state["rewrite_count"] == 1

    def test_search_returns_chunks(self, workflow_app, initial_state):
        """search 노드에서 retrieved_chunks 생성 검증"""
        final_state = workflow_app.invoke(initial_state)
        assert len(final_state["retrieved_chunks"]) >= 2

    def test_rerank_transforms_chunks(self, workflow_app, initial_state):
        """rerank 노드에서 RerankingResult로 변환 검증"""
        final_state = workflow_app.invoke(initial_state)
        assert len(final_state["reranked_chunks"]) == len(final_state["retrieved_chunks"])
        assert hasattr(final_state["reranked_chunks"][0], "rerank_score")

    def test_evaluate_returns_result(self, workflow_app, initial_state):
        """evaluate 노드에서 EvaluationResult 생성 검증"""
        final_state = workflow_app.invoke(initial_state)
        assert final_state["evaluation"] is not None
        assert final_state["evaluation"].is_relevant is True

    def test_generate_response_created(self, workflow_app, initial_state):
        """generate 노드에서 FinalResponse 생성 검증"""
        final_state = workflow_app.invoke(initial_state)
        assert final_state["final_response"] is not None
        # Mock 답변 내용 포함 여부 확인
        assert "채권형 매도가능증권" in final_state["final_response"].answer

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
        assert route_after_evaluate(state) == "rewrite"

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
        assert route_after_evaluate(state) == "generate"

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
        assert route_after_evaluate(state) == "generate"

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
class TestStateTransition:
    """파이프라인 전 과정에서 GraphState의 정합성이 유지되는지 확인"""

    def test_retrieved_chunks_empty_initially(self, initial_state):
        """워크플로우 시작 전 검색 결과 리스트가 비어있는 상태인지 확인"""
        assert initial_state.retrieved_chunks == []

    def test_reranked_chunks_depend_on_retrieved(self, workflow_app, initial_state):
        """리랭킹 결과의 개수가 원본 검색 결과의 개수와 일치하는지 확인"""
        final_state = workflow_app.invoke(initial_state)
        # Mock 노드 기준: retrieved_chunks(2개) -> reranked_chunks(2개)
        assert len(final_state["reranked_chunks"]) == len(final_state["retrieved_chunks"])

    def test_evaluation_none_initially(self, initial_state):
        """워크플로우 시작 전 평가 결과 필드가 None으로 초기화되어 있는지 확인"""
        assert initial_state.evaluation is None

    def test_final_response_none_initially(self, initial_state):
        """워크플로우 시작 전 최종 응답 필드가 None으로 초기화되어 있는지 확인"""
        assert initial_state.final_response is None

    def test_state_accumulation_full_flow(self, workflow_app, initial_state):
        """전체 실행 완료 후 모든 중간 상태 데이터가 보존되는지 확인"""
        final_state = workflow_app.invoke(initial_state)
        
        assert final_state["original_query"] is not None
        assert final_state["rewrite_count"] >= 1
        assert len(final_state["retrieved_chunks"]) > 0
        assert len(final_state["reranked_chunks"]) > 0
        assert final_state["evaluation"] is not None
        assert final_state["final_response"] is not None
