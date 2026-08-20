#!/usr/bin/env bash
# Interactive Linux lifecycle manager for the MTA Strategy Optimizer dashboard.
#
# This is the only command needed after uploading run.sh beside .env: its arrow-key menu
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
readonly DEPLOY_INSTALLATION_ROOT="${DEPLOY_DIR}/installation"
readonly ETC_ROOT="${DEPLOY_INSTALLATION_ROOT}/config"
readonly INSTALL_ROOT="${DEPLOY_INSTALLATION_ROOT}/app"
readonly STATE_ROOT="${DEPLOY_INSTALLATION_ROOT}/state"
readonly SYSTEMD_ROOT="${DEPLOY_INSTALLATION_ROOT}/systemd"
readonly BIN_ROOT="${INSTALL_ROOT}/bin"
readonly RELEASES_ROOT="${INSTALL_ROOT}/releases"
readonly ACL_RECORD="${DEPLOY_INSTALLATION_ROOT}/.installer_acl_paths"
readonly LEGACY_ETC_ROOT="/etc/mta-dashboard"
readonly LEGACY_INSTALL_ROOT="/opt/mta-dashboard"
readonly LEGACY_STATE_ROOT="/var/lib/mta-dashboard"

readonly NODE_AMD64_SHA256="d60acfe00a2932254bb0ad20e01b0d74397a0875595de719654b214f4b03f307"
readonly NODE_ARM64_SHA256="fff4078c5def658577f92c88db7db3bc0072924bfb93fe52c1e744a54e94abb8"
readonly WEBHOOK_AMD64_SHA256="3cdf93f0615f11bfc575c158d0d613666394228f6e830ff6f792178933773f7b"
readonly WEBHOOK_ARM64_SHA256="960187f361ca49403e0d3fce546c0a1999095a4ee6934a57ab8fef3170f2ddc8"
readonly ENQUEUE_RUNTIME_SHA256="5e7ddcda095bc8ad7d8b397282493eec6a0b815f48e617c1f3416232047a3e63"
readonly WORKER_RUNTIME_SHA256="139262167fa9d811ed0282ac88040c5efeab9e5246faf038e9d85127d32c095d"

usage() {
  cat <<'EOF'
Usage: sudo bash run.sh [options]

Options:
  --env PATH          Read a different deployment environment file.
  --non-interactive   Install/update with validated defaults and free ports.
  --check             Validate configuration and host prerequisites only.
  -h, --help          Show this help.

With no options, use Up/Down and Enter to choose install, status, start, stop,
or uninstall. Place the prepared .env beside run.sh before installation.
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
  [[ -f "$ENV_FILE" ]] || fail "Configuration file not found: $ENV_FILE. Place the prepared .env beside run.sh and retry."
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
  [[ ! "$DEPLOY_DIR" =~ [[:space:][:cntrl:]] ]] || fail "The deploy directory path must not contain whitespace or control characters: $DEPLOY_DIR"
  [[ ! -L "$DEPLOY_INSTALLATION_ROOT" ]] || fail "Refusing symbolic-link installation path: $DEPLOY_INSTALLATION_ROOT"
  [[ ! -e "$DEPLOY_INSTALLATION_ROOT" || -d "$DEPLOY_INSTALLATION_ROOT" ]] || fail "Installation path is not a directory: $DEPLOY_INSTALLATION_ROOT"
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
    apt-get install -y acl ca-certificates coreutils curl git openssl sudo tar xz-utils util-linux iproute2
  else
    dnf install -y acl ca-certificates coreutils curl git openssl sudo tar xz util-linux iproute
  fi
  if ! command -v getfacl >/dev/null 2>&1 || ! command -v setfacl >/dev/null 2>&1; then
    fail "The acl package did not provide getfacl and setfacl."
  fi
  command -v base64 >/dev/null 2>&1 || fail "The coreutils base64 command is required to materialize the embedded runtime."
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
  local unit="$1" unit_file="/etc/systemd/system/${unit}"
  local -a markers=()
  case "$unit" in
    mta-dashboard.service)
      markers=("${INSTALL_ROOT}/current/dashboard/server/index.js" "${LEGACY_INSTALL_ROOT}/current/dashboard/server/index.js")
      ;;
    mta-dashboard-webhook.service)
      markers=("${ETC_ROOT}/hooks.json" "${LEGACY_ETC_ROOT}/hooks.json")
      ;;
    mta-dashboard-deploy.service)
      markers=("${BIN_ROOT}/deploy_worker.sh" "${LEGACY_INSTALL_ROOT}/bin/deploy_worker.sh")
      ;;
    *) return 1 ;;
  esac
  if [[ -L "$unit_file" && "$(readlink "$unit_file")" == "${SYSTEMD_ROOT}/${unit}" ]]; then
    return 0
  fi
  [[ -f "$unit_file" ]] || return 1
  local marker
  for marker in "${markers[@]}"; do
    grep -Fq -- "$marker" "$unit_file" && return 0
  done
  return 1
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
      ((MENU_SELECTION == 0)) || fail "Choose a different DASHBOARD_PORT in .env and rerun."
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
      ((MENU_SELECTION == 0)) || fail "Choose a different WEBHOOK_PORT in .env and rerun."
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

grant_service_traversal() {
  local path="$DEPLOY_DIR"
  if [[ ! -f "$ACL_RECORD" ]]; then
    install -m 0600 -o root -g root /dev/null "$ACL_RECORD"
  fi
  while [[ "$path" != / ]]; do
    if ! getfacl -cp -- "$path" 2>/dev/null | grep -Fq "user:${SERVICE_USER}:"; then
      setfacl -m "u:${SERVICE_USER}:--x" -- "$path" || fail "Could not grant $SERVICE_USER traversal on $path."
      grep -Fxq -- "$path" "$ACL_RECORD" 2>/dev/null || printf '%s\n' "$path" >>"$ACL_RECORD"
    fi
    path="$(dirname "$path")"
  done
  runuser -u "$SERVICE_USER" -- test -x "$DEPLOY_DIR" ||
    fail "The $SERVICE_USER account still cannot traverse $DEPLOY_DIR. A pre-existing account ACL may omit execute permission; preserve or repair that ACL, then retry."
}

create_account_and_directories() {
  getent group "$SERVICE_GROUP" >/dev/null 2>&1 || groupadd --system "$SERVICE_GROUP"
  if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --gid "$SERVICE_GROUP" --home-dir "$STATE_ROOT" --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
  fi
  install -d -m 0711 -o root -g root "$DEPLOY_INSTALLATION_ROOT"
  install -d -m 0755 -o root -g root "$SYSTEMD_ROOT"
  install -d -m 0750 -o root -g "$SERVICE_GROUP" "$ETC_ROOT"
  install -d -m 0755 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$INSTALL_ROOT" "$RELEASES_ROOT"
  install -d -m 0755 -o root -g root "$BIN_ROOT"
  install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$STATE_ROOT" "${STATE_ROOT}/queue" "${STATE_ROOT}/deliveries" "${STATE_ROOT}/npm-cache"
  usermod --home "$STATE_ROOT" "$SERVICE_USER"
  grant_service_traversal
}

