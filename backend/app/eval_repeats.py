"""Repeated eval runner: `python -m app.eval_repeats`.

Runs the labelled eval set N times through both the hybrid and dense-only
retrievers and aggregates. This is what produces the README's *Experiment 2*
numbers.

Why repeat? Retrieval is deterministic (embeddings are fixed), so hit@k and MRR
are identical every run. But answer generation is **not** — `llama3.2` sampling
means coverage / grounded / accuracy wobble run to run. Reporting a single run
would over- or under-sell the answer quality; we report the mean and the
[min–max] range instead so the noise is visible.

The corpus is seeded once and reused across runs (re-embedding every run would
be wasted work and wouldn't change retrieval). Set `RAG_EVAL_RUNS` to change N.

Run against real Ollama (the default backends):

    python -m app.eval_repeats           # or: make eval-repeats
"""

import asyncio
import os
import statistics
from typing import List, Tuple

from .config import settings
from .eval import run_eval
from .ingest import load_evalset, seed_corpus
from .store import Store

RUNS = int(os.environ.get("RAG_EVAL_RUNS", "5"))


def _agg(summaries: List[dict], metric: str) -> Tuple[float, float, float]:
    vals = [s[metric] for s in summaries]
    return min(vals), statistics.mean(vals), max(vals)


async def main() -> None:
    store = Store(settings.data_dir)
    if store.is_empty():
        n = await seed_corpus(store)
        print(f"seeded {n} documents ({store.stats()['chunks']} chunks)\n")

    evalset = load_evalset()
    if not evalset:
        print("no evalset found")
        return

    print(f"backend: embed={settings.embed_backend} llm={settings.llm_backend} "
          f"| chunk_tokens={settings.chunk_tokens} top_k={settings.top_k} "
          f"| {RUNS} runs\n")

    runs = {"hybrid": [], "dense": []}
    for i in range(RUNS):
        h = (await run_eval(store, evalset, hybrid=True, top_k=settings.top_k))["summary"]
        d = (await run_eval(store, evalset, hybrid=False, top_k=settings.top_k))["summary"]
        runs["hybrid"].append(h)
        runs["dense"].append(d)
        print(f"run {i + 1}: hybrid cov={h['answer_coverage']:.2f} "
              f"grnd={h['grounded_rate']:.2f} acc={h['accuracy']:.2f} | "
              f"dense cov={d['answer_coverage']:.2f} grnd={d['grounded_rate']:.2f} "
              f"acc={d['accuracy']:.2f}")

    print("\n=== retrieval (deterministic) ===")
    for key in ("hybrid", "dense"):
        s = runs[key][0]
        print(f"{key:<8} hit@k={s['hit_at_k']:.2f}  MRR={s['mrr']:.3f}")

    print("\n=== answer metrics (mean [min-max] over runs) ===")
    for key in ("hybrid", "dense"):
        cov = _agg(runs[key], "answer_coverage")
        gr = _agg(runs[key], "grounded_rate")
        ac = _agg(runs[key], "accuracy")
        print(f"{key:<8} coverage={cov[1]:.2f} [{cov[0]:.2f}-{cov[2]:.2f}]  "
              f"grounded={gr[1]:.2f} [{gr[0]:.2f}-{gr[2]:.2f}]  "
              f"accuracy={ac[1]:.2f} [{ac[0]:.2f}-{ac[2]:.2f}]")


if __name__ == "__main__":
    asyncio.run(main())
