# 문서 온톨로지·청킹 가이드

본 문서는 회계 기준서를 Standard, Section, Subsection 계층 노드와 조항 참조 관계로 구조화하고, 검색 적재를 위해 청크로 분할하는 온톨로지 파이프라인의 설계 및 동작 규칙을 설명합니다. 기본적으로 본문이 존재하는 노드 단위로 청킹하며, `--clause-level` 옵션을 활성화하면 조항 헤더 경계를 우선 적용합니다.

## 1. 목적

온톨로지는 회계기준 원문의 계층과 조항 단위를 검색 시스템이 잃지 않도록 보존하는 중간 표현이다. 단순 텍스트 청크만 만들면 “어느 장·절·조항에서 온 근거인지”를 추적하기 어렵기 때문에, 먼저 구조를 만들고 그 구조에서 청크를 만든다.

## 2. 입력과 출력

| 단계 | 입력 | 출력 | 코드 |
|---|---|---|---|
| Markdown 파싱 | 기준서 Markdown | `OntologyGraph` | `src/ingest/ontology/md_parser.py` |
| 그래프 빌드 | Markdown path + 기준서 ID/type | 노드·엣지 포함 graph | `src/ingest/ontology/builder.py` |
| 청킹 | `OntologyGraph` | `list[RetrievedChunk]` | `src/ingest/ontology/chunker.py` |
| 적재 | 청크 리스트 | pgvector `chunks` rows | `src/db/vector_store.py` |

PDF에서 시작하는 경우 `src/main.py ingest --pdf ...`가 Docling 파싱 후 Markdown을 만들고, 같은 온톨로지 경로로 들어간다.

## 3. 노드 단위

현행 그래프의 주요 노드 타입은 다음과 같다.

| 노드 | 의미 | 청킹 여부 |
|---|---|---|
| `Standard` | 기준서/장 전체 | content가 없으면 제외 |
| `Section` | 절 또는 상위 구획 | 직속 본문이 있으면 청킹 |
| `Subsection` | 조항·세부 문단 묶음 | 주 청킹 대상 |

`chunk_graph()`는 `(node.content or "").strip()`이 있는 노드만 청킹한다. content가 없는 구조 노드는 검색 청크가 되지 않는다.

## 4. 청킹 기본 규칙

기본 청킹은 온톨로지 노드 단위다.

1. content가 있는 노드를 고른다.
2. `CHUNK_MAX_TOKENS=2048` 이하이면 그대로 하나의 청크로 만든다.
3. 초과하면 줄(문단) → 문장 → 문자 순서로 경계를 낮춰 분할한다.
4. 분할 조각은 모두 같은 `metadata.ontology_node_id`를 유지한다.

이 규칙은 노드와 청크의 추적 가능성을 우선한다. 거대한 실무지침·결론도출근거 블록은 토큰 상한 때문에 분할될 수 있다.

## 5. 조항 경계 옵션

`uv run python -m src.main ingest --clause-level`을 사용하면 H4 조항 헤더를 먼저 경계로 삼는다.

경계 정규식은 다음 형태를 잡는다.

```text
#### 21.8
#### 2.6.5
#### 21.5의2
```

H5 이하 하위 헤더는 별도 경계가 아니라 상위 조항 조각에 귀속된다. 조항 헤더가 없는 content는 기본 토큰 분할 규칙으로 처리한다.

## 6. `chunk_id` 규칙

`chunk_id`는 재실행해도 같은 값이 나오도록 결정적이어야 한다.

| 상황 | `chunk_id` |
|---|---|
| 분할 없음 | `node.id` |
| 분할 있음 | `node.id-0`, `node.id-1`, ... |

인덱싱은 `ON CONFLICT(chunk_id) DO UPDATE`를 사용한다. 따라서 `chunk_id`가 흔들리면 같은 문서를 재적재할 때 중복 청크가 생긴다.

## 7. 메타데이터 전파

청크 메타데이터는 검색 필터와 UI 표시의 기준이다.

| 필드 | 값 |
|---|---|
| `ontology_node_id` | 원본 노드 ID |
| `node_type` | Standard/Section/Subsection 등 |
| `standard_type` | Standard 노드의 `standard_type` |
| `chapter` | Standard 노드의 `chapter` |
| `source_path` | 입력 파일 경로. 있으면 extra 필드로 저장 |
| `page_start`, `page_end` | 페이지 백필 이후 API/UI에서 PDF 위치 표시용으로 사용 |

`standard_type`과 `chapter`는 Standard 노드 기준으로 모든 청크에 전파한다. 하위 노드 자체에 값이 비어 있을 수 있기 때문이다.

## 8. 페이지 매핑과 PDF 뷰어

PDF 뷰어는 `document_id`, `page_start`, `page_end`가 있어야 의미 있게 동작한다.

| 기능 | 코드 |
|---|---|
| PDF 경로 해석 | `src/ingest/parse/page_map.py`의 `resolve_pdf_path()` |
| API PDF 서빙 | `GET /documents/{document_id}/pdf` |
| 페이지 필드 API 노출 | `src/api/schemas.py`의 `ClauseOut`, `CitationOut` |
| 페이지 백필 스크립트 | `scripts/backfill_page_map.py` |

페이지 정보가 없으면 API는 조항과 인용은 반환하지만, 프론트는 PDF 보기 버튼을 숨기는 방식으로 처리한다.

## 9. 오류와 실패 정책

| 상황 | 동작 |
|---|---|
| content 노드가 없음 | 빈 청크 리스트 반환 |
| document_id를 결정할 Standard 노드가 없음 | `OntologyParsingError(OT-103)` |
| 토큰 상한 초과 | 청킹 단계에서 최대한 분할 |
| 임베딩 한도 초과 잔여 | 인덱싱 단계에서 `IX-201`로 스킵 |
| 배치 적재 실패 | 실패 배치만 skipped로 기록하고 다음 배치 진행 |

## 10. 문서화 원칙

2026-07-11 회의의 “온톨로지 규칙 문서화” 요구사항은 다음 기준으로 관리한다.

1. 코드가 이미 강제하는 규칙은 이 문서에 현재형으로 쓴다.
2. 회의에서 나온 개선 아이디어는 현행 규칙과 분리해 쓴다.
3. 청킹 기준을 바꾸면 `tests/unit/ingest/ontology/test_chunker.py`와 벤치마크 검색 지표를 같이 확인한다.
4. 원문 PDF와 Markdown 정본 규칙은 [document_parsing_guide.md](document_parsing_guide.md)를 따른다.
