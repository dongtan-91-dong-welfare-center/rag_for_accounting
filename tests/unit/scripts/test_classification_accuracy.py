"""scripts/classification_accuracy.py 순수부 테스트와 경계 질의 표본 규격 검증.

실제 LLM 호출은 하지 않는다. 분류기는 가짜 함수로 대체하여 지표 계산과 리포트 렌더링만 검증한다.
"""
import pytest

from scripts.classification_accuracy import (
    DEFAULT_SAMPLE_PATH,
    compute_metrics,
    evaluate,
    load_samples,
    render_markdown,
)

pytestmark = pytest.mark.unit

_CATEGORIES = {"clear_accounting", "clear_non_accounting", "boundary"}


def test_sample_file_schema():
    samples = load_samples(DEFAULT_SAMPLE_PATH)
    assert len(samples) >= 20
    ids = [s["id"] for s in samples]
    assert len(ids) == len(set(ids))
    for s in samples:
        assert s["query"].strip()
        assert isinstance(s["expected_is_accounting"], bool)
        assert s["category"] in _CATEGORIES


def test_sample_file_covers_all_categories_and_both_labels():
    samples = load_samples(DEFAULT_SAMPLE_PATH)
    assert {s["category"] for s in samples} == _CATEGORIES
    boundary = [s for s in samples if s["category"] == "boundary"]
    assert {s["expected_is_accounting"] for s in boundary} == {True, False}


def test_load_samples_rejects_invalid(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"samples": [{"id": "X", "query": "q", "expected_is_accounting": "yes", "category": "boundary"}]}')
    with pytest.raises(ValueError):
        load_samples(bad)


def _samples():
    return [
        {"id": "A", "query": "a", "expected_is_accounting": True, "category": "clear_accounting"},
        {"id": "B", "query": "b", "expected_is_accounting": False, "category": "boundary"},
        {"id": "C", "query": "c", "expected_is_accounting": True, "category": "boundary"},
        {"id": "D", "query": "d", "expected_is_accounting": False, "category": "clear_non_accounting"},
    ]


def test_evaluate_and_metrics():
    # 분류기는 a, b를 회계로 판단한다: A 정답, B 오답(FP), C 오답(FN), D 정답.
    answers = {"a": True, "b": True, "c": False, "d": False}
    results = evaluate(_samples(), lambda q: (answers[q], 0.9))
    m = compute_metrics(results)
    assert m["total"] == 4
    assert m["accuracy"] == 0.5
    assert m["tp"] == 1 and m["fp"] == 1 and m["fn"] == 1 and m["tn"] == 1
    assert m["precision"] == 0.5 and m["recall"] == 0.5
    assert m["by_category"]["boundary"] == {"total": 2, "correct": 0, "accuracy": 0.0}


def test_metrics_zero_division_safe():
    m = compute_metrics([])
    assert m["total"] == 0 and m["accuracy"] == 0.0 and m["precision"] == 0.0


def test_render_markdown_lists_misclassified():
    results = evaluate(_samples(), lambda q: (True, 0.5))
    md = render_markdown(compute_metrics(results), results, model="m")
    assert "정확도" in md and "오분류" in md and "| D |" in md
