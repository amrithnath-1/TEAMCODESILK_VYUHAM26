#!/usr/bin/env bash
# Starts the FastAPI backend on :8000 and the Vite frontend on :5173.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$ROOT/.env" ]; then set -a; . "$ROOT/.env"; set +a; fi

cd "$ROOT/backend"
if [ ! -d .venv ]; then
  PY=$(command -v python3 || command -v python)
  "$PY" -m venv .venv
fi
if [ -f .venv/Scripts/python.exe ]; then VPY=.venv/Scripts/python.exe; else VPY=.venv/bin/python; fi
"$VPY" -m pip install -q -r requirements.txt
"$VPY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT INT TERM

cd "$ROOT/frontend"
[ -d node_modules ] || npm install --no-audit --no-fund
echo ""
echo "  API      → http://127.0.0.1:8000/docs"
echo "  Frontend → http://localhost:5173"
echo ""
npm run dev
