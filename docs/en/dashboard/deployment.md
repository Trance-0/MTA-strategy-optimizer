---
title: Running Locally and Publishing
compact: "The run.sh/run.bat launcher contract: Vite's `^20.19.0 || >=22.12.0` Node.js range, sample.env copy, install/build skip-if-present rules, exit codes; and the GitHub Pages static build via export_dashboard_snapshot.mjs and build_pages_site.mjs. Read before changing either launcher or the Pages workflow."
lang: en-US
source_files: dashboard/index.html, dashboard/vite.config.js, dashboard/run.sh, dashboard/run.bat, script/build_pages_site.mjs, script/export_dashboard_snapshot.mjs
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
