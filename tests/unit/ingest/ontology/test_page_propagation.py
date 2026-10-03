"""[#297] 페이지 마커 → 노드 start_page → 청크 page_start/page_end 전파 단위 테스트

마커 규약: `<!-- page N -->` 줄은 "이 줄부터 N쪽 내용"을 뜻한다(파서가 쪽마다 앞에 붙인다).
검증 범위:
    - md_parser가 노드 생성 시점의 현재 쪽을 start_page로 기록한다.
    - chunker가 마커를 content에서 제거하고(기존 적재본과 content 동일), 청크별 쪽 범위를 metadata에 싣는다.
    - 토큰 한도 분할 시 조각마다 자기 쪽 범위를 갖는다.
    - 마커가 없는 문서는 page 키를 만들지 않는다(기존 동작 불변).
"""
import pytest

from src.ingest.ontology.chunker import chunk_graph
from src.ingest.ontology.md_parser import parse_markdown


def _words(text: str) -> int:
    return len(text.split())


MD = """# 제6장 금융자산
<!-- page 10 -->
## 제1절 공통사항
### 최초 인식
#### 6.1
첫 문단이다.
<!-- page 11 -->
#### 6.2
둘째 문단이다.
<!-- page 12 -->
### 측정
#### 6.3
셋째 문단이다.
"""

PLAIN = "\n".join(line for line in MD.splitlines() if not line.startswith("<!-- page"))


@pytest.mark.unit
class TestMdParserStartPage:
    def test_subsection_start_page_follows_markers(self):
        graph = parse_markdown(MD, "gaap-ch6", "GAAP")
        subs = {n.title: n for n in graph.nodes if n.node_type == "Subsection"}
        assert subs["최초 인식"].start_page == 10
        assert subs["측정"].start_page == 12

    def test_no_markers_leaves_start_page_none(self):
        graph = parse_markdown(PLAIN, "gaap-ch6", "GAAP")
        assert all(n.start_page is None for n in graph.nodes)


@pytest.mark.unit
class TestChunkerPages:
    def _chunks(self, md=MD, **kw):
        graph = parse_markdown(md, "gaap-ch6", "GAAP")
        return chunk_graph(graph, token_counter=_words, **kw)

    def test_page_range_spans_markers_inside_node(self):
        chunk = next(c for c in self._chunks() if "최초" in c.chunk_id)
        extra = chunk.metadata.model_extra
        assert (extra["page_start"], extra["page_end"]) == (10, 11)

    def test_next_node_starts_on_carried_page(self):
        chunk = next(c for c in self._chunks() if "측정" in c.chunk_id)
        extra = chunk.metadata.model_extra
        assert (extra["page_start"], extra["page_end"]) == (12, 12)

    def test_markers_are_removed_from_content(self):
        for chunk in self._chunks():
            assert "<!-- page" not in chunk.content

    def test_content_matches_markerless_ingest(self):
        with_markers = {c.chunk_id: c.content for c in self._chunks()}
        without = {c.chunk_id: c.content for c in self._chunks(PLAIN)}
        assert with_markers == without

    def test_no_markers_means_no_page_keys(self):
        for chunk in self._chunks(PLAIN):
            extra = chunk.metadata.model_extra or {}
            assert "page_start" not in extra and "page_end" not in extra

    def test_split_pieces_get_own_page_ranges(self):
        body = " ".join(["단어"] * 10)
        md = (
            "# 제6장 금융자산\n## 제1절 공통사항\n### 긴 소절\n<!-- page 5 -->\n"
            f"#### 6.1\n{body}\n#### 6.2\n{body}\n<!-- page 6 -->\n#### 6.3\n{body}\n"
        )
        chunks = chunk_graph(parse_markdown(md, "gaap-ch6", "GAAP"), token_counter=_words, max_tokens=12)
        ranges = [(c.metadata.model_extra["page_start"], c.metadata.model_extra["page_end"]) for c in chunks]
        assert len(chunks) >= 3
        assert ranges[0][0] == 5
        assert ranges[-1] == (6, 6)
        assert ranges == sorted(ranges)

    def test_marker_only_node_is_not_chunked(self):
        md = "# 제6장 금융자산\n## 제1절 공통사항\n### 빈 소절\n<!-- page 3 -->\n"
        graph = parse_markdown(md, "gaap-ch6", "GAAP")
        assert chunk_graph(graph, token_counter=_words) == []
