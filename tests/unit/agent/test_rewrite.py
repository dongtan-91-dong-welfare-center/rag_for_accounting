from src.models.state import GraphState


def test_state_default_fields():
    state = GraphState(query="영업권 손상차손 인식 기준은?")
    assert state.is_accounting_query is True
    assert state.crag_count == 0
    assert state.rewritten_query is None
