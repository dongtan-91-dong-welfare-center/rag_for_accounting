"""chunker.chunk_graph 단위 테스트

검증 항목:
  - 노드 매핑 정합성 — content 노드 ↔ 청크, 모든 청크가 ontology_node_id 보유 (고아 0건)
  - 토큰 한도 분할 — 초과 노드가 분할되고 조각들이 동일 node_id 공유 + 순번
  - chunk_id 결정성 — 동일 입력 재실행 시 동일 ID
  - 빈 문서 처리 — content 노드가 없으면 빈 리스트
  - metadata 전파 — standard_type·chapter(Standard 기준)·source_path(extra)

토큰 카운터는 모델 로드를 피하기 위해 "공백으로 나눈 단어 수"를 쓰는 가벼운 함수를 주입한다.
"""
import pytest

from src.db.ontology.chunker import chunk_graph
from src.db.ontology.models import OntologyGraph, OntologyNode
from src.models.schemas import RetrievedChunk
from src.utils.exception import OntologyParsingError


def _word_count(text: str) -> int:
    """모델 없이 쓰는 가벼운 토큰 카운터 — 공백 기준 단어 수."""
    return len(text.split())


def _sample_graph() -> OntologyGraph:
    """Standard 1 + content Section 1 + content 없는 Section 1 + Subsection 2 구성."""
    graph = OntologyGraph()
    graph.nodes.append(
        OntologyNode(
            id="gaap-ch6",
            node_type="Standard",
            name="제6장 금융자산·금융부채",
            standard_type="GAAP",
            chapter="6",
        )
    )
    # 직속 문단이 있는 Section → 청크화 대상
    graph.nodes.append(
        OntologyNode(
            id="gaap-ch6-s1",
            node_type="Section",
            title="제1절 공통사항",
            order=1,
            content="6.3 제2절~제4절에서 정하지 않은 사항은 이 절의 원칙을 적용한다.",
        )
    )
    # content 없는 Section → 청크화 제외
    graph.nodes.append(
        OntologyNode(
            id="gaap-ch6-s2",
            node_type="Section",
            title="제2절 인식",
            order=2,
            content="",
        )
    )
    graph.nodes.append(
        OntologyNode(
            id="gaap-ch6-s1-최초인식",
            node_type="Subsection",
            title="금융상품의 최초인식",
            order=1,
            content="6.4 금융자산이나 금융부채는 계약당사자가 되는 때에만 인식한다.",
        )
    )
    graph.nodes.append(
        OntologyNode(
            id="gaap-ch6-s2-측정",
            node_type="Subsection",
            title="후속측정",
            order=1,
            content="6.5 최초인식 후 금융자산은 상각후원가로 측정한다.",
        )
    )
    return graph


@pytest.mark.unit
def test_returns_retrieved_chunks():
    """결과물이 RetrievedChunk 타입인지 확인"""
    chunks = chunk_graph(_sample_graph(), token_counter=_word_count)
    assert all(isinstance(c, RetrievedChunk) for c in chunks)


@pytest.mark.unit
def test_only_content_nodes_become_chunks():
    """content 있는 노드만 청크가 되는지 확인"""
    # content 있는 노드: Section 1 + Subsection 2 = 3개. Standard·빈 Section은 제외.
    chunks = chunk_graph(_sample_graph(), token_counter=_word_count)
    assert len(chunks) == 3
    node_ids = {c.metadata.ontology_node_id for c in chunks}
    assert node_ids == {"gaap-ch6-s1", "gaap-ch6-s1-최초인식", "gaap-ch6-s2-측정"}


@pytest.mark.unit
def test_no_orphan_chunks():
    """모든 청크가 ontology_node_id를 보유하는지 확인 (고아 0건)"""
    chunks = chunk_graph(_sample_graph(), token_counter=_word_count)
    assert chunks
    assert all(c.metadata.ontology_node_id for c in chunks)


@pytest.mark.unit
def test_score_is_zero():
    """모든 청크의 score가 0.0인지 확인"""
    chunks = chunk_graph(_sample_graph(), token_counter=_word_count)
    assert all(c.score == 0.0 for c in chunks)


@pytest.mark.unit
def test_unsplit_chunk_id_equals_node_id():
    """분할되지 않은 노드는 chunk_id == node.id (노드 ↔ 청크 1:1)인지 확인"""
    chunks = chunk_graph(_sample_graph(), token_counter=_word_count)
    for c in chunks:
        assert c.chunk_id == c.metadata.ontology_node_id


@pytest.mark.unit
def test_document_id_defaults_to_standard_id():
    """document_id가 없으면 Standard 노드의 id를 사용"""
    chunks = chunk_graph(_sample_graph(), token_counter=_word_count)
    assert all(c.document_id == "gaap-ch6" for c in chunks)


