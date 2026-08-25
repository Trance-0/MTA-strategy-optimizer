#!/usr/bin/env bash
#
# Start the dashboard locally on macOS, Linux, or Git Bash.
#
# One command from a clean clone: this checks the toolchain, installs the
# dependencies, builds the client, and starts the server that serves both the
# Flask JSON API and that client. Node.js and uv must be installed; the script
# says exactly what is missing before it changes the checkout.
#
# Reads `.env` at the repository root for the data source. Copy `sample.env` to
# `.env` and set `DATABASE=true` with the `PG_*` values to read the PostgreSQL
# mirror; leave `DATABASE=false` to read the committed CSV and JSON artifacts.
# Nothing about this command changes between the two.
#
#   ./dashboard/run.sh              # default port 8501, opens a browser
#   ./dashboard/run.sh 8600         # a different port
#   ./dashboard/run.sh --no-open    # do not open a browser
#   ./dashboard/run.sh --rebuild    # discard and rebuild the client
#
# Every failure prints what went wrong, what to do about it, and what to
# include in a bug report. `--rebuild` is the first thing to try when the page
# loads but looks wrong.

# No `set -e`: a failure is diagnosed and reported here rather than aborting
# the script with a bare non-zero status and no explanation.
set -uo pipefail

# Vite's own engine range, `^20.19.0 || >=22.12.0`, as one comparable integer
# per boundary: major * 1000000 + minor * 1000 + patch. The requirement is not
# a round major number, and rounding it down to one is what the check below
# exists to avoid -- see the failure it reports.
REQUIRED_NODE_TEXT="20.19.0 or newer in the 20 series, or 22.12.0 or newer"
NODE_20_FLOOR=20019000
NODE_21_FLOOR=21000000
NODE_22_FLOOR=22012000
ISSUES_URL="https://github.com/Trance-0/MTA-strategy-optimizer/issues"

DASHBOARD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${DASHBOARD_DIR}/.." && pwd)"
LOG_FILE="${DASHBOARD_DIR}/.run.log"

PORT=8501
OPEN_BROWSER=1
REBUILD=0

for argument in "$@"; do
  case "$argument" in
    --no-open) OPEN_BROWSER=0 ;;
    --rebuild) REBUILD=1 ;;
    -h|--help)
      # The banner above: every line from the second until the first that is
      # not a comment, which is the blank line closing the block.
      awk 'NR>1 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    ''|*[!0-9]*)
      echo "Unrecognised argument: ${argument}" >&2
      echo "Usage: $(basename "${BASH_SOURCE[0]}") [port] [--no-open] [--rebuild]" >&2
      exit 2
      ;;
    *) PORT="$argument" ;;
  esac
done

# The length is checked before the value, because `[ "$PORT" -gt 65535 ]` on a
# number too large for a signed 64-bit integer is not a false comparison but a
# bash error printed over the message this exists to give.
if [ "${#PORT}" -gt 5 ] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
  echo "Port must be between 1 and 65535; got ${PORT}." >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

step() { printf '\n[%d/4] %s\n' "$1" "$2"; }
note() { printf '        %s\n' "$1"; }

# Print the failure, the remedy, and the facts a bug report needs. The
# environment block is what turns "it does not work" into a reproducible
# report, so it is printed for the reader to copy rather than left to be asked
# for afterwards.
fail() {
  local title="$1"
  shift
  printf '\n%s\n' "------------------------------------------------------------"
  printf '  %s\n' "$title"
  printf '%s\n\n' "------------------------------------------------------------"
  # A separating blank line is printed bare rather than indented, so the block
  # can be pasted into an issue without carrying trailing whitespace.
  for line in "$@"; do
    if [ -z "$line" ]; then printf '\n'; else printf '  %s\n' "$line"; fi
  done
  printf '\n  If this persists, open an issue with the block below:\n'
  printf '    %s\n\n' "$ISSUES_URL"
  printf '    dashboard      : %s\n' "$(cat "${REPO_ROOT}/VERSION" 2>/dev/null || echo 'unknown')"
  # "git is absent" and "this is not a checkout" are separate facts, and
  # collapsing them sends a triager looking for a damaged clone when the real
  # answer is that the reporter downloaded a zip.
  local commit
  if ! command -v git >/dev/null 2>&1; then
    commit="git is not installed"
  else
    commit="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo 'not a git checkout')"
  fi
  printf '    commit         : %s\n' "$commit"
  printf '    os             : %s\n' "$(uname -srm 2>/dev/null || echo "$OSTYPE")"
  printf '    shell          : %s\n' "${BASH_VERSION:-unknown}"
  printf '    node           : %s\n' "$(command -v node >/dev/null 2>&1 && node -v || echo 'not installed')"
  printf '    npm            : %s\n' "$(command -v npm >/dev/null 2>&1 && npm -v || echo 'not installed')"
  printf '    uv             : %s\n' "$(command -v uv >/dev/null 2>&1 && uv --version || echo 'not installed')"
  printf '    port requested : %s\n' "$PORT"
  printf '    failed step    : %s\n' "$title"
  if [ -s "$LOG_FILE" ]; then
    printf '\n  Last 20 lines of %s:\n\n' "${LOG_FILE#"${REPO_ROOT}/"}"
    tail -n 20 "$LOG_FILE" | sed -e 's/^/      /'
  fi
  printf '\n'
  exit 1
}

