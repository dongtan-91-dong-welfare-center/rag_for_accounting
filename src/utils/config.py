import os
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

# 하이브리드 검색 병합 및 배치 설정
# Dense/Sparse 결과를 RRF(Reciprocal Rank Fusion)로 병합한다.
# 점수가 아닌 순위 기반이므로 가중치 튜닝 없이 분포가 다른 두 검색을 안정적으로 결합한다.
# RRF_K가 클수록 상위 순위 간 점수 격차가 완만해지며, 60은 원 논문 권장 기본값이다.
RRF_K: int = 60                # FUNC-005: RRF 순위 평활 상수
BATCH_SIZE: int = 100          # 인덱싱 배치 크기

# 검색 타임아웃 (초) — pgvector 쿼리가 이 시간을 초과하면 SearchTimeoutError(SE-101) 발생
SEARCH_TIMEOUT_SECONDS: int = 5

# 임베딩 모델 설정 — 이슈 #93에서 KURE-v1(자체호스팅, MIT 라이선스)로 확정
# 인덱싱(FUNC-003)과 검색(FUNC-005)이 src/utils/embedding.embed_texts()를 공유하므로
# 모델·차원 불일치가 구조적으로 발생하지 않는다.
EMBEDDING_MODEL: str = "nlpai-lab/KURE-v1"
EMBEDDING_DIM: int = 1024   # KURE-v1(bge-m3 기반) 벡터 차원 수 → pgvector vector(1024)
EMBEDDING_MAX_TOKENS: int = 8192    # KURE-v1 컨텍스트 한도 — 초과 청크는 IX-201로 스킵(부분 커밋)

# 임베딩 실행 자원 설정 — 대량 적재 시 CPU 포화·메모리 누적 OOM 완화용. 모두 env로 override.
#   - EMBEDDING_DEVICE: "auto"면 _get_model()이 cuda → mps → cpu 순으로 가용 디바이스를 고른다.
#     Docker on Mac 컨테이너에는 MPS/Metal이 패스스루되지 않아 자동으로 cpu가 된다. 호스트 네이티브
#     실행 시 mps로 잡혀 CPU 부하를 GPU로 넘긴다. "cpu"/"mps"/"cuda"로 강제 지정도 가능.
#   - EMBEDDING_NUM_THREADS: torch intra-op 스레드 상한. 0이면 max(1, cpu_count-2)로 자동 산정해 전 코어 점유(오버서브스크립션, 관측된 1000%+ CPU)를 막는다.
#   - EMBEDDING_ENCODE_BATCH_SIZE: model.encode 미니배치 크기. 작을수록 인코딩 1회 peak 메모리가 준다
#     (sentence-transformers는 길이순 정렬 후 이 크기로 쪼개 패딩 낭비도 함께 줄인다).
EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "auto")
EMBEDDING_NUM_THREADS: int = int(os.getenv("EMBEDDING_NUM_THREADS", "0"))
EMBEDDING_ENCODE_BATCH_SIZE: int = int(os.getenv("EMBEDDING_ENCODE_BATCH_SIZE", "16"))

# gpt-5.4-mini 컨텍스트 윈도우(400K) 중 컨텍스트 입력에 할당할 안전 한도
# o200k_base 토크나이저 기준 한국어 ~0.5 토큰/글자 (즉 1 토큰 ≈ 2~3 글자)
# 400K - 최대 출력(128K) - 시스템 프롬프트/쿼리 여유 ≈ 270,000 으로 설정
MAX_CONTEXT_TOKENS: int = 270000

# 검색 대상 테이블명 — RetrievedChunk 스키마와 컬럼명을 통일
CHUNKS_TABLE: str = "chunks"

# 시간대(에러 로그 기록 시 한국 표준시(UTC+9)를 기준으로 하기 위함)
KST = timezone(timedelta(hours=9))