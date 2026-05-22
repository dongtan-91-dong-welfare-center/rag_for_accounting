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
        """직렬 엣지 및 조건부 라우팅 엣지 존재 및 연결 검증"""
        graph = workflow_app.get_graph()
        edges = [(edge.source, edge.target) for edge in graph.edges]
        conditional_edges = [(edge.source, edge.target) for edge in graph.edges if edge.conditional]

        # START/END 엣지 확인
        assert ("__start__", "rewrite") in edges
        assert ("generate", "__end__") in edges

        # 직렬 엣지 확인
        assert ("rewrite", "search") in edges
        assert ("search", "rerank") in edges
        assert ("rerank", "evaluate") in edges

        # 조건부 라우팅 엣지 확인 (evaluate → rewrite, evaluate → generate)
        assert ("evaluate", "rewrite") in conditional_edges
        assert ("evaluate", "generate") in conditional_edges

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
