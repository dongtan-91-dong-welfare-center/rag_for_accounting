# GraphRAG + Docling 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Docling + EdgeQuake + LangGraph 기반 회계기준서 GraphRAG 시스템을 단계적으로 구축한다.

**Architecture:** Docling이 회계 문서(PDF/HTML/Word/HWP)를 정밀 파싱하고, EdgeQuake가 그래프+벡터 하이브리드 검색을 담당하며, LangGraph가 CRAG 품질 게이트와 에이전틱 오케스트레이션을 제어한다. PydanticAI로 인용 포함 구조화 응답을 생성한다.

**Tech Stack:** Python 3.12, uv, Docker Compose, Docling, EdgeQuake (Rust), PostgreSQL (Apache AGE + pgvector), LangGraph, PydanticAI, OpenAI API

**Spec:** `docs/superpowers/specs/2026-03-21-graphrag-docling-design.md`

---

## File Structure

```
rag_for_accounting/
├── pyproject.toml                          # 의존성 관리 (수정)
├── docker-compose.yml                      # EdgeQuake + PostgreSQL (생성)
├── .env.example                            # 환경변수 템플릿 (생성)
├── src/
│   ├── __init__.py
│   ├── config.py                           # 설정 관리 (환경변수, 경로)
│   ├── parsing/
│   │   ├── __init__.py
│   │   ├── hwp_converter.py                # HWP → PDF 변환
│   │   ├── docling_parser.py               # Docling 문서 파싱
│   │   └── preprocessor.py                 # 청킹, 상호참조 추출, 메타데이터
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── edgequake_client.py             # EdgeQuake REST API 클라이언트
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── query_rewriter.py               # 자연어 → 회계 용어 변환
│   │   ├── query_router.py                 # 쿼리 모드 선택 (local/global/hybrid)
│   │   ├── edgequake_searcher.py           # EdgeQuake 검색 래퍼
│   │   └── crag_gate.py                    # CRAG 품질 평가
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── answer_generator.py             # PydanticAI 기반 응답 생성
│   │   └── schemas.py                      # PydanticAI 응답 스키마
│   └── orchestration/
│       ├── __init__.py
│       └── graph.py                        # LangGraph 워크플로우 정의
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── parsing/
│   │   ├── __init__.py
│   │   ├── test_hwp_converter.py
│   │   ├── test_docling_parser.py
│   │   └── test_preprocessor.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── test_edgequake_client.py
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── test_query_rewriter.py
│   │   ├── test_query_router.py
│   │   ├── test_edgequake_searcher.py
│   │   └── test_crag_gate.py
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── test_schemas.py
│   │   └── test_answer_generator.py
│   └── orchestration/
│       ├── __init__.py
│       └── test_graph.py
├── scripts/
│   ├── ingest.py                           # 배치 인제스트 스크립트
│   └── query.py                            # CLI 질의 스크립트
└── config/
    └── edgequake_entity_config.json        # EdgeQuake 도메인 엔티티/관계 설정
```

---

## Task 1: 프로젝트 기반 설정 및 Docker 환경 구축

**Files:**
- Modify: `pyproject.toml`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `tests/__init__.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: EdgeQuake Docker 설정 조사**

EdgeQuake 레포를 클론하여 실제 Docker 이미지 이름, 환경변수, API 엔드포인트를 확인한다.

Run: `git clone --depth 1 https://github.com/raphaelmansuy/edgequake.git /tmp/edgequake && ls /tmp/edgequake/docker-compose*.yml /tmp/edgequake/Dockerfile* 2>/dev/null && cat /tmp/edgequake/docker-compose.yml 2>/dev/null || echo "No docker-compose found, check README"`

이 결과를 바탕으로 아래 docker-compose.yml과 EdgeQuake 클라이언트의 API 엔드포인트를 조정한다.

- [ ] **Step 2: pyproject.toml에 의존성 추가**

```toml
[project]
name = "rag-for-accounting"
version = "0.1.0"
description = "GraphRAG system for K-IFRS accounting standards"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "docling>=2.0.0",
    "openai>=1.0.0",
    "langchain-openai>=0.3.0",
    "langgraph>=0.4.0",
    "pydantic-ai>=0.1.0",
    "httpx>=0.28.0",
    "python-dotenv>=1.0.0",
    "tiktoken>=0.8.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.25.0",
    "pytest-cov>=6.0.0",
]
```

> `pyhwp` 제거 — LibreOffice CLI 단일 방식으로 HWP 변환. `tiktoken` 추가 — 청크 토큰 수 계산용. `openai` 명시적 추가.

- [ ] **Step 3: 의존성 설치**

Run: `cd /Users/sboh/Desktop/dev/rag_for_accounting && uv sync --all-extras`
Expected: 의존성 설치 성공

- [ ] **Step 4: docker-compose.yml 작성**

Step 1에서 조사한 EdgeQuake의 실제 Docker 설정을 기반으로 작성한다. 아래는 예상 구조이며, 실제 이미지 이름/환경변수/포트는 조사 결과에 따라 조정한다.

```yaml
version: "3.8"

services:
  postgres:
    image: apache/age:latest
    environment:
      POSTGRES_USER: edgequake
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-edgequake_dev}
      POSTGRES_DB: edgequake
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U edgequake"]
      interval: 5s
      timeout: 5s
      retries: 5

  edgequake:
    image: ghcr.io/raphaelmansuy/edgequake:latest
    environment:
      DATABASE_URL: postgres://edgequake:${POSTGRES_PASSWORD:-edgequake_dev}@postgres:5432/edgequake
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  pgdata:
```

- [ ] **Step 5: .env.example 작성**

```env
OPENAI_API_KEY=sk-your-key-here
POSTGRES_PASSWORD=edgequake_dev
EDGEQUAKE_URL=http://localhost:8080
```

- [ ] **Step 6: config.py 작성**

`src/config.py`:
```python
from pathlib import Path
from dotenv import load_dotenv
import os


def _load_env():
    load_dotenv()


class Config:
    def __init__(self):
        _load_env()
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.edgequake_url: str = os.getenv("EDGEQUAKE_URL", "http://localhost:8080")
        self.postgres_password: str = os.getenv("POSTGRES_PASSWORD", "edgequake_dev")
        self.data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
        self.chunk_size_target: int = 750  # tokens, target 500-1000
        self.chunk_size_max: int = 1000
        self.chunk_overlap_sentences: int = 1
```

- [ ] **Step 7: 테스트 작성**

