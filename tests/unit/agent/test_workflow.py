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
        assert initial_state.query == "유형자산의 감가상각 방법은 무엇인가요?"
        assert initial_state.rewrite_count == 0
        assert initial_state.error_logs == []
        assert initial_state.retrieved_chunks == []
        assert initial_state.reranked_chunks == []
        assert initial_state.evaluation is None
        assert initial_state.final_response is None