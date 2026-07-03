"""FastAPI application: ingest -> chunk -> embed -> retrieve -> answer (cited).

The lifespan opens the SQLite-backed vector store and, if it's empty, seeds the
bundled sample corpus so the app is useful the moment it boots. The chat
endpoint streams tokens over Server-Sent Events; retrieval and eval are plain
JSON so they're easy to script against.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import settings
from .eval import run_eval
from .ingest import ingest_text, load_evalset, seed_corpus
from .llm import build_prompt, ollama_ready, stream_chat
from .models import (
    ChatRequest, EvalRequest, IngestRequest, IngestResponse, SearchRequest,
)
from .retrieve import best_dense_score, retrieve
from .store import Store

store: Store = Store(settings.data_dir)
_last_eval: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if store.is_empty():
        try:
            n = await seed_corpus(store)
            if n:
                print(f"[rag] seeded {n} sample documents ({store.stats()['chunks']} chunks)")
        except Exception as e:  # e.g. Ollama down and embed_backend=ollama
            print(f"[rag] corpus seeding skipped: {e}")
    yield


app = FastAPI(title="RAG Chat", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "store": store.stats(),
        "ollama_ready": await ollama_ready(),
    }


@app.get("/api/config")
async def get_config():
    return settings.public()


@app.get("/api/documents")
async def list_documents():
    return {"documents": store.documents(), "stats": store.stats()}


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    try:
        doc_id, n = await ingest_text(store, req.title, req.text, req.source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Almost always: embed_backend=ollama but the daemon is unreachable.
        raise HTTPException(status_code=502, detail=f"embedding failed: {e}")
    return IngestResponse(doc_id=doc_id, title=req.title, n_chunks=n)


@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: int):
    if not store.delete_document(doc_id):
        raise HTTPException(status_code=404, detail="document not found")
    return {"deleted": doc_id}


@app.post("/api/search")
async def search(req: SearchRequest):
    """Retrieval inspector — see exactly what the retriever fetches and why."""
    top_k = req.top_k or settings.top_k
    results = await retrieve(
        store, req.query, top_k=top_k, candidate_k=settings.candidate_k, hybrid=req.hybrid
    )
    return {
        "results": [r.to_dict() for r in results],
        "best_dense": best_dense_score(results),
        "min_score": settings.min_score,
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Stream a cited answer over SSE.

    Events: `sources` (once, up front) then many `token` events, then `done`.
    Cite-or-refuse: if the best dense score is below the threshold we emit a
    `refusal` instead of calling the model — no context, no answer.
    """
    top_k = req.top_k or settings.top_k
    results = await retrieve(
        store, req.question, top_k=top_k, candidate_k=settings.candidate_k, hybrid=req.hybrid
    )
    best = best_dense_score(results)

    async def event_stream() -> AsyncIterator[bytes]:
        def sse(event: str, data: dict) -> bytes:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()

        if not results or best < settings.min_score:
            yield sse("refusal", {
                "message": "I couldn't find anything relevant enough in the "
                           "corpus to answer that confidently.",
                "best_dense": best,
                "min_score": settings.min_score,
            })
            yield sse("done", {"refused": True})
            return

        yield sse("sources", {
            "sources": [r.to_dict() for r in results],
            "best_dense": best,
        })
        try:
            async for piece in stream_chat(req.question, [r.text for r in results]):
                yield sse("token", {"text": piece})
        except Exception as e:
            yield sse("error", {"message": f"generation failed: {e}"})
        yield sse("done", {"refused": False})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/eval")
async def evaluate(req: EvalRequest):
    global _last_eval
    evalset = load_evalset()
    if not evalset:
        raise HTTPException(status_code=400, detail="no evalset found")
    if store.is_empty():
        raise HTTPException(status_code=400, detail="corpus is empty")
    top_k = req.top_k or settings.top_k
    _last_eval = await run_eval(store, evalset, hybrid=req.hybrid, top_k=top_k)
    return _last_eval


@app.get("/api/eval/last")
async def last_eval():
    return _last_eval or {"summary": None, "per_question": []}
