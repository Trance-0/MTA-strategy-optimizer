#!/usr/bin/env bash
#
# Start the dashboard locally on macOS, Linux, or Git Bash.
#
# Reads `.env` at the repository root for the data source. Copy `sample.env` to
# `.env` and set `DATABASE=true` with the `PG_*` values to read the PostgreSQL
# mirror; leave `DATABASE=false` to read the committed CSV and JSON artifacts.
#
#   ./dashboard/run.sh          # default port 8501
#   ./dashboard/run.sh 8600     # a different port
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${1:-8501}"

cd "$REPO_ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not on PATH. Install it from https://docs.astral.sh/uv/ first." >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "No .env found. Copying sample.env, which reads the committed files."
  cp sample.env .env
fi

# Sync only when the extra is missing, so a warm checkout starts immediately.
if ! uv run --extra dashboard python -c "import streamlit" >/dev/null 2>&1; then
  echo "Installing the dashboard extra..."
  uv sync --extra dashboard
fi

echo "Starting the dashboard on http://localhost:${PORT}"
exec uv run --extra dashboard streamlit run dashboard/app.py \
  --server.port "$PORT"