write_embedded_enqueue_runtime() {
  local target="${1:-${BIN_ROOT}/enqueue_deploy.sh}"
  base64 --decode >"$target" <<'MTA_ENQUEUE_RUNTIME'
IyEvdXNyL2Jpbi9lbnYgYmFzaAojIFZhbGlkYXRlIHRoZSB1bnRydXN0ZWQgR2l0SHViIHBheWxvYWQgdmFsdWVzIHBhc3NlZCBieSB3ZWJob29rIGFuZCBhdG9taWNhbGx5CiMgcmVwbGFjZSB0aGUgZHVyYWJsZSBkZXNpcmVkLWNvbW1pdCBxdWV1ZSBlbnRyeS4gU2xvdyBkZXBsb3ltZW50IGhhcHBlbnMgaW4KIyBkZXBsb3lfd29ya2VyLnNoLCBuZXZlciBpbiB0aGlzIHJlcXVlc3QgcGF0aC4KCnNldCAtRWV1byBwaXBlZmFpbAoKU0NSSVBUX0RJUj0iJChjZCAiJChkaXJuYW1lICIke0JBU0hfU09VUkNFWzBdfSIpIiAmJiBwd2QpIgpyZWFkb25seSBTQ1JJUFRfRElSCkRFRkFVTFRfSU5TVEFMTEFUSU9OX1JPT1Q9IiQoY2QgIiR7U0NSSVBUX0RJUn0vLi4vLi4iICYmIHB3ZCkiCnJlYWRvbmx5IERFRkFVTFRfSU5TVEFMTEFUSU9OX1JPT1QKcmVhZG9ubHkgU1RBVEVfUk9PVD0iJHtNVEFfREFTSEJPQVJEX1NUQVRFX1JPT1Q6LSR7REVGQVVMVF9JTlNUQUxMQVRJT05fUk9PVH0vc3RhdGV9IgpyZWFkb25seSBRVUVVRV9ESVI9IiR7U1RBVEVfUk9PVH0vcXVldWUiCnJlYWRvbmx5IERFTElWRVJZX0RJUj0iJHtTVEFURV9ST09UfS9kZWxpdmVyaWVzIgpyZWFkb25seSBRVUVVRV9GSUxFPSIke1FVRVVFX0RJUn0vcGVuZGluZyIKcmVhZG9ubHkgUVVFVUVfTE9DSz0iJHtRVUVVRV9ESVJ9L3F1ZXVlLmxvY2siCgpjb21taXQ9IiR7MTotfSIKZGVsaXZlcnk9IiR7MjotfSIKZXZlbnQ9IiR7MzotcHVzaH0iCgppZiBbWyAhICIkZGVsaXZlcnkiID1+IF5bQS1aYS16MC05LV17OCwxMjh9JCBdXTsgdGhlbgogIHByaW50ZiAnW2VucXVldWVdIFJlamVjdGVkIGFuIGludmFsaWQgWC1HaXRIdWItRGVsaXZlcnkgaWRlbnRpZmllci5cbicgPiYyCiAgZXhpdCAyCmZpCgppZiBbWyAiJGV2ZW50IiA9PSBwaW5nIF1dOyB0aGVuCiAgcHJpbnRmICdbZW5xdWV1ZV0gQXV0aGVudGljYXRlZCBHaXRIdWIgc2V0dXAgcGluZyAlcyBhY2NlcHRlZDsgbm8gZGVwbG95bWVudCB3YXMgcXVldWVkLlxuJyAiJGRlbGl2ZXJ5IgogIGV4aXQgMApmaQoKaWYgW1sgIiRldmVudCIgIT0gcHVzaCBdXTsgdGhlbgogIHByaW50ZiAnW2VucXVldWVdIFJlamVjdGVkIHVuc3VwcG9ydGVkIEdpdEh1YiBldmVudCAlcy5cbicgIiRldmVudCIgPiYyCiAgZXhpdCAyCmZpCgppZiBbWyAhICIkY29tbWl0IiA9fiBeWzAtOWEtZkEtRl17NDB9JCBdXTsgdGhlbgogIHByaW50ZiAnW2VucXVldWVdIFJlamVjdGVkIGFuIGludmFsaWQgR2l0SHViIGFmdGVyIGNvbW1pdC5cbicgPiYyCiAgZXhpdCAyCmZpCmNvbW1pdD0iJHtjb21taXQsLH0iCmlmIFtbICIkY29tbWl0IiA9PSAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwIF1dOyB0aGVuCiAgcHJpbnRmICdbZW5xdWV1ZV0gUmVqZWN0ZWQgdGhlIGFsbC16ZXJvIGNvbW1pdCB1c2VkIGZvciBhIGRlbGV0ZWQgcmVmLlxuJyA+JjIKICBleGl0IDIKZmkKCnVtYXNrIDA3Nwpta2RpciAtcCAiJFFVRVVFX0RJUiIgIiRERUxJVkVSWV9ESVIiCgpleGVjIDk+IiRRVUVVRV9MT0NLIgppZiAhIGZsb2NrIC13IDUgOTsgdGhlbgogIHByaW50ZiAnW2VucXVldWVdIENvdWxkIG5vdCBhY3F1aXJlIHRoZSBxdWV1ZSBsb2NrLlxuJyA+JjIKICBleGl0IDEKZmkKCmlmIFtbIC1mICIke0RFTElWRVJZX0RJUn0vJHtkZWxpdmVyeX0iIF1dOyB0aGVuCiAgcHJpbnRmICdbZW5xdWV1ZV0gRGVsaXZlcnkgJXMgd2FzIGFscmVhZHkgYWNjZXB0ZWQuXG4nICIkZGVsaXZlcnkiCiAgZXhpdCAwCmZpCgp0ZW1wb3Jhcnk9IiQobWt0ZW1wICIke1FVRVVFX0RJUn0vLnBlbmRpbmcuWFhYWFhYIikiCmNsZWFudXAoKSB7IHJtIC1mIC0tICIkdGVtcG9yYXJ5IjsgfQp0cmFwIGNsZWFudXAgRVhJVAoKcHJpbnRmICclc1xuJXNcbiVzXG4nIFwKICAiJGNvbW1pdCIgXAogICIkZGVsaXZlcnkiIFwKICAiJChkYXRlIC11ICslWS0lbS0lZFQlSDolTTolU1opIiA+IiR0ZW1wb3JhcnkiCmNobW9kIDYwMCAiJHRlbXBvcmFyeSIKbXYgLWYgLS0gIiR0ZW1wb3JhcnkiICIkUVVFVUVfRklMRSIKdGVtcG9yYXJ5PSIiCgojIFJlY29yZGluZyBhZnRlciB0aGUgYXRvbWljIHF1ZXVlIG1vdmUgbWFrZXMgYSBjcmFzaCBzYWZlOiBhdCB3b3JzdCBHaXRIdWIncwojIHJlZGVsaXZlcnkgd3JpdGVzIHRoZSBzYW1lIGRlc2lyZWQgY29tbWl0IGFnYWluOyBpdCBjYW4gbmV2ZXIgYmUgYWNrbm93bGVkZ2VkCiMgYW5kIHRoZW4gbG9zdCBiZWZvcmUgcmVhY2hpbmcgdGhlIHF1ZXVlLgo6ID4iJHtERUxJVkVSWV9ESVJ9LyR7ZGVsaXZlcnl9IgpmaW5kICIkREVMSVZFUllfRElSIiAtdHlwZSBmIC1tdGltZSArMzAgLWRlbGV0ZSAyPi9kZXYvbnVsbCB8fCB0cnVlCgpwcmludGYgJ1tlbnF1ZXVlXSBBY2NlcHRlZCBkZWxpdmVyeSAlcyBmb3IgY29tbWl0ICVzLlxuJyAiJGRlbGl2ZXJ5IiAiJGNvbW1pdCIK
MTA_ENQUEUE_RUNTIME
}

