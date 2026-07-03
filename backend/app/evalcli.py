"""Command-line eval runner: `python -m app.evalcli`.

Boots the store (seeding the sample corpus if empty), runs the labelled eval set
through both the hybrid and dense-only retrievers, and prints a comparison table.
This is what produces the numbers quoted in the README — re-run it after changing
chunk size, the embedding model, or the retriever to reproduce an experiment.
"""

import asyncio

from .config import settings
from .eval import run_eval
from .ingest import load_evalset, seed_corpus
from .store import Store


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
          f"| chunk_tokens={settings.chunk_tokens} overlap={settings.chunk_overlap} "
          f"top_k={settings.top_k}\n")

    header = f"{'retriever':<24}{'hit@k':>8}{'MRR':>8}{'coverage':>10}{'grounded':>10}{'accuracy':>10}"
    print(header)
    print("-" * len(header))
    for label, hybrid in [("hybrid (dense+BM25 RRF)", True), ("dense only", False)]:
        res = await run_eval(store, evalset, hybrid=hybrid, top_k=settings.top_k)
        s = res["summary"]
        print(f"{label:<24}{s['hit_at_k']:>8.2f}{s['mrr']:>8.3f}"
              f"{s['answer_coverage']:>10.2f}{s['grounded_rate']:>10.2f}{s['accuracy']:>10.2f}")


if __name__ == "__main__":
    asyncio.run(main())
