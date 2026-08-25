#!/usr/bin/env bash
#
# Build and run the local two-container test stack.
#
#   ./deploy/docker/run.sh          stop the old containers, rebuild, start
#   ./deploy/docker/run.sh down     stop and remove them
#   ./deploy/docker/run.sh logs     follow both containers' output
#
# The image tag is the repository-root VERSION file, read here rather than
# written in `compose.yaml`, so bumping VERSION is the only thing that rolls
# the tag and the two cannot disagree.
#
# The data source is detected rather than configured here: `compose.yaml`
# layers the repository root's `.env` over `defaults.env` if the file exists,
# and falls back to the committed CSV and JSON files if it does not. This
# script only reports which of the two happened, so a stack reading the wrong
# source is visible at startup instead of at the first empty chart.
#
# Data flow:
#     VERSION -> PROJECT_VERSION -> deploy/docker/compose.yaml -> two images
#     defaults.env + optional ../../.env -> the API container's environment

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_VERSION="$(tr -d '[:space:]' < "$here/../../VERSION")"
export PROJECT_VERSION

compose() { docker compose --project-directory "$here" -f "$here/compose.yaml" "$@"; }

# What the API container will actually read, resolved the same way Compose
# resolves it: the root `.env` layered over `defaults.env`, last value winning.
# Reported rather than acted on -- this is a description of the configuration,
# not a second copy of it.
describe_source() {
  local root_env="$here/../../.env"
  local database
  database="$(grep -hE '^[[:space:]]*DATABASE[[:space:]]*=' "$here/defaults.env" "$root_env" 2>/dev/null \
    | tail -n 1 | cut -d= -f2- | tr -d '[:space:]"' | tr '[:upper:]' '[:lower:]')"
  case "$database" in
    1|true|yes|on)
      local host
      host="$(grep -hE '^[[:space:]]*PG_HOST[[:space:]]*=' "$here/defaults.env" "$root_env" 2>/dev/null \
        | tail -n 1 | cut -d= -f2- | tr -d '[:space:]"')"
      echo "PostgreSQL ${host:-<PG_HOST unset>} (from .env)"
      ;;
    *)
      if [ -f "$root_env" ]; then
        echo "committed module files (.env sets DATABASE=false)"
      else
        echo "committed module files (no .env found; using defaults.env)"
      fi
      ;;
  esac
}

case "${1:-up}" in
  down) compose down --remove-orphans ;;
  logs) compose logs -f ;;
  up)
    # Down first: the previous run's containers hold the published ports, and
    # a rebuilt image does not replace a container that is already running.
    compose down --remove-orphans
    compose build
    compose up -d
    echo "marketing-roi-analysis ${PROJECT_VERSION}"
    echo "  dashboard  http://localhost:${DASHBOARD_PORT:-8090}"
    echo "  api        http://localhost:${API_PORT:-8501}/api/health"
    echo "  data       $(describe_source)"
    ;;
  *) echo "usage: run.sh [up|down|logs]" >&2; exit 2 ;;
esac