@pytest.mark.unit
def test_document_id_override():
    """document_id를 지정하면 해당 id를 사용"""
    chunks = chunk_graph(_sample_graph(), document_id="custom-doc", token_counter=_word_count)
    assert all(c.document_id == "custom-doc" for c in chunks)


@pytest.mark.unit
def test_metadata_propagation():
    """metadata 전파 테스트 - standard_type·chapter·source_path"""
    chunks = chunk_graph(
        _sample_graph(), source_path="data/회계_sample.pdf", token_counter=_word_count
    )
    sample = chunks[0]
    # standard_type·chapter는 Standard 노드 기준으로 전파된다.
    assert sample.metadata.standard_type == "GAAP"
    assert sample.metadata.chapter == "6"
    # node_type은 해당 노드 기준.
    assert sample.metadata.node_type in {"Section", "Subsection"}
    # source_path는 extra 필드로 실린다.
    assert sample.metadata.model_extra.get("source_path") == "data/회계_sample.pdf"


@pytest.mark.unit
def test_source_path_omitted_when_not_given():
    """source_path가 주어지지 않으면 extra에 포함되지 않음"""
    chunks = chunk_graph(_sample_graph(), token_counter=_word_count)
    assert "source_path" not in (chunks[0].metadata.model_extra or {})


@pytest.mark.unit
def test_empty_graph_returns_empty_list():
    """빈 그래프는 빈 리스트를 반환"""
    assert chunk_graph(OntologyGraph(), token_counter=_word_count) == []


@pytest.mark.unit
def test_graph_without_content_nodes_returns_empty_list():
    """content 노드가 없는 그래프는 빈 리스트를 반환"""
    # Standard 노드만 있고 content 노드가 없는 경우 → 빈 리스트 (에러 아님).
    graph = OntologyGraph()
    graph.nodes.append(
        OntologyNode(id="gaap-ch6", node_type="Standard", standard_type="GAAP", chapter="6")
    )
    assert chunk_graph(graph, token_counter=_word_count) == []


@pytest.mark.unit
def test_missing_standard_raises_when_document_id_absent():
    """content 노드는 있는데 Standard도 없고 document_id도 안 주면 식별자를 못 정한다."""
    graph = OntologyGraph()
    graph.nodes.append(
        OntologyNode(id="orphan-sub", node_type="Subsection", title="x", content="내용 있음")
    )
    with pytest.raises(OntologyParsingError):
        chunk_graph(graph, token_counter=_word_count)


@pytest.mark.unit
def test_missing_standard_ok_when_document_id_given():
    """Standard가 없어도 document_id가 있으면 chunk_graph가 정상 동작"""
    graph = OntologyGraph()
    graph.nodes.append(
        OntologyNode(id="orphan-sub", node_type="Subsection", title="x", content="내용 있음")
    )
    chunks = chunk_graph(graph, document_id="manual-id", token_counter=_word_count)
    assert len(chunks) == 1
    assert chunks[0].document_id == "manual-id"
    # Standard가 없으면 standard_type·chapter는 None.
    assert chunks[0].metadata.standard_type is None
    assert chunks[0].metadata.chapter is None


@pytest.mark.unit
def test_oversized_node_is_split_by_paragraph():
    """노드가 토큰 한도를 초과하면 문단 단위로 분할되는지 확인"""
    # max_tokens=5(단어 5개) 한도. 4문단 × 단어 4개씩 = 분할 발생.
    graph = OntologyGraph()
    graph.nodes.append(
        OntologyNode(id="gaap-ch6", node_type="Standard", standard_type="GAAP", chapter="6")
    )
    content = "\n".join(
        [
            "가 나 다 라",   # 4 단어
            "마 바 사 아",
            "자 차 카 타",
            "파 하 거 너",
        ]
    )
    graph.nodes.append(
        OntologyNode(id="gaap-ch6-big", node_type="Subsection", title="큰절", content=content)
    )
    chunks = chunk_graph(graph, max_tokens=5, token_counter=_word_count)
    # 한 청크에 한 문단(4단어)씩 — 두 문단을 합치면 8 > 5라 묶이지 못한다.
    assert len(chunks) == 4
    # 분할 조각은 동일 ontology_node_id를 공유하고 순번이 붙는다.
    assert all(c.metadata.ontology_node_id == "gaap-ch6-big" for c in chunks)
    assert [c.chunk_id for c in chunks] == [
        "gaap-ch6-big-0",
        "gaap-ch6-big-1",
        "gaap-ch6-big-2",
        "gaap-ch6-big-3",
    ]
    # 모든 조각이 한도 이하.
    assert all(_word_count(c.content) <= 5 for c in chunks)