`tests/test_config.py`:
```python
from src.config import Config


def test_config_defaults():
    config = Config()
    assert config.edgequake_url == "http://localhost:8080"
    assert config.chunk_size_target == 750
    assert config.chunk_size_max == 1000
    assert config.chunk_overlap_sentences == 1
```

- [ ] **Step 8: 테스트 실행**

Run: `cd /Users/sboh/Desktop/dev/rag_for_accounting && uv run pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 9: Docker 환경 확인**

Run: `cd /Users/sboh/Desktop/dev/rag_for_accounting && docker compose up -d`
Expected: postgres, edgequake 컨테이너 정상 실행

Run: `docker compose ps`
Expected: 두 서비스 모두 healthy/running 상태

> EdgeQuake Docker 이미지가 없거나 빌드가 필요하면, EdgeQuake 레포를 클론하여 직접 빌드한다.

- [ ] **Step 10: EdgeQuake API 엔드포인트 확인**

Run: `curl http://localhost:8080/swagger-ui 2>/dev/null || curl http://localhost:8080/api-docs 2>/dev/null || curl http://localhost:8080/ 2>/dev/null`

Swagger UI 또는 API 문서에서 실제 엔드포인트를 확인하고 기록한다. 이 정보는 Task 5에서 사용한다.

- [ ] **Step 11: 커밋**

```bash
git add pyproject.toml docker-compose.yml .env.example src/__init__.py src/config.py tests/__init__.py tests/test_config.py
git commit -m "feat: 프로젝트 기반 설정 및 Docker 환경 구축"
```

---

## Task 2: HWP 변환기 구현

**Files:**
- Create: `src/parsing/__init__.py`
- Create: `src/parsing/hwp_converter.py`
- Create: `tests/parsing/__init__.py`
- Create: `tests/parsing/test_hwp_converter.py`

- [ ] **Step 1: 테스트 작성**

`tests/parsing/test_hwp_converter.py`:
```python
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.parsing.hwp_converter import HwpConverter


def test_convert_hwp_to_pdf_returns_pdf_path(tmp_path):
    hwp_file = tmp_path / "test.hwp"
    hwp_file.write_bytes(b"fake hwp content")
    expected_pdf = tmp_path / "test.pdf"

    converter = HwpConverter(output_dir=tmp_path)
    with patch("src.parsing.hwp_converter.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        expected_pdf.write_bytes(b"fake pdf")
        result = converter.convert(hwp_file)

    assert result == expected_pdf
    assert result.suffix == ".pdf"


def test_skip_non_hwp_files(tmp_path):
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    converter = HwpConverter(output_dir=tmp_path)
    result = converter.convert(pdf_file)

    assert result == pdf_file


def test_convert_failure_raises(tmp_path):
    hwp_file = tmp_path / "test.hwp"
    hwp_file.write_bytes(b"fake hwp content")

    converter = HwpConverter(output_dir=tmp_path)
    with patch("src.parsing.hwp_converter.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="conversion error")
        try:
            converter.convert(hwp_file)
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "변환 실패" in str(e)
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/parsing/test_hwp_converter.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 구현**

`src/parsing/hwp_converter.py`:
```python
import subprocess
from pathlib import Path


class HwpConverter:
    """HWP 파일을 PDF로 변환. LibreOffice CLI 사용."""

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir

    def convert(self, file_path: Path) -> Path:
        if file_path.suffix.lower() not in (".hwp", ".hwpx"):
            return file_path

        output_dir = self.output_dir or file_path.parent
        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(file_path),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"HWP 변환 실패: {file_path}. stderr: {result.stderr}"
            )

        pdf_path = output_dir / f"{file_path.stem}.pdf"
        return pdf_path
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/parsing/test_hwp_converter.py -v`
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add src/parsing/__init__.py src/parsing/hwp_converter.py tests/parsing/__init__.py tests/parsing/test_hwp_converter.py
git commit -m "feat: HWP → PDF 변환기 구현 (LibreOffice CLI)"
```

---

## Task 3: Docling 문서 파서 구현

**Files:**
- Create: `src/parsing/docling_parser.py`
- Create: `tests/parsing/test_docling_parser.py`

- [ ] **Step 1: 테스트 작성**

`tests/parsing/test_docling_parser.py`:
```python
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.parsing.docling_parser import DoclingParser, ParsedDocument


MOCK_MARKDOWN = "# 제1116호\n## 제1장 목적\n문단 1 내용"


def test_parse_returns_parsed_document_with_correct_content():
    parser = DoclingParser()

    mock_doc = MagicMock()
    mock_doc.export_to_markdown.return_value = MOCK_MARKDOWN
    mock_doc.tables = []

    with patch("src.parsing.docling_parser.DocumentConverter") as MockConverter:
        instance = MockConverter.return_value
        mock_result = MagicMock()
        mock_result.document = mock_doc
        instance.convert.return_value = mock_result

        result = parser.parse(Path("test.pdf"))

    assert isinstance(result, ParsedDocument)
    assert result.markdown == MOCK_MARKDOWN
    assert result.source_path == Path("test.pdf")


def test_parsed_document_has_required_fields():
    doc = ParsedDocument(
        source_path=Path("test.pdf"),
        markdown="# Test",
        tables=[],
        metadata={"기준서번호": "1116"},
    )
    assert doc.source_path == Path("test.pdf")
    assert doc.metadata["기준서번호"] == "1116"
    assert doc.tables == []
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/parsing/test_docling_parser.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`src/parsing/docling_parser.py`:
```python
from dataclasses import dataclass, field
from pathlib import Path

from docling.document_converter import DocumentConverter


@dataclass
class ParsedDocument:
    source_path: Path
    markdown: str
    tables: list[dict]
    metadata: dict = field(default_factory=dict)


class DoclingParser:
    """Docling 기반 문서 파서. PDF/HTML/Word를 구조화된 형태로 변환."""

    def __init__(self):
        self.converter = DocumentConverter()

    def parse(self, file_path: Path) -> ParsedDocument:
        result = self.converter.convert(str(file_path))
        doc = result.document

        markdown = doc.export_to_markdown()

        tables = []
        for table in getattr(doc, "tables", []):
            tables.append(
                {
                    "content": table.export_to_markdown()
                    if hasattr(table, "export_to_markdown")
                    else str(table),
                }
            )

        return ParsedDocument(
            source_path=file_path,
            markdown=markdown,
            tables=tables,
        )
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/parsing/test_docling_parser.py -v`
Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add src/parsing/docling_parser.py tests/parsing/test_docling_parser.py
git commit -m "feat: Docling 기반 문서 파서 구현"
```