# Run an npm command in the dashboard directory, showing its output only when
# it fails. A successful install is 700 lines nobody reads; a failed one is the
# only thing that matters.
#
# The directory is changed rather than passed as `npm --prefix`, because
# `--prefix` sets where `node_modules` is written but not where the manifest is
# read from: the npm 10 that ships with Node 20 and 22 still reads
# `package.json` from the working directory, so a fresh clone fails with ENOENT
# naming the repository root. The subshell keeps the change local, so the
# caller stays where it was.
run_quiet_in_dashboard() {
  (cd "$DASHBOARD_DIR" && "$@") >"$LOG_FILE" 2>&1
}

cd "$REPO_ROOT" || fail "Cannot enter the repository" \
  "Could not change directory to ${REPO_ROOT}."

# ---------------------------------------------------------------------------
# 1. Toolchain
# ---------------------------------------------------------------------------

step 1 "Checking the toolchain"

if ! command -v node >/dev/null 2>&1; then
  fail "Node.js is not installed" \
    "The dashboard is a Node application and cannot start without it." \
    "" \
    "  Install the Long Term Support release from:" \
    "      https://nodejs.org/" \
    "" \
    "  macOS with Homebrew : brew install node" \
    "  Debian or Ubuntu    : sudo apt install nodejs npm" \
    "  Fedora              : sudo dnf install nodejs" \
    "" \
    "Then close this terminal, open a new one, and run this script again --" \
    "an installer updates PATH only for shells started after it."
fi

# `node -p` rather than parsing `node -v`, so a prerelease suffix such as
# v23.0.0-nightly cannot break the comparison.
NODE_ENCODED="$(node -p 'const [a,b,c] = process.versions.node.split(".").map(Number); a * 1000000 + b * 1000 + c' 2>/dev/null)"
NODE_OK=0
case "$NODE_ENCODED" in
  ''|*[!0-9]*) NODE_OK=0 ;;
  *)
    if [ "$NODE_ENCODED" -ge "$NODE_22_FLOOR" ]; then
      NODE_OK=1
    elif [ "$NODE_ENCODED" -ge "$NODE_20_FLOOR" ] && [ "$NODE_ENCODED" -lt "$NODE_21_FLOOR" ]; then
      NODE_OK=1
    fi
    ;;
esac

# The minor version matters, and checking only the major is the bug this
# replaced: Vite's native bundler binding is an *optional* dependency carrying
# the same engine range, so on 22.11 npm quietly skips it, reports a
# successful install, and the build then dies with "Cannot find module
# './rolldown-binding…node'" -- a message that names neither Node nor the
# version. Failing here names both.
if [ "$NODE_OK" -ne 1 ]; then
  fail "Node.js ${REQUIRED_NODE_TEXT} is required" \
    "Found: $(node -v 2>/dev/null || echo 'a version that could not be read')" \
    "" \
    "  This is Vite's own engine range. Its bundler ships as a platform-specific" \
    "  binary that npm installs only when the running Node satisfies that range," \
    "  and skips silently otherwise -- so an unsupported version installs cleanly" \
    "  and fails at build time with a missing-module error naming neither cause." \
    "" \
    "  Upgrade from https://nodejs.org/, or with a version manager:" \
    "      nvm install 22 && nvm use 22" \
    "      fnm install 22 && fnm use 22"
fi

