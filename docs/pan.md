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
│   │   ├── answer_generator.py             # LLM 응답 생성
│   │   └── schemas.py                      # PydanticAI 응답 스키마
│   └── orchestration/
│       ├── __init__.py
│       └── graph.py                        # LangGraph 워크플로우 정의
├── tests/
│   ├── __init__.py
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
│   │   └── test_crag_gate.py
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── test_schemas.py
│   │   └── test_answer_generator.py
│   └── orchestration/
│       ├── __init__.py
│       └── test_graph.py
└── scripts/
    ├── ingest.py                           # 배치 인제스트 스크립트
    └── query.py                            # CLI 질의 스크립트
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

- [ ] **Step 1: pyproject.toml에 의존성 추가**

```toml
[project]
name = "rag-for-accounting"
version = "0.1.0"
description = "GraphRAG system for K-IFRS accounting standards"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "docling>=2.0.0",
    "langchain-openai>=0.3.0",
    "langgraph>=0.4.0",
    "pydantic-ai>=0.1.0",
    "httpx>=0.28.0",
    "python-dotenv>=1.0.0",
    "pyhwp>=0.6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.25.0",
    "pytest-cov>=6.0.0",
]
```

- [ ] **Step 2: 의존성 설치**

Run: `cd /Users/sboh/Desktop/dev/rag_for_accounting && uv sync --all-extras`
Expected: 의존성 설치 성공

- [ ] **Step 3: docker-compose.yml 작성**

EdgeQuake의 공식 Docker Compose를 기반으로 작성. EdgeQuake GitHub 저장소(https://github.com/raphaelmansuy/edgequake)의 docker-compose.yml을 참조하여 PostgreSQL(AGE + pgvector) + EdgeQuake 서비스를 정의한다.

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

> **참고:** EdgeQuake의 실제 Docker 이미지 이름과 환경변수는 공식 문서를 확인하여 조정 필요. 위는 예상 구조이며, `docker compose up` 전에 EdgeQuake 레포를 클론하여 정확한 설정을 확인한다.

- [ ] **Step 4: .env.example 작성**

```env
OPENAI_API_KEY=sk-your-key-here
POSTGRES_PASSWORD=edgequake_dev
EDGEQUAKE_URL=http://localhost:8080
```

- [ ] **Step 5: config.py 작성 + 테스트**

`src/config.py`:
```python
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    EDGEQUAKE_URL: str = os.getenv("EDGEQUAKE_URL", "http://localhost:8080")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "edgequake_dev")
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))
    CHUNK_SIZE_TARGET: int = 750  # tokens, target 500-1000
    CHUNK_OVERLAP_SENTENCES: int = 1
```

`tests/test_config.py`:
```python
from src.config import Config


def test_config_defaults():
    config = Config()
    assert config.EDGEQUAKE_URL == "http://localhost:8080"
    assert config.CHUNK_SIZE_TARGET == 750
    assert config.CHUNK_OVERLAP_SENTENCES == 1
```

- [ ] **Step 6: 테스트 실행**

Run: `cd /Users/sboh/Desktop/dev/rag_for_accounting && uv run pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 7: Docker 환경 확인**

Run: `cd /Users/sboh/Desktop/dev/rag_for_accounting && docker compose up -d`
Expected: postgres, edgequake 컨테이너 정상 실행
Run: `docker compose ps`
Expected: 두 서비스 모두 healthy/running 상태

> **참고:** EdgeQuake Docker 이미지가 없거나 설정이 다르면 이 단계에서 EdgeQuake 레포를 클론하여 직접 빌드해야 할 수 있다. 이 경우 `git clone https://github.com/raphaelmansuy/edgequake.git` 후 해당 레포의 docker-compose.yml을 참조한다.

- [ ] **Step 8: 커밋**

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
        expected_pdf.write_bytes(b"fake pdf")  # simulate conversion output
        result = converter.convert(hwp_file)

    assert result == expected_pdf
    assert result.suffix == ".pdf"


def test_skip_non_hwp_files(tmp_path):
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    converter = HwpConverter(output_dir=tmp_path)
    result = converter.convert(pdf_file)

    assert result == pdf_file  # 변환 없이 그대로 반환


def test_convert_failure_raises(tmp_path):
    hwp_file = tmp_path / "test.hwp"
    hwp_file.write_bytes(b"fake hwp content")

    converter = HwpConverter(output_dir=tmp_path)
    with patch("src.parsing.hwp_converter.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        try:
            converter.convert(hwp_file)
            assert False, "Should have raised"
        except RuntimeError:
            pass
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


def test_parse_returns_parsed_document():
    parser = DoclingParser()

    mock_doc = MagicMock()
    mock_doc.export_to_markdown.return_value = "# 제1116호\n## 제1장 목적\n문단 1 내용"
    mock_doc.tables = []

    with patch("src.parsing.docling_parser.DocumentConverter") as MockConverter:
        instance = MockConverter.return_value
        mock_result = MagicMock()
        mock_result.document = mock_doc
        instance.convert.return_value = mock_result

        result = parser.parse(Path("test.pdf"))

    assert isinstance(result, ParsedDocument)
    assert result.markdown is not None
    assert len(result.markdown) > 0


def test_parsed_document_has_required_fields():
    doc = ParsedDocument(
        source_path=Path("test.pdf"),
        markdown="# Test",
        tables=[],
        metadata={"기준서번호": "1116"},
    )
    assert doc.source_path == Path("test.pdf")
    assert doc.metadata["기준서번호"] == "1116"
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
    return ParsedDocument(
        source_path=Path("test.pdf"),
        markdown=markdown,
        tables=[],
    )


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
            cross_refs = self.extract_cross_references(section["content"])
            chunk = Chunk(
                text=section["content"],
                hierarchy_path=section["path"],
                metadata={**metadata},
                cross_references=cross_refs,
            )
            chunks.append(chunk)

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
                            "path": " > ".join(current_path_parts)
                            if current_path_parts
                            else "",
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
                    "path": " > ".join(current_path_parts)
                    if current_path_parts
                    else "",
                    "content": "\n".join(current_content_lines),
                }
            )

        return sections
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/parsing/test_preprocessor.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add src/parsing/preprocessor.py tests/parsing/test_preprocessor.py
git commit -m "feat: 전처리기 구현 (구조 기반 청킹, 상호참조 추출)"
```

---

## Task 5: EdgeQuake REST API 클라이언트 구현

**Files:**
- Create: `src/ingestion/__init__.py`
- Create: `src/ingestion/edgequake_client.py`
- Create: `tests/ingestion/__init__.py`
- Create: `tests/ingestion/test_edgequake_client.py`

- [ ] **Step 1: 테스트 작성**

`tests/ingestion/test_edgequake_client.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.ingestion.edgequake_client import EdgeQuakeClient
from src.parsing.preprocessor import Chunk


