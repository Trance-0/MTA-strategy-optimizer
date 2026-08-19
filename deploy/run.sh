#!/usr/bin/env bash
# Interactive Linux lifecycle manager for the MTA Strategy Optimizer dashboard.
#
# This is the only command needed after uploading deploy/: its arrow-key menu
# installs, inspects, starts, stops, or removes the managed services. Installation
# validates .env, installs checksum-pinned tools, performs an atomic Gitea
# deployment, and prints the GitHub webhook fields. It never prints a credential.

set -Eeuo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_DIR
ENV_FILE="${DEPLOY_DIR}/.env"
NON_INTERACTIVE=0
CHECK_ONLY=0
MENU_SELECTION=0

readonly SERVICE_USER="mta-dashboard"
readonly SERVICE_GROUP="mta-dashboard"
readonly ETC_ROOT="/etc/mta-dashboard"
readonly INSTALL_ROOT="/opt/mta-dashboard"
readonly STATE_ROOT="/var/lib/mta-dashboard"
readonly BIN_ROOT="${INSTALL_ROOT}/bin"
readonly RELEASES_ROOT="${INSTALL_ROOT}/releases"

readonly NODE_AMD64_SHA256="d60acfe00a2932254bb0ad20e01b0d74397a0875595de719654b214f4b03f307"
readonly NODE_ARM64_SHA256="fff4078c5def658577f92c88db7db3bc0072924bfb93fe52c1e744a54e94abb8"
readonly WEBHOOK_AMD64_SHA256="3cdf93f0615f11bfc575c158d0d613666394228f6e830ff6f792178933773f7b"
readonly WEBHOOK_ARM64_SHA256="960187f361ca49403e0d3fce546c0a1999095a4ee6934a57ab8fef3170f2ddc8"

usage() {
  cat <<'EOF'
Usage: sudo bash deploy/run.sh [options]

Options:
  --env PATH          Read a different deployment environment file.
  --non-interactive   Install/update with validated defaults and free ports.
  --check             Validate configuration and host prerequisites only.
  -h, --help          Show this help.

With no options, use Up/Down and Enter to choose install, status, start, stop,
or uninstall. Copy deploy/.env.example to deploy/.env before installation.
EOF
}