if ! command -v npm >/dev/null 2>&1; then
  fail "npm is not installed" \
    "Node.js is present ($(node -v)) but npm is not on PATH." \
    "" \
    "  npm normally ships with Node.js. A package manager that splits them" \
    "  needs it installed separately:" \
    "      Debian or Ubuntu : sudo apt install npm" \
    "" \
    "  Otherwise reinstall Node.js from https://nodejs.org/, which bundles it."
fi

note "node $(node -v), npm $(npm -v)"

if ! command -v uv >/dev/null 2>&1; then
  fail "uv is not installed" \
    "The Flask backend uses the repository's locked Python environment." \
    "Install uv from https://docs.astral.sh/uv/getting-started/installation/" \
    "and run this command again."
fi
note "$(uv --version)"

# ---------------------------------------------------------------------------
# 2. Configuration
# ---------------------------------------------------------------------------

step 2 "Checking the configuration"

if [ ! -f .env ]; then
  if [ ! -f sample.env ]; then
    fail "Neither .env nor sample.env exists" \
      "The repository is incomplete: sample.env is tracked and should be here." \
      "" \
      "  Re-clone the repository, or restore the file:" \
      "      git checkout sample.env"
  fi
  if ! cp sample.env .env 2>/dev/null; then
    fail "Could not create .env" \
      "Copying sample.env to .env failed, usually because ${REPO_ROOT}" \
      "is not writable by the current user." \
      "" \
      "  Check the directory's permissions, or create the file by hand:" \
      "      cp sample.env .env"
  fi
  note "Created .env from sample.env — reads the committed files."
else
  note ".env found."
fi

# ---------------------------------------------------------------------------
# 3. Dependencies
# ---------------------------------------------------------------------------

step 3 "Checking the dependencies"

# `vite` standing in for the client tree: an interrupted install leaves
# node_modules present but incomplete, and testing only for the directory
# would then skip the repair.
if [ ! -d "${DASHBOARD_DIR}/node_modules" ] || [ ! -d "${DASHBOARD_DIR}/node_modules/vite" ]; then
  note "Installing (a few minutes on the first run)..."
  if ! run_quiet_in_dashboard npm install --no-audit --no-fund; then
    fail "Dependency installation failed" \
      "npm install did not complete. The most common causes:" \
      "" \
      "  * No network access, or a proxy or firewall blocking the registry." \
      "    Test it:  npm ping" \
      "" \
      "  * A corporate registry needing configuration." \
      "    Check it:  npm config get registry" \
      "" \
      "  * A partly written node_modules from an interrupted run." \
      "    Clear it:  rm -rf dashboard/node_modules && ./dashboard/run.sh"
  fi
  note "Installed."
else
  note "Already installed."
fi

if ! uv sync --extra backend >>"$LOG_FILE" 2>&1; then
  fail "Backend dependency installation failed" \
    "uv could not install the locked Flask backend environment." \
    "Run this command for the complete diagnostic:" \
    "    uv sync --extra backend"
fi
note "Backend dependencies ready."

# ---------------------------------------------------------------------------
# 4. Client build
# ---------------------------------------------------------------------------

step 4 "Checking the client build"

if [ "$REBUILD" -eq 1 ] && [ -d "${DASHBOARD_DIR}/dist" ]; then
  rm -rf "${DASHBOARD_DIR}/dist"
  note "Discarded the previous build."
fi

if [ ! -f "${DASHBOARD_DIR}/dist/index.html" ]; then
  note "Building..."
  if ! run_quiet_in_dashboard npm run build; then
    fail "Client build failed" \
      "vite build did not produce dashboard/dist/index.html." \
      "" \
      "  This usually means the dependency tree is incomplete or mismatched." \
      "  Reinstalling from scratch fixes most cases:" \
      "" \
      "      rm -rf dashboard/node_modules dashboard/dist" \
      "      ./dashboard/run.sh" \
      "" \
      "  The build output above names the file and line that failed."
  fi
  note "Built."
else
  note "Already built (use --rebuild to force a fresh one)."
fi

rm -f "$LOG_FILE"

# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------
#
# The server owns the port check: it is the process that binds, so it can
# report a conflict precisely rather than racing a probe made here.

printf '\n%s\n' "------------------------------------------------------------"
printf '  Dashboard starting on http://localhost:%s\n' "$PORT"
printf '%s\n' "------------------------------------------------------------"

export BACKEND_PORT="$PORT"
export DASHBOARD_OPEN="$OPEN_BROWSER"
exec uv run --extra backend python -m backend.app
