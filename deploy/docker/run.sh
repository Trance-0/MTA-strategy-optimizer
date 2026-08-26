#!/usr/bin/env bash
#
# Run the two-container stack, from local sources or from the registry.
#
#   ./deploy/docker/run.sh          stop the old containers, rebuild, start
#   ./deploy/docker/run.sh pull     pull the published images and start
#   ./deploy/docker/run.sh down     stop and remove them
#   ./deploy/docker/run.sh logs     follow both containers' output
#
# `up` builds the images from this checkout; `pull` fetches the ones
# `.github/workflows/publish-containers.yml` published for this VERSION and
# builds nothing. Use `pull` on a machine that only runs the stack, and `up`
# when the sources have changed -- a build is the only way to see an edit that
# is not yet released.
#
# The image tag is the repository-root VERSION file, read here rather than
# written in `compose.yaml`, so bumping VERSION is the only thing that rolls
# the tag and the two cannot disagree. That makes `pull` exact rather than
# approximate: it fetches the images built from this checkout's version, not
# whatever `latest` currently points at.
#
# The data source is detected rather than configured here: `compose.yaml`
# layers the repository root's `.env` over `defaults.env` if the file exists,
# and falls back to the committed CSV and JSON files if it does not. This
# script only reports which of the two happened, so a stack reading the wrong
# source is visible at startup instead of at the first empty chart.
#
# Data flow:
#     VERSION -> PROJECT_VERSION -> deploy/docker/compose.yaml -> two images
#     IMAGE_NAMESPACE -> the ghcr.io owner those images are named under
#     defaults.env + optional ../../.env -> the API container's environment

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_VERSION="$(tr -d '[:space:]' < "$here/../../VERSION")"
export PROJECT_VERSION

# Registry paths must be lowercase; the GitHub owner is not. Folded here so a
# fork can export IMAGE_NAMESPACE in whatever case it uses.
IMAGE_NAMESPACE="$(printf '%s' "${IMAGE_NAMESPACE:-Trance-0}" | tr '[:upper:]' '[:lower:]')"
export IMAGE_NAMESPACE

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

# Start the stack and report it. `source_label` names where the images came
# from, so the two modes are told apart in the output rather than by
# remembering which command was typed.
start_stack() {
  local source_label="$1"
  # `--wait` returns only once both health checks pass, so a caller that
  # continues to a request -- a script, a CI step -- is not racing the start.
  # It exits non-zero if a container never becomes healthy, which `set -e`
  # turns into a failure here rather than a confusing error at the first curl.
  compose up -d --wait
  echo "marketing-roi-analysis ${PROJECT_VERSION}"
  echo "  dashboard  http://localhost:${DASHBOARD_PORT:-8090}"
  echo "  api        http://localhost:${API_PORT:-8501}/api/health"
  echo "  images     ${source_label}"
  echo "  data       $(describe_source)"
}

case "${1:-up}" in
  down) compose down --remove-orphans ;;
  logs) compose logs -f ;;
  up)
    # Down first: the previous run's containers hold the published ports, and
    # a rebuilt image does not replace a container that is already running.
    compose down --remove-orphans
    compose build
    start_stack "built from this checkout"
    ;;
  pull)
    compose down --remove-orphans
    # A published tag is rewritten only by a forced republish, but a stale
    # local copy of one is indistinguishable from the registry's without
    # asking, so this always asks. It is also the step that fails when the
    # version was never published, with the registry's own message.
    if ! compose pull; then
      echo "" >&2
      echo "Could not pull ghcr.io/${IMAGE_NAMESPACE}/mta-{backend,dashboard}:${PROJECT_VERSION}." >&2
      echo "The images are published when VERSION changes on main; check that this" >&2
      echo "version was released, or run 'docker login ghcr.io' if they are private." >&2
      echo "Use './deploy/docker/run.sh up' to build from this checkout instead." >&2
      exit 1
    fi
    start_stack "pulled from ghcr.io/${IMAGE_NAMESPACE}"
    ;;
  *) echo "usage: run.sh [up|pull|down|logs]" >&2; exit 2 ;;
esac
