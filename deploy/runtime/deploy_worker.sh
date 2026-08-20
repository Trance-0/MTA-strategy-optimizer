#!/usr/bin/env bash
# Supervised deployment worker: coalesce GitHub requests, wait until Gitea's
# branch tip is the exact requested commit, build an immutable release, switch
# atomically, health-check it, and restore the preceding release on failure.

set -Eeuo pipefail

readonly STATE_ROOT="${MTA_DASHBOARD_STATE_ROOT:-/var/lib/mta-dashboard}"
readonly QUEUE_FILE="${STATE_ROOT}/queue/pending"
readonly QUEUE_LOCK="${STATE_ROOT}/queue/queue.lock"
readonly DEPLOY_LOCK="${STATE_ROOT}/deploy.lock"
readonly ACTIVE_COMMIT_FILE="${STATE_ROOT}/active_commit"
readonly INSTALL_ROOT="${MTA_DASHBOARD_INSTALL_ROOT:-/opt/mta-dashboard}"
readonly RELEASES_ROOT="${INSTALL_ROOT}/releases"
readonly CURRENT_LINK="${INSTALL_ROOT}/current"
readonly SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-/usr/bin/systemctl}"

log() { printf '%s [deploy-worker] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

positive_integer() {
  local name="$1" value="$2"
  if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
    log "$name must be a positive integer; got '$value'."
    exit 2
  fi
}

required=(
  GITEA_REPO_URL GITEA_BRANCH GITEA_AUTH_MODE DASHBOARD_HOST DASHBOARD_PORT
  MIRROR_POLL_SECONDS MIRROR_WAIT_SECONDS MIRROR_RETRY_SECONDS RELEASE_RETENTION
)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    log "Required environment setting $name is missing."
    exit 2
  fi
done

positive_integer MIRROR_POLL_SECONDS "$MIRROR_POLL_SECONDS"
positive_integer MIRROR_WAIT_SECONDS "$MIRROR_WAIT_SECONDS"
positive_integer MIRROR_RETRY_SECONDS "$MIRROR_RETRY_SECONDS"
GITEA_REQUEST_TIMEOUT_SECONDS="${GITEA_REQUEST_TIMEOUT_SECONDS:-45}"
positive_integer GITEA_REQUEST_TIMEOUT_SECONDS "$GITEA_REQUEST_TIMEOUT_SECONDS"
positive_integer RELEASE_RETENTION "$RELEASE_RETENTION"

export GIT_TERMINAL_PROMPT=0
export GIT_HTTP_LOW_SPEED_LIMIT=1
export GIT_HTTP_LOW_SPEED_TIME="$GITEA_REQUEST_TIMEOUT_SECONDS"
case "$GITEA_AUTH_MODE" in
  https)
    export GIT_ASKPASS="${INSTALL_ROOT}/bin/gitea_askpass.sh"
    ;;
  ssh)
    if [[ -z "${GITEA_SSH_PRIVATE_KEY_FILE:-}" || -z "${GITEA_SSH_KNOWN_HOSTS_FILE:-}" ]]; then
      log "SSH mode requires its installed private-key and known-hosts paths."
      exit 2
    fi
    export GIT_SSH_COMMAND="ssh -i ${GITEA_SSH_PRIVATE_KEY_FILE} -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=${GITEA_SSH_KNOWN_HOSTS_FILE}"
    ;;
  *)
    log "GITEA_AUTH_MODE must be https or ssh."
    exit 2
    ;;
esac

read_pending() {
  local first second third
  [[ -f "$QUEUE_FILE" ]] || return 1
  {
    IFS= read -r first
    IFS= read -r second
    IFS= read -r third
  } <"$QUEUE_FILE" || return 1
  [[ "$first" =~ ^[0-9a-f]{40}$ ]] || return 1
  [[ "$second" =~ ^[A-Za-z0-9-]{8,128}$ ]] || return 1
  printf '%s %s %s\n' "$first" "$second" "$third"
}

remote_tip() {
  local output status
  if output="$(timeout --signal=TERM --kill-after=5s "${GITEA_REQUEST_TIMEOUT_SECONDS}s" \
      git ls-remote --refs "$GITEA_REPO_URL" "refs/heads/${GITEA_BRANCH}")"; then
    :
  else
    status=$?
    if ((status == 124 || status == 137)); then
      log "Gitea branch probe timed out after ${GITEA_REQUEST_TIMEOUT_SECONDS}s." >&2
    else
      log "Gitea branch probe failed with Git exit status $status." >&2
    fi
    return 1
  fi
  awk 'NR == 1 { print tolower($1) }' <<<"$output"
}

queue_still_targets() {
  local expected="$1" pending
  pending="$(read_pending 2>/dev/null || true)"
  [[ "${pending%% *}" == "$expected" ]]
}

