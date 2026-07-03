.PHONY: install backend backend-offline frontend dev ollama-setup eval docker clean

# One-time setup: Python venv + npm deps.
install:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
	cd frontend && npm install

# Pull the Ollama models the app expects (needs `ollama serve` running).
ollama-setup:
	ollama pull nomic-embed-text
	ollama pull llama3.2

# Run the API on :8000 against a local Ollama daemon (default backend).
backend:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Run the API on :8000 with NO external dependency (hash embeddings + extractive
# answers). Handy for a demo or a machine without Ollama.
backend-offline:
	cd backend && . .venv/bin/activate && \
		RAG_EMBED_BACKEND=offline RAG_LLM_BACKEND=offline \
		uvicorn app.main:app --reload --port 8000

# Run the chat UI on :5173 (proxies /api -> :8000).
frontend:
	cd frontend && npm run dev

# Run both together (Ollama backend).
dev:
	@echo "Starting backend (:8000) and chat UI (:5173)..."
	@trap 'kill 0' INT; \
	( cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000 ) & \
	( cd frontend && npm run dev ) & \
	wait

# Run the eval harness from the CLI (offline backend) and print the summary.
# This is README Experiment 1; sweep it with `RAG_CHUNK_TOKENS=<n> make eval`.
eval:
	cd backend && . .venv/bin/activate && \
		RAG_EMBED_BACKEND=offline RAG_LLM_BACKEND=offline python -m app.evalcli

# Single eval run against real Ollama (needs `ollama serve` + models pulled).
eval-ollama:
	cd backend && . .venv/bin/activate && python -m app.evalcli

# Repeated eval against real Ollama with mean/range aggregation — README
# Experiment 2. Set RAG_EVAL_RUNS to change the run count (default 5).
eval-repeats:
	cd backend && . .venv/bin/activate && python -m app.eval_repeats

docker:
	docker compose up --build

clean:
	rm -rf backend/.venv backend/data/rag.db frontend/node_modules frontend/dist
