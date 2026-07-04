# frontend — 회계 기준서 RAG 질의 화면 (React)

> **한 줄 요약(BLUF):** FastAPI 서버(`src/api/server.py`)의 `/query`·`/resume`을 소비하는 React(Vite + TypeScript) UI다. Streamlit(`app.py`)과 동일한 흐름(질의 → HIL 승인/재작성 → 조항·답변·인용)을 브라우저 SPA로 제공한다.

## 실행

API 서버가 먼저 떠 있어야 한다(레포 루트에서):

```bash
uv run uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

개발 서버(HMR, 기본 http://localhost:5173):

```bash
npm install
npm run dev
```

프로덕션 빌드·미리보기:

```bash
npm run build     # tsc 타입체크 + dist/ 번들
npm run preview
```

## 설정

| 항목 | 기본값 | 비고 |
|---|---|---|
| API 주소 | `http://localhost:8000` | `VITE_API_BASE` 환경변수로 override (예: `.env.local`) |
| CORS | 서버 쪽 `API_CORS_ORIGINS`가 5173 origin을 기본 허용 | 루트 `.env.example` 참조 |

## 구조

- `src/api.ts` — 백엔드 계약(`src/api/schemas.py`)의 TypeScript 미러 + fetch 클라이언트. 계약 변경 시 이 파일만 함께 고친다.
- `src/App.tsx` — 상태머신(idle → loading → interrupted ⇄ loading → done | error). 검색된 조항을 답변보다 먼저 노출한다(NFR-002).
