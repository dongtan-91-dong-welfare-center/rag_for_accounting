"""
Docling을 이용한 PDF → Markdown 변환 모듈

전체 흐름 요약:
    1. 사용자가 PDF 파일 경로를 넘겨줌
    2. Docling의 DocumentConverter가 PDF를 분석하여 텍스트와 표를 추출
    3. 추출된 결과를 ParsedDocument 객체에 담아서 반환

Docling이란?
    - IBM이 만든 오픈소스 문서 변환 라이브러리입니다.
    - PDF, DOCX 등의 문서를 읽어서 텍스트, 표, 이미지 등을 구조적으로 추출합니다.
    - 내부적으로 OCR(광학 문자 인식)과 레이아웃 분석 AI 모델을 사용합니다.

이 모듈의 역할:
    - Docling을 감싸서(wrapping) 우리 프로젝트에 맞는 인터페이스를 제공합니다.
    - PDF에서 마크다운 텍스트와 표 데이터를 추출하여 ParsedDocument로 반환합니다.
"""
import html
from pathlib import Path
from src.parse.parser_dtos import ParsedDocument
from docling.document_converter import DocumentConverter


class DoclingParser:
    """
    PDF 파일을 마크다운 텍스트로 변환하는 파서(Parser) 클래스.

    사용 예시:
        parser = DoclingParser()
        result = parser.parse("회계보고서.pdf")
        print(result.text)    # 마크다운 형식의 본문
        print(result.tables)  # 추출된 표 목록
    """

    def __init__(
        self,
        overlap_threshold: float | None = None,
        containment_threshold: float | None = None,
        converter: DocumentConverter | None = None,
    ) -> None:
        """
        DoclingParser 초기화.

        Args:
            overlap_threshold:
                레이아웃 분석 시 클러스터(텍스트 블록) 겹침 판단 기준값.
                None이면 Docling 기본값(0.8)을 사용하고,
                값을 지정하면 커스텀 레이아웃 후처리가 적용됩니다.
                (회계 문서처럼 빽빽한 레이아웃에서는 0.15 정도가 적합)

            containment_threshold:
                한 클러스터가 다른 클러스터에 포함되는 비율의 기준값.
                overlap_threshold와 같은 맥락으로 사용됩니다.

            converter:
                이미 만들어진 DocumentConverter 객체를 직접 주입할 수 있습니다.
                테스트 시 미리 설정된 converter를 넣거나,
                여러 파서가 같은 converter를 공유할 때 유용합니다.
                None이면 내부에서 자동으로 생성합니다.
        """
        # 인스턴스 변수에 저장 (앞에 _가 붙으면 "내부용"이라는 관례적 표시)
        self._converter = converter
        self._overlap_threshold = overlap_threshold
        self._containment_threshold = containment_threshold

    def _get_converter(self) -> DocumentConverter:
        """
        DocumentConverter 인스턴스를 가져옵니다. (지연 초기화 패턴)

        "지연 초기화(Lazy Initialization)"란?
            - 객체를 처음 만들 때가 아니라, 실제로 필요한 시점에 생성하는 패턴입니다.
            - DocumentConverter는 AI 모델을 로드하기 때문에 생성 비용이 큽니다.
            - 그래서 parse()가 처음 호출될 때 한 번만 만들고, 이후에는 재사용합니다.

        동작 방식:
            1. self._converter가 이미 있으면 → 그대로 반환 (재생성 안 함)
            2. overlap/containment threshold가 지정되어 있으면
               → 커스텀 설정이 적용된 converter를 생성 (layout_config 모듈 사용)
            3. 아무 설정도 없으면 → Docling 기본 converter를 생성
        """
        if self._converter is None:
            if self._overlap_threshold is not None or self._containment_threshold is not None:
                # 커스텀 임계값이 지정된 경우: 레이아웃 후처리를 패치한 converter 생성
                # (layout_config.py의 create_converter 참고)
                from src.parse.layout_config import create_converter
                self._converter = create_converter(
                    overlap_threshold=self._overlap_threshold or 0.15,
                    containment_threshold=self._containment_threshold or 0.15,
                )
            else:
                # 기본 설정: Docling이 제공하는 기본 DocumentConverter 사용
                self._converter = DocumentConverter()
        return self._converter

    def parse(self, file_path: Path | str) -> ParsedDocument:
        """
        PDF 파일을 파싱하여 ParsedDocument를 반환합니다.

        처리 단계:
            1단계: 파일 경로를 Path 객체로 변환 (문자열이 들어와도 안전하게 처리)
            2단계: DocumentConverter로 PDF를 분석 (텍스트 추출 + 레이아웃 분석)
            3단계: 분석 결과에서 마크다운 텍스트를 추출
            4단계: 분석 결과에서 표(table) 데이터를 추출
            5단계: 모든 결과를 ParsedDocument 객체에 담아서 반환

        Args:
            file_path: 파싱할 PDF 파일의 경로 (예: "data/회계보고서.pdf")

        Returns:
            ParsedDocument: 파싱된 문서 정보 (제목, 본문, 표, 메타데이터)
        """
        # ── 1단계: 경로 정규화 ──
        # Path 객체로 변환하면 OS에 맞는 경로 처리가 자동으로 됩니다.
        file_path = Path(file_path)

        # ── 2단계: PDF 분석 ──
        # converter.convert()가 PDF를 읽고 AI 모델로 레이아웃을 분석합니다.
        # result.document에 분석 결과(텍스트, 표, 구조 정보)가 담깁니다.
        converter = self._get_converter()
        result = converter.convert(str(file_path))
        doc = result.document

        # ── 3단계: 마크다운 텍스트 추출 ──
        # export_to_markdown()은 문서 내용을 마크다운 형식 문자열로 변환합니다.
        # html.unescape()는 HTML 엔티티를 원래 문자로 되돌립니다.
        #   예: "&amp;" → "&",  "&lt;" → "<",  "&#x27;" → "'"
        # Docling이 내부적으로 HTML 인코딩을 사용하는 경우가 있어서 이 처리가 필요합니다.
        markdown_text = html.unescape(doc.export_to_markdown())

        # ── 4단계: 표(Table) 추출 ──
        # doc.tables는 문서에서 감지된 모든 표의 리스트입니다.
        # 각 표를 pandas DataFrame으로 변환한 뒤,
        # {"headers": [열 이름들], "rows": [[행1 데이터], [행2 데이터], ...]} 형태로 저장합니다.
        tables = []
        for table in doc.tables:
            # export_to_dataframe()은 표를 pandas DataFrame으로 변환합니다.
            # DataFrame은 엑셀 시트와 비슷한 2차원 데이터 구조입니다.
            df = table.export_to_dataframe()

            # df.values는 DataFrame의 데이터 부분을 numpy 배열로 반환합니다.
            # .tolist()로 파이썬 기본 리스트로 변환합니다. (JSON 직렬화 등에 필요)
            values = df.values
            rows = values.tolist() if hasattr(values, "tolist") else list(values)

            tables.append({
                "headers": list(df.columns),  # 열 이름(헤더) 리스트
                "rows": rows,                 # 각 행의 데이터 리스트
            })

        # ── 5단계: 결과 반환 ──
        # 추출한 모든 정보를 ParsedDocument에 담아서 반환합니다.
        return ParsedDocument(
            title=file_path.stem,  # .stem은 확장자를 뺀 파일 이름 (예: "회계보고서")
            text=markdown_text,
            tables=tables,
            metadata={"source_path": str(file_path)},  # 원본 파일 경로를 메타데이터로 저장
        )

    def table_to_text(self, table: dict) -> str:
        """
        표(table) 딕셔너리를 사람이 읽기 쉬운 텍스트로 변환합니다.

        표를 텍스트로 변환하는 이유:
            - LLM(대규모 언어 모델)에게 표 내용을 전달할 때,
              JSON이나 HTML보다 "키: 값" 형태의 텍스트가 더 이해하기 쉽습니다.
            - 검색(RAG)에서도 텍스트 형태가 유사도 계산에 더 적합합니다.

        변환 예시:
            입력: {"headers": ["과목", "금액"], "rows": [["매출", "1000"], ["비용", "500"]]}
            출력:
                과목: 매출, 금액: 1000
                과목: 비용, 금액: 500

        Args:
            table: {"headers": [...], "rows": [[...], ...]} 형태의 딕셔너리

        Returns:
            각 행을 "헤더: 값" 쌍으로 표현한 텍스트 (줄바꿈으로 구분)
        """
        lines = []
        headers = table["headers"]

        for row in table["rows"]:
            # zip(headers, row)는 헤더와 행 데이터를 하나씩 짝지어 줍니다.
            # 예: zip(["과목", "금액"], ["매출", "1000"]) → [("과목", "매출"), ("금액", "1000")]
            pairs = [f"{h}: {v}" for h, v in zip(headers, row)]

            # 짝지은 결과를 쉼표로 이어붙입니다.
            # 예: "과목: 매출, 금액: 1000"
            lines.append(", ".join(pairs))

        # 모든 행을 줄바꿈으로 이어붙여서 반환합니다.
        return "\n".join(lines)