fetch_exact_branch() {
  local target="$1" destination="$2" fetched status
  if timeout --signal=TERM --kill-after=5s "${GITEA_REQUEST_TIMEOUT_SECONDS}s" \
      git clone --progress --no-checkout --filter=blob:none --single-branch \
      --branch "$GITEA_BRANCH" "$GITEA_REPO_URL" "$destination"; then
    :
  else
    status=$?
    if ((status == 124 || status == 137)); then
      log "Gitea clone timed out after ${GITEA_REQUEST_TIMEOUT_SECONDS}s; no source was accepted for $target."
    else
      log "Gitea clone failed with Git exit status $status; no source was accepted for $target."
    fi
    return 1
  fi
  fetched="$(git -C "$destination" rev-parse "refs/remotes/origin/${GITEA_BRANCH}" 2>/dev/null || true)"
  fetched="${fetched,,}"
  if [[ "$fetched" != "$target" ]]; then
    log "Exact-commit gate closed after fetch: wanted $target, fetched ${fetched:-none}."
    return 75
  fi
  git -C "$destination" checkout --quiet --detach "$target"
}

restart_dashboard() {
  sudo -n "$SYSTEMCTL_BIN" restart mta-dashboard.service
}

dashboard_healthy() {
  # Checks liveness only (the process is up and Express is routing), not
  # whether PostgreSQL is reachable or `attribution_result` has rows yet.
  # `/api/dashboard` depends on both and is a business-data readiness check,
  # not a deploy-succeeded check: gating releases on it meant a first deploy
  # against an empty database could never go healthy, and a rollback to a
  # perfectly good prior release would fail its health check the same way,
  # for a reason the deployed code had no part in.
  local host="$DASHBOARD_HOST"
  [[ "$host" == "0.0.0.0" || "$host" == "::" ]] && host="127.0.0.1"
  local base="http://${host}:${DASHBOARD_PORT}"
  local attempts=30
  while ((attempts > 0)); do
    if curl --fail --silent --show-error --max-time 5 "${base}/" >/dev/null 2>&1 &&
       curl --fail --silent --show-error --max-time 15 "${base}/api/health" >/dev/null 2>&1; then
      return 0
    fi
    attempts=$((attempts - 1))
    sleep 2
  done
  return 1
}

remove_matching_queue_entry() {
  local deployed="$1" pending
  exec 8>"$QUEUE_LOCK"
  flock -w 5 8 || return 1
  pending="$(read_pending 2>/dev/null || true)"
  if [[ "${pending%% *}" == "$deployed" ]]; then
    rm -f -- "$QUEUE_FILE"
  fi
}

prune_releases() {
  local active previous count=0 path
  active="$(readlink -f "$CURRENT_LINK" 2>/dev/null || true)"
  previous="${1:-}"
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    count=$((count + 1))
    if [[ "$path" == "$active" || "$path" == "$previous" ]]; then
      continue
    fi
    if (( count > RELEASE_RETENTION )); then
      case "$path" in
        "${RELEASES_ROOT}/"*) rm -rf -- "$path" ;;
      esac
    fi
  done < <(find "$RELEASES_ROOT" -mindepth 1 -maxdepth 1 -type d -name '[0-9a-f]*' -printf '%T@ %p\n' 2>/dev/null | sort -rn | cut -d' ' -f2-)
}

