"""
TODO LIST:
- [ ] FUNC-010: 검색 문맥 품질 평가 로직 구현
    - 검색된 노드들이 질의에 답하기 충분한지 평가(is_relevant)
    - 문서 내에 '타 기준서 준용' 등 외부 참조 필요 여부(requires_external_reference) 판별
    - 평가 모델 출력 파싱 실패 시 보수적으로 '재검색 필요' 상태로 처리
- [ ] FUNC-011: 워크플로우 라우팅 제어 함수(Conditional Edge) 구현
    - FUNC-010의 평가 결과(State)를 바탕으로 분기 처리
    - 재검색/외부 참조 필요 시 -> 'rewrite' 노드 이름 반환
    - 유효한 문맥 확보 시 -> 'generate' 노드 이름 반환
"""