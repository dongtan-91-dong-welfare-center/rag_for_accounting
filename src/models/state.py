"""
📖 [개념 설명]: state.py가 하는 일
이 파일은 LangGraph 파이프라인에서 각 부서(노드)가 서로 데이터를 주고받을 때 사용하는 '공통 결재판(상태 객체)'의 양식을 정의하는 곳입니다. 

질문 분석(Rewrite) -> 문서 검색(Search) -> 품질 평가(Evaluate) -> 답변 생성(Generate) 등 여러 단계를 거치는 동안, 데이터가 유실되거나 변수명이 헷갈리지 않도록 파이썬의 TypedDict 등을 사용하여 데이터의 타입과 구조를 엄격하게 고정합니다. 모든 노드는 오직 이 State 객체 하나만을 읽고 씁니다.

✅ TODO LIST:
- [ ] LangGraph에서 사용할 기본 상태(State) 클래스 정의 (TypedDict 상속 권장)
- [ ] 입력 단계 데이터 필드 추가
    - `original_query` (str): 사용자가 처음 입력한 원본 질문
    - `target_standard` (str): 질의에서 추출된 회계기준 (예: 'K-IFRS' 또는 'K-GAAP')
- [ ] 검색 단계 데이터 필드 추가
    - `search_queries` (list[str]): AI가 검색용으로 분해/재작성한 최적화된 키워드 목록
    - `retrieved_nodes` (list[Any]): Milvus DB에서 하이브리드 검색으로 가져온 기준서 문서 청크들
- [ ] 평가 단계 데이터 필드 추가
    - `evaluation_result` (dict): 검색된 문서의 유효성 검사 결과
        - 예: {"is_relevant": bool, "requires_external_reference": bool}
- [ ] 출력 단계 데이터 필드 추가
    - `final_response` (dict): 최종 생성된 구조화된 답변 데이터
        - 예: {"answer": str, "standard_name": str, "clause": str}
"""