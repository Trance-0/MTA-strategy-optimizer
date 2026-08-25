---
title: Running Locally and Publishing
compact: "Dashboard delivery contract: Bash and Windows launchers build Vue then start Flask, Vite hot reload proxies `/api`, a two-container Docker stack runs the client and API separately for testing, static publishing exports Flask's file-mode snapshot through Python, GitHub Pages assembles dashboard and English documentation, and production uses the Yunxiao AppStack image and orchestration."
lang: en-US
source_files: dashboard/index.html, dashboard/vite.config.js, dashboard/run.sh, dashboard/run.bat, deploy/docker/compose.yaml, deploy/docker/defaults.env, deploy/docker/run.sh, deploy/docker/run.bat, script/build_pages_site.mjs, script/export_dashboard_snapshot.py
---

# Running Locally and Publishing

## Running Locally

```bash
./dashboard/run.sh          # macOS, Linux, Git Bash
dashboard\run.bat           # Windows
./dashboard/run.sh 8600     # a different port
./dashboard/run.sh --help   # complete usage
```

The launchers require Node.js in Vite's supported range and `uv`. They resolve
the repository root, copy `sample.env` to `.env` only when absent, install the
locked Node and Flask dependencies, build `dashboard/dist`, and start
`backend.app`. The backend serves the Application Programming Interface (API)
and built client on one port. `--rebuild` removes only the generated client
build before rebuilding it.

For client hot reload, start Flask from the repository root and Vite from
`dashboard/`:

```powershell
uv run --extra backend python -m backend.app
Set-Location dashboard
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8501`. The client therefore exercises
the real Python backend while Vue modules reload in place.

## Two-Container Docker Stack

`deploy/docker/` runs the client and the API as separate containers, so each
can be rebuilt, restarted, and read on its own. It is a testing counterpart to
AppStack, which deploys one image serving both.

```bash
./deploy/docker/run.sh          # build both images and start
./deploy/docker/run.sh down     # stop and remove them
./deploy/docker/run.sh logs     # follow both containers
```

`deploy\docker\run.bat` is the Windows equivalent. Both read the
repository-root `VERSION` file into `PROJECT_VERSION` and tag the two images
with it, so bumping `VERSION` is the only thing that rolls the tag. `up` stops
the previous run first: a rebuilt image does not replace a container that is
already running, and the old one still holds the published ports.

The client is served by NGINX on `http://localhost:8090` and proxies `/api` to
the API container by service name. The API is also published on
`http://localhost:8501` so it can be exercised with `curl`, but the browser
never uses that port — **the only thing the client is given is a URL.** No
credential and no database driver exists on the client side of the stack.

The dashboard container waits for the API's `service_healthy` condition rather
than for its start, because NGINX resolves the upstream name once at worker
start. The API's health check calls `/api/health` with `urllib`, since the slim
Python image carries no `curl` or `wget`.

### The data source is detected, not configured

`compose.yaml` layers two application environment files, last value winning:

- `deploy/docker/defaults.env` is tracked and holds `DATABASE=false` with empty
  `PG_*` values, so a clean checkout with no `.env` starts and serves the
  committed CSV and JSON files.
- The repository-root `.env` is optional and overrides any of those. It is
  passed to the **API container only**, at run time. `.dockerignore` excludes
  `.env` from the build context, so no credential is baked into an image layer.

`run.sh` prints which of the two was resolved, so a stack reading the wrong
source is visible at startup rather than at the first empty chart.

`DATABASE=true` needs a host the container can reach. `localhost` in the root
`.env` names the container itself; a database on the Docker Desktop host is
`host.docker.internal`. Stack knobs — `DASHBOARD_PORT`, `API_PORT` — go in an
ignored `deploy/docker/.env` instead, so the root file's `DASHBOARD_PORT`,
which is where the *local* server binds, cannot silently move the published
port.

## Static GitHub Pages Build

GitHub Pages cannot run Flask, so the published client uses static mode.
`script/export_dashboard_snapshot.py` forces local-file mode and writes the
same fourteen-key JavaScript Object Notation (JSON) object as Flask to
`dashboard/public/data/snapshot.json`. `vite build --mode static` copies it
into the build and sets the one client flag that makes
`dashboard/src/api/client.js` fetch the relative data file.

The exporter must never publish database data. It sets `DATABASE=false` and
`DASHBOARD_HOSTED=true` before loading any repository and refuses a snapshot
whose mode is not `local files`. This makes accidental private-data inclusion
a failed build rather than a review convention.

Run the dashboard static build from `dashboard/`:

```powershell
npm run build:static
```

