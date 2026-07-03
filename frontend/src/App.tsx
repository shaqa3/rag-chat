import { useCallback, useEffect, useState } from "react";
import { getConfig, getHealth, listDocuments } from "./api";
import type { Config, DocInfo, Health, StoreStats } from "./types";
import ChatPanel from "./components/ChatPanel";
import DocumentsPanel from "./components/DocumentsPanel";
import RetrievalInspector from "./components/RetrievalInspector";
import EvalPanel from "./components/EvalPanel";

type Tab = "chat" | "retrieval" | "eval";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [documents, setDocuments] = useState<DocInfo[]>([]);
  const [stats, setStats] = useState<StoreStats | null>(null);
  const [tab, setTab] = useState<Tab>("chat");
  const [hybrid, setHybrid] = useState(true);

  const refresh = useCallback(async () => {
    const [h, d] = [await getHealth(), await listDocuments()];
    setHealth(h);
    setDocuments(d.documents);
    setStats(d.stats);
  }, []);

  useEffect(() => {
    getConfig().then(setConfig).catch(() => {});
    refresh().catch(() => {});
  }, [refresh]);

  const usingOllama =
    config && (config.embed_backend === "ollama" || config.llm_backend === "ollama");
  const ollamaDown = usingOllama && health && !health.ollama_ready;

  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className="logo">◆</span>
          <div>
            <h1>RAG Chat</h1>
            <span className="tagline">chat with your docs · retrieval + evals</span>
          </div>
        </div>

        <div className="header-right">
          {config && (
            <div className="backend">
              <span className="chip">
                embed: {config.embed_backend === "ollama"
                  ? config.embed_model : "offline hash"}
              </span>
              <span className="chip">
                llm: {config.llm_backend === "ollama"
                  ? config.chat_model : "offline extractive"}
              </span>
              <span className={`chip ${ollamaDown ? "chip-bad" : "chip-ok"}`}>
                {usingOllama
                  ? ollamaDown ? "ollama offline" : "ollama ready"
                  : "no daemon needed"}
              </span>
            </div>
          )}
          <label className="toggle">
            <input
              type="checkbox"
              checked={hybrid}
              onChange={(e) => setHybrid(e.target.checked)}
            />
            hybrid rerank
          </label>
        </div>
      </header>

      {ollamaDown && (
        <div className="banner">
          Ollama isn't reachable at <code>{config!.ollama_host}</code>. Start it with{" "}
          <code>ollama serve</code> and pull the models
          (<code>ollama pull {config!.embed_model}</code>,{" "}
          <code>ollama pull {config!.chat_model}</code>), or run the backend with{" "}
          <code>RAG_EMBED_BACKEND=offline RAG_LLM_BACKEND=offline</code>.
        </div>
      )}

      <nav className="tabs">
        <button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>
          Chat
        </button>
        <button className={tab === "retrieval" ? "active" : ""} onClick={() => setTab("retrieval")}>
          Retrieval
        </button>
        <button className={tab === "eval" ? "active" : ""} onClick={() => setTab("eval")}>
          Evals
        </button>
      </nav>

      <main>
        <section className="main-col">
          {tab === "chat" && <ChatPanel hybrid={hybrid} />}
          {tab === "retrieval" && <RetrievalInspector hybrid={hybrid} />}
          {tab === "eval" && <EvalPanel />}
        </section>
        <aside className="side-col">
          <DocumentsPanel documents={documents} stats={stats} onChange={refresh} />
        </aside>
      </main>
    </div>
  );
}
