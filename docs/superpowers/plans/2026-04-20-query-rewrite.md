# Query Rewrite Node — 구현 문서

**상태:** 완료 (2026-04-26)

**Goal:** 사용자 질의를 회계 여부 판단 → 전략 선택(HyDE / Decompose / Step-back) → 검색 쿼리 생성까지 처리하는 rewrite 노드를 구현한다.

**Architecture:** 회계 여부 판단과 전략 선택을 단일 LLM 호출(`classify_and_select`)로 통합하여 2-step을 1-step으로 줄였다. 전략별로 LLM을 한 번 더 호출해 `search_queries`를 생성한 뒤 search 노드에 전달한다. LLM 실패 시 원문 쿼리만 반환하는 Bypass로 폴백한다.

```
사용자 질의
    │
    ▼
classify_and_select (LLM 1회)
    ├─ is_accounting=false → Bypass (원문만 반환)
    └─ is_accounting=true
         ├─ strategy="hyde"      → apply_hyde      (LLM 1회) → [원문, 가상답변]
         ├─ strategy="decompose" → apply_decompose  (LLM 1회) → [원문, 서브쿼리1, ...]
         └─ strategy="stepback"  → apply_stepback   (LLM 1회) → [원문, 추상화쿼리]
```

**전략 선택 기준:**
- `bypass`   : 비회계 질의 (is_accounting=false)
- `stepback` : 특정 회사명·금액·날짜가 포함된 과도하게 구체적인 질의
- `decompose`: 두 가지 이상의 독립적인 회계 주제를 포함한 복합 질의
- `hyde`     : 그 외 일반적인 회계 질의 (기본값)

**Tech Stack:** openai>=1.0.0, pydantic>=2.0.0, python-dotenv>=1.0.0, pytest>=8.0.0

---

## File Map

| 파일 | 작업 | 역할 |
|------|------|------|
| `pyproject.toml` | Modify | openai·pydantic·python-dotenv 의존성 추가 |
| `src/models/state.py` | Modify | `is_accounting_query`, `rewritten_query`, `crag_count`, `error_logs` 필드 추가 |
| `src/models/schemas.py` | Modify | `RewrittenQuery` — `original`, `strategy`, `search_queries` 필드 포함 |
| `src/agent/prompts.py` | Modify | `CLASSIFY_STRATEGY_PROMPT` / `HYDE_PROMPT` / `DECOMPOSE_PROMPT` / `STEPBACK_PROMPT` 추가 |
| `src/agent/nodes/rewrite.py` | Rewrite | `classify_and_select` + 전략별 LLM 호출 + 예외처리 |
| `tests/unit/agent/test_rewrite.py` | Create | 단위 테스트 (30 케이스) |
| `tests/integration/test_rewrite_integration.py` | Create | K-GAAP 실무 질의 18건 통합 테스트 |
| `docs/superpowers/plans/llm_rewrite.md` | Auto-generated | 통합 테스트 실행 결과 스냅샷 |

---

## Task 1: 의존성 추가

- [x] **Step 1: pyproject.toml에 의존성 추가**

```toml
[project]
dependencies = [
    "docling>=2.85.0",
    "streamlit>=1.56.0",
    "pydantic>=2.0.0",
    "openai>=1.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.25.0",
]
```

- [x] **Step 2: 의존성 설치**

```bash
uv sync
```

---

## Task 2: GraphState 필드 추가

- [x] **Step 1: `src/models/state.py`에 필드 추가**

```python
class GraphState(BaseModel):
    query:               str
    is_accounting_query: bool                  = True
    crag_count:          int                   = 0
    rewritten_query:     RewrittenQuery | None = None
    retrieved_chunks:    list[RetrievedChunk]  = []
    reranked_chunks:     list[RerankingResult] = []
    evaluation:          EvaluationResult | None = None
    final_response:      FinalResponse | None  = None
    rewrite_count:       int                   = 0
    error_logs:          list[ErrorLog]        = []
    metadata:            dict                  = {}
```

> **Note:** 초기 설계의 `query_strategy`, `search_queries` 최상위 필드는 `RewrittenQuery`에 통합되어 GraphState에서 제거됨.

---

## Task 3: RewrittenQuery 스키마

- [x] **Step 1: `src/models/schemas.py`의 `RewrittenQuery` 정의**

