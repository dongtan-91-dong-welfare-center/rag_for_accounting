/**
 * K-Accounting — 회계기준 리서치. "리서치 데스크" 디자인의 채팅형(트랜스크립트) UI.
 *
 * 상태머신은 기존과 동일: idle → loading → (interrupted ⇄ loading)* → done | error.
 * 완료된 질의는 exchanges[]에 쌓여 트랜스크립트로 렌더되고(채팅형),
 * 진행 중 상태(loading/HIL/error)는 트랜스크립트 말미에 인라인 카드로 표시된다.
 * NFR-002: 검색된 조항이 1순위 — 답변보다 먼저 노출한다.
 */
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type {
  QueryDoneResponse,
  QueryInterruptedResponse,
  ResumeAction,
  StandardFilter,
  WorkflowResponse,
} from "./api";
import { checkPdfAvailable, documentPdfUrl, postQuery, postResume } from "./api";
import { excerptOf, humanNodeTitle, paraChips } from "./clauseDisplay";

const STANDARD_OPTIONS: { value: StandardFilter; label: string }[] = [
  { value: "ALL", label: "전체 기준" },
  { value: "GAAP", label: "K-GAAP" },
  { value: "KIFRS", label: "K-IFRS" },
];

const PIPELINE = ["rewrite", "search", "rerank", "evaluate", "generate"];

function standardLabel(v: StandardFilter): string {
  return STANDARD_OPTIONS.find((o) => o.value === v)?.label ?? v;
}

function timeNow(): string {
  return new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false });
}

type Stage =
  | { kind: "idle" }
  | { kind: "loading"; label: string }
  | { kind: "interrupted"; response: QueryInterruptedResponse }
  | { kind: "error"; message: string };

/** 트랜스크립트에 남는 완결된 교환(질의 → HIL 기록 → 결과). */
interface Exchange {
  query: string;
  standard: StandardFilter;
  time: string;
  /** 승인/재작성으로 통과한 HIL 기록 — 대화 흐름에 흔적으로 남긴다. */
  hilNote: { strategy: string; searchQueries: string[]; decision: string } | null;
  response: QueryDoneResponse;
}

/** 진행 중인 질의(아직 done이 아님). */
interface Pending {
  query: string;
  standard: StandardFilter;
  time: string;
  hilNote: Exchange["hilNote"];
}