---

## Task 4: 전처리기 구현 (청킹 + 상호참조 추출 + 메타데이터)

**Files:**
- Create: `src/parsing/preprocessor.py`
- Create: `tests/parsing/test_preprocessor.py`

- [ ] **Step 1: 테스트 작성**

`tests/parsing/test_preprocessor.py`:
```python
from pathlib import Path
from src.parsing.preprocessor import Preprocessor, Chunk
from src.parsing.docling_parser import ParsedDocument


def _make_doc(markdown: str) -> ParsedDocument:
    return ParsedDocument(source_path=Path("test.pdf"), markdown=markdown, tables=[])


def test_extract_cross_references():
    preprocessor = Preprocessor()
    text = "제1028호 문단 15에 따라 처리하며, 제1116호를 참조한다."
    refs = preprocessor.extract_cross_references(text)
    assert {"standard": "1028", "paragraph": "15"} in refs
    assert any(r["standard"] == "1116" for r in refs)


def test_extract_metadata_from_markdown():
    preprocessor = Preprocessor()
    markdown = "# 기업회계기준서 제1116호 리스\n## 제1장 목적\n이 기준서는..."
    metadata = preprocessor.extract_metadata(markdown)
    assert metadata["기준서번호"] == "1116"


def test_chunk_by_sections():
    preprocessor = Preprocessor()
    markdown = (
        "# 기업회계기준서 제1116호\n"
        "## 제1장 목적\n"
        "문단 1 내용입니다.\n\n"
        "## 제2장 적용범위\n"
        "문단 5 내용입니다.\n"
    )
    doc = _make_doc(markdown)
    chunks = preprocessor.chunk(doc)

    assert len(chunks) >= 2
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(c.hierarchy_path is not None for c in chunks)


def test_chunk_includes_hierarchy_metadata():
    preprocessor = Preprocessor()
    markdown = (
        "# 기업회계기준서 제1116호\n"
        "## 제5장 사용권자산\n"
        "사용권자산의 감가상각에 대한 내용입니다.\n"
    )
    doc = _make_doc(markdown)
    chunks = preprocessor.chunk(doc)

    assert any("제5장" in c.hierarchy_path for c in chunks)


def test_chunk_enforces_max_token_limit():
    preprocessor = Preprocessor(chunk_size_max=50)
    long_text = "이것은 매우 긴 문단입니다. " * 100
    markdown = f"# 기준서\n## 제1장\n{long_text}\n"
    doc = _make_doc(markdown)
    chunks = preprocessor.chunk(doc)

    # 긴 문단이 분할되어야 함
    assert len(chunks) > 1
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/parsing/test_preprocessor.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`src/parsing/preprocessor.py`:
```python
import re
from dataclasses import dataclass, field
from pathlib import Path

import tiktoken

from src.parsing.docling_parser import ParsedDocument


@dataclass
class Chunk:
    text: str
    hierarchy_path: str
    metadata: dict = field(default_factory=dict)
    cross_references: list[dict] = field(default_factory=list)


class Preprocessor:
    """Docling 파싱 결과를 청킹하고, 상호참조/메타데이터를 추출한다."""

    STANDARD_PATTERN = re.compile(r"제(\d{4})호")
    PARAGRAPH_PATTERN = re.compile(r"문단\s*(\d+)")
    CROSS_REF_PATTERN = re.compile(r"제(\d{4})호(?:\s*문단\s*(\d+))?")

    def __init__(self, chunk_size_max: int = 1000):
        self.chunk_size_max = chunk_size_max
        self._encoder = tiktoken.encoding_for_model("gpt-4o")

    def _count_tokens(self, text: str) -> int:
        return len(self._encoder.encode(text))

    def extract_cross_references(self, text: str) -> list[dict]:
        refs = []
        for match in self.CROSS_REF_PATTERN.finditer(text):
            ref = {"standard": match.group(1)}
            if match.group(2):
                ref["paragraph"] = match.group(2)
            refs.append(ref)
        return refs

    def extract_metadata(self, markdown: str) -> dict:
        metadata = {}
        standard_match = self.STANDARD_PATTERN.search(markdown)
        if standard_match:
            metadata["기준서번호"] = standard_match.group(1)
        return metadata

    def chunk(self, doc: ParsedDocument) -> list[Chunk]:
        metadata = self.extract_metadata(doc.markdown)
        sections = self._split_by_headers(doc.markdown)
        chunks = []

        for section in sections:
            if not section["content"].strip():
                continue

            content = section["content"]
            token_count = self._count_tokens(content)

            if token_count <= self.chunk_size_max:
                cross_refs = self.extract_cross_references(content)
                chunks.append(
                    Chunk(
                        text=content,
                        hierarchy_path=section["path"],
                        metadata={**metadata},
                        cross_references=cross_refs,
                    )
                )
            else:
                # 문장 경계에서 분할
                sub_chunks = self._split_by_sentences(content, section["path"], metadata)
                chunks.extend(sub_chunks)

        return chunks

    def _split_by_sentences(self, text: str, path: str, metadata: dict) -> list[Chunk]:
        sentences = re.split(r"(?<=[.!?。])\s+", text)
        chunks = []
        current_sentences: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)
            if current_tokens + sentence_tokens > self.chunk_size_max and current_sentences:
                chunk_text = " ".join(current_sentences)
                cross_refs = self.extract_cross_references(chunk_text)
                chunks.append(
                    Chunk(
                        text=chunk_text,
                        hierarchy_path=path,
                        metadata={**metadata},
                        cross_references=cross_refs,
                    )
                )
                current_sentences = []
                current_tokens = 0

            current_sentences.append(sentence)
            current_tokens += sentence_tokens

        if current_sentences:
            chunk_text = " ".join(current_sentences)
            cross_refs = self.extract_cross_references(chunk_text)
            chunks.append(
                Chunk(
                    text=chunk_text,
                    hierarchy_path=path,
                    metadata={**metadata},
                    cross_references=cross_refs,
                )
            )

        return chunks

    def _split_by_headers(self, markdown: str) -> list[dict]:
        lines = markdown.split("\n")
        sections = []
        current_path_parts: list[str] = []
        current_content_lines: list[str] = []

        for line in lines:
            header_match = re.match(r"^(#{1,4})\s+(.+)$", line)
            if header_match:
                if current_content_lines:
                    sections.append(
                        {
                            "path": " > ".join(current_path_parts) if current_path_parts else "",
                            "content": "\n".join(current_content_lines),
                        }
                    )
                    current_content_lines = []

                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                current_path_parts = current_path_parts[: level - 1]
                current_path_parts.append(title)
            else:
                current_content_lines.append(line)

        if current_content_lines:
            sections.append(
                {
                    "path": " > ".join(current_path_parts) if current_path_parts else "",
                    "content": "\n".join(current_content_lines),
                }
            )

        return sections
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/parsing/test_preprocessor.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add src/parsing/preprocessor.py tests/parsing/test_preprocessor.py
git commit -m "feat: 전처리기 구현 (구조 기반 청킹, 토큰 제한, 상호참조 추출)"
```

---

## Task 5: EdgeQuake REST API 클라이언트 구현

**Files:**
- Create: `src/ingestion/__init__.py`
- Create: `src/ingestion/edgequake_client.py`
- Create: `tests/ingestion/__init__.py`
- Create: `tests/ingestion/test_edgequake_client.py`

> **중요:** Task 1 Step 10에서 확인한 실제 EdgeQuake API 엔드포인트를 사용한다. 아래는 예상 구조이며, Swagger UI에서 확인한 엔드포인트로 교체한다.

- [ ] **Step 1: 테스트 작성**

`tests/ingestion/test_edgequake_client.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.ingestion.edgequake_client import EdgeQuakeClient


