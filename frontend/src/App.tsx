/**
 * 회계 기준서 RAG 질의 화면 — Streamlit(app.py)과 동일한 상태머신을 React로 옮긴 것.
 *
 * idle → loading → (interrupted ⇄ loading)* → done | error
 * HIL interrupt가 오면 승인/재작성을 받아 /resume으로 재개한다(재중단 가능).
 * NFR-002: 검색된 조항이 1순위 — 답변보다 먼저 노출한다.
 */
import { useEffect, useState } from "react";
import type {
  QueryDoneResponse,
  QueryInterruptedResponse,
  ResumeAction,
  StandardFilter,
  WorkflowResponse,
} from "./api";
import { checkPdfAvailable, documentPdfUrl, postQuery, postResume } from "./api";

const STANDARD_OPTIONS: StandardFilter[] = ["ALL", "GAAP", "KIFRS"];

type Stage =
  | { kind: "idle" }
  | { kind: "loading"; label: string }
  | { kind: "interrupted"; response: QueryInterruptedResponse }
  | { kind: "done"; response: QueryDoneResponse }
  | { kind: "error"; message: string };

export default function App() {
  const [query, setQuery] = useState("");
  const [standard, setStandard] = useState<StandardFilter>("ALL");
  const [feedback, setFeedback] = useState("");
  const [stage, setStage] = useState<Stage>({ kind: "idle" });

  const apply = (response: WorkflowResponse) => {
    setStage(
      response.status === "interrupted"
        ? { kind: "interrupted", response }
        : { kind: "done", response },
    );
  };

  const submitQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    setStage({
      kind: "loading",
      label: "워크플로 실행 중… (rewrite → search → rerank → evaluate → generate)",
    });
    try {
      apply(await postQuery(q, standard));
    } catch (err) {
      setStage({ kind: "error", message: String(err) });
    }
  };

  const resume = async (threadId: string, action: ResumeAction) => {
    setStage({ kind: "loading", label: "재개 중…" });
    try {
      apply(await postResume(threadId, action, action === "rewrite" ? feedback : undefined));
      setFeedback("");
    } catch (err) {
      setStage({ kind: "error", message: String(err) });
    }
  };

  const busy = stage.kind === "loading" || stage.kind === "interrupted";

  return (
    <main>
      <h1>회계 기준서 RAG 질의</h1>

      <form onSubmit={submitQuery} className="card">
        <label>
          질의
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="예: 재고자산의 취득원가는 어떻게 측정하나요?"
            disabled={busy}
          />
        </label>
        <label>
          기준 필터
          <select
            value={standard}
            onChange={(e) => setStandard(e.target.value as StandardFilter)}
            disabled={busy}
          >
            {STANDARD_OPTIONS.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={busy || !query.trim()}>
          질의
        </button>
      </form>

      {stage.kind === "loading" && <p className="notice info">{stage.label}</p>}

      {stage.kind === "error" && (
        <div className="notice error">
          <p>실행 오류: {stage.message}</p>
          <button onClick={() => setStage({ kind: "idle" })}>닫기</button>
        </div>
      )}

      {stage.kind === "interrupted" && (
        <HumanReview
          response={stage.response}
          feedback={feedback}
          onFeedbackChange={setFeedback}
          onDecide={(action) => resume(stage.response.thread_id, action)}
        />
      )}

      {stage.kind === "done" && <Result response={stage.response} />}
    </main>
  );
}

function HumanReview({
  response,
  feedback,
  onFeedbackChange,
  onDecide,
}: {
  response: QueryInterruptedResponse;
  feedback: string;
  onFeedbackChange: (v: string) => void;
  onDecide: (action: ResumeAction) => void;
}) {
  const { interrupt } = response;
  return (
    <section className="card">
      <p className="notice info">재작성 전략이 사용자 확인을 요구합니다.</p>
      <p>
        <strong>전략:</strong> {interrupt.strategy}
      </p>
      <p>
        <strong>원질의:</strong> {interrupt.original_query}
      </p>
      <ul>
        {interrupt.search_queries.map((q, i) => (
          <li key={i}>
            검색쿼리 {i + 1}: {q}
          </li>
        ))}
      </ul>
      <div className="actions">
        {interrupt.options.map((opt) =>
          opt.action === "rewrite" ? (
            <span key={opt.action} className="rewrite-group">
              <input
                value={feedback}
                onChange={(e) => onFeedbackChange(e.target.value)}
                placeholder="재작성 피드백"
              />
              <button onClick={() => onDecide("rewrite")}>{opt.label}</button>
            </span>
          ) : (
            <button key={opt.action} onClick={() => onDecide(opt.action)}>
              {opt.label}
            </button>
          ),
        )}
      </div>
    </section>
  );
}

interface ViewerTarget {
  documentId: string;
  page: number;
}