export default function App() {
  const [query, setQuery] = useState("");
  const [standard, setStandard] = useState<StandardFilter>("ALL");
  const [feedback, setFeedback] = useState("");
  const [stage, setStage] = useState<Stage>({ kind: "idle" });
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [pending, setPending] = useState<Pending | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const busy = stage.kind === "loading" || stage.kind === "interrupted";
  const sessionTitle = exchanges[0]?.query ?? pending?.query ?? "새 리서치";

  // 새 항목이 트랜스크립트에 붙으면 하단으로 스크롤한다.
  useEffect(() => {
    if (exchanges.length > 0 || busy) {
      window.scrollTo(0, document.documentElement.scrollHeight);
    }
  }, [exchanges.length, stage.kind, busy]);

  const apply = (response: WorkflowResponse, current: Pending) => {
    if (response.status === "interrupted") {
      setStage({ kind: "interrupted", response });
      return;
    }
    setExchanges((xs) => [...xs, { ...current, response }]);
    setPending(null);
    setStage({ kind: "idle" });
  };

  const submitQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (!q || busy) return;
    const current: Pending = { query: q, standard, time: timeNow(), hilNote: null };
    setPending(current);
    setQuery("");
    setFeedback(""); // 이전 질의의 HIL 피드백이 새 질의의 재작성 입력에 남지 않게 한다
    setStage({ kind: "loading", label: "워크플로 실행 중" });
    try {
      apply(await postQuery(q, standard), current);
    } catch (err) {
      setStage({ kind: "error", message: err instanceof Error ? err.message : String(err) });
    }
  };

  const resume = async (interrupted: QueryInterruptedResponse, action: ResumeAction) => {
    if (!pending) return;
    const { interrupt } = interrupted;
    const current: Pending = {
      ...pending,
      hilNote: {
        strategy: interrupt.strategy,
        searchQueries: interrupt.search_queries,
        decision: action === "approve" ? `승인됨 ${timeNow()}` : `재작성 요청 ${timeNow()}`,
      },
    };
    setPending(current);
    setStage({ kind: "loading", label: "재개 중" });
    try {
      apply(
        await postResume(interrupted.thread_id, action, action === "rewrite" ? feedback : undefined),
        current,
      );
      setFeedback("");
    } catch (err) {
      setStage({ kind: "error", message: err instanceof Error ? err.message : String(err) });
    }
  };

  const reset = () => {
    if (busy) return;
    setExchanges([]);
    setPending(null);
    setStage({ kind: "idle" });
    setQuery("");
    setFeedback("");
  };

  const dismissError = () => {
    if (pending) setQuery(pending.query); // 실패한 질의를 컴포저로 되돌려 재시도(재입력) 부담을 없앤다
    setPending(null);
    setStage({ kind: "idle" });
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-name">K-Accounting</span>
          <span className="brand-sub">회계기준 리서치</span>
        </div>
        <button className="new-research" onClick={reset} disabled={busy}>
          ＋ 새 리서치
        </button>
        <span className="rail-label">이 세션의 질의</span>
        <div className="rail-list">
          {exchanges.length === 0 && !pending && <span className="rail-empty">아직 질의가 없습니다</span>}
          {exchanges.map((x, i) => (
            <button
              key={i}
              className="rail-item"
              onClick={() => {
                const el = document.getElementById(`exchange-${i}`);
                if (el) window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 70);
              }}
            >
              {x.query}
              <small>
                {x.time} · {standardLabel(x.standard)}
              </small>
            </button>
          ))}
          {pending && (
            <button className="rail-item active">
              {pending.query}
              <small>{pending.time} · 진행 중…</small>
            </button>
          )}
        </div>
        <div className="sidebar-foot">
          답변은 검색된 기준서 조항을 근거로 생성됩니다. 최종 판단 전 원문 확인을 권장합니다.
        </div>
      </aside>

      <main className="main">
        <header className="main-header">
          <h1 className="main-title">{sessionTitle}</h1>
          <span className="main-header-meta">K-GAAP · K-IFRS 전문 검색</span>
        </header>

        <div className="transcript">
          {exchanges.length === 0 && !pending && stage.kind === "idle" && (
            <div className="empty-state">
              <span className="brand-name">K-Accounting</span>
              <p>
                회계기준에 대해 질의하세요. 관련 조항을 먼저 검색해 보여드리고,
                <br />그 조항을 근거로 답변을 생성합니다.
              </p>
            </div>
          )}

          {exchanges.map((x, i) => (
            <ExchangeBlock key={i} index={i} exchange={x} />
          ))}

          {pending && (
            <QueryBlock index={exchanges.length} query={pending.query} standard={pending.standard} time={pending.time} />
          )}

          {stage.kind === "loading" && (
            <div className="loading-card" role="status">
              <span className="spinner" />
              <div>
                <div className="loading-label">{stage.label}</div>
                <div className="loading-pipeline">{PIPELINE.join(" → ")}</div>
              </div>
            </div>
          )}

          {stage.kind === "error" && (
            <div className="error-card" role="alert">
              <p>실행 오류: {stage.message}</p>
              <button onClick={dismissError}>닫기</button>
            </div>
          )}

          {stage.kind === "interrupted" && (
            <HumanReview
              response={stage.response}
              feedback={feedback}
              onFeedbackChange={setFeedback}
              onDecide={(action) => resume(stage.response, action)}
              onDismiss={dismissError}
            />
          )}

          <div ref={endRef} />
        </div>

        <div className="composer-wrap">
          <form className="composer" onSubmit={submitQuery}>
            <select
              name="standard-filter"
              value={standard}
              onChange={(e) => setStandard(e.target.value as StandardFilter)}
              disabled={busy}
              aria-label="기준 필터"
            >
              {STANDARD_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <span className="composer-divider" />
            <input
              name="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="회계기준에 대해 질의하세요… (예: 재고자산의 취득원가는 어떻게 측정하나요?)"
              aria-label="질의 입력"
              disabled={busy}
            />
            <button type="submit" className="btn-primary" disabled={busy || !query.trim()}>
              질의
            </button>
          </form>
          <p className="composer-note">
            답변은 검색된 기준서 조항을 근거로 생성되며, 최종 판단 전 원문 확인을 권장합니다.
          </p>
        </div>
      </main>
    </div>
  );
}