@pytest.mark.unit
def test_split_preserves_no_data_loss():
    """분할 후에도 전체 단어가 보존되어야 한다 (손실 없음)"""
    graph = OntologyGraph()
    graph.nodes.append(
        OntologyNode(id="d", node_type="Standard", standard_type="GAAP", chapter="6")
    )
    words = [f"w{i}" for i in range(20)]
    graph.nodes.append(
        OntologyNode(id="d-node", node_type="Subsection", title="t", content=" ".join(words))
    )
    chunks = chunk_graph(graph, max_tokens=3, token_counter=_word_count)
    recombined = " ".join(c.content for c in chunks).split()
    assert recombined == words


@pytest.mark.unit
def test_hard_split_when_single_unit_exceeds_limit():
    """줄·문장으로 못 나누는 한 덩어리(공백 없는 긴 문자열)는 문자 단위로 강제 분할"""
    graph = OntologyGraph()
    graph.nodes.append(
        OntologyNode(id="d", node_type="Standard", standard_type="GAAP", chapter="6")
    )
    # 공백이 없으면 _word_count는 1을 반환하므로, 문자 수 기반 카운터로 강제 분할을 유도한다.
    long_text = "가" * 100
    graph.nodes.append(
        OntologyNode(id="d-long", node_type="Subsection", title="t", content=long_text)
    )
    chunks = chunk_graph(graph, max_tokens=30, token_counter=len)
    assert len(chunks) >= 4
    assert all(len(c.content) <= 30 for c in chunks)
    # 문자 보존 — 강제 분할이어도 손실 없음.
    assert "".join(c.content for c in chunks) == long_text


@pytest.mark.unit
def test_chunk_id_determinism():
    """동일 입력 재실행 → 동일 chunk_id (upsert 멱등성의 전제) 확인"""
    first = chunk_graph(_sample_graph(), token_counter=_word_count)
    second = chunk_graph(_sample_graph(), token_counter=_word_count)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    # 분할 케이스도 결정적인지 확인.
    graph = OntologyGraph()
    graph.nodes.append(OntologyNode(id="d", node_type="Standard", standard_type="GAAP", chapter="6"))
    graph.nodes.append(
        OntologyNode(
            id="d-n", node_type="Subsection", title="t",
            content="\n".join(["가 나 다 라", "마 바 사 아", "자 차 카 타"]),
        )
    )
    a = chunk_graph(graph, max_tokens=5, token_counter=_word_count)
    b = chunk_graph(graph, max_tokens=5, token_counter=_word_count)
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]


# ════════════════════ clause-level 청킹 ════════════════════
# clause_level=True면 한 노드에 묶인 여러 조항(#### N.N)을 조항 경계로 분리해,
# 다발 노드의 정답 조항이 또렷한 단일 청크가 되도록 한다(NFR-002 Hit@1).


def _clause_node_graph(content: str, node_id: str = "gaap-ch21-bundle") -> OntologyGraph:
    """단일 Subsection 노드(조항 다발 content)로 구성된 최소 그래프."""
    graph = OntologyGraph()
    graph.nodes.append(
        OntologyNode(id="gaap-ch21", node_type="Standard", standard_type="GAAP", chapter="21")
    )
    graph.nodes.append(
        OntologyNode(id=node_id, node_type="Subsection", title="다발", content=content)
    )
    return graph


# 실제 노드 구조(gaap-ch21-...퇴직급여충당부채)를 모방한 조항 다발 — 21.8~21.10.
_BUNDLE = "\n".join(
    [
        "#### 21.8",
        "퇴직급여충당부채는 전종업원이 일시에 퇴직할 경우 지급할 금액으로 한다.",
        "",
        "#### 21.9",
        "급여규정의 개정으로 퇴직금소요액이 증가되면 당기비용으로 인식한다.",
        "",
        "#### 21.10",
        "확정급여형퇴직연금제도의 부채는 다음과 같이 회계처리한다.",
    ]
)


@pytest.mark.unit
def test_clause_level_splits_bundle_into_per_clause_chunks():
    """clause_level=True면 조항 다발이 #### N.N 경계로 조항별 청크로 분리된다."""
    chunks = chunk_graph(_clause_node_graph(_BUNDLE), clause_level=True, token_counter=_word_count)
    assert len(chunks) == 3
    # 각 조각이 자기 조항 헤더로 시작한다.
    assert [c.content.split("\n", 1)[0] for c in chunks] == ["#### 21.8", "#### 21.9", "#### 21.10"]
    # 동일 노드 → 동일 ontology_node_id + 순번 chunk_id.
    assert all(c.metadata.ontology_node_id == "gaap-ch21-bundle" for c in chunks)
    assert [c.chunk_id for c in chunks] == [
        "gaap-ch21-bundle-0",
        "gaap-ch21-bundle-1",
        "gaap-ch21-bundle-2",
    ]


