import os
from datetime import timezone, timedelta

from dotenv import load_dotenv

# config는 logger/exception을 경유한 transitive import로 어떤 진입점의 load_dotenv()보다도 먼저 평가될 수 있다.
# 여기서 직접 로드해 .env 반영을 import 순서와 무관하게 보장한다.
# 이미 설정된 실제 환경변수는 덮어쓰지 않는다(override=False 기본값).
load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    """환경변수를 bool로 파싱한다 — bool("false") == True 함정을 피해 truthy 집합만 True."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"true", "1", "yes"}


def _env_float(name: str, default: float) -> float:
    """환경변수를 float로 파싱한다. 미설정이면 기본값, 숫자가 아니면 ValueError"""
    value = os.getenv(name)
    return default if value is None else float(value)


# 파이프라인 전역 설정값
MAX_REWRITE_COUNT: int = 3          # FUNC-004: CRAG 루프(평가 임계치 미달 재검색) 최대 반복 횟수
MAX_HIL_COUNT: int = 5              # 워크플로우: Human-in-the-Loop 재작성 요청 최대 반복 횟수 (CRAG 루프와 분리)
TOP_K_RETRIEVAL: int = 10           # FUNC-005: 1차 검색 반환 청크 수

# Reranking Configuration — .env로 토글 가능. 기본은 OFF.
USE_RERANKER: bool = _env_bool("USE_RERANKER", False)           # 리랭킹 모델 활성화 여부
RERANK_THRESHOLD: float = _env_float("RERANK_THRESHOLD", 0.5)   # FUNC-006: 재정렬 후 필터링 임계값 (기본값: 중간 신뢰도)
RERANK_MODEL: str = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")  # FUNC-006: Cross-Encoder 모델 식별자
VECTOR_COLLECTION_NAME: str = "rag_for_accounting"  # FUNC-003: pgvector 컬렉션명
OPENAI_MODEL: str = "gpt-5.4-mini"   # FUNC-007, 008, 009: LLM 모델 식별자

# 하이브리드 검색 병합 및 배치 설정
# Dense/Sparse 결과를 RRF(Reciprocal Rank Fusion)로 병합한다.
# 점수가 아닌 순위 기반이므로 점수 분포가 다른 두 검색을 정규화 없이 결합할 수 있다.
# RRF_K가 클수록 상위 순위 간 점수 격차가 완만해지며, 60은 원 논문 권장 기본값이다.
RRF_K: int = 60                # FUNC-005: RRF 순위 평활 상수
BATCH_SIZE: int = 100          # 인덱싱 배치 크기

# Sparse 리스트에 줄 RRF 가중치 (dense=1.0 고정). 1.0이면 대칭 RRF다.
# 순위 기반 병합이어도 "양쪽 리스트에 모두 있는 청크"는 점수가 합산되므로, sparse를 켜면 dense 단독 1위가 청크에 밀리는 회귀가 생긴다 — 이 가중이 그 합산을 억제한다.
# 0.1은 실측 채택 수치다(#261): 가중을 1.0→0.1로 낮출수록 순증−회귀가 −9→+5로 단조 개선했고, 0.1에서 sparse 단독 청크는 dense top-10을 밀어내지 못해(0.1/61 < 1/70) dense 후보를 키워드 근거로 재정렬하는 신호로만 작동한다.
SPARSE_FUSION_WEIGHT: float = _env_float("SPARSE_FUSION_WEIGHT", 0.1)

# 타임아웃 SSoT 및 계층 구조
# 시스템 전체 타임아웃 계층 원칙:
#   Layer 1 (개별 I/O Fast-Fail): SEARCH_TIMEOUT_SECONDS (10s), DB_POOL_TIMEOUT_SECONDS (10s) < LLM_TIMEOUT_SECONDS (45s)
#   Layer 2 (노드 워크플로우): GRAPH_STEP_TIMEOUT_SECONDS (60s)
#   Layer 3 (서브시스템/서버): EMBEDDING_SERVER_TIMEOUT_SECONDS (120s)
# 안쪽(개별 I/O) 타임아웃이 바깥쪽(LangGraph step_timeout)보다 짧아야 개별 에러(SE-101, SE-102, CM-002)가 명확히 포착되며,
# 바깥쪽 step_timeout이 먼저 터져 고아 HTTP/DB 요청이 백그라운드에서 자원을 누수하는 현상을 차단합니다.
# LangSmith/운영 실측 데이터 수집 전 정상적인 긴 답변 생성이 타임아웃되는 오발동을 막기 위해 여유 마진을 부여합니다.
# !TODO 실측 후 타임아웃 세부 수치 조정 필요합니다.

# 검색 타임아웃 (초) — pgvector 쿼리가 이 시간을 초과하면 SearchTimeoutError(SE-101) 발생
SEARCH_TIMEOUT_SECONDS: int = int(_env_float("SEARCH_TIMEOUT_SECONDS", 10.0))

# DB 커넥션 풀 대기 타임아웃 (초)
DB_POOL_TIMEOUT_SECONDS: float = _env_float("DB_POOL_TIMEOUT_SECONDS", 10.0)

# OpenAI LLM API 요청 타임아웃 (초)
LLM_TIMEOUT_SECONDS: float = _env_float("LLM_TIMEOUT_SECONDS", 45.0)

# OpenAI SDK 차원 재시도 상한
LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "1"))

# LangGraph 노드 실행 타임아웃 (초)
GRAPH_STEP_TIMEOUT_SECONDS: int = int(_env_float("GRAPH_STEP_TIMEOUT_SECONDS", 60.0))

# 임베딩 모델 설정
# 인덱싱(FUNC-003)과 검색(FUNC-005)이 src/clients/embedding.embed_texts()를 공유하므로
# 모델·차원 불일치가 구조적으로 발생하지 않는다.
EMBEDDING_MODEL: str = "nlpai-lab/KURE-v1"
EMBEDDING_DIM: int = 1024   # KURE-v1 벡터 차원 수 → pgvector vector(1024)
EMBEDDING_MAX_TOKENS: int = 8192    # KURE-v1 컨텍스트 한도 — 초과 청크는 IX-201로 스킵(부분 커밋)

# 청킹 분할 상한 — 노드를 이 토큰 수 이하 조각으로 분할해 적재한다(chunk_graph 기본값).
# EMBEDDING_MAX_TOKENS(모델 한도·IX-201 스킵 임계)와 분리한다: 
# 거대 노드를 한 벡터로 임베딩할 때 MPS OOM(메모리 ∝ batch×seq²)을 막기 위함
# 2048은 33장 실측상 정상 조항 다발(대부분 ≤2048)은 보존하고 거대 clause-less 블록(결론도출근거·실무지침 등)만 분할하는 값.
CHUNK_MAX_TOKENS: int = 2048

# 임베딩 서빙 분리 설정 — KURE-v1을 기성 서빙 컨테이너(docker-compose `embedding`, TEI)로 분리 실행.
# EMBEDDING_SERVER_URL 설정 시 embed_texts/count_tokens가 src/client를 통해 해당 서버로 HTTP 위임하고,
# 미설정(기본)이면 프로세스 내 로드(현행 동작). 리랭커는 USE_RERANKER 기본 off라 서빙 대상이 아니다.
EMBEDDING_SERVER_URL: str = os.getenv("EMBEDDING_SERVER_URL", "").strip().rstrip("/")
EMBEDDING_SERVER_TIMEOUT_SECONDS: float = _env_float("EMBEDDING_SERVER_TIMEOUT_SECONDS", 120.0)

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

# ── Sparse 형태소 토큰화 ──
# 현행 sparse는 to_tsvector('simple', …)가 띄어쓰기로만 잘라 조사를 못 떼므로 문장형 질의에서 전 케이스 0건을 반환한다
# 하이브리드가 사실상 dense 단독으로 동작한 원인이다.
# 형태소로 사전토큰화한 텍스트를 따로 저장해 이 간극을 메운다. 
# 적재와 검색이 tokenizer.morph_text()를 공유하므로 색인 토큰과 질의 토큰이 구조적으로 어긋나지 않는다
# (embedding.embed_texts()를 공유해 모델·차원을 고정하는 것과 같은 규약).
#
# 품사 화이트리스트 — 남길 형태소 태그. ts_rank_cd에는 IDF가 없어 흔한 형태소가 자동 감쇠되지 않으므로, 저IDF 노이즈를 걷어내는 수단이 이 필터뿐이다(오프라인 BM25와 다른 점).
#   CORE : 순수 명사류. NNG 일반명사 · NNP 고유명사 · SL 외국어 · SN 숫자 · SH 한자
#   WIDE : CORE + 어근·접사. XR 어근("환입액"의 "환") · XSN 명사파생접미사 · XPN 체언접두사
# 과분할된 복합어("환입액"→환/입/액)의 신호를 살리려면 WIDE가 필요할 수 있어 실측으로 가른다.
# 길이 필터(1글자 버리기)는 넣지 않는다.
MORPH_POS_TAGS_CORE: tuple[str, ...] = ("NNG", "NNP", "SL", "SN", "SH")
MORPH_POS_TAGS_WIDE: tuple[str, ...] = MORPH_POS_TAGS_CORE + ("XR", "XSN", "XPN")
MORPH_POS_TAGS: tuple[str, ...] = MORPH_POS_TAGS_CORE   # 운영 확정 — #261 실측에서 CORE(46) > WIDE(44)

# 형태소 사전토큰화 컬럼을 담은 측정용 그림자 테이블 — scripts/build_morph_shadow.py가 만든다.
# 운영 chunks를 건드리지 않고 배포 후보 셀을 재는 격리 지점(sparse_search의 collection 주입점과 같은 용도).
MORPH_CHUNKS_TABLE: str = os.getenv("MORPH_CHUNKS_TABLE", "chunks_morph")

# API 서버(src/api/server.py) CORS 허용 origin — React dev 서버(Vite 기본 5173) 브라우저 호출용.
# 배포 origin이 다르면 콤마 구분 env로 override 한다(예: API_CORS_ORIGINS=https://rag.example.com).
API_CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv("API_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

# 원본 PDF 소재 디렉토리 — 페이지 백필과 PDF 서빙이 공유하는 규약.
# 저작권 문제로 원문 PDF를 저장소에 포함하지 않고, 사용자가 직접 준비해 이 디렉토리에 두는 방식을 쓴다.
# 규약(resolve_pdf_path): {PDF_DIR}/{document_id}.pdf 우선, 없으면 제N장*.pdf 글롭(현행 data/raw_data 호환).
PDF_DIR: str = os.getenv("PDF_DIR", "data/raw_data")

# 시간대 — 일반 로그와 오류 기록(ErrorLog.timestamp) 모두 한국 표준시(KST, UTC+9) 기준으로 통일하기 위함
KST = timezone(timedelta(hours=9))