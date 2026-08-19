#!/usr/bin/env bash
# Validate the untrusted GitHub payload values passed by webhook and atomically
# replace the durable desired-commit queue entry. Slow deployment happens in
# deploy_worker.sh, never in this request path.

set -Eeuo pipefail

readonly STATE_ROOT="${MTA_DASHBOARD_STATE_ROOT:-/var/lib/mta-dashboard}"
readonly QUEUE_DIR="${STATE_ROOT}/queue"
readonly DELIVERY_DIR="${STATE_ROOT}/deliveries"
readonly QUEUE_FILE="${QUEUE_DIR}/pending"
readonly QUEUE_LOCK="${QUEUE_DIR}/queue.lock"

commit="${1:-}"
delivery="${2:-}"
event="${3:-push}"

if [[ ! "$delivery" =~ ^[A-Za-z0-9-]{8,128}$ ]]; then
  printf '[enqueue] Rejected an invalid X-GitHub-Delivery identifier.\n' >&2
  exit 2
fi

if [[ "$event" == ping ]]; then
  printf '[enqueue] Authenticated GitHub setup ping %s accepted; no deployment was queued.\n' "$delivery"
  exit 0
fi

if [[ "$event" != push ]]; then
  printf '[enqueue] Rejected unsupported GitHub event %s.\n' "$event" >&2
  exit 2
fi

if [[ ! "$commit" =~ ^[0-9a-fA-F]{40}$ ]]; then
  printf '[enqueue] Rejected an invalid GitHub after commit.\n' >&2
  exit 2
fi
commit="${commit,,}"
if [[ "$commit" == 0000000000000000000000000000000000000000 ]]; then
  printf '[enqueue] Rejected the all-zero commit used for a deleted ref.\n' >&2
  exit 2
fi

umask 077
mkdir -p "$QUEUE_DIR" "$DELIVERY_DIR"

exec 9>"$QUEUE_LOCK"
if ! flock -w 5 9; then
  printf '[enqueue] Could not acquire the queue lock.\n' >&2
  exit 1
fi

if [[ -f "${DELIVERY_DIR}/${delivery}" ]]; then
  printf '[enqueue] Delivery %s was already accepted.\n' "$delivery"
  exit 0
fi

temporary="$(mktemp "${QUEUE_DIR}/.pending.XXXXXX")"
cleanup() { rm -f -- "$temporary"; }
trap cleanup EXIT

printf '%s\n%s\n%s\n' \
  "$commit" \
  "$delivery" \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$temporary"
chmod 600 "$temporary"
mv -f -- "$temporary" "$QUEUE_FILE"
temporary=""

# Recording after the atomic queue move makes a crash safe: at worst GitHub's
# redelivery writes the same desired commit again; it can never be acknowledged
# and then lost before reaching the queue.
: >"${DELIVERY_DIR}/${delivery}"
find "$DELIVERY_DIR" -type f -mtime +30 -delete 2>/dev/null || true

printf '[enqueue] Accepted delivery %s for commit %s.\n' "$delivery" "$commit"