function PageButton({
  documentId,
  pageStart,
  pageEnd,
  onOpen,
}: {
  documentId: string;
  pageStart: number | null;
  pageEnd: number | null;
  onOpen: (target: ViewerTarget) => void;
}) {
  // 백필 전/미매칭 청크는 페이지가 없어 버튼을 표시하지 않는다(자연 강등).
  if (pageStart === null) return null;
  const label = pageEnd !== null && pageEnd !== pageStart ? `p.${pageStart}–${pageEnd}` : `p.${pageStart}`;
  return (
    <button
      type="button"
      className="page-btn"
      onClick={(e) => {
        // <summary> 안에서 details 토글을 유발하지 않도록 기본 동작을 막는다.
        e.preventDefault();
        e.stopPropagation();
        onOpen({ documentId, page: pageStart });
      }}
    >
      원문 {label}
    </button>
  );
}

function PdfViewerModal({ target, onClose }: { target: ViewerTarget; onClose: () => void }) {
  const [available, setAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    setAvailable(null);
    checkPdfAvailable(target.documentId).then(setAvailable);
  }, [target.documentId]);

  return (
    <div className="viewer-overlay" onClick={onClose}>
      <div className="viewer-panel" onClick={(e) => e.stopPropagation()}>
        <div className="viewer-header">
          <strong>
            원문 보기 — {target.documentId} · {target.page}쪽
          </strong>
          <button type="button" onClick={onClose}>
            닫기
          </button>
        </div>
        {available === null && <p className="notice info">원문 문서를 확인하는 중…</p>}
        {available === false && (
          <p className="notice warning">
            원본 PDF가 서버에 없습니다. 운영 환경에 원본 문서(PDF_DIR)를 배치하면 해당 페이지를 바로
            볼 수 있습니다.
          </p>
        )}
        {available && (
          <iframe
            className="viewer-frame"
            title={`${target.documentId} 원문`}
            src={documentPdfUrl(target.documentId, target.page)}
          />
        )}
        {/* 6/14 회의 결정: 원문 노출 시 한국회계기준원 저작권 표기 */}
        <p className="viewer-copyright">
          ⓒ 한국회계기준원. 본 문서의 저작권은 한국회계기준원에 있으며, 조항 원문 확인 용도로만
          제공됩니다.
        </p>
      </div>
    </div>
  );
}

function Result({ response }: { response: QueryDoneResponse }) {
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);

  return (
    <section>
      {response.error_code === "TIMEOUT" ? (
        <p className="notice warning">
          처리 시간이 초과되어 답변을 생성하지 못했습니다. 일시적인 문제이니 잠시 후 같은 질의로
          다시 시도해 주세요.
        </p>
      ) : response.is_answerable ? (
        <p className="notice success">답변 가능</p>
      ) : (
        <p className="notice warning">제공된 회계기준 문서에서 충분한 근거를 찾지 못했습니다.</p>
      )}

      {/* NFR-002: 조항 검색이 1순위이므로 답변보다 먼저 노출한다. */}
      <h2>검색된 조항 (상위 {response.clauses.length}건)</h2>
      {response.clauses.length === 0 ? (
        <p className="muted">검색된 조항 없음</p>
      ) : (
        <>
          <p className="muted">
            질의와 가장 관련 높은 회계기준 조항입니다. 아래 답변은 이 조항을 참고해 생성됩니다.
          </p>
          {response.clauses.map((c) => (
            <details key={c.rank} className="card">
              <summary>
                [{c.rank}] {c.chapter}장{c.node_id && ` · ${c.node_id}`} · 검색점수{" "}
                {c.score.toFixed(3)}{" "}
                <PageButton
                  documentId={c.document_id}
                  pageStart={c.page_start}
                  pageEnd={c.page_end}
                  onOpen={setViewer}
                />
              </summary>
              <p className="prewrap">{c.content}</p>
            </details>
          ))}
        </>
      )}

      <h2>답변</h2>
      <p className="prewrap">{response.answer}</p>
      <p>
        <strong>신뢰도:</strong> {(response.confidence * 100).toFixed(1)}%
      </p>

      <h2>인용 ({response.citations.length}건)</h2>
      {response.citations.length === 0 && <p className="muted">인용 없음</p>}
      {response.citations.map((c, i) => (
        <details key={c.chunk_id} className="card">
          <summary>
            [{i + 1}] {c.document_id} / {c.chunk_id} · 관련도 {c.relevance_score.toFixed(2)}{" "}
            <PageButton
              documentId={c.document_id}
              pageStart={c.page_start}
              pageEnd={c.page_end}
              onOpen={setViewer}
            />
          </summary>
          <p className="prewrap">{c.content}</p>
        </details>
      ))}

      {viewer && <PdfViewerModal target={viewer} onClose={() => setViewer(null)} />}
    </section>
  );
}