@pytest.mark.unit
def test_clause_level_preserves_preamble_as_separate_chunk():
    """첫 조항 헤더 앞 머리말은 별도 조각으로 보존된다."""
    content = "\n".join(["이 절은 퇴직급여를 다룬다.", "", "#### 21.8", "퇴직급여충당부채는 ... 한다."])
    chunks = chunk_graph(_clause_node_graph(content), clause_level=True, token_counter=_word_count)
    assert len(chunks) == 2
    assert chunks[0].content == "이 절은 퇴직급여를 다룬다."
    assert chunks[1].content.startswith("#### 21.8")


@pytest.mark.unit
def test_clause_level_does_not_split_on_h5_subheaders():
    """##### 하위문단 헤더는 경계가 아니라 상위 조항에 귀속된다."""
    content = "\n".join(
        [
            "#### 21.10",
            "확정급여형퇴직연금제도의 부채는 다음과 같이 처리한다.",
            "",
            "##### (1) 종업원이 퇴직하기 전의 경우",
            "퇴직일시금에 상당하는 금액을 인식한다.",
            "##### (2) 수급요건을 갖추고 퇴사한 경우",
            "예상퇴직연금합계액의 현재가치를 측정한다.",
        ]
    )
    chunks = chunk_graph(_clause_node_graph(content), clause_level=True, token_counter=_word_count)
    assert len(chunks) == 1
    assert "##### (1)" in chunks[0].content and "##### (2)" in chunks[0].content


@pytest.mark.unit
def test_clause_level_recognizes_branch_number_header():
    """가지번호(21.5의2) 헤더도 조항 경계로 인식된다."""
    content = "\n".join(["#### 21.5", "본문 가 나 다.", "", "#### 21.5의2", "가지조항 본문 라 마 바."])
    chunks = chunk_graph(_clause_node_graph(content), clause_level=True, token_counter=_word_count)
    assert len(chunks) == 2
    assert chunks[0].content.startswith("#### 21.5\n")
    assert chunks[1].content.startswith("#### 21.5의2")


@pytest.mark.unit
def test_clause_level_falls_back_to_token_split_for_clauseless_node():
    """조항 헤더가 없는 노드는 clause_level에서도 토큰 한도 분할만 적용된다."""
    content = "\n".join(["가 나 다 라", "마 바 사 아", "자 차 카 타", "파 하 거 너"])
    chunks = chunk_graph(
        _clause_node_graph(content), clause_level=True, max_tokens=5, token_counter=_word_count
    )
    # 헤더가 없으니 조항 분할은 일어나지 않고 _split_content(max_tokens=5)만 동작 → 4조각.
    assert len(chunks) == 4
    assert all(_word_count(c.content) <= 5 for c in chunks)


@pytest.mark.unit
def test_clause_level_applies_token_split_within_oversized_clause():
    """조항 분할 후 한 조각이 토큰 상한을 넘으면 _split_content 2차 분할이 적용된다(손실 없음).

    실측상 6·21장에는 1024를 넘는 단일 조항이 없어 이 경로는 안전망이다.
    헤더 전파(쪼개진 뒷조각에 #### 헤더 부착)는 의도적으로 미구현 — 死코드라 단순화.
    """
    content = "\n".join(["#### 21.8", "가 나 다 라 마 바 사 아 자 차"])
    chunks = chunk_graph(
        _clause_node_graph(content), clause_level=True, max_tokens=5, token_counter=_word_count
    )
    assert len(chunks) >= 2
    assert all(_word_count(c.content) <= 5 for c in chunks)
    # 전체 토큰(헤더 포함)이 보존된다.
    assert " ".join(c.content for c in chunks).split() == content.split()


@pytest.mark.unit
def test_clause_level_false_is_unchanged_default():
    """clause_level 미지정(기본 False)이면 기존 동작과 동일하다(운영 경로 회귀 가드)."""
    default = chunk_graph(_clause_node_graph(_BUNDLE), token_counter=_word_count)
    explicit_false = chunk_graph(
        _clause_node_graph(_BUNDLE), clause_level=False, token_counter=_word_count
    )
    # 기본은 조항 분할을 하지 않으므로 다발이 한 청크(토큰 한도 이하)로 남는다.
    assert len(default) == 1
    assert default[0].chunk_id == "gaap-ch21-bundle"
    assert [c.chunk_id for c in default] == [c.chunk_id for c in explicit_false]
