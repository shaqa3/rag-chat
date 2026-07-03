import { useState } from "react";
import { search } from "../api";
import type { SearchResponse } from "../types";

export default function RetrievalInspector({ hybrid }: { hybrid: boolean }) {
  const [query, setQuery] = useState("");
  const [res, setRes] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    try {
      setRes(await search(query.trim(), hybrid));
    } finally {
      setBusy(false);
    }
  }

  const refuses = res && res.best_dense < res.min_score;

  return (
    <div className="panel">
      <h3>Retrieval inspector</h3>
      <p className="muted small">
        See exactly which chunks the retriever returns and how dense (cosine) and
        lexical (BM25) rankings fuse. This is the {hybrid ? "hybrid" : "dense-only"}{" "}
        retriever.
      </p>
      <form className="row" onSubmit={run}>
        <input
          placeholder="Type a query to inspect retrieval…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit" disabled={busy}>Retrieve</button>
      </form>

      {res && (
        <>
          <div className={`gate ${refuses ? "gate-refuse" : "gate-answer"}`}>
            best cosine {res.best_dense.toFixed(3)} vs threshold {res.min_score} →{" "}
            {refuses ? "would REFUSE" : "would answer"}
          </div>
          <ol className="results">
            {res.results.map((r, i) => (
              <li key={r.chunk_id}>
                <div className="result-head">
                  <span className="cite">[{i + 1}]</span>
                  <span className="src-title">{r.doc_title}</span>
                  <span className="src-score">
                    fused {r.score.toFixed(4)}
                    {r.dense != null && ` · cos ${r.dense.toFixed(3)}`}
                    {r.lexical != null && ` · bm25 ${r.lexical.toFixed(1)}`}
                  </span>
                </div>
                <div className="result-body">{r.text}</div>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
