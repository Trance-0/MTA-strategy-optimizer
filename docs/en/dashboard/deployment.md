---
title: Running Locally and Publishing
compact: "Dashboard launch/deployment contract: local launchers, static publishing, and deploy/run.sh lifecycle with bounded Gitea diagnostics, download progress, project-only stale-process cleanup, GitHub HMAC queueing, exact-commit gating, atomic releases, rollback, and uninstall."
lang: en-US
source_files: dashboard/index.html, dashboard/vite.config.js, dashboard/run.sh, dashboard/run.bat, deploy/run.sh, deploy/runtime/enqueue_deploy.sh, deploy/runtime/deploy_worker.sh, script/build_pages_site.mjs, script/export_dashboard_snapshot.mjs
---

# Running Locally and Publishing

## Running It Locally <span class="status-label status-verified" aria-label="Verified"></span>

```bash
./dashboard/run.sh          # macOS, Linux, Git Bash
dashboard\run.bat           # Windows
./dashboard/run.sh 8600     # a different port
./dashboard/run.sh --help   # the full banner
```

Nothing needs to be installed beforehand except Node.js. Both launchers take an optional port, resolve the repository root themselves so they work from any directory, and then work through four named steps: the toolchain, the configuration, the dependencies, and the client build. They check Node against Vite's engine range, `^20.19.0 || >=22.12.0`; they copy `sample.env` to `.env` when none exists, so a fresh clone starts in file mode rather than failing on a missing variable, and never overwrite an existing one; and they install and build only when what those steps produce is absent, so a warm checkout starts immediately. Reading the PostgreSQL mirror is a matter of setting `DATABASE=true` and the `PG_*` values in `.env`; nothing about the command changes.

Every failure names what went wrong, what to do about it, and the environment facts a bug report needs — version, commit, operating system, Node, npm, requested port, failed step, and the last twenty lines of the install or build output, which is otherwise hidden so a successful run stays quiet.

For client work, `npm run dev` in `dashboard/` serves the sources through Vite with hot reload and proxies `/api` to the Express server, which must be started separately with `npm start`.

## Deploying to a Team Server <span class="status-label status-designed" aria-label="Designed"></span>

The `deploy/` directory is a self-contained transfer bundle for a Linux team server. Its `run.sh` command is an explicit deployment-only exception to the repository's normal rule that maintained project commands live under root `script/`: an operator must be able to upload this one directory, add `deploy/.env`, and run one command before the repository exists on the server. The tracked `.env.example` names every accepted setting but contains no credential. The real `.env` is ignored, must be transferred over a protected administrative channel, and is treated as bootstrap input rather than as a permanent secret store. In the prepared local bundle, current PostgreSQL values and Gitea credentials are mapped from the project-root `.env`, while the GitHub repository/branch and a newly generated webhook secret complete the deployment-only settings. A repository-scoped, read-only Gitea token is preferred over an account password.

After protected transfer, the operator runs `sudo bash run.sh`. The full-screen interface accepts Up, Down, and Enter only. Its main menu installs or updates the deployment, reports status, starts or restarts managed services, stops them without changing their automatic-start setting, terminates stale project processes, uninstalls the service definitions while preserving application data, or exits. Full removal has a separate confirmation whose safe default is cancellation; it removes only `/etc/mta-dashboard`, `/opt/mta-dashboard`, `/var/lib/mta-dashboard`, the three service definitions, their narrow `sudoers` rule, and the service account. Shared Git, Node.js, `adnanh/webhook`, and the uploaded transfer bundle are retained.

Stale-process cleanup first stops only the three named `mta-dashboard` services whose on-disk unit definitions still reference the expected fixed project paths; an unrecognized same-name unit is preserved. It then considers only processes owned by the dedicated `mta-dashboard` account and associated with this deployment through one of those verified `systemd` control groups, a working directory below `/opt/mta-dashboard` or `/var/lib/mta-dashboard`, or a command referencing `/opt/mta-dashboard`, `/var/lib/mta-dashboard`, or `/etc/mta-dashboard/hooks.json`. It never selects by port, `node`, Git, npm, or another generic process name. Each process identifier is checked against those conditions again immediately before a `TERM` signal and, if still alive after the grace period, again before a `KILL` signal. Reused process identifiers and all unrelated processes are therefore excluded.

