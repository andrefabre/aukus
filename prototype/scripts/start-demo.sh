#!/usr/bin/env bash
# One-command local demo (macOS / Linux / Git Bash). Free: no cloud, no API keys.
#   scripts/start-demo.sh          # set up on first run, then serve
#   scripts/start-demo.sh --reset  # wipe demo data and re-seed May..last month
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8000}"

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv 2>/dev/null || python -m venv .venv
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=.venv/Scripts/python; fi
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -e ".[dev]"
fi
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=.venv/Scripts/python; fi

if [ "${1:-}" = "--reset" ] || [ ! -d var/vault ]; then
  "$PY" -m disp_evidence demo-setup
fi
echo "Open http://127.0.0.1:${PORT}"
exec "$PY" -m disp_evidence serve --port "$PORT"
