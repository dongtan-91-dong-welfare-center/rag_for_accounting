from src.db.ontology.edge_detector import detect_candidates


def test_detects_다만():
    content = "- ⑵ 리스에 따른 권리와 의무 . 다만 , ㈎ 리스채권에 대하여는 이 장을 적용한다 ."
    assert any("다만" in c for c in detect_candidates(content))


def test_detects_제외():
    content = "- 6.5 금융자산 ( 제 2 절 유가증권의 적용대상 금융자산은 제외 ) 의 양도의 경우에"
    assert any("제외" in c for c in detect_candidates(content))


def test_detects_section_ref():
    content = "- 6.3 제 2 절 ~ 제 4 절 에서 정하지 않은 사항은 이 절에서 제시하는 원칙을 적용한다 ."
    assert len(detect_candidates(content)) >= 1


def test_detects_문단_ref():
    content = "- 6.21 유가증권의 최초 인식에 관한 규정은 이 장의 제 1 절 공통사항 문단 6.4 를 따른다 ."
    assert any("문단" in c for c in detect_candidates(content))


def test_detects_문단_실_prefix():
    content = "- 6.76 파생상품의 정의에 대하여는 문단 실6.54의 2 를 참조한다 ."
    assert any("문단" in c for c in detect_candidates(content))


def test_detects_문단_range():
    content = "- 6.14 후속 측정에 대하여는 문단 6.5~6.7 을 적용한다 ."
    assert any("문단" in c for c in detect_candidates(content))


def test_detects_불구하고():
    content = "- 6.89 위의 규정에 불구하고 다음의 경우에는 별도의 처리를 한다 ."
    assert any("불구하고" in c for c in detect_candidates(content))


def test_no_false_positive():
    content = "- 6.7 매각거래와 관련하여 취득하거나 부담하는 자산 및 부채의 예로는 위탁수수료를 들 수 있다 ."
    assert detect_candidates(content) == []