@pytest.mark.asyncio
async def test_ingest_document_sends_post_request():
    client = EdgeQuakeClient(base_url="http://localhost:8080")

    with patch("src.ingestion.edgequake_client.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_instance.post.return_value = MagicMock(status_code=200, json=lambda: {"status": "ok"})

        result = await client.ingest_document("사용권자산의 감가상각", {"기준서번호": "1116"})

    mock_instance.post.assert_called_once()
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_query_sends_post_request():
    client = EdgeQuakeClient(base_url="http://localhost:8080")

    with patch("src.ingestion.edgequake_client.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_instance.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"response": "답변", "sources": []},
        )

        result = await client.query("리스 회계처리", mode="hybrid")

    assert "response" in result


@pytest.mark.asyncio
async def test_health_returns_bool():
    client = EdgeQuakeClient(base_url="http://localhost:8080")

    with patch("src.ingestion.edgequake_client.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get.return_value = MagicMock(status_code=200)

        result = await client.health()

    assert result is True
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/ingestion/test_edgequake_client.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`src/ingestion/edgequake_client.py`:
```python
import httpx


class EdgeQuakeClient:
    """EdgeQuake REST API 클라이언트.

    참고: API 엔드포인트는 EdgeQuake Swagger UI에서 확인한 실제 경로로 교체 필요.
    """

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip("/")

    async def ingest_document(self, text: str, metadata: dict | None = None) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/documents",
                json={"content": text, "metadata": metadata or {}},
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()

    async def query(self, query: str, mode: str = "hybrid", top_k: int = 10) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/query",
                json={"query": query, "mode": mode, "top_k": top_k},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/health", timeout=5.0)
                return response.status_code == 200
        except httpx.RequestError:
            return False
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/ingestion/test_edgequake_client.py -v`
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add src/ingestion/__init__.py src/ingestion/edgequake_client.py tests/ingestion/__init__.py tests/ingestion/test_edgequake_client.py
git commit -m "feat: EdgeQuake REST API 클라이언트 구현"
```

---

## Task 6: EdgeQuake 도메인 커스터마이징 설정

**Files:**
- Create: `config/edgequake_entity_config.json`

> 이 태스크는 EdgeQuake의 실제 커스터마이징 메커니즘에 따라 조정 필요. EdgeQuake가 프롬프트 커스터마이징을 지원하는 방식(설정 파일, API, 환경변수)을 Task 1에서 조사한 결과를 바탕으로 작성한다.

- [ ] **Step 1: 엔티티/관계 설정 파일 작성**

`config/edgequake_entity_config.json`:
```json
{
  "entity_types": [
    {
      "name": "concept",
      "subtypes": [
        {
          "subtype": "standard",
          "description": "K-IFRS 회계기준서 (예: K-IFRS 1116, 제1028호)",
          "extraction_hints": ["제\\d{4}호", "K-IFRS\\s*\\d{4}"]
        },
        {
          "subtype": "accounting_concept",
          "description": "회계 개념 (예: 사용권자산, 감가상각, 공정가치)"
        }
      ]
    },
    {
      "name": "event",
      "description": "회계처리 단계 (예: 최초인식, 후속측정, 제거)"
    },
    {
      "name": "organization",
      "description": "규제기관 (예: 금융감독원, IASB)"
    },
    {
      "name": "product",
      "description": "재무제표 항목 (예: 재무상태표, 손익계산서)"
    }
  ],
  "relationship_types": [
    {"name": "참조", "description": "기준서 간 상호참조"},
    {"name": "소속", "description": "계층 구조 (장 > 절 > 문단)"},
    {"name": "적용", "description": "개념 → 회계처리 연결"},
    {"name": "예외", "description": "조건부 예외 조항", "keywords": ["다만", "제외하고", "적용하지 아니한다"]},
    {"name": "후속", "description": "처리 순서/단계"}
  ],
  "extraction_prompt_additions": "엔티티 추출 시 다음 규칙을 따르세요:\n1. '제XXXX호' 패턴을 우선적으로 standard 엔티티로 추출\n2. '문단 XX' 패턴을 문단 참조로 추출\n3. '다만', '제외하고', '적용하지 아니한다' 등의 표현이 있으면 '예외' 관계로 명시 추출\n4. technology, location 타입은 사용하지 않음"
}
```

- [ ] **Step 2: EdgeQuake에 설정 적용**

EdgeQuake의 실제 커스터마이징 방법에 따라 적용한다:
- API를 통한 설정: `curl -X POST http://localhost:8080/api/config -d @config/edgequake_entity_config.json`
- 환경변수: docker-compose.yml에 설정 경로 마운트
- 프롬프트 파일: EdgeQuake 프롬프트 디렉토리에 복사

> 구체적인 적용 방법은 Task 1에서 조사한 EdgeQuake 문서를 참조한다.

- [ ] **Step 3: 커밋**

```bash
git add config/edgequake_entity_config.json
git commit -m "feat: EdgeQuake 도메인 커스터마이징 설정 (회계 엔티티/관계 타입)"
```

---

## Task 7: PydanticAI 응답 스키마 정의

**Files:**
- Create: `src/generation/__init__.py`
- Create: `src/generation/schemas.py`
- Create: `tests/generation/__init__.py`
- Create: `tests/generation/test_schemas.py`

- [ ] **Step 1: 테스트 작성**

`tests/generation/test_schemas.py`:
```python
import pytest
from pydantic import ValidationError
from src.generation.schemas import Citation, RAGResponse


def test_citation_requires_standard():
    citation = Citation(기준서="1116", 문단="31-33", 내용="사용권자산을...")
    assert citation.기준서 == "1116"
    assert citation.문단 == "31-33"


def test_rag_response_rejects_empty_citations():
    with pytest.raises(ValidationError, match="최소 1개의 인용"):
        RAGResponse(answer="답변", citations=[], related_standards=[], confidence=0.9)


def test_valid_rag_response():
    response = RAGResponse(
        answer="사용권자산은 정액법으로 감가상각합니다.",
        citations=[Citation(기준서="1116", 문단="31", 내용="사용권자산의 감가상각...")],
        related_standards=["1028"],
        confidence=0.92,
    )
    assert len(response.citations) == 1
    assert response.confidence == 0.92
    assert response.related_standards == ["1028"]
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/generation/test_schemas.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`src/generation/schemas.py`:
```python
from pydantic import BaseModel, field_validator


class Citation(BaseModel):
    기준서: str
    문단: str
    내용: str


class RAGResponse(BaseModel):
    answer: str
    citations: list[Citation]
    related_standards: list[str]
    confidence: float

    @field_validator("citations")
    @classmethod
    def citations_must_not_be_empty(cls, v: list[Citation]) -> list[Citation]:
        if len(v) == 0:
            raise ValueError("응답에는 최소 1개의 인용이 필요합니다")
        return v
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/generation/test_schemas.py -v`
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add src/generation/__init__.py src/generation/schemas.py tests/generation/__init__.py tests/generation/test_schemas.py
git commit -m "feat: PydanticAI 응답 스키마 정의 (인용 필수)"
```

---

## Task 8: Query Rewriter 구현

**Files:**
- Create: `src/retrieval/__init__.py`
- Create: `src/retrieval/query_rewriter.py`
- Create: `tests/retrieval/__init__.py`
- Create: `tests/retrieval/test_query_rewriter.py`

- [ ] **Step 1: 테스트 작성**

`tests/retrieval/test_query_rewriter.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch
from src.retrieval.query_rewriter import QueryRewriter

EXPECTED_REWRITE = "K-IFRS 1116 사용권자산 감가상각 방법"


@pytest.mark.asyncio
async def test_rewrite_returns_transformed_query():
    rewriter = QueryRewriter()

    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(message=AsyncMock(content=EXPECTED_REWRITE))
    ]

    with patch("src.retrieval.query_rewriter.AsyncOpenAI") as MockOpenAI:
        instance = MockOpenAI.return_value
        instance.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await rewriter.rewrite("리스 계약에서 감가상각 어떻게 해?")

    assert result == EXPECTED_REWRITE
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/retrieval/test_query_rewriter.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`src/retrieval/query_rewriter.py`:
```python
from openai import AsyncOpenAI

REWRITE_PROMPT = """당신은 K-IFRS 회계기준서 검색을 위한 쿼리 변환 전문가입니다.
사용자의 자연어 질문을 회계 전문 용어로 변환하세요.

규칙:
- 관련 기준서 번호가 있으면 포함 (예: K-IFRS 1116)
- 회계 전문 용어 사용 (예: "빌려쓰는 자산" → "사용권자산")
- 핵심 키워드 중심으로 간결하게

사용자 질문: {query}

변환된 검색 쿼리:"""


class QueryRewriter:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI()
        self.model = model

    async def rewrite(self, query: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": REWRITE_PROMPT.format(query=query)}],
            temperature=0.0,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/retrieval/test_query_rewriter.py -v`
Expected: 1 passed

- [ ] **Step 5: 커밋**

```bash
git add src/retrieval/__init__.py src/retrieval/query_rewriter.py tests/retrieval/__init__.py tests/retrieval/test_query_rewriter.py
git commit -m "feat: Query Rewriter 구현 (자연어 → 회계용어 변환)"
```

---

## Task 9: Query Router 구현

**Files:**
- Create: `src/retrieval/query_router.py`
- Create: `tests/retrieval/test_query_router.py`

- [ ] **Step 1: 테스트 작성**

`tests/retrieval/test_query_router.py`:
```python
from src.retrieval.query_router import QueryRouter


def test_route_specific_standard_to_local():
    router = QueryRouter()
    assert router.route("K-IFRS 1116 문단 31 사용권자산 감가상각") == "local"


def test_route_broad_topic_to_global():
    router = QueryRouter()
    assert router.route("리스 관련 기준서 전체 개요") == "global"


def test_route_complex_query_to_hybrid():
    router = QueryRouter()
    assert router.route("사용권자산 감가상각과 관련 예외 조항") == "hybrid"


def test_route_standard_ref_with_broad_keyword_to_hybrid():
    router = QueryRouter()
    assert router.route("제1116호 관련 기준서 전체") == "hybrid"
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/retrieval/test_query_router.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`src/retrieval/query_router.py`:
```python
import re


class QueryRouter:
    """쿼리 유형에 따라 EdgeQuake 검색 모드를 선택하는 규칙 기반 라우터."""

    STANDARD_PATTERN = re.compile(r"(?:제\d{4}호|K-IFRS\s*\d{4}|문단\s*\d+)")
    BROAD_KEYWORDS = {"전체", "개요", "요약", "비교", "관련 기준서", "모든"}

    def route(self, query: str) -> str:
        has_specific_ref = bool(self.STANDARD_PATTERN.search(query))
        has_broad_keyword = any(kw in query for kw in self.BROAD_KEYWORDS)

        if has_specific_ref and not has_broad_keyword:
            return "local"
        if has_broad_keyword and not has_specific_ref:
            return "global"
        return "hybrid"
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/retrieval/test_query_router.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add src/retrieval/query_router.py tests/retrieval/test_query_router.py
git commit -m "feat: Query Router 구현 (규칙 기반 모드 선택)"
```

---

## Task 10: CRAG 품질 게이트 구현

**Files:**
- Create: `src/retrieval/crag_gate.py`
- Create: `tests/retrieval/test_crag_gate.py`

- [ ] **Step 1: 테스트 작성**

`tests/retrieval/test_crag_gate.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch
from src.retrieval.crag_gate import CRAGGate, CRAGResult


@pytest.mark.asyncio
async def test_evaluate_correct():
    gate = CRAGGate()
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(message=AsyncMock(content="CORRECT"))]

    with patch("src.retrieval.crag_gate.AsyncOpenAI") as MockOpenAI:
        instance = MockOpenAI.return_value
        instance.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await gate.evaluate(
            query="사용권자산 감가상각",
            search_results=[{"content": "K-IFRS 1116 문단 31..."}],
        )

    assert result == CRAGResult.CORRECT


@pytest.mark.asyncio
async def test_evaluate_wrong():
    gate = CRAGGate()
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(message=AsyncMock(content="WRONG"))]

    with patch("src.retrieval.crag_gate.AsyncOpenAI") as MockOpenAI:
        instance = MockOpenAI.return_value
        instance.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await gate.evaluate(
            query="사용권자산 감가상각",
            search_results=[{"content": "날씨가 좋습니다"}],
        )

    assert result == CRAGResult.WRONG


@pytest.mark.asyncio
async def test_evaluate_ambiguous():
    gate = CRAGGate()
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(message=AsyncMock(content="AMBIGUOUS"))]

    with patch("src.retrieval.crag_gate.AsyncOpenAI") as MockOpenAI:
        instance = MockOpenAI.return_value
        instance.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await gate.evaluate(
            query="리스 관련",
            search_results=[{"content": "부분적 관련 내용"}],
        )

    assert result == CRAGResult.AMBIGUOUS
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/retrieval/test_crag_gate.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`src/retrieval/crag_gate.py`:
```python
from enum import Enum

from openai import AsyncOpenAI

CRAG_PROMPT = """당신은 검색 결과의 품질을 평가하는 전문가입니다.

사용자 질문: {query}

검색 결과:
{search_results}

검색 결과가 질문에 답하기에 충분한지 평가하세요.

응답은 반드시 다음 중 하나만 출력하세요:
- CORRECT: 검색 결과가 질문에 직접적으로 답할 수 있는 관련 정보를 포함
- AMBIGUOUS: 부분적으로 관련이 있지만 완전한 답변이 어려움
- WRONG: 검색 결과가 질문과 무관하거나 불충분

평가:"""


class CRAGResult(Enum):
    CORRECT = "CORRECT"
    AMBIGUOUS = "AMBIGUOUS"
    WRONG = "WRONG"


class CRAGGate:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI()
        self.model = model

    async def evaluate(self, query: str, search_results: list[dict]) -> CRAGResult:
        results_text = "\n---\n".join(r.get("content", str(r)) for r in search_results)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": CRAG_PROMPT.format(query=query, search_results=results_text)}
            ],
            temperature=0.0,
            max_tokens=20,
        )

        answer = response.choices[0].message.content.strip().upper()

        if "CORRECT" in answer:
            return CRAGResult.CORRECT
        if "AMBIGUOUS" in answer:
            return CRAGResult.AMBIGUOUS
        return CRAGResult.WRONG
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/retrieval/test_crag_gate.py -v`
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add src/retrieval/crag_gate.py tests/retrieval/test_crag_gate.py
git commit -m "feat: CRAG 품질 게이트 구현"
```

---

## Task 11: 응답 생성기 구현 (PydanticAI 기반)

**Files:**
- Create: `src/generation/answer_generator.py`
- Create: `tests/generation/test_answer_generator.py`

- [ ] **Step 1: 테스트 작성**

`tests/generation/test_answer_generator.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.generation.answer_generator import AnswerGenerator
from src.generation.schemas import RAGResponse


@pytest.mark.asyncio
async def test_generate_returns_rag_response():
    generator = AnswerGenerator()

    mock_result = MagicMock()
    mock_result.data = RAGResponse(
        answer="사용권자산은 정액법으로 감가상각합니다.",
        citations=[MagicMock(기준서="1116", 문단="31", 내용="사용권자산의 감가상각...")],
        related_standards=["1028"],
        confidence=0.92,
    )

    with patch("src.generation.answer_generator.Agent") as MockAgent:
        instance = MockAgent.return_value
        instance.run = AsyncMock(return_value=mock_result)

        result = await generator.generate(
            query="사용권자산 감가상각",
            context=[{"content": "K-IFRS 1116 문단 31..."}],
        )

    assert isinstance(result, RAGResponse)
    assert len(result.citations) >= 1
    assert result.confidence == 0.92
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/generation/test_answer_generator.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`src/generation/answer_generator.py`:
```python
from pydantic_ai import Agent

from src.generation.schemas import RAGResponse

ANSWER_PROMPT = """당신은 K-IFRS 회계기준서 전문가입니다.
주어진 검색 결과를 바탕으로 질문에 정확하게 답변하세요.

규칙:
1. 반드시 검색 결과에 있는 내용만 사용하세요
2. 기준서 번호와 문단 번호를 인용하세요
3. 관련 예외 조항이 있으면 반드시 언급하세요
4. confidence는 검색 결과의 관련성과 완전성에 따라 0.0~1.0 사이로 설정하세요"""


class AnswerGenerator:
    def __init__(self, model: str = "openai:gpt-4o"):
        self.agent = Agent(
            model,
            result_type=RAGResponse,
            system_prompt=ANSWER_PROMPT,
        )

    async def generate(self, query: str, context: list[dict]) -> RAGResponse:
        context_text = "\n---\n".join(c.get("content", str(c)) for c in context)

        prompt = f"질문: {query}\n\n검색 결과:\n{context_text}"

        result = await self.agent.run(prompt)
        return result.data
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/generation/test_answer_generator.py -v`
Expected: 1 passed

- [ ] **Step 5: 커밋**

```bash
git add src/generation/answer_generator.py tests/generation/test_answer_generator.py
git commit -m "feat: PydanticAI 기반 응답 생성기 구현"
```

---

## Task 12: EdgeQuake 검색 래퍼 구현

**Files:**
- Create: `src/retrieval/edgequake_searcher.py`
- Create: `tests/retrieval/test_edgequake_searcher.py`

- [ ] **Step 1: 테스트 작성**

`tests/retrieval/test_edgequake_searcher.py`:
```python
import pytest
from unittest.mock import AsyncMock
from src.retrieval.edgequake_searcher import EdgeQuakeSearcher


@pytest.mark.asyncio
async def test_search_returns_sources():
    mock_client = AsyncMock()
    mock_client.query.return_value = {
        "response": "답변",
        "sources": [{"content": "K-IFRS 1116 문단 31..."}],
    }

    searcher = EdgeQuakeSearcher(client=mock_client)
    results = await searcher.search("사용권자산", mode="local")

    assert len(results) == 1
    assert results[0]["content"] == "K-IFRS 1116 문단 31..."
    mock_client.query.assert_called_once_with("사용권자산", mode="local", top_k=10)


@pytest.mark.asyncio
async def test_search_empty_results():
    mock_client = AsyncMock()
    mock_client.query.return_value = {"response": "", "sources": []}

    searcher = EdgeQuakeSearcher(client=mock_client)
    results = await searcher.search("존재하지않는질의")

    assert results == []
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/retrieval/test_edgequake_searcher.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`src/retrieval/edgequake_searcher.py`:
```python
from src.ingestion.edgequake_client import EdgeQuakeClient


class EdgeQuakeSearcher:
    """EdgeQuake 검색을 위한 래퍼. 모드별 검색 실행."""

    def __init__(self, client: EdgeQuakeClient | None = None):
        self.client = client or EdgeQuakeClient()

    async def search(self, query: str, mode: str = "hybrid", top_k: int = 10) -> list[dict]:
        result = await self.client.query(query, mode=mode, top_k=top_k)
        return result.get("sources", [])
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/retrieval/test_edgequake_searcher.py -v`
Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add src/retrieval/edgequake_searcher.py tests/retrieval/test_edgequake_searcher.py
git commit -m "feat: EdgeQuake 검색 래퍼 구현"
```

---

## Task 13: LangGraph 오케스트레이션 워크플로우 구현

**Files:**
- Create: `src/orchestration/__init__.py`
- Create: `src/orchestration/graph.py`
- Create: `tests/orchestration/__init__.py`
- Create: `tests/orchestration/test_graph.py`

- [ ] **Step 1: 테스트 작성**

`tests/orchestration/test_graph.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch
from src.orchestration.graph import build_graph, GraphState, should_retry
from src.retrieval.crag_gate import CRAGResult


def test_build_graph_has_expected_nodes():
    graph = build_graph()
    assert graph is not None


def test_should_retry_returns_generate_on_correct():
    state: GraphState = {
        "query": "test",
        "rewritten_query": "test",
        "mode": "hybrid",
        "search_results": [],
        "crag_result": CRAGResult.CORRECT.value,
        "answer": None,
        "retry_count": 0,
    }
    assert should_retry(state) == "generate"


def test_should_retry_returns_retry_on_wrong():
    state: GraphState = {
        "query": "test",
        "rewritten_query": "test",
        "mode": "hybrid",
        "search_results": [],
        "crag_result": CRAGResult.WRONG.value,
        "answer": None,
        "retry_count": 0,
    }
    assert should_retry(state) == "retry"


def test_should_retry_returns_generate_on_max_retries():
    state: GraphState = {
        "query": "test",
        "rewritten_query": "test",
        "mode": "hybrid",
        "search_results": [],
        "crag_result": CRAGResult.WRONG.value,
        "answer": None,
        "retry_count": 2,
    }
    assert should_retry(state) == "generate"


def test_should_retry_returns_retry_on_ambiguous():
    state: GraphState = {
        "query": "test",
        "rewritten_query": "test",
        "mode": "local",
        "search_results": [],
        "crag_result": CRAGResult.AMBIGUOUS.value,
        "answer": None,
        "retry_count": 1,
    }
    assert should_retry(state) == "retry"
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/orchestration/test_graph.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`src/orchestration/graph.py`:
```python
from typing import TypedDict

from langgraph.graph import StateGraph, END

from src.retrieval.query_rewriter import QueryRewriter
from src.retrieval.query_router import QueryRouter
from src.retrieval.edgequake_searcher import EdgeQuakeSearcher
from src.retrieval.crag_gate import CRAGGate, CRAGResult
from src.generation.answer_generator import AnswerGenerator
from src.generation.schemas import RAGResponse

MAX_RETRIES = 2


class GraphState(TypedDict):
    query: str
    rewritten_query: str
    mode: str
    search_results: list[dict]
    crag_result: str | None
    answer: RAGResponse | None
    retry_count: int


async def rewrite_query(state: GraphState) -> GraphState:
    rewriter = QueryRewriter()
    rewritten = await rewriter.rewrite(state["query"])
    return {**state, "rewritten_query": rewritten}


async def route_query(state: GraphState) -> GraphState:
    router = QueryRouter()
    mode = router.route(state["rewritten_query"])
    return {**state, "mode": mode}


async def search(state: GraphState) -> GraphState:
    searcher = EdgeQuakeSearcher()
    results = await searcher.search(state["rewritten_query"], mode=state["mode"])
    return {**state, "search_results": results}


async def evaluate_crag(state: GraphState) -> GraphState:
    gate = CRAGGate()
    result = await gate.evaluate(state["rewritten_query"], state["search_results"])
    return {**state, "crag_result": result.value}


def should_retry(state: GraphState) -> str:
    if state["crag_result"] == CRAGResult.CORRECT.value:
        return "generate"
    if state["retry_count"] >= MAX_RETRIES:
        return "generate"
    return "retry"


async def retry_search(state: GraphState) -> GraphState:
    modes = ["local", "global", "hybrid"]
    current_idx = modes.index(state["mode"]) if state["mode"] in modes else 0
    next_mode = modes[(current_idx + 1) % len(modes)]

    searcher = EdgeQuakeSearcher()
    results = await searcher.search(state["rewritten_query"], mode=next_mode)
    return {
        **state,
        "mode": next_mode,
        "search_results": results,
        "retry_count": state["retry_count"] + 1,
    }


async def generate_answer(state: GraphState) -> GraphState:
    generator = AnswerGenerator()
    answer = await generator.generate(state["query"], state["search_results"])
    return {**state, "answer": answer}


def build_graph() -> StateGraph:
    workflow = StateGraph(GraphState)

    workflow.add_node("rewrite", rewrite_query)
    workflow.add_node("route", route_query)
    workflow.add_node("search", search)
    workflow.add_node("evaluate", evaluate_crag)
    workflow.add_node("retry", retry_search)
    workflow.add_node("generate", generate_answer)

    workflow.set_entry_point("rewrite")
    workflow.add_edge("rewrite", "route")
    workflow.add_edge("route", "search")
    workflow.add_edge("search", "evaluate")
    workflow.add_conditional_edges("evaluate", should_retry)
    workflow.add_edge("retry", "evaluate")
    workflow.add_edge("generate", END)

    return workflow.compile()
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/orchestration/test_graph.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add src/retrieval/edgequake_searcher.py src/orchestration/__init__.py src/orchestration/graph.py tests/orchestration/__init__.py tests/orchestration/test_graph.py
git commit -m "feat: LangGraph 오케스트레이션 워크플로우 구현 (CRAG 루프 포함)"
```

---

## Task 14: 배치 인제스트 스크립트 구현

**Files:**
- Create: `scripts/ingest.py`
- Create: `tests/test_ingest.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_ingest.py`:
```python
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from scripts.ingest import ingest_directory


@pytest.mark.asyncio
async def test_ingest_processes_pdf_files(tmp_path):
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"fake pdf")

    with patch("scripts.ingest.DoclingParser") as MockParser, \
         patch("scripts.ingest.Preprocessor") as MockPreprocessor, \
         patch("scripts.ingest.EdgeQuakeClient") as MockClient:

        mock_parsed = MagicMock()
        MockParser.return_value.parse.return_value = mock_parsed

        mock_chunk = MagicMock()
        mock_chunk.text = "test text"
        mock_chunk.metadata = {}
        mock_chunk.hierarchy_path = "test > path"
        mock_chunk.cross_references = []
        MockPreprocessor.return_value.chunk.return_value = [mock_chunk]

        MockClient.return_value.ingest_document = AsyncMock(return_value={"status": "ok"})

        stats = await ingest_directory(tmp_path)

    assert stats["total"] == 1
    assert stats["success"] == 1
    assert stats["failed"] == 0


@pytest.mark.asyncio
async def test_ingest_skips_unsupported_files(tmp_path):
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("not supported")

    stats = await ingest_directory(tmp_path)

    assert stats["total"] == 0
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`scripts/ingest.py`:
```python
"""배치 인제스트 스크립트. 지정된 디렉토리의 문서를 파싱하여 EdgeQuake에 투입."""

import asyncio
import logging
from pathlib import Path

from src.config import Config
from src.parsing.hwp_converter import HwpConverter
from src.parsing.docling_parser import DoclingParser
from src.parsing.preprocessor import Preprocessor
from src.ingestion.edgequake_client import EdgeQuakeClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".html", ".htm", ".docx", ".doc", ".hwp", ".hwpx"}