`run.sh` detects the Linux distribution, processor architecture, package manager, init system, occupied Transmission Control Protocol (TCP) ports, and installed Git, Node.js, npm, and `adnanh/webhook` versions. It supports `systemd` as the service manager and refuses an unsupported init system with a named remedy; it never falls back to an unmanaged background process. It accepts an operator-selected unbound port above 8000 or finds one from the configured starting point. This proves only that the server can bind the local port. Firewall, proxy, Domain Name System (DNS), and external reachability remain explicit operator configuration and are never inferred from a local socket probe. Curl displays a progress bar while downloading Node.js or `adnanh/webhook`, and the checksum gate still runs before either archive is extracted.

The installer creates an unprivileged `mta-dashboard` account, copies runtime configuration to `/etc/mta-dashboard/`, restricts its permissions, and installs application state under `/opt/mta-dashboard/` and `/var/lib/mta-dashboard/`. A credential-free Gitea repository address is mandatory. Hypertext Transfer Protocol Secure (HTTPS) access uses a Gitea access token through Git's non-interactive credential helper; Secure Shell (SSH) access uses an operator-supplied private key and pinned known-hosts file. A credential must never appear in a repository address, command argument, service definition, process listing, deployment log, or printed setup summary.

The dashboard binds to the configured private address, `127.0.0.1` by default. A public deployment must put a Transport Layer Security (TLS) reverse proxy with team authentication in front of it, because the dashboard exposes settings and data-mutation routes and does not implement user authentication. The webhook listener also defaults to loopback for a reverse proxy. Binding either service to a non-loopback address requires an explicit setting and causes the installer to print a warning rather than silently widening access.

### GitHub Receives the Push; Gitea Supplies the Code

GitHub is the authoritative event source. Gitea is the only repository the deployment server reads, and its mirror may lag a GitHub push by approximately five minutes. A GitHub push therefore does not mean the matching source is already available for deployment.