function QueryBlock({
  index,
  query,
  standard,
  time,
}: {
  index: number;
  query: string;
  standard: StandardFilter;
  time: string;
}) {
  return (
    <div className="query-block">
      <div className="query-meta">
        <span className="query-kicker">질의 {index + 1}</span>
        <span className="query-time">
          {time} · 필터: {standardLabel(standard)}
        </span>
      </div>
      <h2 className="query-text">{query}</h2>
      <div className="query-rule" />
    </div>
  );
}

function ExchangeBlock({ index, exchange }: { index: number; exchange: Exchange }) {
  return (
    <div id={`exchange-${index}`} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <QueryBlock index={index} query={exchange.query} standard={exchange.standard} time={exchange.time} />
      {exchange.hilNote && (
        <div className="hil-resolved">
          <div className="hil-resolved-head">
            <span className="hil-kicker">확인 요청 — 질의 재작성</span>
            <span className="pill ok">{exchange.hilNote.decision}</span>
          </div>
          <p className="hil-desc">
            전략 <strong>{exchange.hilNote.strategy}</strong> · 검색쿼리{" "}
            {exchange.hilNote.searchQueries.map((q, i) => `${i > 0 ? " " : ""}${"①②③④⑤"[i] ?? `[${i + 1}]`} ${q}`)}
          </p>
        </div>
      )}
      <Result response={exchange.response} />
    </div>
  );
}

function HumanReview({
  response,
  feedback,
  onFeedbackChange,
  onDecide,
  onDismiss,
}: {
  response: QueryInterruptedResponse;
  feedback: string;
  onFeedbackChange: (v: string) => void;
  onDecide: (action: ResumeAction) => void;
  onDismiss: () => void;
}) {
  const { interrupt } = response;
  const approveOption = interrupt.options.find((o) => o.action === "approve");
  const rewriteOption = interrupt.options.find((o) => o.action === "rewrite");
  return (
    <section className="hil-card">
      <span className="hil-kicker">확인 필요 — 질의 재작성</span>
      <p className="hil-desc">
        전략 <strong>{interrupt.strategy}</strong> · 원질의를 아래 {interrupt.search_queries.length}건의
        검색쿼리로 변환했습니다.
      </p>
      <div className="hil-queries">
        {interrupt.search_queries.map((q, i) => (
          <span key={i} className="hil-query">
            {i + 1} · {q}
          </span>
        ))}
      </div>
      <div className="hil-actions">
        {approveOption && (
          <button className="btn-primary" onClick={() => onDecide("approve")}>
            {approveOption.label}
          </button>
        )}
        {rewriteOption && (
          <>
            <input
              name="rewrite-feedback"
              value={feedback}
              onChange={(e) => onFeedbackChange(e.target.value)}
              placeholder="재작성 피드백…"
              aria-label="재작성 피드백"
            />
            <button className="btn-secondary" onClick={() => onDecide("rewrite")}>
              {rewriteOption.label}
            </button>
          </>
        )}
        {!approveOption && !rewriteOption && (
          // 알 수 없는 옵션만 오면 버튼이 하나도 없어 진행 불가 — 탈출구를 남긴다.
          <button className="btn-secondary" onClick={onDismiss}>
            진행할 수 없는 요청 — 닫기
          </button>
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
  const [page, setPage] = useState(target.page);
  const [pageInput, setPageInput] = useState(String(target.page));
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setAvailable(null);
    checkPdfAvailable(target.documentId).then(setAvailable);
  }, [target.documentId]);

  // 모달 기본기: 열릴 때 포커스 이동·배경 스크롤 잠금, Escape 닫기, 닫힐 때 포커스 복원.
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      opener?.focus();
    };
  }, [onClose]);

  const goTo = (next: number) => {
    const p = Math.max(1, next);
    setPage(p);
    setPageInput(String(p));
  };

  const submitPage = (e: React.FormEvent) => {
    e.preventDefault();
    const n = Number(pageInput);
    if (Number.isInteger(n) && n >= 1) goTo(n);
    else setPageInput(String(page));
  };

  return (
    <div className="viewer-overlay" onClick={onClose}>
      <div
        className="viewer-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="viewer-title"
        tabIndex={-1}
        ref={panelRef}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="viewer-header">
          <span className="viewer-title" id="viewer-title">
            원문 — {target.documentId} · {page}쪽
          </span>
          {available && (
            <form className="viewer-nav" onSubmit={submitPage}>
              <button type="button" onClick={() => goTo(page - 1)} disabled={page <= 1}>
                ◀ 이전
              </button>
              <input
                name="viewer-page"
                value={pageInput}
                onChange={(e) => setPageInput(e.target.value)}
                inputMode="numeric"
                aria-label="이동할 페이지 번호"
              />
              <span className="viewer-nav-unit">쪽</span>
              <button type="submit">이동</button>
              <button type="button" onClick={() => goTo(page + 1)}>
                다음 ▶
              </button>
            </form>
          )}
          <button type="button" onClick={onClose}>
            닫기
          </button>
        </div>
        <div className="viewer-body">
          {available === null && <p className="notice info">원문 문서를 확인하는 중…</p>}
          {available === false && (
            <p className="notice warning">
              원본 PDF가 서버에 없습니다. 운영 환경에 원본 문서(PDF_DIR)를 배치하면 해당 페이지를 바로
              볼 수 있습니다.
            </p>
          )}
          {available && (
            <iframe
              key={page} /* src의 #page 해시만 바뀌면 내장 PDF 뷰어가 재로딩하지 않아 리마운트로 강제 이동한다 */
              className="viewer-frame"
              title={`${target.documentId} 원문`}
              src={documentPdfUrl(target.documentId, page)}
            />
          )}
        </div>
        {/* 6/14 회의 결정: 한국회계기준원 저작권 표기. PDF 표시 여부(available)와 무관하게 뷰어 모달을 열면 항상 노출한다 */}
        <p className="viewer-copyright">
          ⓒ 한국회계기준원. 본 문서의 저작권은 한국회계기준원에 있으며, 조항 원문 확인 용도로만
          제공됩니다.
        </p>
      </div>
    </div>
  );
}