write_embedded_worker_runtime() {
  local target="${1:-${BIN_ROOT}/deploy_worker.sh}"
  base64 --decode >"$target" <<'MTA_WORKER_RUNTIME'
IyEvdXNyL2Jpbi9lbnYgYmFzaAojIFN1cGVydmlzZWQgZGVwbG95bWVudCB3b3JrZXI6IGNvYWxlc2NlIEdpdEh1YiByZXF1ZXN0cywgd2FpdCB1bnRpbCBHaXRlYSdzCiMgYnJhbmNoIHRpcCBpcyB0aGUgZXhhY3QgcmVxdWVzdGVkIGNvbW1pdCwgYnVpbGQgYW4gaW1tdXRhYmxlIHJlbGVhc2UsIHN3aXRjaAojIGF0b21pY2FsbHksIGhlYWx0aC1jaGVjayBpdCwgYW5kIHJlc3RvcmUgdGhlIHByZWNlZGluZyByZWxlYXNlIG9uIGZhaWx1cmUuCgpzZXQgLUVldW8gcGlwZWZhaWwKClNDUklQVF9ESVI9IiQoY2QgIiQoZGlybmFtZSAiJHtCQVNIX1NPVVJDRVswXX0iKSIgJiYgcHdkKSIKcmVhZG9ubHkgU0NSSVBUX0RJUgpERUZBVUxUX0FQUF9ST09UPSIkKGNkICIke1NDUklQVF9ESVJ9Ly4uIiAmJiBwd2QpIgpyZWFkb25seSBERUZBVUxUX0FQUF9ST09UCkRFRkFVTFRfSU5TVEFMTEFUSU9OX1JPT1Q9IiQoY2QgIiR7REVGQVVMVF9BUFBfUk9PVH0vLi4iICYmIHB3ZCkiCnJlYWRvbmx5IERFRkFVTFRfSU5TVEFMTEFUSU9OX1JPT1QKcmVhZG9ubHkgU1RBVEVfUk9PVD0iJHtNVEFfREFTSEJPQVJEX1NUQVRFX1JPT1Q6LSR7REVGQVVMVF9JTlNUQUxMQVRJT05fUk9PVH0vc3RhdGV9IgpyZWFkb25seSBRVUVVRV9GSUxFPSIke1NUQVRFX1JPT1R9L3F1ZXVlL3BlbmRpbmciCnJlYWRvbmx5IFFVRVVFX0xPQ0s9IiR7U1RBVEVfUk9PVH0vcXVldWUvcXVldWUubG9jayIKcmVhZG9ubHkgREVQTE9ZX0xPQ0s9IiR7U1RBVEVfUk9PVH0vZGVwbG95LmxvY2siCnJlYWRvbmx5IEFDVElWRV9DT01NSVRfRklMRT0iJHtTVEFURV9ST09UfS9hY3RpdmVfY29tbWl0IgpyZWFkb25seSBQUk9HUkVTU19GSUxFPSIke1NUQVRFX1JPT1R9L2RlcGxveV9wcm9ncmVzcyIKcmVhZG9ubHkgSU5TVEFMTF9ST09UPSIke01UQV9EQVNIQk9BUkRfSU5TVEFMTF9ST09UOi0ke0RFRkFVTFRfQVBQX1JPT1R9fSIKcmVhZG9ubHkgUkVMRUFTRVNfUk9PVD0iJHtJTlNUQUxMX1JPT1R9L3JlbGVhc2VzIgpyZWFkb25seSBDVVJSRU5UX0xJTks9IiR7SU5TVEFMTF9ST09UfS9jdXJyZW50IgpyZWFkb25seSBTWVNURU1DVExfQklOPSIke1NZU1RFTUNUTF9CSU46LS91c3IvYmluL3N5c3RlbWN0bH0iCgpsb2coKSB7IHByaW50ZiAnJXMgW2RlcGxveS13b3JrZXJdICVzXG4nICIkKGRhdGUgLXUgKyVZLSVtLSVkVCVIOiVNOiVTWikiICIkKiI7IH0KCndyaXRlX3Byb2dyZXNzKCkgewogIGxvY2FsIHBoYXNlPSIkMSIgbG93ZXI9IiQyIiB1cHBlcj0iJDMiIHR5cGljYWxfc2Vjb25kcz0iJDQiIGV0YV9zZWNvbmRzPSIkNSIgbWVzc2FnZT0iJDYiCiAgbG9jYWwgdGVtcG9yYXJ5PSIke1BST0dSRVNTX0ZJTEV9LnRtcC4kJCIKICBpZiAodW1hc2sgMDc3ICYmIHByaW50ZiAnJXNcbiVzXG4lc1xuJXNcbiVzXG4lc1xuJXNcbicgXAogICAgICAiJHBoYXNlIiAiJGxvd2VyIiAiJHVwcGVyIiAiJChkYXRlICslcykiICIkdHlwaWNhbF9zZWNvbmRzIiAiJGV0YV9zZWNvbmRzIiAiJG1lc3NhZ2UiIFwKICAgICAgPiIkdGVtcG9yYXJ5IiAmJiBtdiAtZiAtLSAiJHRlbXBvcmFyeSIgIiRQUk9HUkVTU19GSUxFIik7IHRoZW4KICAgIDoKICBlbHNlCiAgICBybSAtZiAtLSAiJHRlbXBvcmFyeSIKICAgIGxvZyAiV0FSTklORzogY291bGQgbm90IHVwZGF0ZSB0aGUgb3BlcmF0b3IgcHJvZ3Jlc3MgcmVjb3JkLiIKICBmaQogIHJldHVybiAwCn0KCnBvc2l0aXZlX2ludGVnZXIoKSB7CiAgbG9jYWwgbmFtZT0iJDEiIHZhbHVlPSIkMiIKICBpZiBbWyAhICIkdmFsdWUiID1+IF5bMS05XVswLTldKiQgXV07IHRoZW4KICAgIGxvZyAiJG5hbWUgbXVzdCBiZSBhIHBvc2l0aXZlIGludGVnZXI7IGdvdCAnJHZhbHVlJy4iCiAgICBleGl0IDIKICBmaQp9CgpyZXF1aXJlZD0oCiAgR0lURUFfUkVQT19VUkwgR0lURUFfQlJBTkNIIEdJVEVBX0FVVEhfTU9ERSBEQVNIQk9BUkRfSE9TVCBEQVNIQk9BUkRfUE9SVAogIE1JUlJPUl9QT0xMX1NFQ09ORFMgTUlSUk9SX1dBSVRfU0VDT05EUyBNSVJST1JfUkVUUllfU0VDT05EUyBSRUxFQVNFX1JFVEVOVElPTgopCmZvciBuYW1lIGluICIke3JlcXVpcmVkW0BdfSI7IGRvCiAgaWYgW1sgLXogIiR7IW5hbWU6LX0iIF1dOyB0aGVuCiAgICBsb2cgIlJlcXVpcmVkIGVudmlyb25tZW50IHNldHRpbmcgJG5hbWUgaXMgbWlzc2luZy4iCiAgICBleGl0IDIKICBmaQpkb25lCgpwb3NpdGl2ZV9pbnRlZ2VyIE1JUlJPUl9QT0xMX1NFQ09ORFMgIiRNSVJST1JfUE9MTF9TRUNPTkRTIgpwb3NpdGl2ZV9pbnRlZ2VyIE1JUlJPUl9XQUlUX1NFQ09ORFMgIiRNSVJST1JfV0FJVF9TRUNPTkRTIgpwb3NpdGl2ZV9pbnRlZ2VyIE1JUlJPUl9SRVRSWV9TRUNPTkRTICIkTUlSUk9SX1JFVFJZX1NFQ09ORFMiCkdJVEVBX1JFUVVFU1RfVElNRU9VVF9TRUNPTkRTPSIke0dJVEVBX1JFUVVFU1RfVElNRU9VVF9TRUNPTkRTOi00NX0iCnBvc2l0aXZlX2ludGVnZXIgR0lURUFfUkVRVUVTVF9USU1FT1VUX1NFQ09ORFMgIiRHSVRFQV9SRVFVRVNUX1RJTUVPVVRfU0VDT05EUyIKcG9zaXRpdmVfaW50ZWdlciBSRUxFQVNFX1JFVEVOVElPTiAiJFJFTEVBU0VfUkVURU5USU9OIgoKZXhwb3J0IEdJVF9URVJNSU5BTF9QUk9NUFQ9MApleHBvcnQgR0lUX0hUVFBfTE9XX1NQRUVEX0xJTUlUPTEKZXhwb3J0IEdJVF9IVFRQX0xPV19TUEVFRF9USU1FPSIkR0lURUFfUkVRVUVTVF9USU1FT1VUX1NFQ09ORFMiCmNhc2UgIiRHSVRFQV9BVVRIX01PREUiIGluCiAgaHR0cHMpCiAgICBleHBvcnQgR0lUX0FTS1BBU1M9IiR7SU5TVEFMTF9ST09UfS9iaW4vZ2l0ZWFfYXNrcGFzcy5zaCIKICAgIDs7CiAgc3NoKQogICAgaWYgW1sgLXogIiR7R0lURUFfU1NIX1BSSVZBVEVfS0VZX0ZJTEU6LX0iIHx8IC16ICIke0dJVEVBX1NTSF9LTk9XTl9IT1NUU19GSUxFOi19IiBdXTsgdGhlbgogICAgICBsb2cgIlNTSCBtb2RlIHJlcXVpcmVzIGl0cyBpbnN0YWxsZWQgcHJpdmF0ZS1rZXkgYW5kIGtub3duLWhvc3RzIHBhdGhzLiIKICAgICAgZXhpdCAyCiAgICBmaQogICAgZXhwb3J0IEdJVF9TU0hfQ09NTUFORD0ic3NoIC1pICR7R0lURUFfU1NIX1BSSVZBVEVfS0VZX0ZJTEV9IC1vIElkZW50aXRpZXNPbmx5PXllcyAtbyBTdHJpY3RIb3N0S2V5Q2hlY2tpbmc9eWVzIC1vIFVzZXJLbm93bkhvc3RzRmlsZT0ke0dJVEVBX1NTSF9LTk9XTl9IT1NUU19GSUxFfSIKICAgIDs7CiAgKikKICAgIGxvZyAiR0lURUFfQVVUSF9NT0RFIG11c3QgYmUgaHR0cHMgb3Igc3NoLiIKICAgIGV4aXQgMgogICAgOzsKZXNhYwoKcmVhZF9wZW5kaW5nKCkgewogIGxvY2FsIGZpcnN0IHNlY29uZCB0aGlyZAogIFtbIC1mICIkUVVFVUVfRklMRSIgXV0gfHwgcmV0dXJuIDEKICB7CiAgICBJRlM9IHJlYWQgLXIgZmlyc3QKICAgIElGUz0gcmVhZCAtciBzZWNvbmQKICAgIElGUz0gcmVhZCAtciB0aGlyZAogIH0gPCIkUVVFVUVfRklMRSIgfHwgcmV0dXJuIDEKICBbWyAiJGZpcnN0IiA9fiBeWzAtOWEtZl17NDB9JCBdXSB8fCByZXR1cm4gMQogIFtbICIkc2Vjb25kIiA9fiBeW0EtWmEtejAtOS1dezgsMTI4fSQgXV0gfHwgcmV0dXJuIDEKICBwcmludGYgJyVzICVzICVzXG4nICIkZmlyc3QiICIkc2Vjb25kIiAiJHRoaXJkIgp9CgpyZW1vdGVfdGlwKCkgewogIGxvY2FsIG91dHB1dCBzdGF0dXMKICBpZiBvdXRwdXQ9IiQodGltZW91dCAtLXNpZ25hbD1URVJNIC0ta2lsbC1hZnRlcj01cyAiJHtHSVRFQV9SRVFVRVNUX1RJTUVPVVRfU0VDT05EU31zIiBcCiAgICAgIGdpdCBscy1yZW1vdGUgLS1yZWZzICIkR0lURUFfUkVQT19VUkwiICJyZWZzL2hlYWRzLyR7R0lURUFfQlJBTkNIfSIpIjsgdGhlbgogICAgOgogIGVsc2UKICAgIHN0YXR1cz0kPwogICAgaWYgKChzdGF0dXMgPT0gMTI0IHx8IHN0YXR1cyA9PSAxMzcpKTsgdGhlbgogICAgICBsb2cgIkdpdGVhIGJyYW5jaCBwcm9iZSB0aW1lZCBvdXQgYWZ0ZXIgJHtHSVRFQV9SRVFVRVNUX1RJTUVPVVRfU0VDT05EU31zLiIgPiYyCiAgICBlbHNlCiAgICAgIGxvZyAiR2l0ZWEgYnJhbmNoIHByb2JlIGZhaWxlZCB3aXRoIEdpdCBleGl0IHN0YXR1cyAkc3RhdHVzLiIgPiYyCiAgICBmaQogICAgcmV0dXJuIDEKICBmaQogIGF3ayAnTlIgPT0gMSB7IHByaW50IHRvbG93ZXIoJDEpIH0nIDw8PCIkb3V0cHV0Igp9CgpxdWV1ZV9zdGlsbF90YXJnZXRzKCkgewogIGxvY2FsIGV4cGVjdGVkPSIkMSIgcGVuZGluZwogIHBlbmRpbmc9IiQocmVhZF9wZW5kaW5nIDI+L2Rldi9udWxsIHx8IHRydWUpIgogIFtbICIke3BlbmRpbmclJSAqfSIgPT0gIiRleHBlY3RlZCIgXV0KfQoKZmV0Y2hfZXhhY3RfYnJhbmNoKCkgewogIGxvY2FsIHRhcmdldD0iJDEiIGRlc3RpbmF0aW9uPSIkMiIgZmV0Y2hlZCBzdGF0dXMKICBpZiB0aW1lb3V0IC0tc2lnbmFsPVRFUk0gLS1raWxsLWFmdGVyPTVzICIke0dJVEVBX1JFUVVFU1RfVElNRU9VVF9TRUNPTkRTfXMiIFwKICAgICAgZ2l0IGNsb25lIC0tcHJvZ3Jlc3MgLS1uby1jaGVja291dCAtLWZpbHRlcj1ibG9iOm5vbmUgLS1zaW5nbGUtYnJhbmNoIFwKICAgICAgLS1icmFuY2ggIiRHSVRFQV9CUkFOQ0giICIkR0lURUFfUkVQT19VUkwiICIkZGVzdGluYXRpb24iOyB0aGVuCiAgICA6CiAgZWxzZQogICAgc3RhdHVzPSQ/CiAgICBpZiAoKHN0YXR1cyA9PSAxMjQgfHwgc3RhdHVzID09IDEzNykpOyB0aGVuCiAgICAgIGxvZyAiR2l0ZWEgY2xvbmUgdGltZWQgb3V0IGFmdGVyICR7R0lURUFfUkVRVUVTVF9USU1FT1VUX1NFQ09ORFN9czsgbm8gc291cmNlIHdhcyBhY2NlcHRlZCBmb3IgJHRhcmdldC4iCiAgICBlbHNlCiAgICAgIGxvZyAiR2l0ZWEgY2xvbmUgZmFpbGVkIHdpdGggR2l0IGV4aXQgc3RhdHVzICRzdGF0dXM7IG5vIHNvdXJjZSB3YXMgYWNjZXB0ZWQgZm9yICR0YXJnZXQuIgogICAgZmkKICAgIHJldHVybiAxCiAgZmkKICBmZXRjaGVkPSIkKGdpdCAtQyAiJGRlc3RpbmF0aW9uIiByZXYtcGFyc2UgInJlZnMvcmVtb3Rlcy9vcmlnaW4vJHtHSVRFQV9CUkFOQ0h9IiAyPi9kZXYvbnVsbCB8fCB0cnVlKSIKICBmZXRjaGVkPSIke2ZldGNoZWQsLH0iCiAgaWYgW1sgIiRmZXRjaGVkIiAhPSAiJHRhcmdldCIgXV07IHRoZW4KICAgIGxvZyAiRXhhY3QtY29tbWl0IGdhdGUgY2xvc2VkIGFmdGVyIGZldGNoOiB3YW50ZWQgJHRhcmdldCwgZmV0Y2hlZCAke2ZldGNoZWQ6LW5vbmV9LiIKICAgIHJldHVybiA3NQogIGZpCiAgZ2l0IC1DICIkZGVzdGluYXRpb24iIGNoZWNrb3V0IC0tcXVpZXQgLS1kZXRhY2ggIiR0YXJnZXQiCn0KCnJlc3RhcnRfZGFzaGJvYXJkKCkgewogIHN1ZG8gLW4gIiRTWVNURU1DVExfQklOIiByZXN0YXJ0IG10YS1kYXNoYm9hcmQuc2VydmljZQp9CgpkYXNoYm9hcmRfaGVhbHRoeSgpIHsKICAjIENoZWNrcyBsaXZlbmVzcyBvbmx5ICh0aGUgcHJvY2VzcyBpcyB1cCBhbmQgRXhwcmVzcyBpcyByb3V0aW5nKSwgbm90CiAgIyB3aGV0aGVyIFBvc3RncmVTUUwgaXMgcmVhY2hhYmxlIG9yIGBhdHRyaWJ1dGlvbl9yZXN1bHRgIGhhcyByb3dzIHlldC4KICAjIGAvYXBpL2Rhc2hib2FyZGAgZGVwZW5kcyBvbiBib3RoIGFuZCBpcyBhIGJ1c2luZXNzLWRhdGEgcmVhZGluZXNzIGNoZWNrLAogICMgbm90IGEgZGVwbG95LXN1Y2NlZWRlZCBjaGVjazogZ2F0aW5nIHJlbGVhc2VzIG9uIGl0IG1lYW50IGEgZmlyc3QgZGVwbG95CiAgIyBhZ2FpbnN0IGFuIGVtcHR5IGRhdGFiYXNlIGNvdWxkIG5ldmVyIGdvIGhlYWx0aHksIGFuZCBhIHJvbGxiYWNrIHRvIGEKICAjIHBlcmZlY3RseSBnb29kIHByaW9yIHJlbGVhc2Ugd291bGQgZmFpbCBpdHMgaGVhbHRoIGNoZWNrIHRoZSBzYW1lIHdheSwKICAjIGZvciBhIHJlYXNvbiB0aGUgZGVwbG95ZWQgY29kZSBoYWQgbm8gcGFydCBpbi4KICBsb2NhbCBob3N0PSIkREFTSEJPQVJEX0hPU1QiCiAgW1sgIiRob3N0IiA9PSAiMC4wLjAuMCIgfHwgIiRob3N0IiA9PSAiOjoiIF1dICYmIGhvc3Q9IjEyNy4wLjAuMSIKICBsb2NhbCBiYXNlPSJodHRwOi8vJHtob3N0fToke0RBU0hCT0FSRF9QT1JUfSIKICBsb2NhbCBhdHRlbXB0cz0zMAogIHdoaWxlICgoYXR0ZW1wdHMgPiAwKSk7IGRvCiAgICBpZiBjdXJsIC0tZmFpbCAtLXNpbGVudCAtLXNob3ctZXJyb3IgLS1tYXgtdGltZSA1ICIke2Jhc2V9LyIgPi9kZXYvbnVsbCAyPiYxICYmCiAgICAgICBjdXJsIC0tZmFpbCAtLXNpbGVudCAtLXNob3ctZXJyb3IgLS1tYXgtdGltZSAxNSAiJHtiYXNlfS9hcGkvaGVhbHRoIiA+L2Rldi9udWxsIDI+JjE7IHRoZW4KICAgICAgcmV0dXJuIDAKICAgIGZpCiAgICBhdHRlbXB0cz0kKChhdHRlbXB0cyAtIDEpKQogICAgc2xlZXAgMgogIGRvbmUKICByZXR1cm4gMQp9CgpyZW1vdmVfbWF0Y2hpbmdfcXVldWVfZW50cnkoKSB7CiAgbG9jYWwgZGVwbG95ZWQ9IiQxIiBwZW5kaW5nCiAgZXhlYyA4PiIkUVVFVUVfTE9DSyIKICBmbG9jayAtdyA1IDggfHwgcmV0dXJuIDEKICBwZW5kaW5nPSIkKHJlYWRfcGVuZGluZyAyPi9kZXYvbnVsbCB8fCB0cnVlKSIKICBpZiBbWyAiJHtwZW5kaW5nJSUgKn0iID09ICIkZGVwbG95ZWQiIF1dOyB0aGVuCiAgICBybSAtZiAtLSAiJFFVRVVFX0ZJTEUiCiAgZmkKfQoKcHJ1bmVfcmVsZWFzZXMoKSB7CiAgbG9jYWwgYWN0aXZlIHByZXZpb3VzIGNvdW50PTAgcGF0aAogIGFjdGl2ZT0iJChyZWFkbGluayAtZiAiJENVUlJFTlRfTElOSyIgMj4vZGV2L251bGwgfHwgdHJ1ZSkiCiAgcHJldmlvdXM9IiR7MTotfSIKICB3aGlsZSBJRlM9IHJlYWQgLXIgcGF0aDsgZG8KICAgIFtbIC1uICIkcGF0aCIgXV0gfHwgY29udGludWUKICAgIGNvdW50PSQoKGNvdW50ICsgMSkpCiAgICBpZiBbWyAiJHBhdGgiID09ICIkYWN0aXZlIiB8fCAiJHBhdGgiID09ICIkcHJldmlvdXMiIF1dOyB0aGVuCiAgICAgIGNvbnRpbnVlCiAgICBmaQogICAgaWYgKCggY291bnQgPiBSRUxFQVNFX1JFVEVOVElPTiApKTsgdGhlbgogICAgICBjYXNlICIkcGF0aCIgaW4KICAgICAgICAiJHtSRUxFQVNFU19ST09UfS8iKikgcm0gLXJmIC0tICIkcGF0aCIgOzsKICAgICAgZXNhYwogICAgZmkKICBkb25lIDwgPChmaW5kICIkUkVMRUFTRVNfUk9PVCIgLW1pbmRlcHRoIDEgLW1heGRlcHRoIDEgLXR5cGUgZCAtbmFtZSAnWzAtOWEtZl0qJyAtcHJpbnRmICclVEAgJXBcbicgMj4vZGV2L251bGwgfCBzb3J0IC1ybiB8IGN1dCAtZCcgJyAtZjItKQp9CgpkZXBsb3lfY29tbWl0KCkgewogIGxvY2FsIHRhcmdldD0iJDEiCiAgbG9jYWwgcmVsZWFzZT0iJHtSRUxFQVNFU19ST09UfS8ke3RhcmdldH0iCiAgbG9jYWwgYnVpbGQ9IiR7UkVMRUFTRVNfUk9PVH0vLiR7dGFyZ2V0fS5idWlsZGluZy4kJCIKICBsb2NhbCBwcmV2aW91cyBmZXRjaF9zdGF0dXMKICBsb2NhbCAtYSBjbGVhbl9idWlsZF9lbnZpcm9ubWVudD0oCiAgICBlbnYKICAgIC11IEdJVEVBX1RPS0VOCiAgICAtdSBHSVRFQV9VU0VSTkFNRQogICAgLXUgR0lURUFfU1NIX1BSSVZBVEVfS0VZX0ZJTEUKICAgIC11IEdJVEVBX1NTSF9LTk9XTl9IT1NUU19GSUxFCiAgICAtdSBHSVRfQVNLUEFTUwogICAgLXUgR0lUX1NTSF9DT01NQU5ECiAgKQoKICBleGVjIDc+IiRERVBMT1lfTE9DSyIKICBpZiAhIGZsb2NrIC1uIDc7IHRoZW4KICAgIGxvZyAiQW5vdGhlciBkZXBsb3ltZW50IG93bnMgdGhlIGJ1aWxkIGxvY2s7IHRoZSBxdWV1ZWQgY29tbWl0IHJlbWFpbnMgcGVuZGluZy4iCiAgICByZXR1cm4gNzUKICBmaQoKICBpZiAhIHF1ZXVlX3N0aWxsX3RhcmdldHMgIiR0YXJnZXQiOyB0aGVuCiAgICBsb2cgIkNvbW1pdCAkdGFyZ2V0IHdhcyBzdXBlcnNlZGVkIGJlZm9yZSBpdHMgYnVpbGQgYmVnYW4uIgogICAgcmV0dXJuIDc1CiAgZmkKCiAgaWYgW1sgLWYgIiRBQ1RJVkVfQ09NTUlUX0ZJTEUiIF1dICYmCiAgICAgW1sgIiQodHIgLWQgJ1xyXG4nIDwiJEFDVElWRV9DT01NSVRfRklMRSIpIiA9PSAiJHRhcmdldCIgXV0gJiYKICAgICBbWyAiJChyZWFkbGluayAtZiAiJENVUlJFTlRfTElOSyIgMj4vZGV2L251bGwgfHwgdHJ1ZSkiID09ICIkcmVsZWFzZSIgXV0gJiYKICAgICBbWyAtZiAiJHJlbGVhc2UvLnJlYWR5IiBdXTsgdGhlbgogICAgd3JpdGVfcHJvZ3Jlc3MgaGVhbHRoIDk1IDk5IDQwIDQwICJDaGVja2luZyB0aGUgYWxyZWFkeS1idWlsdCByZWxlYXNlIGF0IC8gYW5kIC9hcGkvZGFzaGJvYXJkIgogICAgcmVzdGFydF9kYXNoYm9hcmQgfHwgdHJ1ZQogICAgaWYgZGFzaGJvYXJkX2hlYWx0aHk7IHRoZW4KICAgICAgcmVtb3ZlX21hdGNoaW5nX3F1ZXVlX2VudHJ5ICIkdGFyZ2V0IiB8fCB0cnVlCiAgICAgIHdyaXRlX3Byb2dyZXNzIGNvbXBsZXRlIDEwMCAxMDAgMSAwICJSZWxlYXNlICR7dGFyZ2V0OjA6MTJ9IGlzIGFjdGl2ZSBhbmQgaGVhbHRoeTsgbm8gcmVidWlsZCB3YXMgbmVlZGVkIgogICAgICBsb2cgIkNvbW1pdCAkdGFyZ2V0IGlzIGFscmVhZHkgYWN0aXZlIGFuZCBoZWFsdGh5OyBubyByZWJ1aWxkIGlzIG5lZWRlZC4iCiAgICAgIHJldHVybiAwCiAgICBmaQogICAgbG9nICJUaGUgcmVjb3JkZWQgcmVsZWFzZSAkdGFyZ2V0IGNvdWxkIG5vdCBwYXNzIGl0cyBoZWFsdGggY2hlY2s7IHJlZnVzaW5nIHRvIGRlbGV0ZSBpdCBpbiBwbGFjZS4iCiAgICByZXR1cm4gMQogIGZpCgogIHJtIC1yZiAtLSAiJGJ1aWxkIgogIG1rZGlyIC1wICIkYnVpbGQiCiAgd3JpdGVfcHJvZ3Jlc3MgY2xvbmUgNSAyMCA2MCA1MDAgIlB1bGxpbmcgR2l0ZWEgYnJhbmNoICRHSVRFQV9CUkFOQ0ggaW50byBhbiBpc29sYXRlZCByZWxlYXNlIGNoZWNrb3V0IgogIGxvZyAiRmV0Y2hpbmcgR2l0ZWEgYnJhbmNoICRHSVRFQV9CUkFOQ0ggZm9yIGV4YWN0LWNvbW1pdCB2ZXJpZmljYXRpb24uIgogIGlmIGZldGNoX2V4YWN0X2JyYW5jaCAiJHRhcmdldCIgIiRidWlsZCI7IHRoZW4KICAgIDoKICBlbHNlCiAgICBmZXRjaF9zdGF0dXM9JD8KICAgIGlmICgoZmV0Y2hfc3RhdHVzID09IDc1KSk7IHRoZW4KICAgICAgd3JpdGVfcHJvZ3Jlc3MgbWlycm9yIDIgNSAiJE1JUlJPUl9QT0xMX1NFQ09ORFMiIDUxMCAiRmV0Y2hlZCBicmFuY2ggY2hhbmdlZCBiZWZvcmUgdmVyaWZpY2F0aW9uOyBjaGVja2luZyB0aGUgbWlycm9yZWQgdGlwIGFnYWluIgogICAgZWxzZQogICAgICB3cml0ZV9wcm9ncmVzcyByZXRyeSAyIDUgIiRNSVJST1JfUkVUUllfU0VDT05EUyIgIiQoKE1JUlJPUl9SRVRSWV9TRUNPTkRTICsgNTAwKSkiICJHaXRlYSBwdWxsIGZhaWxlZDsgcHJlc2VydmluZyB0aGUgYWN0aXZlIHJlbGVhc2UgYmVmb3JlIHJldHJ5IgogICAgZmkKICAgIHJtIC1yZiAtLSAiJGJ1aWxkIgogICAgcmV0dXJuICIkZmV0Y2hfc3RhdHVzIgogIGZpCiAgaWYgISBxdWV1ZV9zdGlsbF90YXJnZXRzICIkdGFyZ2V0IjsgdGhlbgogICAgd3JpdGVfcHJvZ3Jlc3MgbWlycm9yIDIgNSAiJE1JUlJPUl9QT0xMX1NFQ09ORFMiIDUxMCAiQSBuZXdlciBHaXRIdWIgcHVzaCBzdXBlcnNlZGVkIHRoZSBmZXRjaGVkIGNoZWNrb3V0IgogICAgbG9nICJDb21taXQgJHRhcmdldCB3YXMgc3VwZXJzZWRlZCBkdXJpbmcgZmV0Y2g7IHNraXBwaW5nIGl0cyBidWlsZC4iCiAgICBybSAtcmYgLS0gIiRidWlsZCIKICAgIHJldHVybiA3NQogIGZpCgogIHdyaXRlX3Byb2dyZXNzIHZlcmlmeSAyMCAyMiA1IDQ0MCAiRmV0Y2hlZCBicmFuY2ggdGlwIG1hdGNoZXMgcXVldWVkIEdpdEh1YiBTSEEgJHt0YXJnZXQ6MDoxMn0iCiAgbG9nICJJbnN0YWxsaW5nIGxvY2tlZCBkYXNoYm9hcmQgZGVwZW5kZW5jaWVzIGZvciAkdGFyZ2V0LiIKICB3cml0ZV9wcm9ncmVzcyBucG1fY2kgMjIgNTUgMTgwIDQzNSAiSW5zdGFsbGluZyBsb2NrZWQgbnBtIGRlcGVuZGVuY2llcyB3aXRoIG5wbSBjaSIKICBpZiAhIChjZCAiJGJ1aWxkL2Rhc2hib2FyZCIgJiYgIiR7Y2xlYW5fYnVpbGRfZW52aXJvbm1lbnRbQF19IiBucG0gY2kgLS1uby1hdWRpdCAtLW5vLWZ1bmQpOyB0aGVuCiAgICB3cml0ZV9wcm9ncmVzcyByZXRyeSAyIDUgIiRNSVJST1JfUkVUUllfU0VDT05EUyIgIiQoKE1JUlJPUl9SRVRSWV9TRUNPTkRTICsgNTAwKSkiICJucG0gY2kgZmFpbGVkOyBwcmVzZXJ2aW5nIHRoZSBhY3RpdmUgcmVsZWFzZSBiZWZvcmUgcmV0cnkiCiAgICBsb2cgIm5wbSBjaSBmYWlsZWQgZm9yICR0YXJnZXQ7IHRoZSBjdXJyZW50IHJlbGVhc2UgaXMgdW5jaGFuZ2VkLiIKICAgIHJtIC1yZiAtLSAiJGJ1aWxkIgogICAgcmV0dXJuIDEKICBmaQoKICBsb2cgIlJ1bm5pbmcgZGFzaGJvYXJkIHRlc3RzIGZvciAkdGFyZ2V0LiIKICB3cml0ZV9wcm9ncmVzcyB0ZXN0cyA1NSA3MCA5MCAyNTUgIlJ1bm5pbmcgdGhlIGRhc2hib2FyZCBucG0gdGVzdCBzdWl0ZSIKICBpZiAhIChjZCAiJGJ1aWxkL2Rhc2hib2FyZCIgJiYgIiR7Y2xlYW5fYnVpbGRfZW52aXJvbm1lbnRbQF19IiBucG0gdGVzdCk7IHRoZW4KICAgIHdyaXRlX3Byb2dyZXNzIHJldHJ5IDIgNSAiJE1JUlJPUl9SRVRSWV9TRUNPTkRTIiAiJCgoTUlSUk9SX1JFVFJZX1NFQ09ORFMgKyA1MDApKSIgIkRhc2hib2FyZCB0ZXN0cyBmYWlsZWQ7IHByZXNlcnZpbmcgdGhlIGFjdGl2ZSByZWxlYXNlIGJlZm9yZSByZXRyeSIKICAgIGxvZyAiRGFzaGJvYXJkIHRlc3RzIGZhaWxlZCBmb3IgJHRhcmdldDsgdGhlIGN1cnJlbnQgcmVsZWFzZSBpcyB1bmNoYW5nZWQuIgogICAgcm0gLXJmIC0tICIkYnVpbGQiCiAgICByZXR1cm4gMQogIGZpCgogIGxvZyAiQnVpbGRpbmcgZGFzaGJvYXJkIHJlbGVhc2UgJHRhcmdldC4iCiAgd3JpdGVfcHJvZ3Jlc3MgYnVpbGQgNzAgOTAgMTIwIDE2NSAiUnVubmluZyB0aGUgZGFzaGJvYXJkIHByb2R1Y3Rpb24gYnVpbGQiCiAgaWYgISAoY2QgIiRidWlsZC9kYXNoYm9hcmQiICYmICIke2NsZWFuX2J1aWxkX2Vudmlyb25tZW50W0BdfSIgbnBtIHJ1biBidWlsZCkgfHwgW1sgISAtZiAiJGJ1aWxkL2Rhc2hib2FyZC9kaXN0L2luZGV4Lmh0bWwiIF1dOyB0aGVuCiAgICB3cml0ZV9wcm9ncmVzcyByZXRyeSAyIDUgIiRNSVJST1JfUkVUUllfU0VDT05EUyIgIiQoKE1JUlJPUl9SRVRSWV9TRUNPTkRTICsgNTAwKSkiICJQcm9kdWN0aW9uIGJ1aWxkIGZhaWxlZDsgcHJlc2VydmluZyB0aGUgYWN0aXZlIHJlbGVhc2UgYmVmb3JlIHJldHJ5IgogICAgbG9nICJEYXNoYm9hcmQgYnVpbGQgZmFpbGVkIGZvciAkdGFyZ2V0OyB0aGUgY3VycmVudCByZWxlYXNlIGlzIHVuY2hhbmdlZC4iCiAgICBybSAtcmYgLS0gIiRidWlsZCIKICAgIHJldHVybiAxCiAgZmkKCiAgaWYgISBxdWV1ZV9zdGlsbF90YXJnZXRzICIkdGFyZ2V0IjsgdGhlbgogICAgd3JpdGVfcHJvZ3Jlc3MgbWlycm9yIDIgNSAiJE1JUlJPUl9QT0xMX1NFQ09ORFMiIDUxMCAiQSBuZXdlciBHaXRIdWIgcHVzaCBzdXBlcnNlZGVkIHRoZSBjb21wbGV0ZWQgYnVpbGQiCiAgICBsb2cgIkNvbW1pdCAkdGFyZ2V0IHdhcyBzdXBlcnNlZGVkIGR1cmluZyBpdHMgYnVpbGQ7IGl0IHdpbGwgbm90IGJlIGFjdGl2YXRlZC4iCiAgICBybSAtcmYgLS0gIiRidWlsZCIKICAgIHJldHVybiA3NQogIGZpCgogIHByaW50ZiAnJXNcbicgIiR0YXJnZXQiID4iJGJ1aWxkLy5yZWFkeSIKICBybSAtcmYgLS0gIiRyZWxlYXNlIgogIG12IC0tICIkYnVpbGQiICIkcmVsZWFzZSIKCiAgcHJldmlvdXM9IiQocmVhZGxpbmsgLWYgIiRDVVJSRU5UX0xJTksiIDI+L2Rldi9udWxsIHx8IHRydWUpIgogIGxuIC1zZm4gIiRyZWxlYXNlIiAiJHtDVVJSRU5UX0xJTkt9Lm5ldyIKICBtdiAtVGYgIiR7Q1VSUkVOVF9MSU5LfS5uZXciICIkQ1VSUkVOVF9MSU5LIgoKICB3cml0ZV9wcm9ncmVzcyBhY3RpdmF0ZSA5MCA5NSAxMCA1MCAiQWN0aXZhdGluZyBpbW11dGFibGUgcmVsZWFzZSAke3RhcmdldDowOjEyfSBhbmQgcmVzdGFydGluZyB0aGUgZGFzaGJvYXJkIgogIGxvZyAiQWN0aXZhdGVkICR0YXJnZXQ7IHJlc3RhcnRpbmcgdGhlIGRhc2hib2FyZC4iCiAgaWYgcmVzdGFydF9kYXNoYm9hcmQ7IHRoZW4KICAgIHdyaXRlX3Byb2dyZXNzIGhlYWx0aCA5NSA5OSA0MCA0MCAiQ2hlY2tpbmcgZGFzaGJvYXJkIGVuZHBvaW50cyAvIGFuZCAvYXBpL2Rhc2hib2FyZCIKICAgIGlmIGRhc2hib2FyZF9oZWFsdGh5OyB0aGVuCiAgICAgIHByaW50ZiAnJXNcbicgIiR0YXJnZXQiID4iJEFDVElWRV9DT01NSVRfRklMRSIKICAgICAgcmVtb3ZlX21hdGNoaW5nX3F1ZXVlX2VudHJ5ICIkdGFyZ2V0IiB8fCB0cnVlCiAgICAgIHBydW5lX3JlbGVhc2VzICIkcHJldmlvdXMiCiAgICAgIHdyaXRlX3Byb2dyZXNzIGNvbXBsZXRlIDEwMCAxMDAgMSAwICJSZWxlYXNlICR7dGFyZ2V0OjA6MTJ9IGlzIGFjdGl2ZSBhbmQgaGVhbHRoeSIKICAgICAgbG9nICJEZXBsb3ltZW50ICR0YXJnZXQgaXMgaGVhbHRoeS4iCiAgICAgIHJldHVybiAwCiAgICBmaQogIGZpCgogIHdyaXRlX3Byb2dyZXNzIHJvbGxiYWNrIDkwIDk1IDYwIDYwICJIZWFsdGggY2hlY2sgZmFpbGVkOyByZXN0b3JpbmcgYW5kIGNoZWNraW5nIHRoZSBwcmVjZWRpbmcgcmVsZWFzZSIKICBsb2cgIkhlYWx0aCBjaGVjayBmYWlsZWQgZm9yICR0YXJnZXQ7IHJlc3RvcmluZyB0aGUgcHJlY2VkaW5nIHJlbGVhc2UuIgogIGlmIFtbIC1uICIkcHJldmlvdXMiICYmICIkcHJldmlvdXMiID09ICIke1JFTEVBU0VTX1JPT1R9LyIqICYmIC1kICIkcHJldmlvdXMiIF1dOyB0aGVuCiAgICBsbiAtc2ZuICIkcHJldmlvdXMiICIke0NVUlJFTlRfTElOS30ucm9sbGJhY2siCiAgICBtdiAtVGYgIiR7Q1VSUkVOVF9MSU5LfS5yb2xsYmFjayIgIiRDVVJSRU5UX0xJTksiCiAgICBpZiByZXN0YXJ0X2Rhc2hib2FyZCAmJiBkYXNoYm9hcmRfaGVhbHRoeTsgdGhlbgogICAgICBwcmludGYgJyVzXG4nICIkKGJhc2VuYW1lICIkcHJldmlvdXMiKSIgPiIkQUNUSVZFX0NPTU1JVF9GSUxFIgogICAgICB3cml0ZV9wcm9ncmVzcyByZXRyeSAyIDUgIiRNSVJST1JfUkVUUllfU0VDT05EUyIgIiQoKE1JUlJPUl9SRVRSWV9TRUNPTkRTICsgNTAwKSkiICJSb2xsYmFjayBpcyBoZWFsdGh5OyBmYWlsZWQgcmVsZWFzZSByZW1haW5zIHF1ZXVlZCBmb3IgcmV0cnkiCiAgICAgIGxvZyAiUm9sbGJhY2sgdG8gJChiYXNlbmFtZSAiJHByZXZpb3VzIikgaXMgaGVhbHRoeS4iCiAgICBlbHNlCiAgICAgIHdyaXRlX3Byb2dyZXNzIGZhaWxlZCAwIDEgMSAwICJEZXBsb3ltZW50IGFuZCByb2xsYmFjayBoZWFsdGggY2hlY2tzIGZhaWxlZDsgaW5zcGVjdCB0aGUgd29ya2VyIGpvdXJuYWwiCiAgICAgIGxvZyAiQ1JJVElDQUw6IHJvbGxiYWNrIGhlYWx0aCBjaGVjayBhbHNvIGZhaWxlZC4iCiAgICBmaQogIGVsc2UKICAgIHdyaXRlX3Byb2dyZXNzIHJldHJ5IDIgNSAiJE1JUlJPUl9SRVRSWV9TRUNPTkRTIiAiJCgoTUlSUk9SX1JFVFJZX1NFQ09ORFMgKyA1MDApKSIgIkZpcnN0IGRlcGxveW1lbnQgZmFpbGVkIGl0cyBoZWFsdGggY2hlY2sgYW5kIHJlbWFpbnMgcXVldWVkIGZvciByZXRyeSIKICAgIGxvZyAiTm8gcHJlY2VkaW5nIHJlbGVhc2UgZXhpc3RzOyB0aGUgZmFpbGVkIGZpcnN0IGRlcGxveW1lbnQgcmVtYWlucyBpbmFjdGl2ZS4iCiAgZmkKICByZXR1cm4gMQp9Cgpta2RpciAtcCAiJFJFTEVBU0VTX1JPT1QiICIke1NUQVRFX1JPT1R9L3F1ZXVlIgoKaWYgW1sgIiR7MTotfSIgPT0gIi0tdmVyaWZ5LWV4YWN0IiBdXTsgdGhlbgogIHRhcmdldD0iJHsyOi19IgogIFtbICIkdGFyZ2V0IiA9fiBeWzAtOWEtZl17NDB9JCBdXSB8fCB7IGxvZyAiLS12ZXJpZnktZXhhY3QgcmVxdWlyZXMgYSBsb3dlcmNhc2UgNDAtY2hhcmFjdGVyIGNvbW1pdC4iOyBleGl0IDI7IH0KICB2ZXJpZmljYXRpb249IiR7UkVMRUFTRVNfUk9PVH0vLnZlcmlmaWNhdGlvbi4kJCIKICBybSAtcmYgLS0gIiR2ZXJpZmljYXRpb24iCiAgbWtkaXIgLXAgIiR2ZXJpZmljYXRpb24iCiAgaWYgZmV0Y2hfZXhhY3RfYnJhbmNoICIkdGFyZ2V0IiAiJHZlcmlmaWNhdGlvbiI7IHRoZW4KICAgIHJtIC1yZiAtLSAiJHZlcmlmaWNhdGlvbiIKICAgIGxvZyAiRXhhY3QtY29tbWl0IHZlcmlmaWNhdGlvbiBwYXNzZWQgZm9yICR0YXJnZXQuIgogICAgZXhpdCAwCiAgZWxzZQogICAgc3RhdHVzPSQ/CiAgICBybSAtcmYgLS0gIiR2ZXJpZmljYXRpb24iCiAgICBleGl0ICIkc3RhdHVzIgogIGZpCmZpCgpsb2cgIldvcmtlciBzdGFydGVkOyB3YWl0aW5nIGZvciBHaXRIdWIgcmVxdWVzdHMgYW5kIHRoZSBkZWxheWVkIEdpdGVhIG1pcnJvci4iCndyaXRlX3Byb2dyZXNzIGlkbGUgMCAyIDEgNTEwICJXb3JrZXIgc3RhcnRlZDsgd2FpdGluZyBmb3IgYSBxdWV1ZWQgR2l0SHViIGNvbW1pdCIKCndoaWxlIHRydWU7IGRvCiAgcGVuZGluZz0iJChyZWFkX3BlbmRpbmcgMj4vZGV2L251bGwgfHwgdHJ1ZSkiCiAgaWYgW1sgLXogIiRwZW5kaW5nIiBdXTsgdGhlbgogICAgc2xlZXAgMgogICAgY29udGludWUKICBmaQoKICB0YXJnZXQ9IiR7cGVuZGluZyUlICp9IgogIHN0YXJ0ZWQ9IiQoZGF0ZSArJXMpIgogIGxhc3Rfb2JzZXJ2ZWQ9IiIKICB3cml0ZV9wcm9ncmVzcyBtaXJyb3IgMiA1IDE1IDUxMCAiQ2hlY2tpbmcgR2l0ZWEgYnJhbmNoICRHSVRFQV9CUkFOQ0ggZm9yIHF1ZXVlZCBHaXRIdWIgU0hBICR7dGFyZ2V0OjA6MTJ9IgogIGxvZyAiV2FpdGluZyBmb3IgR2l0ZWEgYnJhbmNoICRHSVRFQV9CUkFOQ0ggdG8gcmVhY2ggR2l0SHViIGNvbW1pdCAkdGFyZ2V0LiIKCiAgd2hpbGUgdHJ1ZTsgZG8KICAgIGxhdGVzdD0iJChyZWFkX3BlbmRpbmcgMj4vZGV2L251bGwgfHwgdHJ1ZSkiCiAgICBpZiBbWyAteiAiJGxhdGVzdCIgXV07IHRoZW4KICAgICAgYnJlYWsKICAgIGZpCiAgICBsYXRlc3RfdGFyZ2V0PSIke2xhdGVzdCUlICp9IgogICAgaWYgW1sgIiRsYXRlc3RfdGFyZ2V0IiAhPSAiJHRhcmdldCIgXV07IHRoZW4KICAgICAgdGFyZ2V0PSIkbGF0ZXN0X3RhcmdldCIKICAgICAgc3RhcnRlZD0iJChkYXRlICslcykiCiAgICAgIHdyaXRlX3Byb2dyZXNzIG1pcnJvciAyIDUgMTUgNTEwICJOZXdlciBwdXNoIHF1ZXVlZDsgY2hlY2tpbmcgR2l0ZWEgZm9yIEdpdEh1YiBTSEEgJHt0YXJnZXQ6MDoxMn0iCiAgICAgIGxvZyAiQSBuZXdlciBwdXNoIHN1cGVyc2VkZWQgdGhlIHRhcmdldDsgbm93IHdhaXRpbmcgZm9yICR0YXJnZXQuIgogICAgZmkKCiAgICBvYnNlcnZlZD0iJChyZW1vdGVfdGlwIHx8IHRydWUpIgogICAgaWYgW1sgIiRvYnNlcnZlZCIgIT0gIiRsYXN0X29ic2VydmVkIiBdXTsgdGhlbgogICAgICBsb2cgIkdpdGVhIGJyYW5jaCBjdXJyZW50bHkgcmVzb2x2ZXMgdG8gJHtvYnNlcnZlZDotdW5hdmFpbGFibGV9OyBleHBlY3RlZCAkdGFyZ2V0LiIKICAgICAgbGFzdF9vYnNlcnZlZD0iJG9ic2VydmVkIgogICAgZmkKCiAgICBpZiBbWyAiJG9ic2VydmVkIiA9PSAiJHRhcmdldCIgXV07IHRoZW4KICAgICAgIyBUaGUgY2xvbmUgaW4gZGVwbG95X2NvbW1pdCByZXBlYXRzIHRoaXMgY29tcGFyaXNvbiBhZnRlciBmZXRjaGluZy4gVGhlCiAgICAgICMgcmVtb3RlIHByb2JlIGlzIGEgd2FpdCBjb25kaXRpb24sIG5ldmVyIHRoZSBidWlsZCdzIHRydXN0IGJvdW5kYXJ5LgogICAgICBpZiBkZXBsb3lfY29tbWl0ICIkdGFyZ2V0IjsgdGhlbgogICAgICAgIDoKICAgICAgZWxzZQogICAgICAgIGRlcGxveV9zdGF0dXM9JD8KICAgICAgICBpZiAoKGRlcGxveV9zdGF0dXMgIT0gNzUpKTsgdGhlbgogICAgICAgICAgbG9nICJEZXBsb3ltZW50IGF0dGVtcHQgZm9yICR0YXJnZXQgZmFpbGVkOyByZXRyeWluZyBpbiAke01JUlJPUl9SRVRSWV9TRUNPTkRTfXMuIgogICAgICAgICAgc2xlZXAgIiRNSVJST1JfUkVUUllfU0VDT05EUyIKICAgICAgICBmaQogICAgICBmaQogICAgICBicmVhawogICAgZmkKCiAgICBub3c9IiQoZGF0ZSArJXMpIgogICAgaWYgKCggbm93IC0gc3RhcnRlZCA+PSBNSVJST1JfV0FJVF9TRUNPTkRTICkpOyB0aGVuCiAgICAgIHdyaXRlX3Byb2dyZXNzIHJldHJ5IDIgNSAiJE1JUlJPUl9SRVRSWV9TRUNPTkRTIiAiJCgoTUlSUk9SX1JFVFJZX1NFQ09ORFMgKyBNSVJST1JfV0FJVF9TRUNPTkRTICsgNTAwKSkiICJHaXRlYSBtaXJyb3Igd2luZG93IGV4cGlyZWQ7IGFjdGl2ZSByZWxlYXNlIHByZXNlcnZlZCBiZWZvcmUgcmV0cnkiCiAgICAgIGxvZyAiTWlycm9yIHdhaXQgZXhwaXJlZCBmb3IgJHRhcmdldDsgY3VycmVudCByZWxlYXNlIHJlbWFpbnMgYWN0aXZlLiBSZXRyeWluZyBpbiAke01JUlJPUl9SRVRSWV9TRUNPTkRTfXMuIgogICAgICBzbGVlcCAiJE1JUlJPUl9SRVRSWV9TRUNPTkRTIgogICAgICBicmVhawogICAgZmkKICAgIHNsZWVwICIkTUlSUk9SX1BPTExfU0VDT05EUyIKICBkb25lCmRvbmUK
MTA_WORKER_RUNTIME
}

