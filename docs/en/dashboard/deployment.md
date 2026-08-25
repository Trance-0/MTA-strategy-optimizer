---
title: Running Locally and Publishing
compact: "Dashboard delivery contract: Bash and Windows launchers build Vue then start Flask, Vite hot reload proxies `/api`, static publishing exports Flask's file-mode snapshot through Python, GitHub Pages assembles dashboard and English documentation, and production uses the Yunxiao AppStack image and orchestration."
lang: en-US
source_files: dashboard/index.html, dashboard/vite.config.js, dashboard/run.sh, dashboard/run.bat, script/build_pages_site.mjs, script/export_dashboard_snapshot.py
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