```python
class RewrittenQuery(BaseModel):
    original:       str       # 사용자 원문 쿼리
    strategy:       str       # "hyde" | "decompose" | "stepback" | "bypass"
    search_queries: list[str] # 검색에 사용할 쿼리 목록 (원문 항상 [0]에 위치)
```

---

## Task 4: 프롬프트 추가

- [x] **Step 1: `src/agent/prompts.py`에 프롬프트 추가**

초기 설계의 `INTENT_CLASSIFY_PROMPT`(분류 전용)를 제거하고, 회계 여부 판단과 전략 선택을 동시에 수행하는 `CLASSIFY_STRATEGY_PROMPT`로 대체했다.

```python
CLASSIFY_STRATEGY_PROMPT: str = """당신은 사용자 질의를 분석하여 회계·감사 관련 여부와 검색 전략을 동시에 판단하는 전문가입니다.

질의: {query}

반드시 JSON으로만 답하세요:
{{"is_accounting": true | false, "strategy": "hyde" | "decompose" | "stepback" | "bypass"}}

[is_accounting 판단 기준]
회계 관련 (true):
- 재무제표: 재무상태표, 손익계산서, 현금흐름표, 자본변동표, 주석
- 회계기준: K-IFRS, K-GAAP, 한국채택국제회계기준, 일반기업회계기준
- 자산·부채: 유형자산, 무형자산, 유동자산, 비유동자산, 금융자산, 유동부채, 비유동부채, 충당부채, 사채, 리스부채
- 손익: 수익인식, 비용, 매출, 손상차손, 감가상각, 대손상각, 공정가치 평가
- 자본: 자본금, 주식발행초과금, 이익잉여금, 기타포괄손익
- 감사: 외부감사, 내부통제, 감사보고서, 감사의견, 핵심감사사항(KAM)
- 결합: 사업결합, 연결재무제표, 지분법, 종속기업·관계기업
비회계 (false): 인사말, 날씨, 일반 상식, 코딩, 요리, 법률(민법·상법 일반), 세무·세법

[strategy 선택 기준] — is_accounting=true인 경우에만 적용
- "bypass"  : is_accounting=false인 경우
- "stepback": 특정 회사명·금액·날짜가 포함된 과도하게 구체적인 질의
- "decompose": 두 가지 이상의 독립적인 회계 주제를 동시에 묻는 복합 질의
- "hyde"    : 그 외 일반적인 회계 질의 (기본값)"""

HYDE_PROMPT: str = """당신은 한국 회계기준서(K-IFRS/K-GAAP) 전문가입니다.
아래 질문에 대해 기준서에 나올 법한 답변을 2~3문장으로 작성하세요.
정확하지 않아도 됩니다. 기준서 문체와 전문 용어를 사용하는 것이 중요합니다.

질문: {query}

반드시 JSON으로만 답하세요:
{{"hypothetical_answer": "기준서 문체의 가상 답변"}}"""

DECOMPOSE_PROMPT: str = """당신은 복합 회계 질의를 단순 질의들로 분해하는 전문가입니다.

원문 질의: {query}

위 질의에 포함된 독립적인 하위 질문들을 2~4개로 분해하세요.
각 하위 질문은 단독으로 검색 가능해야 합니다.

반드시 JSON으로만 답하세요:
{{"sub_queries": ["하위질문1", "하위질문2", "하위질문3"]}}"""

STEPBACK_PROMPT: str = """당신은 구체적인 회계 질의를 일반 원칙 질의로 추상화하는 전문가입니다.

구체적 질의: {query}

위 질의에서 특정 회사명·금액·날짜를 제거하고, 적용되는 일반 회계 원칙을 묻는 질의로 바꾸세요.

반드시 JSON으로만 답하세요:
{{"abstract_query": "일반화된 원칙 질의"}}"""
```

---

## Task 5: rewrite 노드 구현

- [x] **Step 1: `src/agent/nodes/rewrite.py` 구현**

초기 설계에서 `classify_intent(LLM) + select_strategy(regex)` 2단계였던 구조를 `classify_and_select(LLM 1회)`로 통합했다. 또한 LLM이 JSON을 마크다운 코드블록으로 감싸 반환하는 경우를 처리하는 `_strip_markdown` 헬퍼를 추가했다.

