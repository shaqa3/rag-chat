#!/usr/bin/env bash
#
# stop.sh — stop the local RAG Chat services.
#
# By default stops just the app (backend :8000 + frontend :5173). Pass --ollama
# to also stop the Ollama daemon — this is only needed if you started it for
# this project and want it fully shut down.
#
# Usage:
#   ./stop.sh              # stop backend + frontend
#   ./stop.sh --ollama     # also stop Ollama (brew service or `ollama serve`)
#
set -eu

STOP_OLLAMA=0
for arg in "$@"; do
  case "$arg" in
    --ollama) STOP_OLLAMA=1 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

info() { printf '\033[36m▸\033[0m %s\n' "$1"; }
ok()   { printf '\033[32m✓\033[0m %s\n' "$1"; }

# Stop a process matched by pattern; report whether anything was running.
stop_match() {
  local label="$1" pattern="$2"
  if pkill -f "$pattern" >/dev/null 2>&1; then
    ok "stopped $label"
  else
    info "$label not running"
  fi
}

stop_match "backend (uvicorn :8000)" "uvicorn app.main:app"
stop_match "frontend (vite :5173)" "vite"

if [ "$STOP_OLLAMA" -eq 1 ]; then
  if command -v brew >/dev/null 2>&1 && brew services list 2>/dev/null | grep -qE '^ollama\s+started'; then
    brew services stop ollama >/dev/null 2>&1 && ok "stopped Ollama (brew service)"
  else
    stop_match "Ollama daemon (ollama serve)" "ollama serve"
  fi
fi
