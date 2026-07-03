import { useState } from "react";
import { deleteDocument, ingest } from "../api";
import type { DocInfo, StoreStats } from "../types";

interface Props {
  documents: DocInfo[];
  stats: StoreStats | null;
  onChange: () => void;
}

export default function DocumentsPanel({ documents, stats, onChange }: Props) {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !text.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await ingest(title.trim(), text.trim());
      setMsg(`Ingested “${r.title}” → ${r.n_chunks} chunks embedded.`);
      setTitle("");
      setText("");
      onChange();
    } catch (err) {
      setMsg(`Error: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    await deleteDocument(id);
    onChange();
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const content = await file.text();
    setText(content);
    if (!title) setTitle(file.name.replace(/\.[^.]+$/, ""));
  }

  return (
    <div className="panel">
      <h3>Corpus</h3>
      {stats && (
        <p className="muted">
          {stats.documents} documents · {stats.chunks} chunks · {stats.dim}-dim
          embeddings
        </p>
      )}

      <ul className="doclist">
        {documents.map((d) => (
          <li key={d.id}>
            <div>
              <div className="doc-title">{d.title}</div>
              <div className="muted small">{d.source} · {d.n_chunks} chunks</div>
            </div>
            <button className="ghost danger" onClick={() => remove(d.id)}>
              delete
            </button>
          </li>
        ))}
      </ul>

      <form className="ingest-form" onSubmit={add}>
        <h4>Add a document</h4>
        <input
          placeholder="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <textarea
          placeholder="Paste text, or load a .txt / .md file below…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
        />
        <div className="row">
          <input type="file" accept=".txt,.md,.markdown" onChange={onFile} />
          <button type="submit" disabled={busy}>
            {busy ? "Embedding…" : "Ingest"}
          </button>
        </div>
        {msg && <p className="muted small">{msg}</p>}
      </form>
    </div>
  );
}
