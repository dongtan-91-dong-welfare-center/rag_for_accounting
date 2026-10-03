# 파이프라인 데이터 형식 예시 (Examples)

본 디렉터리는 시스템의 데이터 파이프라인(문서 파싱 → 온톨로지 지식 그래프 구성 → 벡터 및 형태소 청킹)에서 사용되는 데이터 구조와 형식을 안내하기 위한 **최소 설계 샘플**을 제공합니다.

## 1. 법적 고지 및 데이터 사용 정책 (BYO)

- **출처 고지**: 본 예시에 포함된 일반기업회계기준(K-GAAP) 발췌 문단은 한국회계기준원(KASB)이 공표한 회계기준서에 기초합니다.
- **비영리 및 교육적 목적**: 본 예시는 시스템의 데이터 스키마 및 입출력 규격을 설명하기 위한 교육·연구 목적으로만 제공됩니다.
- **라이선스 적용 예외**: 저장소의 루트 라이선스(MIT License)는 본 예시 데이터에 포함된 회계기준 원문 발췌 내용에는 적용되지 않습니다.
- **전체 데이터 구성**: 원문 전체 PDF 및 전체 파싱 데이터는 저장소에 포함되어 있지 않으므로 [data/raw_data/README.md](../data/raw_data/README.md) 안내에 따라 직접 준비(Bring Your Own)해야 합니다.

## 2. 디렉터리 구성

- [`parsed_md/`](./parsed_md/): 원본 PDF로부터 구조화된 파싱 마크다운 발췌 샘플 ([sample_kgaap_ch21_excerpt.md](./parsed_md/sample_kgaap_ch21_excerpt.md))
- [`ontology/`](./ontology/): 기준서의 계층 구조(장-절-조항)를 표현하는 온톨로지 그래프 JSON 샘플 ([sample_ontology_graph.json](./ontology/sample_ontology_graph.json))
- [`chunks/`](./chunks/): Dense 임베딩 및 형태소 Sparse 검색을 위해 분할된 청크 데이터 JSON 샘플 ([sample_chunks.json](./chunks/sample_chunks.json))