The webhook accepts only a JavaScript Object Notation (JSON) `POST`. Before executing any project command, `adnanh/webhook` verifies the [Hash-based Message Authentication Code (HMAC)](/en/reference/definitions#hmac-hash-based-message-authentication-code) carried by `X-Hub-Signature-256` and matches the configured `repository.full_name`. An authenticated GitHub `ping` is acknowledged without queueing work, so the setup delivery succeeds. A deployment additionally requires `X-GitHub-Event: push` and the configured `refs/heads/<branch>`. The enqueue command then independently validates the push payload's 40-character `after` commit identifier and the `X-GitHub-Delivery` identifier. A delivery identifier already recorded in the protected state directory is acknowledged without creating a second deployment.

The webhook command only writes the latest desired commit to a durable queue by atomic rename. It does not clone, install, build, restart, or wait for Gitea. This separation lets the webhook return a successful response within GitHub's ten-second delivery window while the supervised deployment worker handles the slow path. Several pushes received during one mirror delay are coalesced: the durable queue retains the newest desired commit, so an intermediate commit is not deployed immediately before its successor.

### Exact-Commit Gate

For each queued request, the deployment worker polls the configured Gitea branch at the configured interval, ten seconds by default. It reloads the queue on every poll so a newer GitHub push replaces the target being awaited. The normal waiting window is ten minutes, which covers the expected five-minute mirror delay with margin; both values are configurable. Each individual Gitea probe or clone has a separate bounded request timeout, 45 seconds by default. A timeout reports the repository host and branch without printing authentication data, retains the queued request, and enters the ordinary retry path instead of hanging the installer or worker indefinitely. Other Git failures preserve their diagnostic text because repository addresses are required to be credential-free.

**Before building, the worker fetches the Gitea branch and verifies that its resolved commit exactly equals the latest queued GitHub `after` commit.** Seeing the commit anywhere in the object store is insufficient, and seeing a different branch tip is insufficient. Until the branch tip and queued commit are identical, the currently running dashboard remains untouched.

If the waiting window expires, the worker records the expected and observed commit identifiers, retains the pending request, and enters the configured retry delay. It never deploys the older Gitea branch as a fallback. The continuously supervised worker then retries without requiring GitHub to redeliver the webhook. A newer queued push supersedes the timed-out target on the next poll.

### Atomic Release and Recovery

After the exact-commit gate passes, the worker creates `/opt/mta-dashboard/releases/<commit>`, checks out that commit from Gitea, runs `npm ci`, the dashboard tests, and `npm run build`, and verifies that `dashboard/dist/index.html` exists. A deployment lock prevents concurrent builds. The active `/opt/mta-dashboard/current` symbolic link changes only after every pre-activation check passes.

The dashboard service is then restarted and checked through both its page and `/api/dashboard`. If either health check fails, the worker restores the previous symbolic link, restarts the previous release, verifies recovery, and leaves the failed release and logs available for diagnosis. A successful deployment removes the matching queue entry only if no newer desired commit arrived during the build, records the active commit, and prunes releases beyond the configured retention count. The initial interactive installation deploys the branch tip currently available from Gitea; exact GitHub-to-Gitea matching governs every queued webhook deployment after that.

### Services and Operator Output

`systemd` owns three long-running services: the Node dashboard, the small `adnanh/webhook` receiver, and the queue worker. They run as the unprivileged service account, restart after recoverable failures, start after networking, and write operational output to the journal. The installer enables them, performs the initial deployment, exercises a locally signed GitHub-style webhook, and reports service and health status. Stop is reversible and preserves enablement; start restores the receiver and worker immediately and starts the dashboard when an active release exists. Status works without loading the bootstrap credential file.

The final summary prints the verified dashboard address and the GitHub repository-webhook fields the operator must enter: payload address, `application/json` content type, push events only, active status, TLS verification enabled, and the name of the protected secret setting. It never prints the secret value. The receiver enforces the branch because GitHub repository webhooks do not provide a branch-filter control.

## Published Build <span class="status-label status-verified" aria-label="Verified"></span>

The dashboard is deployed to GitHub Pages at the site root, with the documentation one level down at `/docs/`.

Pages serves static files and cannot run the Express Application Programming Interface (API), so the published client is built in **static mode**: `script/export_dashboard_snapshot.mjs` writes the same payload the API would return to `data/snapshot.json` at build time, and `src/api/client.js` fetches that file instead. A view sees no difference. This is the browser-side counterpart of the `DATABASE=true/false` contract — the same client source, a different data path, never a different codebase.

Three consequences follow, and each is handled rather than hidden:

- **The database source is unavailable.** A static host has no server to open a connection from. The export command pins file mode and **refuses to write a snapshot read from a database**, so a private deployment's data cannot be baked into a public artifact. The settings dialog replaces the credential form with the local-run instructions, so a visitor is never invited to type a real password into a page that cannot use it.
- **The base path is relative.** Pages serves a project site from a subdirectory, so `vite build --mode static` sets `base` to `./` and the snapshot is fetched at a relative path; an absolute path would resolve against the domain root.
- **Only the data the loaders read is published.** One snapshot of roughly 720 KB, exported from the eleven committed artifacts. The 2.8 MB synthetic-events extract is excluded because no view reads it.

The workflow is `.github/workflows/deploy-pages.yml`. It builds the client with `npm run build:static`, builds the documentation with its base path set to the Pages base plus `docs/` — because Pages performs no rewrites and every internal link is resolved at build time — then assembles both into `site/` and uploads that as the Pages artifact.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `deploy/run.sh`

Source: `deploy/run.sh`

- Responsibility: Manage one Linux team server from the self-contained `deploy/` transfer bundle through an Up/Down/Enter menu: install or update, inspect, start or restart, stop, or uninstall the managed services; perform the first deployment from Gitea; verify the signed webhook path; and print the GitHub setup fields.
- Inputs: `deploy/.env` by default or `--env PATH` for installation; `--non-interactive`, `--check`, and `--help`; an `apt`- or `dnf`-based Linux distribution with `systemd`; root or `sudo`; outbound access to the configured Gitea service, Node.js downloads, and the `adnanh/webhook` release. The real `.env` follows `.env.example` and supplies the GitHub repository/branch/secret, credential-free Gitea address and read-only authentication, listener addresses and ports, mirror timing, data source, and optional public addresses. Status, start, stop, and uninstall do not parse bootstrap credentials.
- Outputs: Node.js and `adnanh/webhook` when compatible versions are absent; visible progress for their downloads; the `mta-dashboard` account; protected configuration and a root-only GitHub webhook-secret file under `/etc/mta-dashboard`; runtime commands, releases, and the active link under `/opt/mta-dashboard`; queue state under `/var/lib/mta-dashboard`; `mta-dashboard`, `mta-dashboard-webhook`, and `mta-dashboard-deploy` services; a narrow service-restart `sudoers` rule; an initial healthy release; and a credential-free operator summary. The uninstall paths can remove only service definitions or, after a second confirmation, all fixed application paths and the service account; shared packages and the transfer bundle remain.
- Behavior contract: The default terminal interface accepts Up/Down and Enter; text confirmation is never required inside the command. The safe option is selected by default for credential removal, stale cleanup, and both uninstall menus. The parser accepts only named keys and never evaluates `.env` as shell code. Repository addresses containing credentials, query strings, or fragments are rejected. [HTTPS](/en/reference/definitions#https-hypertext-transfer-protocol-secure) authentication requires a read-only token; [SSH](/en/reference/definitions#ssh-secure-shell) authentication requires both a private key and a pinned known-hosts file. GitHub's webhook secret must contain at least 32 URL-safe characters. Dashboard and webhook ports must be unbound, distinct on the same address, above 8000, and no greater than 65535; an occupied configured port is replaced only with arrow-key operator confirmation, or automatically in non-interactive mode. Compatible installed tools are retained. Otherwise Node 22.23.2 and webhook 2.8.3 archives are downloaded with a curl progress bar from their upstream secure addresses and checked against the architecture-specific [SHA-256](/en/reference/definitions#sha-256-secure-hash-algorithm-256-bit) digest embedded in the command before extraction. Gitea probes and clones have the configured per-request timeout and preserve credential-free diagnostics. `--check` performs no install or service mutation. A rerun stops only the three managed services before probing their ports, regenerates root-owned definitions, and reuses a healthy release whose commit still matches Gitea. Stale cleanup stops those same units, then signals only revalidated processes owned by the dedicated account and tied to the fixed project control groups, paths, or hooks file; it never kills by port or generic executable name. Real credentials are separated between the dashboard and deploy environment files, given only to the service that needs them, and never printed. The root-only webhook-secret file lets an administrator retrieve that one value explicitly while configuring GitHub. After a healthy interactive install, the operator can retain or permanently remove the exact uploaded `.env`; non-interactive mode keeps it and prints the removal reminder. The final GitHub fields name `POST`, `application/json`, push-only events, active status, certificate verification, the exact endpoint, and the protected secret path.
- Dependencies: Bash, then the operating-system packages the command installs: certificate authorities, `curl`, Git, OpenSSL, `sudo`, archive tools, `util-linux`, and `iproute`. The uploaded directory must include `runtime/enqueue_deploy.sh` and `runtime/deploy_worker.sh`.
- Verification: `bash -n deploy/run.sh`; `sudo bash deploy/run.sh --check --env <test-env>` on Ubuntu with `systemd`; `npm test` and `npm run build` in `dashboard/`; then a full run on the target class of server. The check path was executed on Ubuntu 22.04 under Windows Subsystem for Linux without changing packages or services.

### `deploy/runtime/enqueue_deploy.sh`

Source: `deploy/runtime/enqueue_deploy.sh`

- Responsibility: Keep the GitHub request path short by independently validating the untrusted commit and delivery arguments, deduplicating the delivery, and atomically replacing the durable desired-commit queue entry.
- Inputs: `enqueue_deploy.sh <after-commit> <delivery-id> <event>`, invoked only after `adnanh/webhook` has verified GitHub's [Hash-based Message Authentication Code (HMAC)](/en/reference/definitions#hmac-hash-based-message-authentication-code), content type, repository, and either the setup-ping event or the push event plus branch. The normal state root is `/var/lib/mta-dashboard`; `MTA_DASHBOARD_STATE_ROOT` exists only to isolate verification.
- Outputs: A three-line `queue/pending` file containing the lowercase 40-character commit, delivery identifier, and Coordinated Universal Time (UTC) receipt time; plus a protected delivery marker retained for thirty days.
- Behavior contract: An authenticated `ping` with a valid delivery identifier exits 0 without writing queue state. For a push, a malformed commit, the all-zero deleted-ref commit, a malformed delivery identifier, or any other event exits 2 without writing state. Queue mutation holds `queue.lock`, writes a mode-`600` temporary file, and renames it over `pending`, so the worker sees either the whole old request or the whole new request. The delivery marker is written only after the atomic queue move; a crash can therefore cause an idempotent duplicate write but cannot acknowledge and lose a request. A recorded delivery exits 0 without replacing the queue. A newer accepted delivery replaces the desired commit, which is how pushes coalesce during mirror delay.
- Dependencies: Bash, `flock`, `mktemp`, `find`, and the protected state directory.
- Verification: `bash -n deploy/runtime/enqueue_deploy.sh`; an isolated temporary-state test covering acceptance, delivery deduplication, newest-request replacement, and malformed-commit rejection.

### `deploy/runtime/deploy_worker.sh`

Source: `deploy/runtime/deploy_worker.sh`

- Responsibility: Supervise the eventual-consistency boundary between GitHub and Gitea, enforce the exact-commit gate, build immutable dashboard releases without privilege, activate and health-check them, and roll back a failed activation.
- Inputs: The durable queue; the root-only deploy environment passed by `systemd`; the credential-free Gitea repository and branch; optional HTTPS token or SSH key paths; mirror polling/wait/retry values; dashboard private address; release retention; and the narrow permission to restart exactly `mta-dashboard.service`. `--verify-exact <commit>` exercises only the fetched-branch equality gate. The two `MTA_DASHBOARD_*_ROOT` overrides isolate verification and are not set by production services.
- Outputs: Immutable `/opt/mta-dashboard/releases/<commit>` checkouts with built clients, the atomic `current` link, `active_commit`, journal records that name expected and observed commits, removal of a satisfied queue entry, and bounded old releases.
- Behavior contract: The worker reloads `pending` on every poll, so the newest accepted push supersedes an older wait and resets its waiting window. A mirror-window timeout retains the request and the active release, sleeps for the retry interval, and tries again; an older Gitea revision is never a fallback. Each Git network command also has the configured per-request timeout, preventing one probe or clone from consuming that entire window or hanging forever. When the remote branch first reports the desired commit, the build path **clones the branch and independently resolves `refs/remotes/origin/<branch>` again**. Unless that fetched identifier exactly equals the current queued GitHub commit, the checkout is rejected before dependency installation. It also rechecks the queue before the build and before activation, so a superseded release is never switched live. A deployment lock serializes builds. The accepted checkout runs `npm ci`, tests, and the production build as `mta-dashboard`; no repository command runs as root, and the npm subprocesses have every Gitea/Git authentication variable removed from their environment. A failed or timed-out clone, dependency install, test, build, or health check retains the queue and waits for the retry interval instead of entering a tight failure loop. Activation uses an atomic symbolic-link rename. Both `/` and `/api/dashboard` must become healthy after restart. Failure restores and verifies the preceding link; success removes the queue only when it still names the deployed commit. A queued commit already active and healthy is an idempotent no-op. Git authentication is non-interactive, and a credential cannot enter a clone address or log.
- Dependencies: Bash, Git, npm, `curl`, `flock`, the generated askpass helper or pinned SSH files, and the three installed services.
- Verification: `bash -n deploy/runtime/deploy_worker.sh`; an isolated local bare-repository test in which the current branch tip passes `--verify-exact` and its stale parent fails; the dashboard test/build commands; then a target-server exercise covering delayed mirroring, coalesced pushes, timeout/retry, activation health, and rollback.

### `index.html` and `vite.config.js`

Source: `dashboard/index.html`, `dashboard/vite.config.js`

- Responsibility: Mount the client, and build it for the two deployments.
- Inputs: `src/main.js`. The build mode.
- Outputs: `dashboard/dist` for a local run, `dashboard/dist-static` for the published build.
- Behavior contract: One source tree serves both targets; the only difference is `base` and the `VITE_STATIC_BUILD` flag `src/api/client.js` reads. `base` is relative in the static build because Pages serves a project site from a subdirectory and an absolute asset path would resolve against the domain root. Plotly and Vue are split into their own chunks, so a change to a view leaves the visitor's cached copy of the 4.6 MB chart library intact. `manualChunks` is written as a **function**: Vite 8 bundles with Rolldown, which fails the build on the object form rather than normalising it. The dev server proxies `/api` to the Express server, so client work has hot reload against the real API.
- Dependencies: `vite`, `@vitejs/plugin-vue`.
- Verification: `npm run build` and `npm run build:static` in `dashboard/`, then serving each and driving it in a real browser.

### `export_dashboard_snapshot.mjs`

Source: `script/export_dashboard_snapshot.mjs`

- Responsibility: Write the dashboard snapshot to a JavaScript Object Notation (JSON) file for the published static build.
- Inputs: The committed Comma-Separated Values (CSV) and JSON artifacts.
- Outputs: `dashboard/public/data/snapshot.json` by default, which Vite copies into the build output verbatim, plus a summary line naming the row count, the size, and the source.
- Behavior contract: The export is **forced to file mode**, pinned before `data_source.js` is imported because the mode is cached on first read, and it **refuses to write a snapshot whose mode is anything else** — a published artifact must never carry data read from a private database. The payload is the same one the API returns, produced by the same loaders, which is what keeps the two deployments one codebase. It is not pretty-printed: indentation adds roughly a third to a file every visitor downloads.
- Dependencies: Everything `server/data_source.js` needs in file mode.
- Verification: `node script/export_dashboard_snapshot.mjs`, then serving `dashboard/dist-static` and driving it in a real browser; the six views render identically to the API-backed run with no failed request.

### `build_pages_site.mjs`

Source: `script/build_pages_site.mjs`

- Responsibility: Assemble the GitHub Pages site — the dashboard at the root, the documentation under `/docs/`.
- Inputs: `dashboard/dist-static` and `docs/.vitepress/dist`.
- Outputs: `site/`, which the workflow uploads as the Pages artifact, plus a summary line naming the file count and total size.
- Behavior contract: The script refuses to run, naming the command that fixes it, when either build is missing **or when the static build carries no `data/snapshot.json`** — the snapshot is the published build's only data source, so without it every view would render its error card, which would reach a visitor as a broken page rather than as a failed build. A `.nojekyll` marker is written, without which Pages runs Jekyll and drops the underscore-prefixed files inside the built assets.
- Dependencies: Node's `fs`, `path`, and `url`. No build tool of its own.
- Verification: `node script/build_pages_site.mjs` after both builds, then serving `site/`. The assembled site was verified in a real browser: the dashboard at the root with all six views rendering, the snapshot at `/data/snapshot.json`, and the documentation at `/docs/`.

### `run.sh` and `run.bat`

Source: `dashboard/run.sh`, `dashboard/run.bat`

- Responsibility: Start the local dashboard from a clean clone, on either platform, with one command and nothing installed beforehand but Node.js.
- Inputs: An optional port as the first argument, defaulting to 8501; `--no-open`, `--rebuild`, and `-h`/`--help`. Node on `PATH`. `DASHBOARD_NONINTERACTIVE=1` suppresses the `pause` that `run.bat` uses to hold a double-clicked window open on failure.
- Outputs: A running server, with its Uniform Resource Locator (URL) printed before it starts. On failure, a named cause, a remedy, and a bug-report block.
- Behavior contract: Both resolve the repository root from the script's own location rather than the working directory, so the command works from anywhere. Four steps run in order — toolchain, configuration, dependencies, client build — and each failure is reported by name rather than as the raw error of whatever ran last.

  Node is checked against **Vite's own engine range**, `^20.19.0 || >=22.12.0`, comparing the minor and patch numbers rather than the major alone. The precision matters: Vite's bundler binding is an optional dependency carrying that same range, so an unsupported version installs cleanly — npm skips the binding silently — and fails minutes later at build time with a missing-module error naming neither Node nor the version.

  `sample.env` is copied to `.env` when none exists, which is what makes a fresh clone start in file mode instead of failing on a missing variable; an existing `.env` is never overwritten, because it holds the operator's real credentials. `npm install` runs only when `node_modules/express` is absent — the package standing in for the whole tree, so an interrupted install is repaired rather than skipped — and `npm run build` only when `dist/index.html` is absent, or always with `--rebuild`. Both npm commands run from `dashboard/` rather than through `npm --prefix`, which sets where `node_modules` is written but not where the manifest is read from.

  An unrecognised argument or an out-of-range port exits 2, `--help` exits 0, and a failed step exits 1. The port is not probed here: the server binds it, so it is the process that can report a conflict precisely rather than racing a check made in advance.
- Dependencies: Node and npm. Nothing else is assumed present.
- Verification: Both were run against a simulated clean clone — `node_modules` and `dist` removed — on Node 26.5, which installed, built, and served the client and the API, and on Node 22.11, which is refused at step one with the range named. Every argument path was checked for its exit code, and the failure report was confirmed to carry the environment block and the tail of `dashboard/.run.log` from an install forced to fail. `dashboard\run.bat 8602` from a directory outside the repository served both the client and the API against the live PostgreSQL mirror with `DATABASE=true`.
