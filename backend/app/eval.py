"""Evaluation harness — the actual differentiator.

For every labelled question we measure two layers independently, because RAG can
fail at either:

Retrieval quality (did we fetch the right chunk?)
    * hit@k       — a chunk from the labelled relevant document is in the top-k.
    * MRR         — 1/rank of the first relevant chunk (0 if none), averaged.

Answer quality (given the context, is the answer right and grounded?)
    * keyword coverage — fraction of expected answer keywords present.
    * grounded         — the answer carries at least one [n] citation.
    * refusal handling — for `answerable: false` questions, the *correct*
      behaviour is to refuse; we score whether the system did.

Running the same set with `hybrid` on vs off is how the README's "which reranker
/ chunk size wins" numbers are produced.
"""

from __future__ import annotations

import re
from typing import List

from .config import settings
from .llm import stream_chat
from .retrieve import best_dense_score, retrieve
from .store import Store

_CITE_RE = re.compile(r"\[\d+\]")


def _coverage(answer: str, keywords: List[str]) -> float:
    if not keywords:
        return 1.0
    low = answer.lower()
    hit = sum(1 for k in keywords if k.lower() in low)
    return hit / len(keywords)


async def _answer(question: str, contexts: List[str]) -> str:
    parts = []
    async for piece in stream_chat(question, contexts):
        parts.append(piece)
    return "".join(parts).strip()


async def run_eval(store: Store, evalset: list, hybrid: bool, top_k: int) -> dict:
    per_question = []
    for item in evalset:
        q = item["question"]
        answerable = item.get("answerable", True)
        relevant = (item.get("relevant_doc") or "").lower()
        keywords = item.get("expect_keywords", [])

        results = await retrieve(
            store, q, top_k=top_k, candidate_k=settings.candidate_k, hybrid=hybrid
        )

        # --- retrieval metrics ---
        rank_of_relevant = 0
        for i, r in enumerate(results):
            if relevant and relevant in r.doc_title.lower():
                rank_of_relevant = i + 1
                break
        hit = rank_of_relevant > 0
        rr = (1.0 / rank_of_relevant) if rank_of_relevant else 0.0

        # --- answer metrics ---
        best = best_dense_score(results)
        refused = best < settings.min_score
        if refused:
            answer = "(refused — retrieval below confidence threshold)"
        else:
            answer = await _answer(q, [r.text for r in results])

        grounded = bool(_CITE_RE.search(answer))
        coverage = 0.0 if refused else _coverage(answer, keywords)

        if answerable:
            # Correct = retrieved the doc, answered, covered the keywords.
            correct = hit and not refused and coverage >= 0.5
        else:
            # Correct = refused (or clearly declined) on an out-of-corpus question.
            correct = refused or "don't know" in answer.lower()

        per_question.append({
            "question": q,
            "answerable": answerable,
            "hit": hit,
            "reciprocal_rank": round(rr, 3),
            "best_dense": round(best, 3),
            "refused": refused,
            "grounded": grounded,
            "coverage": round(coverage, 3),
            "correct": bool(correct),
            "answer": answer,
        })

    answerable_qs = [p for p in per_question if p["answerable"]]
    n = len(per_question) or 1
    na = len(answerable_qs) or 1
    summary = {
        "n_questions": len(per_question),
        "hit_at_k": round(sum(p["hit"] for p in answerable_qs) / na, 3),
        "mrr": round(sum(p["reciprocal_rank"] for p in answerable_qs) / na, 3),
        "answer_coverage": round(sum(p["coverage"] for p in answerable_qs) / na, 3),
        "grounded_rate": round(sum(p["grounded"] for p in answerable_qs) / na, 3),
        "accuracy": round(sum(p["correct"] for p in per_question) / n, 3),
        "hybrid": hybrid,
        "top_k": top_k,
    }
    return {"summary": summary, "per_question": per_question}
