import type {
  Config, DocInfo, EvalResult, Health, Retrieved, SearchResponse, StoreStats,
} from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "content-type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const getHealth = () => req<Health>("/health");
export const getConfig = () => req<Config>("/config");
export const listDocuments = () =>
  req<{ documents: DocInfo[]; stats: StoreStats }>("/documents");
export const ingest = (title: string, text: string) =>
  req<{ doc_id: number; title: string; n_chunks: number }>("/ingest", {
    method: "POST",
    body: JSON.stringify({ title, text }),
  });
export const deleteDocument = (id: number) =>
  req<{ deleted: number }>(`/documents/${id}`, { method: "DELETE" });
export const search = (query: string, hybrid: boolean, top_k?: number) =>
  req<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify({ query, hybrid, top_k }),
  });
export const runEval = (hybrid: boolean) =>
  req<EvalResult>("/eval", { method: "POST", body: JSON.stringify({ hybrid }) });

// ---- streaming chat over SSE --------------------------------------------- //

export interface ChatCallbacks {
  onSources: (sources: Retrieved[], bestDense: number) => void;
  onToken: (text: string) => void;
  onRefusal: (message: string, bestDense: number, minScore: number) => void;
  onError: (message: string) => void;
  onDone: () => void;
}

/**
 * POST /api/chat returns a text/event-stream. We parse the SSE frames by hand
 * (the browser EventSource API is GET-only, and we need to POST the question).
 */
export async function streamChat(
  question: string,
  hybrid: boolean,
  cb: ChatCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, hybrid }),
    signal,
  });
  if (!res.ok || !res.body) {
    cb.onError(`chat failed: ${res.status} ${res.statusText}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (frame: string) => {
    let event = "message";
    let data = "";
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    if (!data) return;
    const payload = JSON.parse(data);
    switch (event) {
      case "sources": return cb.onSources(payload.sources, payload.best_dense);
      case "token": return cb.onToken(payload.text);
      case "refusal":
        return cb.onRefusal(payload.message, payload.best_dense, payload.min_score);
      case "error": return cb.onError(payload.message);
      case "done": return cb.onDone();
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      if (frame.trim()) dispatch(frame);
    }
  }
}