@pytest.mark.asyncio
async def test_ingest_chunk_sends_post_request():
    client = EdgeQuakeClient(base_url="http://localhost:8080")
    chunk = Chunk(
        text="사용권자산의 감가상각",
        hierarchy_path="제1116호 > 제5장",
        metadata={"기준서번호": "1116"},
        cross_references=[{"standard": "1028", "paragraph": "15"}],
    )

    with patch("src.ingestion.edgequake_client.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_instance.post.return_value = MagicMock(status_code=200, json=lambda: {"status": "ok"})

        result = await client.ingest_document(chunk.text, chunk.metadata)

    mock_instance.post.assert_called_once()
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_query_sends_get_request():
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
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/ingestion/test_edgequake_client.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`src/ingestion/edgequake_client.py`:
```python
import httpx


class EdgeQuakeClient:
    """EdgeQuake REST API 클라이언트."""

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

    async def query(
        self, query: str, mode: str = "hybrid", top_k: int = 10
    ) -> dict:
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
                response = await client.get(
                    f"{self.base_url}/api/health", timeout=5.0
                )
                return response.status_code == 200
        except httpx.RequestError:
            return False
```

> **참고:** EdgeQuake의 실제 API 엔드포인트와 페이로드 형식은 공식 문서/소스코드를 확인하여 조정 필요. 위는 LightRAG 구현들의 일반적인 패턴 기반이며, `docker compose up` 후 Swagger UI(`http://localhost:8080/swagger-ui`)에서 정확한 API를 확인한다.

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/ingestion/test_edgequake_client.py -v`
Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add src/ingestion/__init__.py src/ingestion/edgequake_client.py tests/ingestion/__init__.py tests/ingestion/test_edgequake_client.py
git commit -m "feat: EdgeQuake REST API 클라이언트 구현"
```

---

## Task 6: PydanticAI 응답 스키마 정의

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


def test_rag_response_requires_citations():
    with pytest.raises(ValidationError):
        RAGResponse(answer="답변", citations=[], related_standards=[], confidence=0.9)


def test_valid_rag_response():
    response = RAGResponse(
        answer="사용권자산은 정액법으로 감가상각합니다.",
        citations=[
            Citation(기준서="1116", 문단="31", 내용="사용권자산의 감가상각...")
        ],
        related_standards=["1028"],
        confidence=0.92,
    )
    assert len(response.citations) == 1
    assert response.confidence == 0.92
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

## Task 7: Query Rewriter 구현

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


@pytest.mark.asyncio
async def test_rewrite_transforms_natural_language():
    rewriter = QueryRewriter()

    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(message=AsyncMock(content="K-IFRS 1116 사용권자산 감가상각 방법"))
    ]

    with patch("src.retrieval.query_rewriter.AsyncOpenAI") as MockOpenAI:
        instance = MockOpenAI.return_value
        instance.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await rewriter.rewrite("리스 계약에서 감가상각 어떻게 해?")

    assert isinstance(result, str)
    assert len(result) > 0
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
- 회계 전문 용어 사용 (예: "감가상각" → "감가상각", "빌려쓰는 자산" → "사용권자산")
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
            messages=[
                {"role": "user", "content": REWRITE_PROMPT.format(query=query)}
            ],
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

