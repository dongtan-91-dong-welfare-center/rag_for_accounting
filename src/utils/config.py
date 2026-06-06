from datetime import timezone, timedelta

# 파이프라인 전역 설정값
MAX_REWRITE_COUNT: int = 3          # FUNC-004: CRAG 루프(평가 임계치 미달 재검색) 최대 반복 횟수
MAX_HIL_COUNT: int = 5              # 워크플로우: Human-in-the-Loop 재작성 요청 최대 반복 횟수 (CRAG 루프와 분리)
TOP_K_RETRIEVAL: int = 10           # FUNC-005: 1차 검색 반환 청크 수

# Reranking Configuration
USE_RERANKER: bool = False          # 리랭킹 모델 활성화 여부
RERANK_THRESHOLD: float = 0.5       # FUNC-006: 재정렬 후 필터링 임계값 (기본값: 중간 신뢰도)
RERANK_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # FUNC-006: Cross-Encoder 모델 식별자
VECTOR_COLLECTION_NAME: str = "rag_for_accounting"  # FUNC-003: pgvector 컬렉션명
OPENAI_MODEL: str = "gpt-5.4-mini"   # FUNC-007, 008, 009: LLM 모델 식별자

# 하이브리드 검색 가중치 및 배치 설정
# 회계 기준서는 정확한 용어·조항 번호 매칭이 중요하므로 Sparse 가중치를 높게 설정
DENSE_WEIGHT: float = 0.4      # Dense(벡터 의미 유사도) 검색 가중치
SPARSE_WEIGHT: float = 0.6     # Sparse(키워드 BM25 유사) 검색 가중치
BATCH_SIZE: int = 100          # 인덱싱 배치 크기

# 검색 타임아웃 (초) — pgvector 쿼리가 이 시간을 초과하면 SearchTimeoutError(SE-101) 발생
SEARCH_TIMEOUT_SECONDS: int = 5

# 임베딩 모델 설정
# !TODO: 인덱싱(FUNC-003)에서 사용한 모델과 차원 수를 반드시 동일하게 맞출 것
EMBEDDING_MODEL: str = "text-embedding-3-small"
EMBEDDING_DIM: int = 1536   # OpenAI 임베딩 모델의 벡터 차원 수

# gpt-5.4-mini 컨텍스트 윈도우(128K) 중 컨텍스트 입력에 할당할 안전 한도
# o200k_base 토크나이저 기준 한국어 ~0.5 토큰/글자 (즉 1 토큰 ≈ 2~3 글자)
# 128K - 최대 출력(16,384) - 시스템 프롬프트/쿼리 여유 ≈ 105,000 으로 설정
MAX_CONTEXT_TOKENS: int = 105000

# 검색 대상 테이블명 — RetrievedChunk 스키마와 컬럼명을 통일
CHUNKS_TABLE: str = "chunks"

# 시간대(에러 로그 기록 시 한국 표준시(UTC+9)를 기준으로 하기 위함)
KST = timezone(timedelta(hours=9))