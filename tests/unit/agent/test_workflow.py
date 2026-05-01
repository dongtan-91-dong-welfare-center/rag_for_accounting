import pytest
from langgraph.graph.state import CompiledStateGraph
from src.agent.workflow import build_workflow
from src.models.state import GraphState

@pytest.fixture
def initial_state():
    """기본 GraphState 객체 생성 피처"""
    return GraphState(query="영업권 손상차손 인식 기준은?")

@pytest.fixture
def workflow_app():
    """컴파일된 LangGraph 워크플로우 앱 피처"""
    return build_workflow()

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
        assert initial_state.query == "영업권 손상차손 인식 기준은?"
        assert initial_state.rewrite_count == 0
        assert initial_state.error_logs == []
        assert initial_state.retrieved_chunks == []
        assert initial_state.reranked_chunks == []
        assert initial_state.evaluation is None
        assert initial_state.final_response is None

class TestNormalFlowPath:
    """
    Test Group 2: 정상 경로
    목표: 정상적인 상황에서 파이프라인이 의도된 순서대로 실행되는지 확인
    """

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