```python
def _strip_markdown(content: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())


def classify_and_select(query: str) -> tuple[bool, str]:
    """회계 여부와 검색 전략을 단일 LLM 호출로 판단한다. 실패 시 (True, 'hyde')로 폴백."""
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": CLASSIFY_STRATEGY_PROMPT.format(query=query)}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        data = json.loads(_strip_markdown(resp.choices[0].message.content))
        raw = data.get("is_accounting", True)
        is_accounting = raw if isinstance(raw, bool) else str(raw).lower() == "true"
        strategy = data.get("strategy", "hyde")
        return is_accounting, strategy
    except Exception:
        return True, "hyde"


def apply_hyde(query: str) -> list[str]: ...
def apply_decompose(query: str) -> list[str]: ...
def apply_stepback(query: str) -> list[str]: ...


_STRATEGY_FN = {
    "hyde":      apply_hyde,
    "decompose": apply_decompose,
    "stepback":  apply_stepback,
}


def rewrite_query(state: GraphState) -> GraphState:
    try:
        is_accounting, strategy = classify_and_select(state.query)
        state.is_accounting_query = is_accounting

        if not is_accounting:
            state.rewritten_query = RewrittenQuery(
                original=state.query, strategy="bypass", search_queries=[state.query]
            )
            return state

        queries = _STRATEGY_FN[strategy](state.query)
        state.rewritten_query = RewrittenQuery(
            original=state.query, strategy=strategy, search_queries=queries
        )
    except Exception as e:
        state.rewritten_query = RewrittenQuery(
            original=state.query, strategy="bypass", search_queries=[state.query]
        )
        state.error_logs.append({
            "timestamp": "", "node": "rewrite",
            "error_type": type(e).__name__, "message": str(e),
        })
    return state
```

- [x] **Step 2: 단위 테스트 작성 — `tests/unit/agent/test_rewrite.py`**

| 테스트 클래스 | 케이스 수 | 검증 대상 |
|---|---|---|
| `TestClassifyAndSelect` | 9 | LLM 응답 파싱, boolean 타입 변환, 마크다운 래퍼 제거, 폴백 |
| `TestApplyHyde` | 4 | 원문+가상답변 반환, 빈 응답·LLM 실패 시 원문만 반환 |
| `TestApplyDecompose` | 4 | 원문+서브쿼리 반환, 빈 응답·LLM 실패 시 원문만 반환 |
| `TestApplyStepback` | 4 | 원문+추상화쿼리 반환, 빈 응답·LLM 실패 시 원문만 반환 |
| `TestRewriteQuery` | 8 | GraphState 변이, 2-step LLM 체인, 예외 전파 경로 |
| 독립 테스트 | 1 | GraphState 기본값 검증 |

**총 30 케이스, 전체 통과.**

```bash
uv run pytest tests/unit/agent/test_rewrite.py -v
# 30 passed
```

---

## Task 6: 통합 테스트 추가

- [x] **Step 1: `tests/integration/test_rewrite_integration.py` 작성**

K-GAAP 실무 질의 18건을 실제 LLM에 입력하여 전략 분류와 `search_queries` 생성을 검증한다. 결과는 `docs/superpowers/plans/llm_rewrite.md`에 스냅샷으로 저장된다.

```bash
uv run pytest tests/integration/test_rewrite_integration.py -v
# 1 passed in 54.48s
```

**검증 항목:**
- `is_accounting_query is True` — 모든 회계 질의가 회계로 분류됨
- `strategy in {"hyde", "decompose", "stepback"}` — 유효한 전략만 반환됨
- `search_queries[0] == query` — 원문이 항상 첫 번째에 위치함
- `rewritten_query.original == query` — original 필드가 원문과 일치함

**전략 분포 결과 (18건):**

| 전략 | 건수 | 예시 질의 |
|------|------|-----------|
| `hyde` | 15 | 일반 K-GAAP 회계처리 원칙 질의 |
| `stepback` | 2 | 삼성전자 + 특정 날짜 + 금액 포함 질의 |
| `decompose` | 2 | 복수의 독립적 회계 주제를 동시에 묻는 질의 |

> 상세 실행 결과: [`llm_rewrite.md`](./llm_rewrite.md)

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-20 | 초기 계획 작성 |
| 2026-04-24 | GraphState 중복 필드(`query_strategy`, `search_queries`) 제거 |
| 2026-04-25 | `INTENT_CLASSIFY_PROMPT` 제거, `CLASSIFY_STRATEGY_PROMPT`로 통합 |
| 2026-04-26 | `classify_intent + select_strategy` → `classify_and_select` 단일 호출로 리팩토링 / `_strip_markdown` 헬퍼 추가 / 단위 테스트 30건 작성 / 통합 테스트 추가 |
