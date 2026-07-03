"""Vector store: SQLite for durability + NumPy for search.

Documents and chunks live in SQLite; each chunk's embedding is stored as a
float32 blob. On load we pull all embeddings into one NumPy matrix so vector
search is a single normalised mat-vec (cosine similarity). A tiny in-process
BM25 index over the same chunks gives us a lexical retriever for hybrid search.

This is deliberately a "roll-your-own" vector DB — no Chroma/FAISS/pgvector — so
the whole project runs with just `python` + `numpy`, and the retrieval mechanics
are visible rather than hidden behind a library.
"""

from __future__ import annotations

import math
import os
import re
import sqlite3
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _WORD_RE.findall(text.lower())


@dataclass
class ChunkRow:
    id: int
    doc_id: int
    doc_title: str
    index: int
    text: str


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    title    TEXT NOT NULL,
    source   TEXT,
    n_chunks INTEGER NOT NULL DEFAULT 0,
    created  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id    INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    idx       INTEGER NOT NULL,
    text      TEXT NOT NULL,
    tokens    INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    dim       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
"""


class Store:
    def __init__(self, data_dir: str):
        os.makedirs(data_dir, exist_ok=True)
        self.path = os.path.join(data_dir, "rag.db")
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

        # In-memory search structures, rebuilt from SQLite on load / mutation.
        self._matrix: Optional[np.ndarray] = None      # (n_chunks, dim), L2-normalised
        self._ids: List[int] = []                      # row id per matrix row
        self._rows: Dict[int, ChunkRow] = {}
        self._bm25: Optional[_BM25] = None
        self._reload()

    # ---- mutation ------------------------------------------------------- #

    def add_document(
        self,
        title: str,
        source: str,
        chunks: List[Tuple[str, int]],          # (text, token_estimate)
        embeddings: List[List[float]],
    ) -> int:
        assert len(chunks) == len(embeddings)
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO documents (title, source, n_chunks, created) VALUES (?,?,?, strftime('%s','now'))",
                (title, source, len(chunks)),
            )
            doc_id = cur.lastrowid
            for i, ((text, tokens), emb) in enumerate(zip(chunks, embeddings)):
                arr = np.asarray(emb, dtype=np.float32)
                cur.execute(
                    "INSERT INTO chunks (doc_id, idx, text, tokens, embedding, dim) VALUES (?,?,?,?,?,?)",
                    (doc_id, i, text, tokens, arr.tobytes(), arr.shape[0]),
                )
            self._conn.commit()
        self._reload()
        return doc_id

    def delete_document(self, doc_id: int) -> bool:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
            cur.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            deleted = cur.rowcount > 0
            self._conn.commit()
        self._reload()
        return deleted

    def clear(self) -> None:
        with self._lock:
            self._conn.executescript("DELETE FROM chunks; DELETE FROM documents;")
            self._conn.commit()
        self._reload()

    # ---- read ----------------------------------------------------------- #

    def documents(self) -> List[dict]:
        cur = self._conn.execute(
            "SELECT id, title, source, n_chunks, created FROM documents ORDER BY id"
        )
        return [dict(r) for r in cur.fetchall()]

    def stats(self) -> dict:
        docs = self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chs = self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        dim = self._matrix.shape[1] if self._matrix is not None and self._matrix.size else 0
        return {"documents": docs, "chunks": chs, "dim": dim}

    def get_chunk(self, chunk_id: int) -> Optional[ChunkRow]:
        return self._rows.get(chunk_id)

    def is_empty(self) -> bool:
        return len(self._ids) == 0

    # ---- search --------------------------------------------------------- #

    def search_vector(self, query_vec: List[float], k: int) -> List[Tuple[int, float]]:
        """Return [(chunk_id, cosine)] for the top-k nearest chunks."""
        if self._matrix is None or self._matrix.size == 0:
            return []
        q = np.asarray(query_vec, dtype=np.float32)
        n = np.linalg.norm(q)
        if n > 0:
            q = q / n
        sims = self._matrix @ q                       # rows are pre-normalised
        k = min(k, sims.shape[0])
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]
        return [(self._ids[i], float(sims[i])) for i in top]

    def search_bm25(self, query: str, k: int) -> List[Tuple[int, float]]:
        if self._bm25 is None:
            return []
        return self._bm25.search(_tokenize(query), k)

    # ---- internal ------------------------------------------------------- #

    def _reload(self) -> None:
        cur = self._conn.execute(
            """SELECT c.id, c.doc_id, c.idx, c.text, c.embedding, c.dim, d.title
                 FROM chunks c JOIN documents d ON d.id = c.doc_id
                ORDER BY c.id"""
        )
        rows = cur.fetchall()
        self._ids = []
        self._rows = {}
        vectors: List[np.ndarray] = []
        corpus: List[List[str]] = []
        for r in rows:
            self._ids.append(r["id"])
            self._rows[r["id"]] = ChunkRow(
                id=r["id"], doc_id=r["doc_id"], doc_title=r["title"],
                index=r["idx"], text=r["text"],
            )
            v = np.frombuffer(r["embedding"], dtype=np.float32, count=r["dim"]).copy()
            norm = np.linalg.norm(v)
            if norm > 0:
                v = v / norm
            vectors.append(v)
            corpus.append(_tokenize(r["text"]))

        if vectors:
            self._matrix = np.vstack(vectors)
            self._bm25 = _BM25(corpus, self._ids)
        else:
            self._matrix = None
            self._bm25 = None


class _BM25:
    """Minimal BM25 (Okapi) over the chunk corpus — the lexical half of hybrid
    retrieval. Rare query terms that vector search glosses over (IDs, error
    codes, exact names) are exactly what BM25 nails."""

    def __init__(self, corpus: List[List[str]], ids: List[int], k1: float = 1.5, b: float = 0.75):
        self.ids = ids
        self.k1 = k1
        self.b = b
        self.doc_len = [len(d) for d in corpus]
        self.avg_len = (sum(self.doc_len) / len(corpus)) if corpus else 0.0
        self.freqs: List[Counter] = [Counter(d) for d in corpus]
        df: Dict[str, int] = defaultdict(int)
        for d in self.freqs:
            for term in d:
                df[term] += 1
        n = len(corpus)
        self.idf = {
            t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()
        }

    def search(self, q_tokens: List[str], k: int) -> List[Tuple[int, float]]:
        scores: List[Tuple[int, float]] = []
        for i, freq in enumerate(self.freqs):
            s = 0.0
            for t in q_tokens:
                if t not in freq:
                    continue
                idf = self.idf.get(t, 0.0)
                tf = freq[t]
                denom = tf + self.k1 * (1 - self.b + self.b * self.doc_len[i] / (self.avg_len or 1))
                s += idf * (tf * (self.k1 + 1)) / denom
            if s > 0:
                scores.append((self.ids[i], s))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]
