-- 0001_initial.sql
-- 회계 기준서 RAG 시스템 기본 테이블 및 인덱스 초기화 스키마
--
-- 관리 대상:
-- 1. pgvector 확장 (vector)
-- 2. chunks (청크 및 임베딩 벡터 저장소)
-- 3. interaction_log (질의응답 상호작용 및 CRAG 평가 로그)
-- 4. answer_feedback (사용자 피드백 평가 로그)

-- 1. pgvector 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. chunks 테이블 (문서 청크, 임베딩 벡터, 형태소 토큰)
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    embedding vector(1024) NOT NULL,
    content_morph TEXT
);

-- HNSW 벡터 유사도 인덱스 (cosine 거리 기준)
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx ON chunks
USING hnsw (embedding vector_cosine_ops);

-- 형태소 텍스트 GIN 역색인 (단어 기반 sparse 검색)
CREATE INDEX IF NOT EXISTS chunks_content_morph_gin_idx ON chunks
USING GIN (to_tsvector('simple', content_morph));

-- 3. interaction_log 테이블 (질의/응답/평가 기록)
CREATE TABLE IF NOT EXISTS interaction_log (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    thread_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    query TEXT NOT NULL,
    standard_filter TEXT,
    status TEXT NOT NULL,
    answer TEXT,
    is_answerable BOOLEAN,
    confidence DOUBLE PRECISION,
    error_code TEXT,
    eval_is_relevant BOOLEAN,
    eval_needs_external BOOLEAN,
    eval_confidence DOUBLE PRECISION,
    eval_reasoning TEXT,
    citations JSONB,
    elapsed_ms INTEGER
);

CREATE INDEX IF NOT EXISTS interaction_log_thread_id_idx ON interaction_log (thread_id);
CREATE INDEX IF NOT EXISTS interaction_log_created_at_idx ON interaction_log (created_at DESC);

-- 4. answer_feedback 테이블 (사용자 답변 평가)
CREATE TABLE IF NOT EXISTS answer_feedback (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    thread_id TEXT NOT NULL,
    rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
    reason TEXT
);

CREATE INDEX IF NOT EXISTS answer_feedback_thread_id_idx ON answer_feedback (thread_id);