deploy_commit() {
  local target="$1"
  local release="${RELEASES_ROOT}/${target}"
  local build="${RELEASES_ROOT}/.${target}.building.$$"
  local previous fetch_status
  local -a clean_build_environment=(
    env
    -u GITEA_TOKEN
    -u GITEA_USERNAME
    -u GITEA_SSH_PRIVATE_KEY_FILE
    -u GITEA_SSH_KNOWN_HOSTS_FILE
    -u GIT_ASKPASS
    -u GIT_SSH_COMMAND
  )

  exec 7>"$DEPLOY_LOCK"
  if ! flock -n 7; then
    log "Another deployment owns the build lock; the queued commit remains pending."
    return 75
  fi

  if ! queue_still_targets "$target"; then
    log "Commit $target was superseded before its build began."
    return 75
  fi

  if [[ -f "$ACTIVE_COMMIT_FILE" ]] &&
     [[ "$(tr -d '\r\n' <"$ACTIVE_COMMIT_FILE")" == "$target" ]] &&
     [[ "$(readlink -f "$CURRENT_LINK" 2>/dev/null || true)" == "$release" ]] &&
     [[ -f "$release/.ready" ]]; then
    restart_dashboard || true
    if dashboard_healthy; then
      remove_matching_queue_entry "$target" || true
      log "Commit $target is already active and healthy; no rebuild is needed."
      return 0
    fi
    log "The recorded release $target could not pass its health check; refusing to delete it in place."
    return 1
  fi

  rm -rf -- "$build"
  mkdir -p "$build"
  log "Fetching Gitea branch $GITEA_BRANCH for exact-commit verification."
  if fetch_exact_branch "$target" "$build"; then
    :
  else
    fetch_status=$?
    rm -rf -- "$build"
    return "$fetch_status"
  fi
  if ! queue_still_targets "$target"; then
    log "Commit $target was superseded during fetch; skipping its build."
    rm -rf -- "$build"
    return 75
  fi

  log "Installing locked dashboard dependencies for $target."
  if ! (cd "$build/dashboard" && "${clean_build_environment[@]}" npm ci --no-audit --no-fund); then
    log "npm ci failed for $target; the current release is unchanged."
    rm -rf -- "$build"
    return 1
  fi

  log "Running dashboard tests for $target."
  if ! (cd "$build/dashboard" && "${clean_build_environment[@]}" npm test); then
    log "Dashboard tests failed for $target; the current release is unchanged."
    rm -rf -- "$build"
    return 1
  fi

  log "Building dashboard release $target."
  if ! (cd "$build/dashboard" && "${clean_build_environment[@]}" npm run build) || [[ ! -f "$build/dashboard/dist/index.html" ]]; then
    log "Dashboard build failed for $target; the current release is unchanged."
    rm -rf -- "$build"
    return 1
  fi

  if ! queue_still_targets "$target"; then
    log "Commit $target was superseded during its build; it will not be activated."
    rm -rf -- "$build"
    return 75
  fi

  printf '%s\n' "$target" >"$build/.ready"
  rm -rf -- "$release"
  mv -- "$build" "$release"

  previous="$(readlink -f "$CURRENT_LINK" 2>/dev/null || true)"
  ln -sfn "$release" "${CURRENT_LINK}.new"
  mv -Tf "${CURRENT_LINK}.new" "$CURRENT_LINK"

  log "Activated $target; restarting the dashboard."
  if restart_dashboard && dashboard_healthy; then
    printf '%s\n' "$target" >"$ACTIVE_COMMIT_FILE"
    remove_matching_queue_entry "$target" || true
    prune_releases "$previous"
    log "Deployment $target is healthy."
    return 0
  fi

  log "Health check failed for $target; restoring the preceding release."
  if [[ -n "$previous" && "$previous" == "${RELEASES_ROOT}/"* && -d "$previous" ]]; then
    ln -sfn "$previous" "${CURRENT_LINK}.rollback"
    mv -Tf "${CURRENT_LINK}.rollback" "$CURRENT_LINK"
    if restart_dashboard && dashboard_healthy; then
      printf '%s\n' "$(basename "$previous")" >"$ACTIVE_COMMIT_FILE"
      log "Rollback to $(basename "$previous") is healthy."
    else
      log "CRITICAL: rollback health check also failed."
    fi
  else
    log "No preceding release exists; the failed first deployment remains inactive."
  fi
  return 1
}

mkdir -p "$RELEASES_ROOT" "${STATE_ROOT}/queue"

if [[ "${1:-}" == "--verify-exact" ]]; then
  target="${2:-}"
  [[ "$target" =~ ^[0-9a-f]{40}$ ]] || { log "--verify-exact requires a lowercase 40-character commit."; exit 2; }
  verification="${RELEASES_ROOT}/.verification.$$"
  rm -rf -- "$verification"
  mkdir -p "$verification"
  if fetch_exact_branch "$target" "$verification"; then
    rm -rf -- "$verification"
    log "Exact-commit verification passed for $target."
    exit 0
  else
    status=$?
    rm -rf -- "$verification"
    exit "$status"
  fi
fi

log "Worker started; waiting for GitHub requests and the delayed Gitea mirror."

while true; do
  pending="$(read_pending 2>/dev/null || true)"
  if [[ -z "$pending" ]]; then
    sleep 2
    continue
  fi

  target="${pending%% *}"
  started="$(date +%s)"
  last_observed=""
  log "Waiting for Gitea branch $GITEA_BRANCH to reach GitHub commit $target."

  while true; do
    latest="$(read_pending 2>/dev/null || true)"
    if [[ -z "$latest" ]]; then
      break
    fi
    latest_target="${latest%% *}"
    if [[ "$latest_target" != "$target" ]]; then
      target="$latest_target"
      started="$(date +%s)"
      log "A newer push superseded the target; now waiting for $target."
    fi

    observed="$(remote_tip || true)"
    if [[ "$observed" != "$last_observed" ]]; then
      log "Gitea branch currently resolves to ${observed:-unavailable}; expected $target."
      last_observed="$observed"
    fi

    if [[ "$observed" == "$target" ]]; then
      # The clone in deploy_commit repeats this comparison after fetching. The
      # remote probe is a wait condition, never the build's trust boundary.
      if deploy_commit "$target"; then
        :
      else
        deploy_status=$?
        if ((deploy_status != 75)); then
          log "Deployment attempt for $target failed; retrying in ${MIRROR_RETRY_SECONDS}s."
          sleep "$MIRROR_RETRY_SECONDS"
        fi
      fi
      break
    fi

    now="$(date +%s)"
    if (( now - started >= MIRROR_WAIT_SECONDS )); then
      log "Mirror wait expired for $target; current release remains active. Retrying in ${MIRROR_RETRY_SECONDS}s."
      sleep "$MIRROR_RETRY_SECONDS"
      break
    fi
    sleep "$MIRROR_POLL_SECONDS"
  done
done