async def ingest_directory(data_dir: Path) -> dict:
    converter = HwpConverter()
    parser = DoclingParser()
    preprocessor = Preprocessor()
    client = EdgeQuakeClient()

    stats = {"total": 0, "success": 0, "failed": 0, "failed_files": []}

    files = [f for f in data_dir.rglob("*") if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    stats["total"] = len(files)
    logger.info(f"Found {len(files)} documents in {data_dir}")

    for file_path in files:
        try:
            converted = converter.convert(file_path)
            parsed = parser.parse(converted)
            chunks = preprocessor.chunk(parsed)
            logger.info(f"  {file_path.name}: {len(chunks)} chunks")

            for chunk in chunks:
                await client.ingest_document(
                    text=chunk.text,
                    metadata={
                        **chunk.metadata,
                        "hierarchy_path": chunk.hierarchy_path,
                        "cross_references": chunk.cross_references,
                        "source_file": str(file_path.name),
                    },
                )

            stats["success"] += 1
            logger.info(f"  [OK] {file_path.name}")

        except Exception as e:
            stats["failed"] += 1
            stats["failed_files"].append(str(file_path))
            logger.error(f"  [FAIL] {file_path.name}: {e}")

    return stats


def main():
    config = Config()
    data_dir = config.data_dir

    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return

    stats = asyncio.run(ingest_directory(data_dir))
    logger.info(
        f"Ingestion complete: {stats['success']}/{stats['total']} succeeded, "
        f"{stats['failed']} failed"
    )
    if stats["failed_files"]:
        logger.warning(f"Failed files: {stats['failed_files']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add scripts/ingest.py tests/test_ingest.py
git commit -m "feat: 배치 인제스트 스크립트 구현"
```

---

## Task 15: CLI 질의 스크립트 구현

**Files:**
- Create: `scripts/query.py`

- [ ] **Step 1: 구현**

`scripts/query.py`:
```python
"""CLI 질의 스크립트. LangGraph 워크플로우를 통해 질의하고 구조화된 응답을 출력."""

import asyncio
import sys
import json

from src.orchestration.graph import build_graph, GraphState


async def run_query(query: str) -> None:
    graph = build_graph()

    initial_state: GraphState = {
        "query": query,
        "rewritten_query": "",
        "mode": "hybrid",
        "search_results": [],
        "crag_result": None,
        "answer": None,
        "retry_count": 0,
    }

    result = await graph.ainvoke(initial_state)

    if result.get("answer"):
        print(json.dumps(result["answer"].model_dump(), ensure_ascii=False, indent=2))
    else:
        print("응답을 생성하지 못했습니다.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.query '질의 내용'")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    asyncio.run(run_query(query))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 커밋**

```bash
git add scripts/query.py
git commit -m "feat: CLI 질의 스크립트 구현"
```

---

## Task 16: 전체 테스트 실행 및 통합 확인

- [ ] **Step 1: 전체 테스트 실행**

Run: `cd /Users/sboh/Desktop/dev/rag_for_accounting && uv run pytest tests/ -v --tb=short`
Expected: All tests passed

- [ ] **Step 2: 테스트 실패 시 수정 후 재실행**

실패한 테스트가 있으면 원인을 파악하고 수정한다.

- [ ] **Step 3: 최종 커밋**

```bash
git add -A
git commit -m "test: 전체 테스트 통과 확인"
```

---

## 파일럿 테스트 (Task 16 이후)

> 전체 구현 후 소규모 파일럿으로 검증:
> 1. 회계기준서 PDF 5개를 `data/` 디렉토리에 배치
> 2. `docker compose up -d`로 EdgeQuake 실행
> 3. `uv run python scripts/ingest.py`로 인제스트
> 4. `uv run python scripts/query.py "사용권자산 감가상각 방법은?"`으로 질의 테스트
> 5. 응답 품질과 인용 정확도 확인
> 6. EdgeQuake 그래프 시각화 UI에서 엔티티/관계 구조 확인
