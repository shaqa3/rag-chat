"""Ingestion: raw text -> chunks -> embeddings -> store, plus corpus seeding."""

from __future__ import annotations

import json
import os
from typing import List, Tuple

from .chunk import chunk_text
from .config import settings
from .llm import embed_texts
from .store import Store


async def ingest_text(store: Store, title: str, text: str, source: str = "upload") -> Tuple[int, int]:
    """Chunk, embed, and persist one document. Returns (doc_id, n_chunks)."""
    chunks = chunk_text(text, settings.chunk_tokens, settings.chunk_overlap)
    if not chunks:
        raise ValueError("document produced no chunks")
    embeddings = await embed_texts([c.text for c in chunks])
    payload: List[Tuple[str, int]] = [(c.text, c.token_estimate) for c in chunks]
    doc_id = store.add_document(title, source, payload, embeddings)
    return doc_id, len(chunks)


def corpus_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "data", "corpus")


async def seed_corpus(store: Store) -> int:
    """Load the bundled sample corpus (once, if the store is empty).

    Returns the number of documents ingested.
    """
    d = corpus_dir()
    if not os.path.isdir(d):
        return 0
    n = 0
    for fname in sorted(os.listdir(d)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(d, fname)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        # First markdown heading (or filename) becomes the title.
        title = fname[:-3]
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        await ingest_text(store, title, text, source=f"corpus/{fname}")
        n += 1
    return n


def load_evalset() -> list:
    path = os.path.join(os.path.dirname(__file__), "..", "data", "evalset.json")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)