verify_embedded_runtime() {
  command -v base64 >/dev/null 2>&1 || fail "base64 is required to verify the runtime embedded in run.sh. Install coreutils and retry."
  command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is required to verify the runtime embedded in run.sh. Install coreutils and retry."

  local temporary failed=0
  temporary="$(mktemp -d "${TMPDIR:-/tmp}/mta-dashboard-runtime.XXXXXX")"
  write_embedded_enqueue_runtime "${temporary}/enqueue_deploy.sh" || failed=1
  write_embedded_worker_runtime "${temporary}/deploy_worker.sh" || failed=1

  if ((failed == 0)); then
    (
      cd "$temporary"
      printf '%s  %s\n' \
        "$ENQUEUE_RUNTIME_SHA256" enqueue_deploy.sh \
        "$WORKER_RUNTIME_SHA256" deploy_worker.sh \
        | sha256sum --check --status
    ) || failed=1
  fi
  if ((failed == 0)); then
    bash -n "${temporary}/enqueue_deploy.sh" "${temporary}/deploy_worker.sh" || failed=1
  fi

  rm -f -- "${temporary}/enqueue_deploy.sh" "${temporary}/deploy_worker.sh"
  rmdir -- "$temporary" 2>/dev/null || true
  ((failed == 0)) || fail "The runtime embedded in run.sh failed its checksum or Bash syntax check. Upload a complete, unmodified run.sh and retry."
}

