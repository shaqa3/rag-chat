import { useRef, useState } from "react";
import { streamChat } from "../api";
import type { Retrieved } from "../types";

interface Turn {
  role: "user" | "assistant";
  text: string;
  sources?: Retrieved[];
  refused?: boolean;
  streaming?: boolean;
  error?: string;
}

const SUGGESTIONS = [
  "How long does Nimbus keep version history on the Pro plan?",
  "What is the API rate limit for a Free token?",
  "What happens if I forget my E2EE passphrase?",
  "How much does the Pro plan cost?",
];

// Split an answer into text + [n] citation chips so citations are clickable.
function renderWithCitations(text: string, sources: Retrieved[] | undefined,
                             onCite: (n: number) => void) {
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (m) {
      const n = parseInt(m[1], 10);
      const valid = sources && n >= 1 && n <= sources.length;
      return (
        <sup
          key={i}
          className={valid ? "cite" : "cite cite-bad"}
          title={valid ? sources![n - 1].doc_title : "unknown citation"}
          onClick={() => valid && onCite(n)}
        >
          [{n}]
        </sup>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export default function ChatPanel({ hybrid }: { hybrid: boolean }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [openSource, setOpenSource] = useState<{ turn: number; cite: number } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollDown = () =>
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
    });

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setInput("");
    setBusy(true);
    setTurns((t) => [
      ...t,
      { role: "user", text: question },
      { role: "assistant", text: "", streaming: true },
    ]);
    scrollDown();

    const patch = (fn: (a: Turn) => Turn) =>
      setTurns((t) => {
        const copy = [...t];
        const last = copy.length - 1;
        copy[last] = fn(copy[last]);
        return copy;
      });

    await streamChat(question, hybrid, {
      onSources: (sources) => { patch((a) => ({ ...a, sources })); scrollDown(); },
      onToken: (text) => { patch((a) => ({ ...a, text: a.text + text })); scrollDown(); },
      onRefusal: (message) =>
        patch((a) => ({ ...a, text: message, refused: true, streaming: false })),
      onError: (message) => patch((a) => ({ ...a, error: message, streaming: false })),
      onDone: () => patch((a) => ({ ...a, streaming: false })),
    });
    setBusy(false);
    scrollDown();
  }

  return (
    <div className="chat">
      <div className="chat-log" ref={scrollRef}>
        {turns.length === 0 && (
          <div className="empty">
            <h2>Chat with your docs</h2>
            <p>
              Ask about the bundled <strong>Nimbus</strong> product corpus. Every
              answer is grounded in retrieved passages and cites them — and the
              assistant refuses when nothing relevant is found.
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => ask(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {turns.map((turn, i) =>
          turn.role === "user" ? (
            <div key={i} className="msg user"><div className="bubble">{turn.text}</div></div>
          ) : (
            <div key={i} className={`msg assistant${turn.refused ? " refused" : ""}`}>
              <div className="bubble">
                {turn.error ? (
                  <span className="err">⚠ {turn.error}</span>
                ) : (
                  <>
                    {renderWithCitations(turn.text, turn.sources, (cite) =>
                      setOpenSource({ turn: i, cite }))}
                    {turn.streaming && <span className="caret" />}
                  </>
                )}
                {turn.refused && <span className="refused-tag">refused · cite-or-refuse</span>}
              </div>

              {turn.sources && turn.sources.length > 0 && (
                <div className="sources">
                  <div className="sources-head">
                    {turn.sources.length} retrieved passage
                    {turn.sources.length > 1 ? "s" : ""}
                  </div>
                  {turn.sources.map((s, n) => {
                    const isOpen = openSource?.turn === i && openSource?.cite === n + 1;
                    return (
                      <div key={s.chunk_id} className={`source${isOpen ? " open" : ""}`}>
                        <button
                          className="source-head"
                          onClick={() =>
                            setOpenSource(isOpen ? null : { turn: i, cite: n + 1 })}
                        >
                          <span className="cite">[{n + 1}]</span>
                          <span className="src-title">{s.doc_title}</span>
                          <span className="src-score">
                            {s.dense != null && `cos ${s.dense.toFixed(3)}`}
                            {s.lexical != null && ` · bm25 ${s.lexical.toFixed(1)}`}
                          </span>
                        </button>
                        {isOpen && <div className="source-body">{s.text}</div>}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ),
        )}
      </div>

      <form
        className="composer"
        onSubmit={(e) => { e.preventDefault(); ask(input); }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the Nimbus docs…"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          {busy ? "…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
