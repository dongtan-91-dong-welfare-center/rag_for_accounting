/**
 * API 클라이언트 — src/api/schemas.py 계약의 TypeScript 미러.
 *
 * 응답은 status(done|interrupted)로 구분되는 유니언이다. 필드를 여기 말고
 * 다른 곳에 정의하지 말 것 — 백엔드 계약 변경 시 이 파일만 함께 고친다.
 */

export interface ClauseOut {
  rank: number;
  chapter: string;
  node_id: string;
  score: number;
  content: string;
  document_id: string;
  /** 원본 PDF 페이지 범위 — 백필 전/미매칭이면 null(원문 보기 버튼 미표시). */
  page_start: number | null;
  page_end: number | null;
}

export interface CitationOut {
  document_id: string;
  chunk_id: string;
  content: string;
  relevance_score: number;
  page_start: number | null;
  page_end: number | null;
}

export type ResumeAction = "approve" | "rewrite";

export interface InterruptOption {
  action: ResumeAction;
  label: string;
}

export interface InterruptInfo {
  strategy: string;
  original_query: string;
  search_queries: string[];
  options: InterruptOption[];
}

export interface QueryDoneResponse {
  status: "done";
  thread_id: string;
  answer: string;
  is_answerable: boolean;
  confidence: number;
  /** 서버가 error_logs에서 파생한 폴백 구분자 — TIMEOUT이면 일시적 실패(재시도 유도). */
  error_code: "TIMEOUT" | null;
  clauses: ClauseOut[];
  citations: CitationOut[];
}

export interface QueryInterruptedResponse {
  status: "interrupted";
  thread_id: string;
  interrupt: InterruptInfo;
}

export type WorkflowResponse = QueryDoneResponse | QueryInterruptedResponse;

export type StandardFilter = "ALL" | "GAAP" | "KIFRS";

const API_BASE: string = import.meta.env.VITE_API_BASE ?? "";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status} ${res.statusText} — ${detail}`);
  }
  return res.json() as Promise<T>;
}

export function postQuery(query: string, standardFilter: StandardFilter): Promise<WorkflowResponse> {
  return post("/query", { query, standard_filter: standardFilter });
}

export function postResume(
  threadId: string,
  action: ResumeAction,
  feedback?: string,
): Promise<WorkflowResponse> {
  const body: Record<string, unknown> = { thread_id: threadId, action };
  if (feedback !== undefined) body.feedback = feedback;
  return post("/resume", body);
}

/** 원문 PDF 서빙 경로 — 브라우저 내장 뷰어의 #page=N 으로 해당 페이지를 연다. */
export function documentPdfUrl(documentId: string, page?: number): string {
  const hash = page ? `#page=${page}` : "";
  return `${API_BASE}/documents/${documentId}/pdf${hash}`;
}

/** PDF 제공 여부 확인(BYO 환경 폴백용) — 404면 뷰어를 안내 메시지로 강등한다. */
export async function checkPdfAvailable(documentId: string): Promise<boolean> {
  try {
    const res = await fetch(documentPdfUrl(documentId), { method: "HEAD" });
    return res.ok;
  } catch {
    return false;
  }
}
