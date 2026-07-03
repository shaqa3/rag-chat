#!/usr/bin/env bash
#
# start.sh — one command to run RAG Chat locally.
#
# Handles first-run setup (venv + npm install), checks that Ollama is reachable
# (or falls back to the dependency-free offline backend), frees stale ports,
# starts the backend (:8000) and frontend (:5173), and opens the browser.
#
# Usage:
#   ./start.sh              # run against Ollama (default)
#   ./start.sh --offline    # hash embeddings + extractive answers, no Ollama
#   ./start.sh --no-open    # don't auto-open the browser
#
set -eu

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$REPO/backend"
FRONTEND="$REPO/frontend"
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OFFLINE=0
OPEN=1

for arg in "$@"; do
  case "$arg" in
    --offline) OFFLINE=1 ;;
    --no-open) OPEN=0 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

info() { printf '\033[36m▸\033[0m %s\n' "$1"; }
warn() { printf '\033[33m!\033[0m %s\n' "$1"; }

# --- first-run setup -------------------------------------------------------- #
if [ ! -d "$BACKEND/.venv" ]; then
  info "Creating Python venv and installing backend deps (first run)…"
  python3 -m venv "$BACKEND/.venv"
  # shellcheck disable=SC1091
  . "$BACKEND/.venv/bin/activate"
  pip install -q -r "$BACKEND/requirements.txt"
else
  # shellcheck disable=SC1091
  . "$BACKEND/.venv/bin/activate"
fi

if [ ! -d "$FRONTEND/node_modules" ]; then
  info "Installing frontend deps (first run)…"
  (cd "$FRONTEND" && npm install)
fi

# --- backend selection ------------------------------------------------------ #
if [ "$OFFLINE" -eq 1 ]; then
  export RAG_EMBED_BACKEND=offline RAG_LLM_BACKEND=offline
  info "Backend mode: offline (no Ollama needed)."
else
  if curl -sf --max-time 3 "$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then
    info "Ollama reachable at $OLLAMA_HOST."
  else
    warn "Ollama not reachable at $OLLAMA_HOST."
    warn "Start it with 'ollama serve' (or 'brew services start ollama') and"
    warn "pull models: ollama pull nomic-embed-text && ollama pull llama3.2"
    warn "Falling back to the offline backend for this run."
    export RAG_EMBED_BACKEND=offline RAG_LLM_BACKEND=offline
  fi
fi

# --- free stale ports ------------------------------------------------------- #
pkill -f "uvicorn app.main:app" >/dev/null 2>&1 || true
pkill -f "vite" >/dev/null 2>&1 || true
sleep 1

# --- start both services ---------------------------------------------------- #
trap 'echo; info "Shutting down…"; kill 0' EXIT INT TERM

info "Starting backend on :8000…"
(cd "$BACKEND" && uvicorn app.main:app --port 8000) &

info "Starting frontend on :5173…"
(cd "$FRONTEND" && npm run dev) &

# --- wait for readiness, then open the browser ------------------------------ #
for _ in $(seq 1 30); do
  if curl -sf -o /dev/null "http://localhost:5173/"; then break; fi
  sleep 0.5
done

info "RAG Chat is running → http://localhost:5173  (Ctrl-C to stop)"
if [ "$OPEN" -eq 1 ] && command -v open >/dev/null 2>&1; then
  open "http://localhost:5173"
fi

wait
