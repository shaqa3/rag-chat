"""Chunking.

A chunk is the unit of retrieval, so its size is the single biggest lever on
retrieval quality — too big and embeddings blur across topics; too small and a
chunk loses the context needed to answer. We split on paragraph then sentence
boundaries and pack sentences into overlapping windows of ~`target_tokens`
tokens. Overlap keeps facts that straddle a boundary retrievable from either
side.

Token counts are approximated as `words / 0.75` (~1.33 tokens/word), which is
close enough to real tokenizers for sizing and keeps us dependency-free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_WORDS_PER_TOKEN = 0.75


@dataclass
class Chunk:
    text: str
    index: int          # position within its document
    token_estimate: int


def _approx_tokens(text: str) -> int:
    return max(1, round(len(text.split()) / _WORDS_PER_TOKEN))


def _sentences(text: str) -> List[str]:
    out: List[str] = []
    for para in re.split(r"\n{2,}", text.strip()):
        para = para.strip()
        if not para:
            continue
        for sent in _SENT_SPLIT.split(para):
            sent = sent.strip()
            if sent:
                out.append(sent)
    return out


def chunk_text(text: str, target_tokens: int, overlap_tokens: int) -> List[Chunk]:
    """Pack sentences into overlapping ~target_tokens windows.

    `overlap_tokens` worth of trailing sentences are carried into the next
    window so a fact spanning a boundary stays retrievable from both chunks.
    """
    sents = _sentences(text)
    if not sents:
        return []

    chunks: List[Chunk] = []
    window: List[str] = []
    window_tokens = 0
    idx = 0

    def flush() -> List[str]:
        nonlocal window, window_tokens
        joined = " ".join(window)
        chunks.append(Chunk(text=joined, index=len(chunks), token_estimate=_approx_tokens(joined)))
        # Carry trailing sentences to reach the overlap budget.
        carry: List[str] = []
        carry_tokens = 0
        for sent in reversed(window):
            t = _approx_tokens(sent)
            if carry_tokens + t > overlap_tokens:
                break
            carry.insert(0, sent)
            carry_tokens += t
        window = carry
        window_tokens = carry_tokens
        return window

    while idx < len(sents):
        sent = sents[idx]
        t = _approx_tokens(sent)
        # A single oversized sentence becomes its own chunk.
        if t >= target_tokens and not window:
            chunks.append(Chunk(text=sent, index=len(chunks), token_estimate=t))
            idx += 1
            continue
        if window_tokens + t > target_tokens and window:
            flush()
            continue
        window.append(sent)
        window_tokens += t
        idx += 1

    if window:
        joined = " ".join(window)
        chunks.append(Chunk(text=joined, index=len(chunks), token_estimate=_approx_tokens(joined)))

    # Re-number (flush() appended before we knew the final count is fine, but be safe).
    for i, c in enumerate(chunks):
        c.index = i
    return chunks