## Task 8: Query Router 구현

**Files:**
- Create: `src/retrieval/query_router.py`
- Create: `tests/retrieval/test_query_router.py`

- [ ] **Step 1: 테스트 작성**

`tests/retrieval/test_query_router.py`:
```python
from src.retrieval.query_router import QueryRouter


def test_route_specific_standard_to_local():
    router = QueryRouter()
    mode = router.route("K-IFRS 1116 문단 31 사용권자산 감가상각")
    assert mode == "local"


def test_route_broad_topic_to_global():
    router = QueryRouter()
    mode = router.route("리스 관련 기준서 전체 개요")
    assert mode == "global"


def test_route_complex_query_to_hybrid():
    router = QueryRouter()
    mode = router.route("사용권자산 감가상각과 관련 예외 조항")
    assert mode == "hybrid"
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
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add src/retrieval/query_router.py tests/retrieval/test_query_router.py
git commit -m "feat: Query Router 구현 (규칙 기반 모드 선택)"
```

---

## Task 9: CRAG 품질 게이트 구현

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

    async def evaluate(
        self, query: str, search_results: list[dict]
    ) -> CRAGResult:
        results_text = "\n---\n".join(
            r.get("content", str(r)) for r in search_results
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": CRAG_PROMPT.format(
                        query=query, search_results=results_text
                    ),
                }
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
Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add src/retrieval/crag_gate.py tests/retrieval/test_crag_gate.py
git commit -m "feat: CRAG 품질 게이트 구현"
```

---

## Task 10: 응답 생성기 구현

**Files:**
- Create: `src/generation/answer_generator.py`
- Create: `tests/generation/test_answer_generator.py`

- [ ] **Step 1: 테스트 작성**

`tests/generation/test_answer_generator.py`:
```python
import pytest
import json
from unittest.mock import AsyncMock, patch
from src.generation.answer_generator import AnswerGenerator
from src.generation.schemas import RAGResponse


@pytest.mark.asyncio
async def test_generate_returns_rag_response():
    generator = AnswerGenerator()

    mock_json = json.dumps(
        {
            "answer": "사용권자산은 정액법으로 감가상각합니다.",
            "citations": [
                {"기준서": "1116", "문단": "31", "내용": "사용권자산의 감가상각..."}
            ],
            "related_standards": ["1028"],
            "confidence": 0.92,
        }
    )

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(message=AsyncMock(content=mock_json))]

    with patch("src.generation.answer_generator.AsyncOpenAI") as MockOpenAI:
        instance = MockOpenAI.return_value
        instance.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await generator.generate(
            query="사용권자산 감가상각",
            context=[{"content": "K-IFRS 1116 문단 31..."}],
        )

    assert isinstance(result, RAGResponse)
    assert len(result.citations) >= 1
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/generation/test_answer_generator.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`src/generation/answer_generator.py`:
```python
import json

from openai import AsyncOpenAI

from src.generation.schemas import RAGResponse

ANSWER_PROMPT = """당신은 K-IFRS 회계기준서 전문가입니다.
주어진 검색 결과를 바탕으로 질문에 정확하게 답변하세요.

규칙:
1. 반드시 검색 결과에 있는 내용만 사용하세요
2. 기준서 번호와 문단 번호를 인용하세요
3. 관련 예외 조항이 있으면 반드시 언급하세요

질문: {query}

검색 결과:
{context}

응답을 다음 JSON 형식으로 출력하세요:
{{
    "answer": "답변 내용",
    "citations": [{{"기준서": "번호", "문단": "번호", "내용": "인용 내용"}}],
    "related_standards": ["관련 기준서 번호들"],
    "confidence": 0.0~1.0
}}

JSON 응답:"""


class AnswerGenerator:
    def __init__(self, model: str = "gpt-4o"):
        self.client = AsyncOpenAI()
        self.model = model

    async def generate(self, query: str, context: list[dict]) -> RAGResponse:
        context_text = "\n---\n".join(
            c.get("content", str(c)) for c in context
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": ANSWER_PROMPT.format(
                        query=query, context=context_text
                    ),
                }
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        return RAGResponse(**data)
```

