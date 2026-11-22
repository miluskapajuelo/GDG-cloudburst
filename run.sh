#!/usr/bin/env bash
# Starts the SentinelDesk API (port 8000) and the web console (port 5173) on macOS / Linux.
# The macOS/Linux counterpart of run.bat.
#
# Usage:  ./run.sh          real models (first run sets everything up, ~5 min)
#         ./run.sh mock     mock API (SENTINEL_MOCK=1, no models)
#
# First run, automatically: creates .venv, installs requirements, copies .env.example to .env,
# builds the split / classifier / FAISS index if they are missing, and installs web packages.
# Ctrl+C stops both servers.
set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\033[1;34m[run]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[run]\033[0m %s\n' "$*" >&2; exit 1; }

# --- ports must be free -------------------------------------------------------------------------
for port in 8000 5173; do
  if lsof -ti "tcp:$port" >/dev/null 2>&1; then
    fail "Port $port is already in use. Stop the other server first (lsof -ti tcp:$port | xargs kill)."
  fi
done

# --- Python virtualenv --------------------------------------------------------------------------
if [ ! -x .venv/bin/python ]; then
  PY=""
  for cand in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$cand" >/dev/null 2>&1 && \
       "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      PY="$cand"; break
    fi
  done
  [ -n "$PY" ] || fail "Python 3.11+ not found. Install it (e.g. 'brew install python@3.12') and rerun."
  say "Creating .venv with $("$PY" --version)"
  "$PY" -m venv .venv
  .venv/bin/python -m pip install -q --upgrade pip
  say "Installing Python requirements (first run only, a few minutes)"
  .venv/bin/python -m pip install -q -r requirements.txt
fi
PYTHON=.venv/bin/python

# --- settings -------------------------------------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  say "Created .env from .env.example. Add GEMINI_API_KEY there to get AI-drafted replies."
fi
if ! grep -Eq '^GEMINI_API_KEY=.+' .env; then
  say "Note: GEMINI_API_KEY is empty in .env, so drafts show as LLM unavailable (everything else works)."
fi

# --- data and models (real mode only) --------------------------------------------------------------
if [ "${1:-}" = "mock" ]; then
  export SENTINEL_MOCK=1
  say "Mock mode: the API returns the fixture response, no models are loaded."
else
  unset SENTINEL_MOCK || true
  [ -f data/kb_train.parquet ] || { say "Building the data split";        "$PYTHON" -m ml.make_split; }
  [ -f artifacts/clf.joblib ]  || { say "Training the classifier (~2 min)"; "$PYTHON" -m ml.train; }
  [ -f artifacts/kb.faiss ]    || { say "Building the search index (~2 min)"; "$PYTHON" -m agent.build_index; }
fi

# --- web packages -----------------------------------------------------------------------------------
command -v npm >/dev/null 2>&1 || fail "npm not found. Install Node.js 20+ (e.g. 'brew install node') and rerun."
if [ ! -d web/node_modules ]; then
  say "Installing web packages (first run only)"
  (cd web && npm ci --no-audit --no-fund)
fi

# --- start both servers, stop both on Ctrl+C ----------------------------------------------------------
PIDS=()
cleanup() {
  trap - INT TERM EXIT
  say "Stopping servers"
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

say "Starting API on http://localhost:8000"
"$PYTHON" -m uvicorn api.main:app --port 8000 &
PIDS+=($!)

say "Starting web console on http://localhost:5173"
(cd web && exec npm run dev -- --port 5173 --strictPort) &
PIDS+=($!)

# Wait for the API to answer (model loading takes a few seconds), then open the browser.
for _ in $(seq 1 60); do
  curl -sf http://localhost:8000/health >/dev/null 2>&1 && break
  sleep 1
done
curl -sf http://localhost:8000/health >/dev/null 2>&1 || fail "The API did not start. Check the messages above."
say "Ready:  UI http://localhost:5173   API http://localhost:8000/health   (Ctrl+C to stop)"
if command -v open >/dev/null 2>&1; then open http://localhost:5173
elif command -v xdg-open >/dev/null 2>&1; then xdg-open http://localhost:5173 >/dev/null 2>&1 || true
fi

wait
