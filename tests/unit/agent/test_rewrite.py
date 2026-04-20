from src.models.state import GraphState


def test_state_default_fields():
    state = GraphState(query="영업권 손상차손 인식 기준은?")
    assert state.is_accounting_query is True
    assert state.query_strategy == "hyde"
    assert state.search_queries == []
    assert state.crag_count == 0


def test_state_search_queries_assignable():
    state = GraphState(query="test")
    state.search_queries = ["q1", "q2"]
    assert len(state.search_queries) == 2
