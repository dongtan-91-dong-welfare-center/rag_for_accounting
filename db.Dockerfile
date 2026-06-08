FROM postgres:16

# [벡터 지원 및 컴파일 필수 의존성 설치]
# apt-get을 통해 PostgreSQL 16 환경에서 pgvector를 바로 설치합니다 (postgresql-16-pgvector).
# Apache AGE 확장은 소스 코드로 명시적 컴파일을 수행해야 하므로 build-essential, git, make, gcc 및 관련 C 라이브러리 개발 패키지들이 필수적입니다.
    # Apache AGE 확장은 C언어로 작성된 PostgreSQL의 내부 엔진 확장이라 직접 컴파일(기계어로 번역)해야 함
# 마지막의 rm -rf /var/lib/apt/lists/* 구문은 설치 후 남은 임시 패키지 캐시를 삭제하여 최종 이미지 용량을 최적화하는 Best Practice 입니다.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    postgresql-16-pgvector \
    build-essential \
    postgresql-server-dev-16 \
    git \
    make \
    gcc \
    bison \
    flex \
    libreadline-dev \
    zlib1g-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# [Apache AGE 소스 코드 컴파일 및 설치]
# /tmp 디렉토리로 이동 후, PostgreSQL 16 버전에 대응하는 호환 브랜치인 'PG16'을 클론합니다.
    # /tmp 디렉터리에서 clone 후 make(빌드) 한 이후에 .so 파일 등 바이너리 파일만 시스템 폴더로 복사하고, 나머지 소스 코드 잔여물은 삭제하여 이미지 크기를 한 번 더 줄인다.(최적화)
# `make PG_CONFIG=/...` 명령을 통해 현재 시스템에 설치된 PostgreSQL 환경 변수(include, lib 경로 등)를 정확히 매핑하여 age 라이브러리를 안전하게 빌드 및 설치한다.
# 빌드 및 링킹 과정이 무사히 끝나면 컨테이너 내 불필요해진 소스코드 폴더(/tmp/age)를 완전히 삭제하여 이미지 크기를 한 번 더 줄인다.
    # 링킹: 소스 코드(.c)를 개별 부품(.o)으로 만들어서 PostgreSQL 본체나 시스템 라이브러리와 합쳐서 실제로 실행 가능한 하나의 라이브러리 파일(age.so)로 완성하는 최종 단계이다.
RUN cd /tmp && \
    git clone --branch PG16 https://github.com/apache/age.git && \
    cd age && \
    make PG_CONFIG=/usr/lib/postgresql/16/bin/pg_config install && \
    rm -rf /tmp/age

# [공유 메모리 라이브러리 로드 안내]
# 일반적으로 DB가 켜진 후에 "이 기능을 사용하겠습니다." 선언하고 불러오면 된다.
# 주의: Apache AGE (그래프 데이터베이스) 확장은 DB가 처음 부팅할 때 메모리 공간을 미리 할당받아야 하기 때문에 단순 CREATE EXTENSION 구문만으로는 작동하지 않으며, 반드시 컨테이너 실행 시점에 메모리에 올라가 있어야 한다.
# 이 설정은 docker-compose.yml의 command 부분에서 매개변수('-c shared_preload_libraries=age')를 통해 주입된다.