The Pages workflow installs Python, `uv`, Node, dashboard dependencies, and
documentation dependencies. It builds the dashboard and English VitePress
site, then `script/build_pages_site.mjs` assembles the dashboard at `/` and the
documentation at `/docs/` in the ignored `site/` directory. GitHub Pages is
the only maintained documentation deployment target.

## Production Deployment

The retired `deploy/run.sh` host bundle no longer exists. Production builds
one full-stack container and deploys it through Alibaba Cloud Yunxiao AppStack.
The exact image, placeholders, Kubernetes resources, credential boundary,
health probes, and validation sequence are specified in
[Backend Setup and Deployment](/en/introduction/backend/setups).

## Source Files

### `dashboard/run.sh` and `dashboard/run.bat`

Source: `dashboard/run.sh`, `dashboard/run.bat`

- Responsibility: Validate local Node and uv toolchains, initialize safe file
  configuration, install dependencies, build Vue, and launch Flask.
- Inputs: Optional port, `--no-open`, `--rebuild`, and root `.env`.
- Outputs: `dashboard/dist` and one local backend process.
- Dependencies: Node.js, npm, uv, and the locked project files.
- Verification: `bash -n dashboard/run.sh`, `dashboard\run.bat --help`, and a
  local `/api/health` request after startup.

### The two-container test stack

Source: `deploy/docker/compose.yaml`, `deploy/docker/defaults.env`,
`deploy/docker/Dockerfile.api`, `deploy/docker/Dockerfile.dashboard`,
`deploy/docker/nginx.conf`, `deploy/docker/run.sh`, `deploy/docker/run.bat`

- Responsibility: Build and run the client and API as two containers, tagged
  from `VERSION`, reading whichever data source the checkout is configured for.
- Inputs: The repository root as build context; `defaults.env`; the optional
  root `.env`; the optional `deploy/docker/.env` for ports.
- Outputs: `marketing-roi-analysis-dashboard` on 8090 and
  `marketing-roi-analysis-api` on 8501, both with health checks.
- Behavior contract: `Dockerfile.api` deliberately does **not** copy
  `dashboard/dist`, so `client_dist_directory()` returns None and the service
  registers API routes only — the client is the other image. It builds with
  `npm run build`, not `--mode static`, which would bake a snapshot and make
  Flask unreachable. `HOME` and `UV_CACHE_DIR` are set to `/tmp` *after*
  `uv sync` and the `useradd`, because the build runs as root and an earlier
  `UV_CACHE_DIR` bakes a root-owned cache the service account is then denied;
  without them every pipeline stage fails at launch, since the unprivileged
  user's home is `/nonexistent` and uv initializes a cache before it runs
  anything. The root `.env` is layered over `defaults.env` at run time and
  never copied into an image. The client container holds no credential and
  reaches the API by service name.
- Dependencies: Docker with Compose v2. No local Node or uv.
- Verification: `./deploy/docker/run.sh up`, then both containers reach
  `healthy`; `/api/health` answers directly and through the proxy;
  `/api/dashboard` returns fifteen keys; and the six views render in a browser
  with no console, page, or network error. Verified in both file mode and
  against the live PostgreSQL instance.

### `dashboard/index.html` and `dashboard/vite.config.js`

Source: `dashboard/index.html`, `dashboard/vite.config.js`

- Responsibility: Provide the Vue document and configure API/static builds,
  output directories, chunking, and the development proxy.
- Inputs: Build mode and client source modules.
- Outputs: `dist` for Flask or `dist-static` for Pages.
- Dependencies: Vite and Vue plugin.
- Verification: `npm test`, `npm run build`, and `npm run build:static` in
  `dashboard/`.

### `script/export_dashboard_snapshot.py`

Source: `script/export_dashboard_snapshot.py`

- Responsibility: Export the Flask snapshot repositories in forced file mode
  to the generated static-client data path using an atomic replacement.
- Inputs: Committed module artifacts only.
- Outputs: Minified UTF-8 `dashboard/public/data/snapshot.json`.
- Dependencies: `backend.repository.snapshot` and the backend dependency extra.
- Verification: `uv run --extra backend python -X utf8 -B -m script.export_dashboard_snapshot`;
  assert the result reports `mode: local files` and fourteen keys.

### `script/build_pages_site.mjs`

Source: `script/build_pages_site.mjs`

- Responsibility: Validate both production builds, copy them into one Pages
  artifact, and add `.nojekyll`.
- Inputs: `dashboard/dist-static` and `docs/.vitepress/dist`.
- Outputs: Ignored `site/` with dashboard root and `/docs/` documentation.
- Dependencies: Node's standard library.
- Verification: Run after both builds and confirm it reports the assembled
  file count and size.
