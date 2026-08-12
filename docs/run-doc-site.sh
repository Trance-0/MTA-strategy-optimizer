#!/usr/bin/env sh
set -eu

SCRIPT_DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIRECTORY"

RUN_MODE=${1:-dev}
case "$RUN_MODE" in
  dev|build|preview)
    ;;
  --help|-h)
    echo "Usage: sh run-doc-site.sh [dev|build|preview]"
    exit 0
    ;;
  *)
    echo "[docs] ERROR: Unsupported mode '$RUN_MODE'." >&2
    exit 2
    ;;
esac

if ! command -v node >/dev/null 2>&1; then
  echo "[docs] ERROR: Node.js is not available on PATH." >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "[docs] ERROR: npm is not available on PATH." >&2
  exit 1
fi

echo "[docs] Directory: $SCRIPT_DIRECTORY"
echo "[docs] Mode: $RUN_MODE"
echo "[docs] Node.js: $(node --version)"
echo "[docs] npm: $(npm --version)"

if [ ! -f node_modules/vitepress/package.json ]; then
  if [ -f package-lock.json ]; then
    npm ci
  else
    npm install
  fi
fi

exec npm run "$RUN_MODE"
