"""Embedding and chat backends.

Two implementations of each, chosen at runtime by config:

* **ollama**  — calls a local Ollama daemon's HTTP API
  (`/api/embeddings`, `/api/chat` with `stream: true`).
* **offline** — deterministic, dependency-free. Embeddings are a hashed
  bag-of-words projection (lexical, but real cosine geometry); chat is an
  extractive answerer that stitches the most relevant retrieved sentences
  together. This keeps the entire RAG loop runnable in CI and offline.

Everything downstream (chunking, the vector store, retrieval, eval) is
backend-agnostic: it only ever sees vectors and token streams.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import AsyncIterator, List

import httpx

from .config import settings

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _WORD_RE.findall(text.lower())


def _stem(tok: str) -> str:
    """Very light suffix stripping so `limit`/`limits`/`limited` match in the
    offline lexical answerer. Not linguistically correct — just enough to make
    the dependency-free fallback produce decent grounded answers."""
    for suf in ("ing", "ed", "es", "s"):
        if len(tok) > len(suf) + 2 and tok.endswith(suf):
            return tok[: -len(suf)]
    return tok


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #

def _hash_embed(text: str, dim: int) -> List[float]:
    """Deterministic hashed bag-of-words embedding, L2-normalised.

    Each token is hashed into a bucket with a signed weight; repeated tokens
    accumulate. It captures lexical overlap (enough to make retrieval and the
    eval harness meaningful) without any model or network.
    """
    vec = [0.0] * dim
    for tok in _tokenize(text):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts with the configured backend."""
    if settings.embed_backend == "offline":
        return [_hash_embed(t, settings.hash_dim) for t in texts]

    # Ollama: one request per text (the /api/embeddings endpoint is singular).
    out: List[List[float]] = []
    url = f"{settings.ollama_host}/api/embeddings"
    async with httpx.AsyncClient(timeout=60.0) as client:
        for t in texts:
            resp = await client.post(url, json={"model": settings.embed_model, "prompt": t})
            resp.raise_for_status()
            out.append(resp.json()["embedding"])
    return out


async def embed_one(text: str) -> List[float]:
    return (await embed_texts([text]))[0]


# --------------------------------------------------------------------------- #
# Chat / generation
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = (
    "You are a careful assistant that answers strictly from the provided "
    "context passages. Each passage is prefixed with a citation marker like "
    "[1]. Cite the passages you use inline, e.g. 'Nimbus keeps 30 days of "
    "history [2].' If the context does not contain the answer, say you don't "
    "know rather than guessing. Never invent facts or citations."
)


def build_prompt(question: str, contexts: List[str]) -> str:
    """Assemble the user turn: numbered context block + the question."""
    block = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(contexts))
    return (
        f"Context passages:\n{block}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the context above, with inline [n] citations."
    )


def _extractive_answer(question: str, contexts: List[str]) -> str:
    """Offline answerer: pick the sentences most lexically relevant to the
    question and return them with citations. Not clever — but honest, grounded,
    and deterministic, so the RAG loop produces a real cited answer with no LLM.
    """
    q = {_stem(t) for t in _tokenize(question)}
    scored = []
    for i, ctx in enumerate(contexts):
        for sent in re.split(r"(?<=[.!?])\s+", ctx.strip()):
            toks = {_stem(t) for t in _tokenize(sent)}
            if not toks:
                continue
            # Raw overlap count, lightly penalising very long sentences so a
            # specific fact beats a broad topic sentence.
            overlap = len(q & toks) / (1 + len(toks) / 40)
            if overlap > 0:
                scored.append((overlap, i + 1, sent.strip()))
    scored.sort(key=lambda s: s[0], reverse=True)
    if not scored:
        return "I don't know — the retrieved passages don't cover that."
    picked = scored[:3]
    # Keep original passage order for readability.
    picked.sort(key=lambda s: s[1])
    return " ".join(f"{sent} [{cite}]" for _, cite, sent in picked)


async def stream_chat(question: str, contexts: List[str]) -> AsyncIterator[str]:
    """Yield answer text incrementally for the configured backend."""
    if settings.llm_backend == "offline":
        answer = _extractive_answer(question, contexts)
        # Stream word-by-word so the frontend exercises the same SSE path.
        for word in answer.split(" "):
            yield word + " "
        return

    url = f"{settings.ollama_host}/api/chat"
    payload = {
        "model": settings.chat_model,
        "stream": True,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(question, contexts)},
        ],
    }
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                import json

                data = json.loads(line)
                piece = data.get("message", {}).get("content", "")
                if piece:
                    yield piece
                if data.get("done"):
                    break


async def ollama_ready() -> bool:
    """Best-effort probe so the UI can warn when the daemon is down."""
    if settings.embed_backend == "offline" and settings.llm_backend == "offline":
        return True
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{settings.ollama_host}/api/tags")
            return r.status_code == 200
    except Exception:
        return False
