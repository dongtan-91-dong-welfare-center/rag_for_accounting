FROM postgres:16

# [벡터 지원 의존성 설치]
# apt-get을 통해 PostgreSQL 16 환경에서 pgvector를 바로 설치합니다 (postgresql-16-pgvector).
# 마지막의 rm -rf /var/lib/apt/lists/* 구문은 설치 후 남은 임시 패키지 캐시를 삭제하여 최종 이미지 용량을 최적화하는 Best Practice 입니다.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
