# 회계 기준서 RAG 시스템

이 프로젝트는 회계 기준서에 대한 질의응답을 위해 설계된 RAG(Retrieval-Augmented Generation) 시스템입니다. LangGraph를 활용한 에이전트 워크플로우를 통해 질문 분석, 문서 검색, 답변 생성 과정을 자동화합니다.

## 🚀 주요 기능

- **에이전트 워크플로우**: 질문 재작성 → 문서 검색 → 품질 평가 → 답변 생성의 4단계 파이프라인
- **하이브리드 검색**: Dense(의미) 및 Sparse(키워드) 벡터를 결합한 고성능 검색
- **고급 RAG 기법**: 컨텍스트얼 리트리벌, 리랭킹 등 적용
- **구조화된 답변**: Pydantic을 활용한 정제된 답변 출력

## 🛠️ 설치 및 실행

### 1. 환경 설정 및 의존성 설정

프로젝트 루트 디렉토리에서 가상 환경을 생성하고 활성화합니다.
uv 사용을 권장합니다.

```bash
uv sync
```

### 3. 실행

에이전트 워크플로우를 실행합니다.

<!-- 현재 구현되어 있지 않습니다. -->
```bash
uv run python src/main.py
```

## 📂 프로젝트 구조

```
src/
├── agent/              # 에이전트 로직 및 워크플로우
│   ├── nodes/          # 워크플로우의 각 노드 (evaluate, generate, rewrite)
│   │   ├── evaluate.py # 품질 평가 노드
│   │   ├── generate.py # 답변 생성 노드
│   │   └── rewrite.py  # 질문 재작성 노드
│   ├── prompts.py      # LLM 프롬프트 정의
│   └── workflow.py     # LangGraph 워크플로우 오케스트레이션
├── db/                 # 벡터 데이터베이스 연동
│   └── vector_store.py # 벡터 스토어 구현
├── ingestion/          # 데이터 수집 및 처리
│   ├── embedder.py     # 임베딩 생성 (Dense/Sparse)
│   └── parser.py       # 문서 파싱 및 청킹
├── models/             # 데이터 모델 및 스키마
│   ├── schemas.py      # Pydantic 스키마 정의
│   └── state.py        # LangGraph State 정의
├── parse/              # 추가 파싱 및 클러스터링
│   ├── cluster_merge.py # 클러스터 병합 로직
│   ├── layout_config.py # 레이아웃 설정
│   ├── parser.py       # 파서 구현
│   └── parser_dtos.py  # 파서 DTO 정의
├── retrieval/          # 검색 및 리랭킹
│   ├── reranker.py     # 리랭킹 로직
│   └── searcher.py     # 검색 구현
└── utils/              # 유틸리티 및 설정
    ├── config.py       # 설정 관리
    └── logger.py       # 로깅 유틸리티
```

## 📖 문서 학습

RAG 기술에 대한 자세한 학습 자료는 `docs/rag_study.md` 파일에 정리되어 있습니다.

## 📝 TODO

현재 진행 중인 작업은 `task-board.html` 파일에 정리되어 있습니다.


## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.