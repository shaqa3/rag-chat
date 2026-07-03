"""Retrieval: dense + lexical + fusion reranking.

Given a query we run two retrievers over the candidate pool:

* **dense**  — cosine over Ollama (or offline) embeddings; good at paraphrase
  and meaning.
* **lexical** — BM25; good at exact terms, names, codes.

We fuse their rankings with **Reciprocal Rank Fusion** (RRF), the reranking
pass: a chunk that ranks well in *either* retriever floats to the top, and one
that ranks well in *both* wins. RRF needs no score calibration between the two
very different score scales, which is why it's a robust default reranker.

`hybrid=False` falls back to pure dense retrieval so the eval harness can
measure what the rerank actually buys.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from .llm import embed_one
from .store import Store

RRF_K = 60  # standard RRF damping constant


@dataclass
class Retrieved:
    chunk_id: int
    doc_id: int
    doc_title: str
    index: int
    text: str
    score: float                 # fused score used for ranking / refusal
    dense: Optional[float] = None
    lexical: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _rrf(rank: int) -> float:
    return 1.0 / (RRF_K + rank)


async def retrieve(
    store: Store,
    query: str,
    top_k: int,
    candidate_k: int,
    hybrid: bool = True,
) -> List[Retrieved]:
    q_vec = await embed_one(query)
    dense = store.search_vector(q_vec, candidate_k)
    dense_score = {cid: s for cid, s in dense}

    if not hybrid:
        ranked = [(cid, s) for cid, s in dense]
        out = []
        for cid, s in ranked[:top_k]:
            row = store.get_chunk(cid)
            if row:
                out.append(Retrieved(
                    chunk_id=cid, doc_id=row.doc_id, doc_title=row.doc_title,
                    index=row.index, text=row.text, score=s, dense=s,
                ))
        return out

    lexical = store.search_bm25(query, candidate_k)
    lex_score = {cid: s for cid, s in lexical}

    # Fuse by reciprocal rank across both lists.
    fused: Dict[int, float] = {}
    for rank, (cid, _) in enumerate(dense):
        fused[cid] = fused.get(cid, 0.0) + _rrf(rank)
    for rank, (cid, _) in enumerate(lexical):
        fused[cid] = fused.get(cid, 0.0) + _rrf(rank)

    ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:top_k]
    out: List[Retrieved] = []
    for cid, fused_score in ranked:
        row = store.get_chunk(cid)
        if not row:
            continue
        out.append(Retrieved(
            chunk_id=cid, doc_id=row.doc_id, doc_title=row.doc_title,
            index=row.index, text=row.text,
            score=fused_score,
            dense=dense_score.get(cid),
            lexical=lex_score.get(cid),
        ))
    return out


def best_dense_score(results: List[Retrieved]) -> float:
    """Highest cosine among results — the signal for cite-or-refuse.

    We use the raw dense cosine (not the fused RRF score) for the refusal gate
    because cosine has an absolute, interpretable scale; RRF scores don't.
    """
    vals = [r.dense for r in results if r.dense is not None]
    return max(vals) if vals else 0.0
