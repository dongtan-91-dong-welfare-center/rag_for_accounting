"""
TODO LIST:
- [ ] FUNC-003: Dense(의미) 벡터 임베딩 생성 함수 구현
    - 노드 텍스트 리스트를 입력받아 Dense 벡터 리스트 반환
    - API Rate Limit(HTTP 429 등) 발생 시 지수 백오프(Exponential Backoff) 및 자동 재시도 로직 구현 (tenacity 등 활용)
- [ ] FUNC-004: Sparse(키워드) 벡터 임베딩 생성 함수 구현
    - 텍스트 분석기 및 회계 전문 용어 사전 로드
    - 노드 내 단어 빈도/중요도 기반 희소(Sparse) 벡터 변환 로직 구현
    - 사전 파일 로드 실패 시 기본 토크나이징 모드로 작동하는 Fallback 로직 추가
"""