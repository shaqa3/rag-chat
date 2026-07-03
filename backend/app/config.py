"""Runtime configuration, all overridable via environment variables.

The two backends (`embed` and `llm`) can each be `ollama` (talk to a local
Ollama daemon) or `offline` (deterministic, dependency-free). The offline
backend lets the whole RAG loop — chunk → embed → retrieve → answer → cite —
run in CI and without a GPU, which is what the smoke test and eval harness use.
"""

import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass
class Settings:
    # Where the SQLite index and any uploaded corpus live.
    data_dir: str = field(default_factory=lambda: _env("RAG_DATA_DIR", "data"))

    # Backends: "ollama" | "offline".
    embed_backend: str = field(default_factory=lambda: _env("RAG_EMBED_BACKEND", "ollama"))
    llm_backend: str = field(default_factory=lambda: _env("RAG_LLM_BACKEND", "ollama"))

    # Ollama connection + model names.
    ollama_host: str = field(default_factory=lambda: _env("OLLAMA_HOST", "http://localhost:11434"))
    embed_model: str = field(default_factory=lambda: _env("RAG_EMBED_MODEL", "nomic-embed-text"))
    chat_model: str = field(default_factory=lambda: _env("RAG_CHAT_MODEL", "llama3.2"))

    # Offline hash-embedding dimensionality (only used when embed_backend=offline).
    hash_dim: int = field(default_factory=lambda: int(_env("RAG_HASH_DIM", "384")))

    # Chunking defaults (approximate tokens; a "token" ~= 0.75 words).
    chunk_tokens: int = field(default_factory=lambda: int(_env("RAG_CHUNK_TOKENS", "220")))
    chunk_overlap: int = field(default_factory=lambda: int(_env("RAG_CHUNK_OVERLAP", "40")))

    # Retrieval defaults.
    top_k: int = field(default_factory=lambda: int(_env("RAG_TOP_K", "5")))
    candidate_k: int = field(default_factory=lambda: int(_env("RAG_CANDIDATE_K", "20")))
    # Cite-or-refuse: if the best retrieval score is below this, refuse to answer.
    min_score: float = field(default_factory=lambda: float(_env("RAG_MIN_SCORE", "0.15")))

    def public(self) -> Dict[str, Any]:
        """Config safe to expose to the frontend (no secrets here anyway)."""
        d = asdict(self)
        return d


settings = Settings()
