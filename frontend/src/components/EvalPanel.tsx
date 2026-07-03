import { useState } from "react";
import { runEval } from "../api";
import type { EvalResult, EvalSummary } from "../types";

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="metric">
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
      {hint && <div className="metric-hint">{hint}</div>}
    </div>
  );
}

function SummaryRow({ s, tag }: { s: EvalSummary; tag: string }) {
  return (
    <div className="eval-summary">
      <div className="eval-tag">{tag}</div>
      <Metric label="hit@k" value={s.hit_at_k.toFixed(2)} />
      <Metric label="MRR" value={s.mrr.toFixed(3)} />
      <Metric label="answer coverage" value={s.answer_coverage.toFixed(2)} />
      <Metric label="grounded" value={s.grounded_rate.toFixed(2)} />
      <Metric label="accuracy" value={s.accuracy.toFixed(2)} />
    </div>
  );
}

export default function EvalPanel() {
  const [hybrid, setHybrid] = useState<EvalResult | null>(null);
  const [dense, setDense] = useState<EvalResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    try {
      // Run the labelled set through both retrievers to compare rerank vs dense.
      const [h, d] = [await runEval(true), await runEval(false)];
      setHybrid(h);
      setDense(d);
    } finally {
      setBusy(false);
    }
  }

  const rows = hybrid?.per_question ?? [];

  return (
    <div className="panel">
      <h3>Evaluation harness</h3>
      <p className="muted small">
        A labelled question set scored on retrieval (hit@k, MRR) and answer
        quality (keyword coverage, grounded rate, accuracy). Runs the same set
        with hybrid reranking on and off so the numbers justify the design.
      </p>
      <button onClick={run} disabled={busy}>
        {busy ? "Running…" : "Run evaluation"}
      </button>

      {hybrid?.summary && <SummaryRow s={hybrid.summary} tag="hybrid (dense + BM25 · RRF)" />}
      {dense?.summary && <SummaryRow s={dense.summary} tag="dense only" />}

      {hybrid?.summary && dense?.summary && (
        <p className="muted small delta">
          Reranking moves MRR {dense.summary.mrr.toFixed(3)} →{" "}
          {hybrid.summary.mrr.toFixed(3)} (
          {(hybrid.summary.mrr - dense.summary.mrr >= 0 ? "+" : "")}
          {(hybrid.summary.mrr - dense.summary.mrr).toFixed(3)}).
        </p>
      )}

      {rows.length > 0 && (
        <table className="eval-table">
          <thead>
            <tr>
              <th>Question</th><th>hit</th><th>RR</th><th>cov</th>
              <th>grounded</th><th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((q, i) => (
              <tr key={i} className={q.correct ? "ok" : "bad"}>
                <td>
                  {q.question}
                  {!q.answerable && <span className="pill">out-of-corpus</span>}
                </td>
                <td>{q.answerable ? (q.hit ? "✓" : "✗") : "—"}</td>
                <td>{q.answerable ? q.reciprocal_rank.toFixed(2) : "—"}</td>
                <td>{q.refused ? "refused" : q.coverage.toFixed(2)}</td>
                <td>{q.grounded ? "✓" : "—"}</td>
                <td>{q.correct ? "✓" : "✗"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