install_runtime_files() {
  write_embedded_enqueue_runtime
  write_embedded_worker_runtime
  chown root:root "${BIN_ROOT}/enqueue_deploy.sh" "${BIN_ROOT}/deploy_worker.sh"
  chmod 0755 "${BIN_ROOT}/enqueue_deploy.sh" "${BIN_ROOT}/deploy_worker.sh"

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
  write_setting "$deploy_env" MTA_DASHBOARD_INSTALL_ROOT "$INSTALL_ROOT"
  write_setting "$deploy_env" MTA_DASHBOARD_STATE_ROOT "$STATE_ROOT"

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
  local protect_home=true unit unit_file
  case "$DEPLOY_DIR" in
    /root|/root/*|/home/*|/run/user/*) protect_home=false ;;
  esac
  for unit in mta-dashboard.service mta-dashboard-webhook.service mta-dashboard-deploy.service; do
    unit_file="/etc/systemd/system/${unit}"
    if [[ -e "$unit_file" || -L "$unit_file" ]]; then
      if project_unit_matches "$unit"; then
        rm -f -- "$unit_file"
      else
        fail "Refusing to replace unrecognized systemd registration: $unit_file"
      fi
    fi
  done

  cat >"${SYSTEMD_ROOT}/mta-dashboard.service" <<EOF
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
Environment=HOME=${STATE_ROOT}
ExecStart=${NODE_BIN} ${INSTALL_ROOT}/current/dashboard/server/index.js
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=${protect_home}
ProtectSystem=strict
ReadWritePaths=${STATE_ROOT}

[Install]
WantedBy=multi-user.target
EOF

  cat >"${SYSTEMD_ROOT}/mta-dashboard-webhook.service" <<EOF
[Unit]
Description=GitHub webhook receiver for the MTA dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
Environment=HOME=${STATE_ROOT}
ExecStart=${WEBHOOK_BIN} -ip ${WEBHOOK_HOST} -port ${WEBHOOK_PORT} -http-methods POST -hooks ${ETC_ROOT}/hooks.json
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=${protect_home}
ProtectSystem=strict
ReadOnlyPaths=${ETC_ROOT}
ReadWritePaths=${STATE_ROOT}/queue ${STATE_ROOT}/deliveries

[Install]
WantedBy=multi-user.target
EOF

  cat >"${SYSTEMD_ROOT}/mta-dashboard-deploy.service" <<EOF
[Unit]
Description=Delayed Gitea deployment worker for the MTA dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
EnvironmentFile=${ETC_ROOT}/deploy.env
Environment=HOME=${STATE_ROOT}
Environment=NPM_CONFIG_CACHE=${STATE_ROOT}/npm-cache
ExecStart=${BIN_ROOT}/deploy_worker.sh
Restart=always
RestartSec=5
PrivateTmp=true
ProtectHome=${protect_home}
ProtectSystem=strict
ReadOnlyPaths=${ETC_ROOT} ${BIN_ROOT}
ReadWritePaths=${INSTALL_ROOT} ${STATE_ROOT}

[Install]
WantedBy=multi-user.target
EOF

  chmod 0644 "${SYSTEMD_ROOT}/mta-dashboard.service" \
    "${SYSTEMD_ROOT}/mta-dashboard-webhook.service" \
    "${SYSTEMD_ROOT}/mta-dashboard-deploy.service"
  systemctl link "${SYSTEMD_ROOT}/mta-dashboard.service" \
    "${SYSTEMD_ROOT}/mta-dashboard-webhook.service" \
    "${SYSTEMD_ROOT}/mta-dashboard-deploy.service" >/dev/null

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
    "HOME=$STATE_ROOT"
    "XDG_CONFIG_HOME=$STATE_ROOT/.config"
    "GITEA_USERNAME=$GITEA_USERNAME"
    "GITEA_TOKEN=$GITEA_TOKEN"
  )
  if [[ "$GITEA_AUTH_MODE" == https ]]; then
    environment+=("GIT_ASKPASS=${BIN_ROOT}/gitea_askpass.sh")
  else
    environment+=("GIT_SSH_COMMAND=ssh -i ${INSTALLED_SSH_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=${INSTALLED_SSH_HOSTS}")
  fi
  if output="$(cd "$STATE_ROOT" && runuser -u "$SERVICE_USER" -- env "${environment[@]}" \
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
  (cd "$STATE_ROOT" && runuser -u "$SERVICE_USER" -- \
    "${BIN_ROOT}/enqueue_deploy.sh" "$tip" "$delivery")
  INITIAL_COMMIT="$tip"
}

format_seconds() {
  local seconds="$1" minutes hours
  if ((seconds < 60)); then
    printf '%ss' "$seconds"
  elif ((seconds < 3600)); then
    minutes=$(((seconds + 59) / 60))
    printf '%sm' "$minutes"
  else
    hours=$((seconds / 3600))
    minutes=$(((seconds % 3600 + 59) / 60))
    printf '%sh %sm' "$hours" "$minutes"
  fi
}

clear_progress_line() {
  printf '\r%*s\r' 120 ''
}

render_progress_bar() {
  local percent="$1" phase="$2" elapsed="$3" eta_seconds="$4"
  local width=30 filled empty bar eta_text
  ((percent < 0)) && percent=0
  ((percent > 100)) && percent=100
  filled=$((percent * width / 100))
  empty=$((width - filled))
  printf -v bar '%*s' "$filled" ''
  bar="${bar// /#}"
  printf -v phase '%-12.12s' "${phase//_/ }"
  if ((eta_seconds > 0)); then
    eta_text="ETA≈$(format_seconds "$eta_seconds")"
  elif ((percent < 100)); then
    eta_text="ETA estimate exceeded"
  else
    eta_text="complete"
  fi
  printf '\r    [%s%*s] %3d%% | %s | elapsed %s | %s' \
    "$bar" "$empty" '' "$percent" "$phase" "$(format_seconds "$elapsed")" "$eta_text"
}

wait_for_initial_deployment() {
  local started deadline active="" worker_state restarts elapsed now
  local phase="starting" lower=0 upper=2 phase_started typical_seconds=15 eta_at_start=510 message="Starting deployment worker"
  local phase_elapsed displayed_percent eta_remaining last_phase=""
  local -a progress=()
  started="$(date +%s)"
  deadline=$((started + 1800))
  note "Worker phases and approximate remaining time will appear below."
  note "Detailed Git/npm output: journalctl -u mta-dashboard-deploy.service -f"
  while (( $(date +%s) < deadline )); do
    if [[ -f "${STATE_ROOT}/active_commit" ]]; then
      active="$(tr -d '\r\n' <"${STATE_ROOT}/active_commit")"
    else
      active=""
    fi
    if [[ "$active" == "$INITIAL_COMMIT" ]] && systemctl is-active --quiet mta-dashboard.service; then
      clear_progress_line
      render_progress_bar 100 complete "$(( $(date +%s) - started ))" 0
      printf '\n'
      note "Initial release $active is active."
      return 0
    fi
    worker_state="$(systemctl is-active mta-dashboard-deploy.service 2>/dev/null || true)"
    restarts="$(systemctl show mta-dashboard-deploy.service -p NRestarts --value 2>/dev/null || true)"
    if [[ "$worker_state" == inactive || "$worker_state" == failed ]] ||
       [[ "$restarts" =~ ^[0-9]+$ && "$restarts" -ge 3 && -z "$active" ]]; then
      clear_progress_line
      journalctl -u mta-dashboard-deploy.service -n 40 --no-pager >&2 || true
      fail "The deployment worker is not stable (state=${worker_state:-unknown}, restarts=${restarts:-unknown}); review the journal above."
    fi

    if [[ -r "${STATE_ROOT}/deploy_progress" ]]; then
      mapfile -t progress <"${STATE_ROOT}/deploy_progress" || progress=()
      if ((${#progress[@]} >= 7)) &&
         [[ "${progress[1]}" =~ ^[0-9]+$ && "${progress[2]}" =~ ^[0-9]+$ &&
            "${progress[3]}" =~ ^[0-9]+$ && "${progress[4]}" =~ ^[1-9][0-9]*$ &&
            "${progress[5]}" =~ ^[0-9]+$ ]]; then
        phase="${progress[0]}"
        lower="${progress[1]}"
        upper="${progress[2]}"
        phase_started="${progress[3]}"
        typical_seconds="${progress[4]}"
        eta_at_start="${progress[5]}"
        message="${progress[6]}"
      fi
    fi

    now="$(date +%s)"
    elapsed=$((now - started))
    phase_started="${phase_started:-$started}"
    phase_elapsed=$((now > phase_started ? now - phase_started : 0))
    displayed_percent="$lower"
    if ((upper > lower)); then
      if ((phase_elapsed < typical_seconds)); then
        displayed_percent=$((lower + (upper - lower) * phase_elapsed / typical_seconds))
      else
        displayed_percent=$((upper - 1))
      fi
    fi
    eta_remaining=$((eta_at_start > phase_elapsed ? eta_at_start - phase_elapsed : 0))

    if [[ "$phase" != "$last_phase" ]]; then
      clear_progress_line
      note "Worker: $message"
      last_phase="$phase"
    fi
    render_progress_bar "$displayed_percent" "$phase" "$elapsed" "$eta_remaining"
    sleep 2
  done
  clear_progress_line
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
  elif [[ -r "${LEGACY_STATE_ROOT}/active_commit" ]]; then
    note "Active legacy commit: $(tr -d '\r\n' <"${LEGACY_STATE_ROOT}/active_commit")"
  fi
  note "Logs: journalctl -u mta-dashboard-deploy.service -f"
}

start_managed_services() {
  managed_unit_exists mta-dashboard-webhook.service || { note "Services are not installed. Choose Install or update first."; return 0; }
  systemctl enable mta-dashboard-webhook.service mta-dashboard-deploy.service >/dev/null
  systemctl restart mta-dashboard-webhook.service mta-dashboard-deploy.service
  if [[ ( -L "${INSTALL_ROOT}/current" || -L "${LEGACY_INSTALL_ROOT}/current" ) ]] && managed_unit_exists mta-dashboard.service; then
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
    "$INSTALL_ROOT"|"${INSTALL_ROOT}/"*|"$STATE_ROOT"|"${STATE_ROOT}/"*|\
    "$LEGACY_INSTALL_ROOT"|"${LEGACY_INSTALL_ROOT}/"*|"$LEGACY_STATE_ROOT"|"${LEGACY_STATE_ROOT}/"*) return 0 ;;
  esac

  if [[ -r "/proc/${pid}/cmdline" ]]; then
    command_line="$(tr '\0' ' ' <"/proc/${pid}/cmdline")"
  else
    command_line=""
  fi
  case "$command_line" in
    *"${INSTALL_ROOT}/"*|*"${STATE_ROOT}/"*|*"${ETC_ROOT}/hooks.json"*|\
    *"${LEGACY_INSTALL_ROOT}/"*|*"${LEGACY_STATE_ROOT}/"*|*"${LEGACY_ETC_ROOT}/hooks.json"*) return 0 ;;
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
  [[ "$DEPLOY_INSTALLATION_ROOT" == "${DEPLOY_DIR}/installation" ]] || fail "Refusing unexpected installation path: $DEPLOY_INSTALLATION_ROOT"

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

is_deploy_ancestor() {
  local candidate="$1" path="$DEPLOY_DIR"
  while [[ "$path" != / ]]; do
    [[ "$path" == "$candidate" ]] && return 0
    path="$(dirname "$path")"
  done
  return 1
}

remove_recorded_traversal_acls() {
  local path
  [[ -f "$ACL_RECORD" ]] || return 0
  while IFS= read -r path || [[ -n "$path" ]]; do
    [[ -n "$path" ]] || continue
    if is_deploy_ancestor "$path" && [[ -e "$path" ]]; then
      setfacl -x "u:${SERVICE_USER}" -- "$path" || note "Could not remove the recorded traversal ACL from $path."
    else
      note "Skipped unexpected recorded ACL path: $path"
    fi
  done <"$ACL_RECORD"
}

render_action_progress() {
  local percent="$1" message="$2" width=30 filled empty bar
  ((percent < 0)) && percent=0
  ((percent > 100)) && percent=100
  filled=$((percent * width / 100))
  empty=$((width - filled))
  printf -v bar '%*s' "$filled" ''
  bar="${bar// /#}"
  printf '\r    [%s%*s] %3d%% | %s' "$bar" "$empty" '' "$percent" "$message"
}

remove_tree_with_progress() {
  local target="$1" label="$2" start_percent="$3" end_percent="$4"
  local manifest total=0 processed=0 percent started elapsed eta path
  case "$target" in
    "$DEPLOY_INSTALLATION_ROOT"|"$LEGACY_ETC_ROOT"|"$LEGACY_INSTALL_ROOT"|"$LEGACY_STATE_ROOT") ;;
    *) fail "Refusing unapproved progress-deletion target: $target" ;;
  esac
  if [[ ! -e "$target" && ! -L "$target" ]]; then
    render_action_progress "$end_percent" "$label: nothing to remove"
    return 0
  fi

  manifest="$(mktemp "${TMPDIR:-/tmp}/mta-dashboard-delete.XXXXXX")"
  if ! find -P "$target" -xdev -depth -print0 >"$manifest"; then
    rm -f -- "$manifest"
    fail "Could not enumerate the approved deletion target $target."
  fi
  total="$(tr -cd '\0' <"$manifest" | wc -c | tr -d '[:space:]')"
  [[ "$total" =~ ^[0-9]+$ ]] || total=0
  started="$(date +%s)"
  render_action_progress "$start_percent" "$label: counted $total entries"

  while IFS= read -r -d '' path; do
    case "$path" in
      "$target"|"${target}/"*) ;;
      *) rm -f -- "$manifest"; fail "Deletion manifest escaped its approved root: $path" ;;
    esac
    if [[ -d "$path" && ! -L "$path" ]]; then
      if ! rmdir -- "$path"; then
        rm -f -- "$manifest"
        clear_progress_line
        fail "Could not remove project directory $path."
      fi
    elif ! rm -f -- "$path"; then
      rm -f -- "$manifest"
      clear_progress_line
      fail "Could not remove project entry $path."
    fi
    processed=$((processed + 1))
    if ((total > 0)); then
      percent=$((start_percent + (end_percent - start_percent) * processed / total))
    else
      percent="$end_percent"
    fi
    elapsed=$(( $(date +%s) - started ))
    if ((processed > 0 && elapsed > 0)); then
      eta=$(((total - processed) * elapsed / processed))
      render_action_progress "$percent" "$label: $processed/$total entries, ETA≈$(format_seconds "$eta")"
    else
      render_action_progress "$percent" "$label: $processed/$total entries"
    fi
  done <"$manifest"
  rm -f -- "$manifest"
  render_action_progress "$end_percent" "$label: complete"
}

remove_legacy_installation() {
  local start_percent="${1:-0}" end_percent="${2:-100}" span checkpoint
  [[ "$LEGACY_ETC_ROOT" == /etc/mta-dashboard ]] || fail "Refusing unexpected legacy configuration path."
  [[ "$LEGACY_INSTALL_ROOT" == /opt/mta-dashboard ]] || fail "Refusing unexpected legacy application path."
  [[ "$LEGACY_STATE_ROOT" == /var/lib/mta-dashboard ]] || fail "Refusing unexpected legacy state path."
  if [[ -e "$LEGACY_ETC_ROOT" || -e "$LEGACY_INSTALL_ROOT" || -e "$LEGACY_STATE_ROOT" ]]; then
    span=$((end_percent - start_percent))
    checkpoint=$((start_percent + span / 6))
    remove_tree_with_progress "$LEGACY_ETC_ROOT" "Deleting legacy configuration" "$start_percent" "$checkpoint"
    remove_tree_with_progress "$LEGACY_INSTALL_ROOT" "Deleting legacy releases" "$checkpoint" "$((start_percent + span * 5 / 6))"
    remove_tree_with_progress "$LEGACY_STATE_ROOT" "Deleting legacy state" "$((start_percent + span * 5 / 6))" "$end_percent"
    clear_progress_line
    note "Removed the obsolete system-level project installation after the local release became healthy."
  fi
}

remove_service_definitions() {
  local start_percent="${1:-0}" end_percent="${2:-100}" unit unit_file index=0 percent
  render_action_progress "$start_percent" "Stopping verified project services"
  stop_existing_services
  for unit in mta-dashboard.service mta-dashboard-webhook.service mta-dashboard-deploy.service; do
    unit_file="/etc/systemd/system/${unit}"
    if project_unit_matches "$unit"; then
      systemctl disable "$unit" >/dev/null 2>&1 || true
      rm -f -- "$unit_file"
    elif [[ -e "$unit_file" ]]; then
      clear_progress_line
      note "Preserved unrecognized unit file $unit_file."
    fi
    index=$((index + 1))
    percent=$((start_percent + (end_percent - start_percent) * index / 5))
    render_action_progress "$percent" "Removing verified service registrations ($index/3)"
  done
  if [[ -f /etc/sudoers.d/mta-dashboard-restart ]] &&
     grep -Fq -- 'restart mta-dashboard.service' /etc/sudoers.d/mta-dashboard-restart; then
    rm -f -- /etc/sudoers.d/mta-dashboard-restart
  fi
  render_action_progress "$((start_percent + (end_percent - start_percent) * 4 / 5))" "Reloading systemd configuration"
  systemctl daemon-reload
  systemctl reset-failed >/dev/null 2>&1 || true
  render_action_progress "$end_percent" "Service removal complete"
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
      remove_service_definitions 0 100
      printf '\n'
      note "Removed the three systemd service definitions. Configuration, releases, state, and the service account were preserved."
      ;;
    2)
      MENU_SELECTION=0
      select_menu "Full uninstall permanently deletes $DEPLOY_INSTALLATION_ROOT and any reviewed legacy project roots." \
        "Cancel (recommended)" \
        "Permanently delete managed deployment data"
      if ((MENU_SELECTION == 1)); then
        [[ "$DEPLOY_INSTALLATION_ROOT" == "${DEPLOY_DIR}/installation" ]] || fail "Refusing unexpected installation path: $DEPLOY_INSTALLATION_ROOT"
        [[ "$DEPLOY_INSTALLATION_ROOT" != / && "$DEPLOY_INSTALLATION_ROOT" != "$DEPLOY_DIR" ]] || fail "Refusing broad installation removal target."
        remove_service_definitions 0 20
        render_action_progress 22 "Removing recorded path-traversal permissions"
        remove_recorded_traversal_acls
        remove_tree_with_progress "$DEPLOY_INSTALLATION_ROOT" "Deleting local deployment data" 22 82
        remove_legacy_installation 82 96
        render_action_progress 98 "Removing the dedicated service account"
        if id "$SERVICE_USER" >/dev/null 2>&1; then userdel "$SERVICE_USER"; fi
        if getent group "$SERVICE_GROUP" >/dev/null 2>&1; then groupdel "$SERVICE_GROUP"; fi
        render_action_progress 100 "Full uninstall complete"
        printf '\n'
        note "Full uninstall complete. The uploaded run.sh, .env, and shared dependencies were not removed."
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
  verify_embedded_runtime
  note "Embedded runtime helpers passed checksum and Bash syntax verification."

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
  rm -f -- "${STATE_ROOT}/deploy_progress"
  systemctl restart mta-dashboard-webhook.service
  systemctl restart mta-dashboard-deploy.service
  wait_for_initial_deployment
  remove_legacy_installation

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
  verify_embedded_runtime
  note "Configuration, host prerequisites, and embedded runtime helpers are valid; no credential was printed and no installation or service mutation was performed."
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