/** 문단번호 칩 행 — 다발이면 목록, 개수가 많으면 범위 한 칩으로 축약. */
function ParaChips({ paras }: { paras: string[] }) {
  if (paras.length === 0) return null;
  return (
    <div className="para-chips">
      {paraChips(paras).map((p) => (
        <span key={p} className="para-chip">
          {p}
        </span>
      ))}
    </div>
  );
}

/** 기준서 마크다운 본문 렌더 — 편집기호(####·**·표 |)를 글자로 내보내지 않고 해석한다. */
function MarkdownContent({ children }: { children: string }) {
  return (
    <div className="md-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}

/** 조항 본문 — 접힘(첫 문단 발췌) ⇄ 펼침(전문 마크다운 렌더).
 *  전문을 카드에서 빼지 않는 이유: BYO 환경에서는 PDF가 없어 DB content가 유일한 근거다. */
function ClauseContent({ content }: { content: string }) {
  const [open, setOpen] = useState(false);
  if (open) {
    return (
      <div className="clause-expand">
        <MarkdownContent>{content}</MarkdownContent>
        <button type="button" className="more-btn" onClick={() => setOpen(false)}>
          ▴ 접기
        </button>
      </div>
    );
  }
  const excerpt = excerptOf(content);
  return (
    <div className="clause-expand">
      {excerpt.kind === "text" && <p className="clause-excerpt">{excerpt.text}</p>}
      {excerpt.kind === "table-only" && (
        <p className="clause-excerpt is-table-note">표 형태의 조항입니다 — 펼치면 표로 보입니다.</p>
      )}
      <button type="button" className="more-btn" onClick={() => setOpen(true)}>
        ▾ 더보기
      </button>
    </div>
  );
}

function Result({ response }: { response: QueryDoneResponse }) {
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);

  // 타임아웃 폴백은 조항·답변·인용이 모두 비어 있으므로 안내만 간결하게 보여준다.
  if (response.error_code === "TIMEOUT") {
    return (
      <section style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="result-head">
          <span className="result-kicker">K-ACCOUNTING 검토 결과</span>
          <span className="pill warn">처리 시간 초과</span>
        </div>
        <p className="notice warning">
          처리 시간이 초과되어 답변을 생성하지 못했습니다. 일시적인 문제이니 잠시 후 같은 질의로 다시
          시도해 주세요.
        </p>
      </section>
    );
  }

  // 재시도 소진 폴백도 조항·답변·인용이 비어 있으므로 안내만 간결하게 보여준다.
  if (response.error_code === "RECURSION_LIMIT") {
    return (
      <section style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="result-head">
          <span className="result-kicker">K-ACCOUNTING 검토 결과</span>
          <span className="pill warn">처리 중단</span>
        </div>
        <p className="notice warning">
          답변 생성 과정이 지연되거나 무한 반복되어 중단되었습니다.
          조금 더 명확하거나 구체적인 질문을 입력해 주시기 바랍니다.
        </p>
      </section>
    );
  }

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="result-head">
        <span className="result-kicker">K-ACCOUNTING 검토 결과</span>
        {response.is_answerable ? (
          <span className="pill ok">답변 가능</span>
        ) : (
          <span className="pill warn">근거 부족</span>
        )}
        <span className="confidence">
          신뢰도 <strong>{(response.confidence * 100).toFixed(1)}%</strong>
        </span>
      </div>

      {/* NFR-002: 조항 검색이 1순위이므로 답변보다 먼저 노출한다. */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div className="section-head">
          <h3 className="section-title">
            검색된 조항 <span className="accent">상위 {response.clauses.length}건</span>
          </h3>
          <span className="section-note">답변은 아래 조항을 근거로 생성됩니다</span>
        </div>
        {response.clauses.length === 0 ? (
          <p className="muted">검색된 조항 없음</p>
        ) : (
          <div className="clause-list">
            {response.clauses.map((c) => {
              const title = humanNodeTitle(c.node_id, c.document_id);
              return (
                <article key={c.rank} className="clause-card">
                  <div className={`clause-rank r${Math.min(c.rank, 3)}`}>
                    <span className="num">{String(c.rank).padStart(2, "0")}</span>
                    <span className="score">{c.score.toFixed(3)}</span>
                  </div>
                  <div className="clause-body">
                    <div className="clause-title-row">
                      <span className="clause-title">
                        제{c.chapter}장{title && ` · ${title}`}
                      </span>
                      <PageButton
                        documentId={c.document_id}
                        pageStart={c.page_start}
                        pageEnd={c.page_end}
                        onOpen={setViewer}
                      />
                    </div>
                    <ParaChips paras={c.paras} />
                    <ClauseContent content={c.content} />
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>

      <div className="answer-block">
        <h3 className="section-title">답변</h3>
        <p className="answer-text">{response.answer}</p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div className="section-head">
          <h3 className="section-title">
            인용 <span className="accent">{response.citations.length}건</span>
          </h3>
        </div>
        {response.citations.length === 0 ? (
          <p className="muted">인용 없음</p>
        ) : (
          <div className="cite-list">
            {response.citations.map((c, i) => (
              <details key={c.chunk_id} className="cite-card">
                <summary>
                  <strong>[{i + 1}]</strong>
                  {/* 검색된 조항 카드와 같은 표기(제목·칩) — 두 목록에서 같은 조항이 같은 모양으로 보인다 */}
                  {c.document_id} · {humanNodeTitle(c.chunk_id, c.document_id) || c.chunk_id}
                  <ParaChips paras={c.paras} />
                  <span className="rel">관련도 {c.relevance_score.toFixed(2)}</span>
                  <PageButton
                    documentId={c.document_id}
                    pageStart={c.page_start}
                    pageEnd={c.page_end}
                    onOpen={setViewer}
                  />
                </summary>
                <div className="cite-content">
                  <MarkdownContent>{c.content}</MarkdownContent>
                </div>
              </details>
            ))}
          </div>
        )}
      </div>

      {viewer && <PdfViewerModal target={viewer} onClose={() => setViewer(null)} />}
    </section>
  );
}
