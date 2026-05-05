from datetime import timezone, timedelta

# 파이프라인 전역 설정값
MAX_REWRITE_COUNT: int = 3          # FUNC-004: 질의 재작성 최대 반복 횟수
TOP_K_RETRIEVAL: int = 10           # FUNC-005: 1차 검색 반환 청크 수
RERANK_THRESHOLD: float = 0.5       # FUNC-006: 재정렬 후 필터링 임계값
VECTOR_COLLECTION_NAME: str = "rag_for_accounting"  # FUNC-003: pgvector 컬렉션명
OPENAI_MODEL: str = "gpt-5.4-mini"   # FUNC-007, 008, 009: LLM 모델 식별자

# 하이브리드 검색 가중치 및 배치 설정
DENSE_WEIGHT: float = 0.6      # 벡터 검색 가중치
SPARSE_WEIGHT: float = 0.4     # 그래프 검색 가중치
BATCH_SIZE: int = 100          # 인덱싱 배치 크기

# 시간대(에러 로그 기록 시 한국 표준시(UTC+9)를 기준으로 하기 위함)
KST = timezone(timedelta(hours=9))