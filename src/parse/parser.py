"""Docling을 이용해서 PDF -> Markdown으로 변환"""
import html
from pathlib import Path
from src.parse.parser_dtos import ParsedDocument
from docling.document_converter import DocumentConverter


class DoclingParser:
    def __init__(
        self,
        overlap_threshold: float | None = None,
        containment_threshold: float | None = None,
        converter: DocumentConverter | None = None,
    ) -> None:
        self._converter = converter
        self._overlap_threshold = overlap_threshold
        self._containment_threshold = containment_threshold

    def _get_converter(self) -> DocumentConverter:
        if self._converter is None:
            if self._overlap_threshold is not None or self._containment_threshold is not None:
                from src.parse.layout_config import create_converter
                self._converter = create_converter(
                    overlap_threshold=self._overlap_threshold or 0.15,
                    containment_threshold=self._containment_threshold or 0.15,
                )
            else:
                self._converter = DocumentConverter()
        return self._converter

    def parse(self, file_path: Path | str) -> ParsedDocument:
        file_path = Path(file_path)
        converter = self._get_converter()
        result = converter.convert(str(file_path))
        doc = result.document

        markdown_text = html.unescape(doc.export_to_markdown())

        tables = []
        for table in doc.tables:
            df = table.export_to_dataframe()
            values = df.values
            rows = values.tolist() if hasattr(values, "tolist") else list(values)
            tables.append({
                "headers": list(df.columns),
                "rows": rows,
            })

        return ParsedDocument(
            title=file_path.stem,
            text=markdown_text,
            tables=tables,
            metadata={"source_path": str(file_path)},
        )

    def table_to_text(self, table: dict) -> str:
        lines = []
        headers = table["headers"]
        for row in table["rows"]:
            pairs = [f"{h}: {v}" for h, v in zip(headers, row)]
            lines.append(", ".join(pairs))
        return "\n".join(lines)
