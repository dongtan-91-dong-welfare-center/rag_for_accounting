# dev → main 통합 리뷰 (2026-06-14, D-Day)

> v1.0(FUNC-001~009) 병합 가부 결정. 사전 감사 기반. 상세: `docs/v1_audit_report.md`

## 1. 감사 요약 (5분)
- 9개 FUNC 코어 구현 완료, 단위 테스트 276 passed. **하드 블로커 없음 → 조건부 병합 가능**
- FUNC 판정: 🟢 002·003·007·008 / 🟡 001·004·005·006·009

## 2. 병합 전 결정 필요 (핵심, 10분)
- 🔴 **라이브 스모크 1회**: 전 테스트가 mock. 실 DB·실 LLM ingest→query 1회 관통 미검증. `OPENAI_MODEL='gpt-5.4-mini'` 유효성 포함 확인

## 3. Major fast-follow (10분)
- search 노드 CM-002 오분류 → CRAG 재시도 누락 (버그)
- rewrite LLM 실패 silent (로깅 부재)
- DB 인프라 AGE 잔재(#126) — 결정과 모순, 통합테스트 skip
- TimeoutError 미처리 / ParsedDocument 이원 정의 / CI 부재

## 4. 액션·역할 (5분)
- 담당·기한 배정 (이슈 트래킹)

## 결정 사항
- [ ] 병합 진행 여부
- [ ] 저작권 데이터 처리 방침
- [ ] 라이브 스모크 담당자