- [ ] **Step 4: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/generation/test_answer_generator.py -v`
Expected: 1 passed

- [ ] **Step 5: 커밋**

```bash
git add src/generation/answer_generator.py tests/generation/test_answer_generator.py
git commit -m "feat: 응답 생성기 구현 (구조화 JSON 출력)"
```

---

## Task 11: LangGraph 오케스트레이션 워크플로우 구현

**Files:**
- Create: `src/orchestration/__init__.py`
- Create: `src/orchestration/graph.py`
- Create: `src/retrieval/edgequake_searcher.py`
- Create: `tests/orchestration/__init__.py`
- Create: `tests/orchestration/test_graph.py`

- [ ] **Step 1: EdgeQuake 검색 래퍼 작성**

`src/retrieval/edgequake_searcher.py`:
```python
from src.ingestion.edgequake_client import EdgeQuakeClient


class EdgeQuakeSearcher:
    """EdgeQuake 검색을 위한 래퍼. 모드별 검색 실행."""

    def __init__(self, client: EdgeQuakeClient | None = None):
        self.client = client or EdgeQuakeClient()

    async def search(
        self, query: str, mode: str = "hybrid", top_k: int = 10
    ) -> list[dict]:
        result = await self.client.query(query, mode=mode, top_k=top_k)
        return result.get("sources", [])
```

- [ ] **Step 2: 테스트 작성**

`tests/orchestration/test_graph.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.orchestration.graph import build_graph, GraphState


def test_build_graph_returns_compiled_graph():
    graph = build_graph()
    assert graph is not None


def test_graph_state_has_required_fields():
    state = GraphState(
        query="테스트 질문",
        rewritten_query="",
        mode="hybrid",
        search_results=[],
        crag_result=None,
        answer=None,
        retry_count=0,
    )
    assert state["query"] == "테스트 질문"
    assert state["retry_count"] == 0
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

Run: `uv run pytest tests/orchestration/test_graph.py -v`
Expected: FAIL

- [ ] **Step 4: 구현**

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
    results = await searcher.search(
        state["rewritten_query"], mode=state["mode"]
    )
    return {**state, "search_results": results}


async def evaluate_crag(state: GraphState) -> GraphState:
    gate = CRAGGate()
    result = await gate.evaluate(
        state["rewritten_query"], state["search_results"]
    )
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
    results = await searcher.search(
        state["rewritten_query"], mode=next_mode
    )
    return {
        **state,
        "mode": next_mode,
        "search_results": results,
        "retry_count": state["retry_count"] + 1,
    }


async def generate_answer(state: GraphState) -> GraphState:
    generator = AnswerGenerator()
    answer = await generator.generate(
        state["query"], state["search_results"]
    )
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

- [ ] **Step 5: 테스트 실행 — 성공 확인**

Run: `uv run pytest tests/orchestration/test_graph.py -v`
Expected: 2 passed

- [ ] **Step 6: 커밋**

```bash
git add src/retrieval/edgequake_searcher.py src/orchestration/__init__.py src/orchestration/graph.py tests/orchestration/__init__.py tests/orchestration/test_graph.py
git commit -m "feat: LangGraph 오케스트레이션 워크플로우 구현 (CRAG 루프 포함)"
```

---

## Task 12: 배치 인제스트 스크립트 구현

**Files:**
- Create: `scripts/ingest.py`

- [ ] **Step 1: 구현**

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
            # HWP 변환
            converted = converter.convert(file_path)

            # Docling 파싱
            parsed = parser.parse(converted)

            # 전처리 (청킹)
            chunks = preprocessor.chunk(parsed)
            logger.info(f"  {file_path.name}: {len(chunks)} chunks")

            # EdgeQuake 인제스트
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
    data_dir = config.DATA_DIR

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

- [ ] **Step 2: 커밋**

```bash
git add scripts/ingest.py
git commit -m "feat: 배치 인제스트 스크립트 구현"
```

---

## Task 13: CLI 질의 스크립트 구현

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

## Task 14: 전체 테스트 실행 및 통합 확인

- [ ] **Step 1: 전체 테스트 실행**

Run: `cd /Users/sboh/Desktop/dev/rag_for_accounting && uv run pytest tests/ -v --tb=short`
Expected: All tests passed

- [ ] **Step 2: 테스트 실패 시 수정 후 재실행**

실패한 테스트가 있으면 원인을 파악하고 수정한다.

- [ ] **Step 3: 최종 커밋**

```bash
git add -A
git commit -m "fix: 전체 테스트 통과 확인 및 수정"
```

---

## 파일럿 테스트 (Task 14 이후)

> 전체 구현 후 소규모 파일럿으로 검증:
> 1. 회계기준서 PDF 5개를 `data/` 디렉토리에 배치
> 2. `docker compose up -d`로 EdgeQuake 실행
> 3. `uv run python scripts/ingest.py`로 인제스트
> 4. `uv run python scripts/query.py "사용권자산 감가상각 방법은?"`으로 질의 테스트
> 5. 응답 품질과 인용 정확도 확인