while (($#)); do
  case "$1" in
    --env)
      [[ $# -ge 2 ]] || { printf '%s\n' '--env requires a path.' >&2; exit 2; }
      ENV_FILE="$2"
      shift 2
      ;;
    --non-interactive) NON_INTERACTIVE=1; shift ;;
    --check) CHECK_ONLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

step() { printf '\n[%s] %s\n' "$1" "$2"; }
note() { printf '    %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

select_menu() {
  local title="$1" key suffix option index=0
  shift
  local -a options=("$@")
  [[ -t 0 && -t 1 ]] || fail "The interactive menu requires a terminal. Use --check or --non-interactive for automation."
  while true; do
    printf '\033[2J\033[H%s\n\n' "$title"
    for option in "${options[@]}"; do
      if ((index == MENU_SELECTION)); then
        printf '  \033[1;36m> %s\033[0m\n' "$option"
      else
        printf '    %s\n' "$option"
      fi
      index=$((index + 1))
    done
    index=0
    printf '\nUse Up/Down and Enter.\n'
    IFS= read -rsn1 key || fail "Could not read the interactive terminal."
    if [[ "$key" == $'\033' ]]; then
      IFS= read -rsn2 suffix || true
      key+="$suffix"
    fi
    case "$key" in
      $'\033[A')
        if ((MENU_SELECTION == 0)); then
          MENU_SELECTION=$((${#options[@]} - 1))
        else
          MENU_SELECTION=$((MENU_SELECTION - 1))
        fi
        ;;
      $'\033[B') MENU_SELECTION=$(((MENU_SELECTION + 1) % ${#options[@]})) ;;
      '') return 0 ;;
    esac
  done
}

wait_for_enter() {
  ((NON_INTERACTIVE == 1)) && return 0
  printf '\nPress Enter to return to the menu.'
  IFS= read -rs
}

if [[ "$(uname -s 2>/dev/null || true)" != "Linux" ]]; then
  fail "deploy/run.sh supports Linux team servers only."
fi

if ((EUID != 0)); then
  command -v sudo >/dev/null 2>&1 || fail "Run as root, or install sudo and run this command again."
  escalation=("$0" --env "$ENV_FILE")
  ((NON_INTERACTIVE == 1)) && escalation+=(--non-interactive)
  ((CHECK_ONLY == 1)) && escalation+=(--check)
  exec sudo -- bash "${escalation[@]}"
fi

declare -A CONFIG=()
readonly ALLOWED_KEYS='GITHUB_REPOSITORY GITHUB_BRANCH GITHUB_WEBHOOK_SECRET GITEA_REPO_URL GITEA_BRANCH GITEA_AUTH_MODE GITEA_USERNAME GITEA_TOKEN GITEA_SSH_PRIVATE_KEY_FILE GITEA_SSH_KNOWN_HOSTS_FILE DASHBOARD_HOST DASHBOARD_PORT WEBHOOK_HOST WEBHOOK_PORT PUBLIC_DASHBOARD_URL PUBLIC_WEBHOOK_URL MIRROR_POLL_SECONDS MIRROR_WAIT_SECONDS MIRROR_RETRY_SECONDS GITEA_REQUEST_TIMEOUT_SECONDS RELEASE_RETENTION DATABASE PG_HOST PG_PORT PG_DATABASE PG_USER PG_PASSWORD PG_SSLMODE NODE_VERSION WEBHOOK_VERSION'

load_env_file() {
  [[ -f "$ENV_FILE" ]] || fail "Configuration file not found: $ENV_FILE. Copy deploy/.env.example to deploy/.env first."
  local raw key value allowed
  while IFS= read -r raw || [[ -n "$raw" ]]; do
    raw="${raw%$'\r'}"
    [[ "$raw" =~ ^[[:space:]]*$ || "$raw" =~ ^[[:space:]]*# ]] && continue
    [[ "$raw" == *=* ]] || fail "Invalid configuration line (expected KEY=value): $raw"
    key="${raw%%=*}"
    value="${raw#*=}"
    key="${key//[[:space:]]/}"
    [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] || fail "Invalid configuration key: $key"
    allowed=0
    for candidate in $ALLOWED_KEYS; do
      [[ "$candidate" == "$key" ]] && allowed=1 && break
    done
    ((allowed == 1)) || fail "Unknown configuration key: $key"
    if [[ "$value" =~ ^\".*\"$ ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" =~ ^\'.*\'$ ]]; then
      value="${value:1:${#value}-2}"
    fi
    CONFIG["$key"]="$value"
  done <"$ENV_FILE"
}

value() {
  local key="$1" default="${2:-}"
  printf '%s' "${CONFIG[$key]:-$default}"
}

require_value() {
  local key="$1"
  [[ -n "${CONFIG[$key]:-}" ]] || fail "$key is required in $ENV_FILE."
}

positive_integer() {
  local key="$1" number="$2"
  [[ "$number" =~ ^[1-9][0-9]*$ ]] || fail "$key must be a positive integer; got '$number'."
}

validate_port() {
  local key="$1" port="$2"
  [[ "$port" =~ ^[0-9]+$ ]] || fail "$key must be a number."
  ((10#$port > 8000 && 10#$port <= 65535)) || fail "$key must be above 8000 and no greater than 65535."
}

validate_standard_port() {
  local key="$1" port="$2"
  [[ "$port" =~ ^[0-9]+$ ]] || fail "$key must be a number."
  ((10#$port >= 1 && 10#$port <= 65535)) || fail "$key must be between 1 and 65535."
}

resolve_secret_file() {
  local configured="$1"
  [[ -n "$configured" ]] || return 1
  if [[ "$configured" = /* ]]; then
    printf '%s' "$configured"
  else
    printf '%s' "${DEPLOY_DIR}/${configured}"
  fi
}

validate_configuration() {
  require_value GITHUB_REPOSITORY
  require_value GITHUB_BRANCH
  require_value GITHUB_WEBHOOK_SECRET
  require_value GITEA_REPO_URL

  GITHUB_REPOSITORY="$(value GITHUB_REPOSITORY)"
  GITHUB_BRANCH="$(value GITHUB_BRANCH main)"
  GITHUB_WEBHOOK_SECRET="$(value GITHUB_WEBHOOK_SECRET)"
  GITEA_REPO_URL="$(value GITEA_REPO_URL)"
  GITEA_BRANCH="$(value GITEA_BRANCH "$GITHUB_BRANCH")"
  GITEA_AUTH_MODE="$(value GITEA_AUTH_MODE https)"
  GITEA_USERNAME="$(value GITEA_USERNAME)"
  GITEA_TOKEN="$(value GITEA_TOKEN)"
  DASHBOARD_HOST="$(value DASHBOARD_HOST 127.0.0.1)"
  DASHBOARD_PORT="$(value DASHBOARD_PORT 8501)"
  WEBHOOK_HOST="$(value WEBHOOK_HOST 127.0.0.1)"
  WEBHOOK_PORT="$(value WEBHOOK_PORT 9000)"
  PUBLIC_DASHBOARD_URL="$(value PUBLIC_DASHBOARD_URL)"
  PUBLIC_WEBHOOK_URL="$(value PUBLIC_WEBHOOK_URL)"
  MIRROR_POLL_SECONDS="$(value MIRROR_POLL_SECONDS 10)"
  MIRROR_WAIT_SECONDS="$(value MIRROR_WAIT_SECONDS 600)"
  MIRROR_RETRY_SECONDS="$(value MIRROR_RETRY_SECONDS 120)"
  GITEA_REQUEST_TIMEOUT_SECONDS="$(value GITEA_REQUEST_TIMEOUT_SECONDS 45)"
  RELEASE_RETENTION="$(value RELEASE_RETENTION 3)"
  DATABASE="$(value DATABASE false)"
  PG_HOST="$(value PG_HOST)"
  PG_PORT="$(value PG_PORT 5432)"
  PG_DATABASE="$(value PG_DATABASE)"
  PG_USER="$(value PG_USER)"
  PG_PASSWORD="$(value PG_PASSWORD)"
  PG_SSLMODE="$(value PG_SSLMODE prefer)"
  NODE_VERSION="$(value NODE_VERSION 22.23.2)"
  WEBHOOK_VERSION="$(value WEBHOOK_VERSION 2.8.3)"

  [[ "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || fail "GITHUB_REPOSITORY must be owner/repository."
  [[ "$GITHUB_BRANCH" =~ ^[A-Za-z0-9._/-]+$ && "$GITHUB_BRANCH" != *..* ]] || fail "GITHUB_BRANCH contains unsupported characters."
  [[ "$GITEA_BRANCH" =~ ^[A-Za-z0-9._/-]+$ && "$GITEA_BRANCH" != *..* ]] || fail "GITEA_BRANCH contains unsupported characters."
  [[ "$GITHUB_WEBHOOK_SECRET" =~ ^[A-Za-z0-9._~-]{32,}$ ]] || fail "GITHUB_WEBHOOK_SECRET must contain at least 32 URL-safe characters."
  [[ "$GITEA_REPO_URL" != *://*@* ]] || fail "GITEA_REPO_URL must not contain embedded credentials."
  [[ "$GITEA_REPO_URL" != *\?* && "$GITEA_REPO_URL" != *\#* ]] || fail "GITEA_REPO_URL must not contain a query string or fragment."

  case "$GITEA_AUTH_MODE" in
    https)
      [[ "$GITEA_REPO_URL" == https://* ]] || fail "HTTPS authentication requires an https:// GITEA_REPO_URL."
      [[ "$GITEA_REPO_URL" != *'@'* ]] || fail "The HTTPS Gitea URL must not contain credentials."
      [[ -n "$GITEA_USERNAME" && -n "$GITEA_TOKEN" ]] || fail "HTTPS mode requires GITEA_USERNAME and GITEA_TOKEN."
      ;;
    ssh)
      [[ "$GITEA_REPO_URL" == ssh://* || "$GITEA_REPO_URL" =~ ^[A-Za-z0-9._-]+@[A-Za-z0-9._-]+: ]] || fail "SSH mode requires an ssh:// or user@host:path Gitea URL."
      SSH_SOURCE_KEY="$(resolve_secret_file "$(value GITEA_SSH_PRIVATE_KEY_FILE)" || true)"
      SSH_SOURCE_HOSTS="$(resolve_secret_file "$(value GITEA_SSH_KNOWN_HOSTS_FILE)" || true)"
      [[ -f "$SSH_SOURCE_KEY" ]] || fail "GITEA_SSH_PRIVATE_KEY_FILE was not found."
      [[ -f "$SSH_SOURCE_HOSTS" ]] || fail "GITEA_SSH_KNOWN_HOSTS_FILE was not found."
      ;;
    *) fail "GITEA_AUTH_MODE must be https or ssh." ;;
  esac

  validate_port DASHBOARD_PORT "$DASHBOARD_PORT"
  validate_port WEBHOOK_PORT "$WEBHOOK_PORT"
  [[ "$DASHBOARD_PORT" != "$WEBHOOK_PORT" || "$DASHBOARD_HOST" != "$WEBHOOK_HOST" ]] || fail "Dashboard and webhook cannot use the same address and port."
  positive_integer MIRROR_POLL_SECONDS "$MIRROR_POLL_SECONDS"
  positive_integer MIRROR_WAIT_SECONDS "$MIRROR_WAIT_SECONDS"
  positive_integer MIRROR_RETRY_SECONDS "$MIRROR_RETRY_SECONDS"
  positive_integer GITEA_REQUEST_TIMEOUT_SECONDS "$GITEA_REQUEST_TIMEOUT_SECONDS"
  positive_integer RELEASE_RETENTION "$RELEASE_RETENTION"
  validate_standard_port PG_PORT "$PG_PORT"
  [[ "$NODE_VERSION" == 22.23.2 ]] || fail "This bundle supports checksum-pinned NODE_VERSION=22.23.2."
  [[ "$WEBHOOK_VERSION" == 2.8.3 ]] || fail "This bundle supports checksum-pinned WEBHOOK_VERSION=2.8.3."

  for public_url in "$PUBLIC_DASHBOARD_URL" "$PUBLIC_WEBHOOK_URL"; do
    if [[ -n "$public_url" ]]; then
      [[ "$public_url" == https://* && ! "$public_url" =~ [[:space:][:cntrl:]] ]] || fail "Configured public URLs must be whitespace-free HTTPS addresses."
    fi
  done

  if [[ "${DATABASE,,}" =~ ^(1|true|yes|on)$ ]]; then
    [[ -n "$PG_HOST" && -n "$PG_DATABASE" && -n "$PG_USER" && -n "$PG_PASSWORD" ]] || fail "DATABASE=true requires PG_HOST, PG_DATABASE, PG_USER, and PG_PASSWORD."
    DATABASE=true
  else
    DATABASE=false
  fi
}

detect_host() {
  [[ -r /etc/os-release ]] || fail "/etc/os-release is required to identify this Linux distribution."
  # shellcheck disable=SC1091
  source /etc/os-release
  OS_NAME="${PRETTY_NAME:-${ID:-Linux}}"
  case "${ID:-}" in
    ubuntu|debian) PACKAGE_MANAGER=apt ;;
    fedora|rhel|centos|rocky|almalinux) PACKAGE_MANAGER=dnf ;;
    *)
      if command -v apt-get >/dev/null 2>&1; then PACKAGE_MANAGER=apt
      elif command -v dnf >/dev/null 2>&1; then PACKAGE_MANAGER=dnf
      else fail "Only apt- and dnf-based Linux distributions are currently supported."
      fi
      ;;
  esac
  [[ "$(ps -p 1 -o comm= 2>/dev/null | tr -d ' ')" == systemd ]] || fail "systemd must be process 1; unmanaged fallbacks are intentionally unsupported."
  command -v systemctl >/dev/null 2>&1 || fail "systemctl is missing."
  SYSTEMCTL_BIN="$(command -v systemctl)"
  case "$(uname -m)" in
    x86_64|amd64) ARCH=amd64; NODE_ARCH=x64 ;;
    aarch64|arm64) ARCH=arm64; NODE_ARCH=arm64 ;;
    *) fail "Supported processor architectures are x86_64 and arm64." ;;
  esac
}

install_base_packages() {
  if [[ "$PACKAGE_MANAGER" == apt ]]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y ca-certificates curl git openssl sudo tar xz-utils util-linux iproute2
  else
    dnf install -y ca-certificates curl git openssl sudo tar xz util-linux iproute
  fi
}

node_is_compatible() {
  command -v node >/dev/null 2>&1 || return 1
  node -e '
    const [a,b,c] = process.versions.node.split(".").map(Number);
    process.exit((a === 20 && (b > 19 || (b === 19 && c >= 0))) ||
                 (a >= 22 && (a > 22 || b > 12 || (b === 12 && c >= 0))) ? 0 : 1);
  ' >/dev/null 2>&1
}

install_node() {
  if node_is_compatible && command -v npm >/dev/null 2>&1; then
    NODE_BIN="$(command -v node)"
    note "Using installed $(node --version), npm $(npm --version)."
    return
  fi
  local archive="node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.xz"
  local expected
  case "$ARCH" in
    amd64) expected="$NODE_AMD64_SHA256" ;;
    arm64) expected="$NODE_ARM64_SHA256" ;;
  esac
  [[ -n "$expected" ]] || fail "No reviewed Node ${NODE_VERSION} checksum is recorded for $ARCH."
  local temporary
  temporary="$(mktemp -d)"
  note "Downloading Node.js ${NODE_VERSION}."
  curl --fail --location --progress-bar --proto '=https' --tlsv1.2 \
    "https://nodejs.org/download/release/v${NODE_VERSION}/${archive}" \
    --output "${temporary}/${archive}"
  (cd "$temporary" && printf '%s  %s\n' "$expected" "$archive" | sha256sum --check --status) || fail "Node archive checksum verification failed."
  mkdir -p "/opt/node-v${NODE_VERSION}"
  tar -xJf "${temporary}/${archive}" --strip-components=1 -C "/opt/node-v${NODE_VERSION}"
  ln -sfn "/opt/node-v${NODE_VERSION}/bin/node" /usr/local/bin/node
  ln -sfn "/opt/node-v${NODE_VERSION}/bin/npm" /usr/local/bin/npm
  ln -sfn "/opt/node-v${NODE_VERSION}/bin/npx" /usr/local/bin/npx
  rm -rf -- "$temporary"
  node_is_compatible || fail "The installed Node binary does not satisfy the dashboard requirement."
  NODE_BIN="$(command -v node)"
  note "Installed $(node --version), npm $(npm --version)."
}

install_webhook() {
  if command -v webhook >/dev/null 2>&1 && webhook -version 2>&1 | grep -q "${WEBHOOK_VERSION}"; then
    WEBHOOK_BIN="$(command -v webhook)"
    note "Using installed webhook ${WEBHOOK_VERSION}."
    return
  fi
  local archive="webhook-linux-${ARCH}.tar.gz" expected temporary extracted
  case "$ARCH" in
    amd64) expected="$WEBHOOK_AMD64_SHA256" ;;
    arm64) expected="$WEBHOOK_ARM64_SHA256" ;;
  esac
  temporary="$(mktemp -d)"
  note "Downloading adnanh/webhook ${WEBHOOK_VERSION}."
  curl --fail --location --progress-bar --proto '=https' --tlsv1.2 \
    "https://github.com/adnanh/webhook/releases/download/${WEBHOOK_VERSION}/${archive}" \
    --output "${temporary}/${archive}"
  (cd "$temporary" && printf '%s  %s\n' "$expected" "$archive" | sha256sum --check --status) || fail "webhook archive checksum verification failed."
  tar -xzf "${temporary}/${archive}" -C "$temporary"
  extracted="$(find "$temporary" -type f -name webhook -print -quit)"
  [[ -n "$extracted" ]] || fail "The verified webhook archive did not contain the webhook binary."
  install -m 0755 "$extracted" /usr/local/bin/webhook
  rm -rf -- "$temporary"
  /usr/local/bin/webhook -version >/dev/null 2>&1 || fail "The installed webhook binary did not start."
  WEBHOOK_BIN="/usr/local/bin/webhook"
  note "Installed webhook ${WEBHOOK_VERSION}."
}

project_unit_matches() {
  local unit="$1" marker unit_file="/etc/systemd/system/${unit}"
  case "$unit" in
    mta-dashboard.service) marker="${INSTALL_ROOT}/current/dashboard/server/index.js" ;;
    mta-dashboard-webhook.service) marker="${ETC_ROOT}/hooks.json" ;;
    mta-dashboard-deploy.service) marker="${BIN_ROOT}/deploy_worker.sh" ;;
    *) return 1 ;;
  esac
  [[ -f "$unit_file" ]] && grep -Fq -- "$marker" "$unit_file"
}

stop_existing_services() {
  local unit
  for unit in mta-dashboard-webhook.service mta-dashboard-deploy.service mta-dashboard.service; do
    if project_unit_matches "$unit"; then
      systemctl stop "$unit" || true
    elif systemctl cat "$unit" >/dev/null 2>&1; then
      note "Skipped unrecognized unit $unit; its definition does not reference this deployment's fixed paths."
    fi
  done
}

port_in_use() {
  local port="$1"
  ss -H -ltn 2>/dev/null | awk '{print $4}' | grep -Eq ":${port}$"
}

next_free_port() {
  local port="$1"
  while ((port <= 65535)); do
    if ! port_in_use "$port"; then printf '%s' "$port"; return 0; fi
    port=$((port + 1))
  done
  return 1
}

choose_ports() {
  local replacement
  if port_in_use "$DASHBOARD_PORT"; then
    replacement="$(next_free_port "$((DASHBOARD_PORT + 1))")" || fail "No free dashboard port remains above $DASHBOARD_PORT."
    if ((NON_INTERACTIVE)); then
      DASHBOARD_PORT="$replacement"
    else
      MENU_SELECTION=0
      select_menu "Dashboard port $DASHBOARD_PORT is occupied." "Use free port $replacement" "Cancel installation"
      ((MENU_SELECTION == 0)) || fail "Choose a different DASHBOARD_PORT in deploy/.env and rerun."
      DASHBOARD_PORT="$replacement"
    fi
  fi
  if port_in_use "$WEBHOOK_PORT" || [[ "$WEBHOOK_PORT" == "$DASHBOARD_PORT" && "$WEBHOOK_HOST" == "$DASHBOARD_HOST" ]]; then
    replacement="$(next_free_port "$((WEBHOOK_PORT + 1))")" || fail "No free webhook port remains above $WEBHOOK_PORT."
    if ((NON_INTERACTIVE)); then
      WEBHOOK_PORT="$replacement"
    else
      MENU_SELECTION=0
      select_menu "Webhook port $WEBHOOK_PORT is occupied." "Use free port $replacement" "Cancel installation"
      ((MENU_SELECTION == 0)) || fail "Choose a different WEBHOOK_PORT in deploy/.env and rerun."
      WEBHOOK_PORT="$replacement"
    fi
  fi
}

systemd_quote() {
  local text="$1"
  text="${text//\\/\\\\}"
  text="${text//\"/\\\"}"
  printf '"%s"' "$text"
}

write_setting() {
  local file="$1" key="$2" setting="$3"
  printf '%s=%s\n' "$key" "$(systemd_quote "$setting")" >>"$file"
}

create_account_and_directories() {
  getent group "$SERVICE_GROUP" >/dev/null 2>&1 || groupadd --system "$SERVICE_GROUP"
  if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --gid "$SERVICE_GROUP" --home-dir "$STATE_ROOT" --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
  fi
  install -d -m 0750 -o root -g "$SERVICE_GROUP" "$ETC_ROOT"
  install -d -m 0755 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$INSTALL_ROOT" "$RELEASES_ROOT"
  install -d -m 0755 -o root -g root "$BIN_ROOT"
  install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$STATE_ROOT" "${STATE_ROOT}/queue" "${STATE_ROOT}/deliveries"
}

install_runtime_files() {
  install -m 0755 -o root -g root "${DEPLOY_DIR}/runtime/enqueue_deploy.sh" "${BIN_ROOT}/enqueue_deploy.sh"
  install -m 0755 -o root -g root "${DEPLOY_DIR}/runtime/deploy_worker.sh" "${BIN_ROOT}/deploy_worker.sh"

  cat >"${BIN_ROOT}/gitea_askpass.sh" <<'EOF'
#!/usr/bin/env bash
case "${1:-}" in
  *Username*) printf '%s\n' "${GITEA_USERNAME:-}" ;;
  *Password*) printf '%s\n' "${GITEA_TOKEN:-}" ;;
  *) exit 1 ;;
esac
EOF
  chmod 0755 "${BIN_ROOT}/gitea_askpass.sh"

  INSTALLED_SSH_KEY=""
  INSTALLED_SSH_HOSTS=""
  if [[ "$GITEA_AUTH_MODE" == ssh ]]; then
    install -d -m 0700 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "${STATE_ROOT}/.ssh"
    INSTALLED_SSH_KEY="${STATE_ROOT}/.ssh/gitea_deploy_key"
    INSTALLED_SSH_HOSTS="${STATE_ROOT}/.ssh/known_hosts"
    install -m 0600 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$SSH_SOURCE_KEY" "$INSTALLED_SSH_KEY"
    install -m 0600 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$SSH_SOURCE_HOSTS" "$INSTALLED_SSH_HOSTS"
  fi
}

write_runtime_configuration() {
  local dashboard_env="${ETC_ROOT}/dashboard.env"
  local deploy_env="${ETC_ROOT}/deploy.env"
  local webhook_secret_file="${ETC_ROOT}/github_webhook_secret"
  : >"$dashboard_env"
  : >"$deploy_env"

  write_setting "$dashboard_env" DASHBOARD_HOST "$DASHBOARD_HOST"
  write_setting "$dashboard_env" DASHBOARD_PORT "$DASHBOARD_PORT"
  write_setting "$dashboard_env" DASHBOARD_CONFIG_READ_ONLY true
  write_setting "$dashboard_env" DATABASE "$DATABASE"
  write_setting "$dashboard_env" PG_HOST "$PG_HOST"
  write_setting "$dashboard_env" PG_PORT "$PG_PORT"
  write_setting "$dashboard_env" PG_DATABASE "$PG_DATABASE"
  write_setting "$dashboard_env" PG_USER "$PG_USER"
  write_setting "$dashboard_env" PG_PASSWORD "$PG_PASSWORD"
  write_setting "$dashboard_env" PG_SSLMODE "$PG_SSLMODE"

  write_setting "$deploy_env" GITEA_REPO_URL "$GITEA_REPO_URL"
  write_setting "$deploy_env" GITEA_BRANCH "$GITEA_BRANCH"
  write_setting "$deploy_env" GITEA_AUTH_MODE "$GITEA_AUTH_MODE"
  write_setting "$deploy_env" GITEA_USERNAME "$GITEA_USERNAME"
  write_setting "$deploy_env" GITEA_TOKEN "$GITEA_TOKEN"
  write_setting "$deploy_env" GITEA_SSH_PRIVATE_KEY_FILE "$INSTALLED_SSH_KEY"
  write_setting "$deploy_env" GITEA_SSH_KNOWN_HOSTS_FILE "$INSTALLED_SSH_HOSTS"
  write_setting "$deploy_env" DASHBOARD_HOST "$DASHBOARD_HOST"
  write_setting "$deploy_env" DASHBOARD_PORT "$DASHBOARD_PORT"
  write_setting "$deploy_env" MIRROR_POLL_SECONDS "$MIRROR_POLL_SECONDS"
  write_setting "$deploy_env" MIRROR_WAIT_SECONDS "$MIRROR_WAIT_SECONDS"
  write_setting "$deploy_env" MIRROR_RETRY_SECONDS "$MIRROR_RETRY_SECONDS"
  write_setting "$deploy_env" GITEA_REQUEST_TIMEOUT_SECONDS "$GITEA_REQUEST_TIMEOUT_SECONDS"
  write_setting "$deploy_env" RELEASE_RETENTION "$RELEASE_RETENTION"
  write_setting "$deploy_env" SYSTEMCTL_BIN "$SYSTEMCTL_BIN"

  chown root:root "$dashboard_env" "$deploy_env"
  chmod 0600 "$dashboard_env" "$deploy_env"
  printf '%s\n' "$GITHUB_WEBHOOK_SECRET" >"$webhook_secret_file"
  chown root:root "$webhook_secret_file"
  chmod 0600 "$webhook_secret_file"

  cat >"${ETC_ROOT}/hooks.json" <<EOF
[
  {
    "id": "mta-dashboard-deploy",
    "execute-command": "${BIN_ROOT}/enqueue_deploy.sh",
    "command-working-directory": "${STATE_ROOT}",
    "response-message": "Deployment request accepted.",
    "include-command-output-in-response": false,
    "pass-arguments-to-command": [
      { "source": "payload", "name": "after" },
      { "source": "header", "name": "X-GitHub-Delivery" },
      { "source": "header", "name": "X-GitHub-Event" }
    ],
    "trigger-rule": {
      "and": [
        {
          "match": {
            "type": "payload-hmac-sha256",
            "secret": "${GITHUB_WEBHOOK_SECRET}",
            "parameter": { "source": "header", "name": "X-Hub-Signature-256" }
          }
        },
        {
          "match": {
            "type": "value",
            "value": "application/json",
            "parameter": { "source": "header", "name": "Content-Type" }
          }
        },
        {
          "match": {
            "type": "value",
            "value": "${GITHUB_REPOSITORY}",
            "parameter": { "source": "payload", "name": "repository.full_name" }
          }
        },
        {
          "or": [
            {
              "and": [
                {
                  "match": {
                    "type": "value",
                    "value": "push",
                    "parameter": { "source": "header", "name": "X-GitHub-Event" }
                  }
                },
                {
                  "match": {
                    "type": "value",
                    "value": "refs/heads/${GITHUB_BRANCH}",
                    "parameter": { "source": "payload", "name": "ref" }
                  }
                }
              ]
            },
            {
              "match": {
                "type": "value",
                "value": "ping",
                "parameter": { "source": "header", "name": "X-GitHub-Event" }
              }
            }
          ]
        }
      ]
    }
  }
]
EOF
  chown root:"$SERVICE_GROUP" "${ETC_ROOT}/hooks.json"
  chmod 0640 "${ETC_ROOT}/hooks.json"
}

install_systemd_services() {
  cat >/etc/systemd/system/mta-dashboard.service <<EOF
[Unit]
Description=MTA Strategy Optimizer dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${INSTALL_ROOT}/current
EnvironmentFile=${ETC_ROOT}/dashboard.env
ExecStart=${NODE_BIN} ${INSTALL_ROOT}/current/dashboard/server/index.js
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=${STATE_ROOT}

[Install]
WantedBy=multi-user.target
EOF

  cat >/etc/systemd/system/mta-dashboard-webhook.service <<EOF
[Unit]
Description=GitHub webhook receiver for the MTA dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
ExecStart=${WEBHOOK_BIN} -ip ${WEBHOOK_HOST} -port ${WEBHOOK_PORT} -http-methods POST -hooks ${ETC_ROOT}/hooks.json
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadOnlyPaths=${ETC_ROOT}
ReadWritePaths=${STATE_ROOT}/queue ${STATE_ROOT}/deliveries

[Install]
WantedBy=multi-user.target
EOF

  cat >/etc/systemd/system/mta-dashboard-deploy.service <<EOF
[Unit]
Description=Delayed Gitea deployment worker for the MTA dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
EnvironmentFile=${ETC_ROOT}/deploy.env
ExecStart=${BIN_ROOT}/deploy_worker.sh
Restart=always
RestartSec=5
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadOnlyPaths=${ETC_ROOT} ${BIN_ROOT}
ReadWritePaths=${INSTALL_ROOT} ${STATE_ROOT}

[Install]
WantedBy=multi-user.target
EOF

  printf '%s ALL=(root) NOPASSWD: %s restart mta-dashboard.service\n' \
    "$SERVICE_USER" "$SYSTEMCTL_BIN" >"/etc/sudoers.d/mta-dashboard-restart"
  chmod 0440 /etc/sudoers.d/mta-dashboard-restart
  visudo -cf /etc/sudoers.d/mta-dashboard-restart >/dev/null || fail "Generated sudoers rule did not validate."
  systemctl daemon-reload
  systemctl enable mta-dashboard.service mta-dashboard-webhook.service mta-dashboard-deploy.service
}

gitea_tip_as_service_user() {
  local output status
  local -a environment=(
    "GIT_TERMINAL_PROMPT=0"
    "GIT_HTTP_LOW_SPEED_LIMIT=1"
    "GIT_HTTP_LOW_SPEED_TIME=$GITEA_REQUEST_TIMEOUT_SECONDS"
    "GITEA_USERNAME=$GITEA_USERNAME"
    "GITEA_TOKEN=$GITEA_TOKEN"
  )
  if [[ "$GITEA_AUTH_MODE" == https ]]; then
    environment+=("GIT_ASKPASS=${BIN_ROOT}/gitea_askpass.sh")
  else
    environment+=("GIT_SSH_COMMAND=ssh -i ${INSTALLED_SSH_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=${INSTALLED_SSH_HOSTS}")
  fi
  if output="$(runuser -u "$SERVICE_USER" -- env "${environment[@]}" \
      timeout --signal=TERM --kill-after=5s "${GITEA_REQUEST_TIMEOUT_SECONDS}s" \
      git ls-remote --refs "$GITEA_REPO_URL" "refs/heads/${GITEA_BRANCH}")"; then
    :
  else
    status=$?
    if ((status == 124 || status == 137)); then
      printf '    Gitea did not respond within %ss. Check server DNS, firewall, TLS, and the repository address.\n' \
        "$GITEA_REQUEST_TIMEOUT_SECONDS" >&2
    else
      printf '    Gitea branch lookup failed with Git exit status %s. Review the Git error above and verify the read-only credential.\n' \
        "$status" >&2
    fi
    return "$status"
  fi
  output="$(awk 'NR == 1 { print tolower($1) }' <<<"$output")"
  if [[ -z "$output" ]]; then
    printf '    Gitea was reachable, but branch %s was not found in the configured repository.\n' "$GITEA_BRANCH" >&2
    return 3
  fi
  printf '%s' "$output"
}

queue_initial_deployment() {
  local tip delivery
  if tip="$(gitea_tip_as_service_user)"; then
    :
  else
    fail "Could not resolve the configured Gitea branch. No dashboard process was started; correct the reported cause and choose Install or update again."
  fi
  [[ "$tip" =~ ^[0-9a-f]{40}$ ]] || fail "Could not resolve Gitea branch $GITEA_BRANCH with the configured credentials."
  delivery="bootstrap-$(date -u +%Y%m%d%H%M%S)"
  runuser -u "$SERVICE_USER" -- "${BIN_ROOT}/enqueue_deploy.sh" "$tip" "$delivery"
  INITIAL_COMMIT="$tip"
}

wait_for_initial_deployment() {
  local deadline=$(( $(date +%s) + 1800 )) active=""
  while (( $(date +%s) < deadline )); do
    active="$(tr -d '\r\n' <"${STATE_ROOT}/active_commit" 2>/dev/null || true)"
    if [[ "$active" == "$INITIAL_COMMIT" ]] && systemctl is-active --quiet mta-dashboard.service; then
      note "Initial release $active is active."
      return 0
    fi
    sleep 5
  done
  journalctl -u mta-dashboard-deploy.service -n 30 --no-pager >&2 || true
  fail "Initial deployment did not become healthy within 30 minutes."
}

test_signed_webhook() {
  local host="$WEBHOOK_HOST" base payload signature delivery
  [[ "$host" == "0.0.0.0" || "$host" == "::" ]] && host="127.0.0.1"
  base="http://${host}:${WEBHOOK_PORT}"
  delivery="localtest-$(date -u +%Y%m%d%H%M%S)"
  payload="{\"ref\":\"refs/heads/${GITHUB_BRANCH}\",\"after\":\"${INITIAL_COMMIT}\",\"repository\":{\"full_name\":\"${GITHUB_REPOSITORY}\"}}"
  signature="$(GITHUB_WEBHOOK_SECRET="$GITHUB_WEBHOOK_SECRET" PAYLOAD="$payload" node -e '
    const crypto = require("node:crypto");
    process.stdout.write("sha256=" + crypto.createHmac("sha256", process.env.GITHUB_WEBHOOK_SECRET).update(process.env.PAYLOAD).digest("hex"));
  ')"
  curl --fail --silent --show-error --max-time 8 \
    -X POST \
    -H 'Content-Type: application/json' \
    -H 'X-GitHub-Event: push' \
    -H "X-GitHub-Delivery: ${delivery}" \
    -H "X-Hub-Signature-256: ${signature}" \
    --data-binary "$payload" \
    "${base}/hooks/mta-dashboard-deploy" >/dev/null
  note "The locally signed GitHub-style webhook was accepted."
}

offer_remove_bootstrap_env() {
  if ((NON_INTERACTIVE)); then
    note "Bootstrap credentials remain at $ENV_FILE; remove that file after confirming the services are healthy."
    return
  fi
  MENU_SELECTION=0
  select_menu "Runtime credentials are installed under $ETC_ROOT. What should happen to $ENV_FILE?" \
    "Keep bootstrap file for now (recommended)" \
    "Permanently remove bootstrap file"
  if ((MENU_SELECTION == 1)); then
    rm -f -- "$ENV_FILE"
    note "Removed the uploaded bootstrap credential file; this cannot be undone."
  else
    note "Bootstrap credentials remain at $ENV_FILE; remove that file after confirming the services are healthy."
  fi
}

managed_unit_exists() {
  project_unit_matches "$1"
}

show_status() {
  local unit enabled active
  step STATUS "Managed service state"
  for unit in mta-dashboard.service mta-dashboard-webhook.service mta-dashboard-deploy.service; do
    if managed_unit_exists "$unit"; then
      enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
      active="$(systemctl is-active "$unit" 2>/dev/null || true)"
      printf '    %-38s active=%-10s enabled=%s\n' "$unit" "${active:-unknown}" "${enabled:-unknown}"
    else
      printf '    %-38s not installed\n' "$unit"
    fi
  done
  if [[ -r "${STATE_ROOT}/active_commit" ]]; then
    note "Active commit: $(tr -d '\r\n' <"${STATE_ROOT}/active_commit")"
  fi
  note "Logs: journalctl -u mta-dashboard-deploy.service -f"
}

start_managed_services() {
  managed_unit_exists mta-dashboard-webhook.service || { note "Services are not installed. Choose Install or update first."; return 0; }
  systemctl enable mta-dashboard-webhook.service mta-dashboard-deploy.service >/dev/null
  systemctl restart mta-dashboard-webhook.service mta-dashboard-deploy.service
  if [[ -L "${INSTALL_ROOT}/current" ]] && managed_unit_exists mta-dashboard.service; then
    systemctl enable mta-dashboard.service >/dev/null
    systemctl restart mta-dashboard.service
  else
    note "Dashboard has no active release yet; the deploy worker will start it after a successful build."
  fi
  note "Managed services started."
  show_status
}

stop_managed_services() {
  stop_existing_services
  note "Managed services stopped; installed files and automatic-start settings were preserved."
  show_status
}

project_process_matches() {
  local pid="$1" process_uid command_line working_directory unit
  [[ "$pid" =~ ^[1-9][0-9]*$ && -r "/proc/${pid}/status" ]] || return 1
  process_uid="$(awk '$1 == "Uid:" { print $2; exit }' "/proc/${pid}/status" 2>/dev/null || true)"
  [[ -n "${PROJECT_SERVICE_UID:-}" && "$process_uid" == "$PROJECT_SERVICE_UID" ]] || return 1

  for unit in mta-dashboard.service mta-dashboard-webhook.service mta-dashboard-deploy.service; do
    if project_unit_matches "$unit" && grep -Fq -- "/${unit}" "/proc/${pid}/cgroup" 2>/dev/null; then
      return 0
    fi
  done

  working_directory="$(readlink -f "/proc/${pid}/cwd" 2>/dev/null || true)"
  case "$working_directory" in
    "$INSTALL_ROOT"|"${INSTALL_ROOT}/"*|"$STATE_ROOT"|"${STATE_ROOT}/"*) return 0 ;;
  esac

  command_line="$(tr '\0' ' ' <"/proc/${pid}/cmdline" 2>/dev/null || true)"
  case "$command_line" in
    *"${INSTALL_ROOT}/"*|*"${STATE_ROOT}/"*|*"${ETC_ROOT}/hooks.json"*) return 0 ;;
  esac
  return 1
}

find_project_processes() {
  local process_path pid
  for process_path in /proc/[1-9]*; do
    [[ -d "$process_path" ]] || continue
    pid="${process_path##*/}"
    project_process_matches "$pid" && printf '%s\n' "$pid"
  done
}

terminate_stale_project_processes() {
  local pid executable
  local -a candidates=() remaining=()
  MENU_SELECTION=0
  select_menu "This stops the three dashboard services, then terminates only revalidated mta-dashboard project processes." \
    "Cancel (recommended)" \
    "Stop services and terminate stale project processes"
  if ((MENU_SELECTION == 0)); then
    note "Stale-process cleanup cancelled."
    return 0
  fi

  [[ "$SERVICE_USER" == mta-dashboard ]] || fail "Refusing unexpected service account: $SERVICE_USER"
  [[ "$ETC_ROOT" == /etc/mta-dashboard ]] || fail "Refusing unexpected configuration path: $ETC_ROOT"
  [[ "$INSTALL_ROOT" == /opt/mta-dashboard ]] || fail "Refusing unexpected install path: $INSTALL_ROOT"
  [[ "$STATE_ROOT" == /var/lib/mta-dashboard ]] || fail "Refusing unexpected state path: $STATE_ROOT"

  stop_existing_services
  if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    note "The dedicated service account does not exist; there are no eligible project processes."
    return 0
  fi
  PROJECT_SERVICE_UID="$(id -u "$SERVICE_USER")"
  mapfile -t candidates < <(find_project_processes)
  if ((${#candidates[@]} == 0)); then
    note "No stale process matched the dedicated account and fixed project paths."
    return 0
  fi

  note "Eligible project process identifiers: ${candidates[*]}"
  for pid in "${candidates[@]}"; do
    if project_process_matches "$pid"; then
      executable="$(readlink -f "/proc/${pid}/exe" 2>/dev/null || true)"
      note "Sending TERM to project PID $pid (${executable:-unknown executable})."
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done

  for _ in {1..10}; do
    remaining=()
    for pid in "${candidates[@]}"; do
      project_process_matches "$pid" && remaining+=("$pid")
    done
    ((${#remaining[@]} == 0)) && break
    sleep 0.5
  done

  for pid in "${remaining[@]}"; do
    if project_process_matches "$pid"; then
      note "Project PID $pid ignored TERM; sending KILL after revalidation."
      kill -KILL "$pid" 2>/dev/null || true
    fi
  done
  note "Project-only stale-process cleanup complete. Automatic-start settings were preserved."
}

remove_service_definitions() {
  local unit unit_file
  stop_existing_services
  for unit in mta-dashboard.service mta-dashboard-webhook.service mta-dashboard-deploy.service; do
    unit_file="/etc/systemd/system/${unit}"
    if project_unit_matches "$unit"; then
      systemctl disable "$unit" >/dev/null 2>&1 || true
      rm -f -- "$unit_file"
    elif [[ -e "$unit_file" ]]; then
      note "Preserved unrecognized unit file $unit_file."
    fi
  done
  if [[ -f /etc/sudoers.d/mta-dashboard-restart ]] &&
     grep -Fq -- 'restart mta-dashboard.service' /etc/sudoers.d/mta-dashboard-restart; then
    rm -f -- /etc/sudoers.d/mta-dashboard-restart
  fi
  systemctl daemon-reload
  systemctl reset-failed >/dev/null 2>&1 || true
}

uninstall_managed_services() {
  MENU_SELECTION=0
  select_menu "Choose uninstall scope. Shared packages such as Git, Node.js, and webhook are retained." \
    "Cancel (recommended)" \
    "Remove systemd services; preserve configuration, releases, and state" \
    "Full uninstall: remove services, configuration, releases, state, and service account"
  case "$MENU_SELECTION" in
    0) note "Uninstall cancelled." ;;
    1)
      remove_service_definitions
      note "Removed the three systemd service definitions. Configuration, releases, state, and the service account were preserved."
      ;;
    2)
      MENU_SELECTION=0
      select_menu "Full uninstall permanently deletes $ETC_ROOT, $INSTALL_ROOT, and $STATE_ROOT." \
        "Cancel (recommended)" \
        "Permanently delete managed deployment data"
      if ((MENU_SELECTION == 1)); then
        [[ "$ETC_ROOT" == /etc/mta-dashboard ]] || fail "Refusing unexpected configuration path: $ETC_ROOT"
        [[ "$INSTALL_ROOT" == /opt/mta-dashboard ]] || fail "Refusing unexpected install path: $INSTALL_ROOT"
        [[ "$STATE_ROOT" == /var/lib/mta-dashboard ]] || fail "Refusing unexpected state path: $STATE_ROOT"
        remove_service_definitions
        rm -rf -- /etc/mta-dashboard /opt/mta-dashboard /var/lib/mta-dashboard
        if id "$SERVICE_USER" >/dev/null 2>&1; then userdel "$SERVICE_USER"; fi
        if getent group "$SERVICE_GROUP" >/dev/null 2>&1; then groupdel "$SERVICE_GROUP"; fi
        note "Full uninstall complete. The uploaded deploy/ bundle and shared packages were not removed."
      else
        note "Full uninstall cancelled."
      fi
      ;;
  esac
}

print_summary() {
  local dashboard_url webhook_url
  dashboard_url="${PUBLIC_DASHBOARD_URL:-http://${DASHBOARD_HOST}:${DASHBOARD_PORT}}"
  webhook_url="${PUBLIC_WEBHOOK_URL:-http://${WEBHOOK_HOST}:${WEBHOOK_PORT}}"
  if [[ "$webhook_url" != */hooks/mta-dashboard-deploy ]]; then
    webhook_url="${webhook_url%/}/hooks/mta-dashboard-deploy"
  fi
  cat <<EOF

------------------------------------------------------------
Deployment complete
------------------------------------------------------------
Dashboard:       ${dashboard_url}
Active commit:   ${INITIAL_COMMIT}

Configure the GitHub repository webhook with:
  Payload URL:   ${webhook_url}
  Content type:  application/json
  Secret:        the protected value in ${ETC_ROOT}/github_webhook_secret
  Events:        push events only
  Active:        enabled
  SSL verify:    enabled

The receiver accepts only ${GITHUB_REPOSITORY} pushes to ${GITHUB_BRANCH}.
The server pulls ${GITEA_BRANCH} only from the configured Gitea repository and
will not build until that branch resolves to the exact queued GitHub commit.

Service status:
  systemctl status mta-dashboard.service
  systemctl status mta-dashboard-webhook.service
  systemctl status mta-dashboard-deploy.service

Deployment logs:
  journalctl -u mta-dashboard-deploy.service -f

To display the webhook secret while configuring GitHub:
  sudo cat ${ETC_ROOT}/github_webhook_secret
EOF
  if [[ "$DASHBOARD_HOST" != 127.0.0.1 && "$DASHBOARD_HOST" != ::1 ]]; then
    printf '\nWARNING: the dashboard is bound beyond loopback. Restrict it to the team network or put authenticated TLS in front of it.\n'
  fi
  if [[ "$WEBHOOK_HOST" != 127.0.0.1 && "$WEBHOOK_HOST" != ::1 ]]; then
    printf '\nWARNING: the webhook is bound beyond loopback. Require HTTPS and keep HMAC verification enabled.\n'
  fi
}

install_or_update() {
  step 1 "Reading and validating deployment configuration"
  CONFIG=()
  load_env_file
  validate_configuration
  chmod 0600 "$ENV_FILE" 2>/dev/null || true
  note "Configuration is valid; no credential was printed."

  step 2 "Installing operating-system prerequisites"
  install_base_packages
  install_node
  install_webhook

  step 3 "Selecting local service ports"
  stop_existing_services
  choose_ports
  note "Dashboard ${DASHBOARD_HOST}:${DASHBOARD_PORT}; webhook ${WEBHOOK_HOST}:${WEBHOOK_PORT}."

  step 4 "Installing protected configuration and runtime files"
  create_account_and_directories
  install_runtime_files
  write_runtime_configuration
  install_systemd_services

  step 5 "Resolving and queueing the current Gitea branch"
  queue_initial_deployment
  note "Gitea currently exposes $INITIAL_COMMIT."

  step 6 "Starting supervised services and building the first release"
  systemctl restart mta-dashboard-webhook.service
  systemctl restart mta-dashboard-deploy.service
  wait_for_initial_deployment

  step 7 "Testing the signed GitHub webhook path"
  test_signed_webhook
  offer_remove_bootstrap_env
  print_summary
}

detect_host

if ((CHECK_ONLY)); then
  step CHECK "Reading and validating deployment configuration"
  load_env_file
  validate_configuration
  note "Configuration and host prerequisites are valid; no credential was printed and no installation or service mutation was performed."
  exit 0
fi

if ((NON_INTERACTIVE)); then
  note "$OS_NAME on $ARCH, systemd, $PACKAGE_MANAGER."
  install_or_update
  exit 0
fi

while true; do
  MENU_SELECTION=0
  select_menu "MTA Strategy Optimizer deployment — $OS_NAME" \
    "Install or update" \
    "Show service status" \
    "Start or restart services" \
    "Stop services" \
    "Terminate stale project processes" \
    "Uninstall services" \
    "Exit"
  case "$MENU_SELECTION" in
    0) install_or_update; wait_for_enter ;;
    1) show_status; wait_for_enter ;;
    2) start_managed_services; wait_for_enter ;;
    3) stop_managed_services; wait_for_enter ;;
    4) terminate_stale_project_processes; wait_for_enter ;;
    5) uninstall_managed_services; wait_for_enter ;;
    6) printf '\033[2J\033[H'; exit 0 ;;
  esac
done
