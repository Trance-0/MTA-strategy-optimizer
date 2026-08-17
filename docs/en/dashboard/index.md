---
title: Dashboard
description: The Vue dashboard, its six views, its dual data source, and the published static build
compact: "Presentation layer specification: `./dashboard/run.sh` starts one Node process serving the JSON API and the Vue client, the six views (Command Center, Budget Manager, Campaigns, Campaign Optimizer, Optimization Log, Knowledge Base), the navigation rail and its settings dialog, the DATABASE=true/false dual source contract and its row-order rule, the static build published to GitHub Pages, and the rule that the dashboard never recomputes a pipeline number. Read before adding a view or a chart."
lang: en-US
source_files: dashboard/server/config.js, dashboard/server/csv.js, dashboard/server/data_source.js, dashboard/server/index.js, dashboard/server/settings.js, dashboard/src/main.js, dashboard/src/App.vue, dashboard/src/pages.js, dashboard/src/theme.js, dashboard/src/style.css, dashboard/src/api/client.js, dashboard/src/lib/common.js, dashboard/src/lib/useDashboard.js, dashboard/src/components/SidebarNav.vue, dashboard/src/components/TopBar.vue, dashboard/src/components/SettingsDialog.vue, dashboard/src/components/PlotlyChart.vue, dashboard/src/components/DataTable.vue, dashboard/src/components/TableView.vue, dashboard/src/components/MetricRow.vue, dashboard/src/components/KeyValuePanel.vue, dashboard/src/components/ReliabilityBanner.vue, dashboard/src/views/CommandCenter.vue, dashboard/src/views/BudgetManager.vue, dashboard/src/views/Campaigns.vue, dashboard/src/views/CampaignOptimizer.vue, dashboard/src/views/OptimizationLog.vue, dashboard/src/views/KnowledgeBase.vue, dashboard/index.html, dashboard/vite.config.js, dashboard/tests/dashboard.test.js, dashboard/run.sh, dashboard/run.bat, dashboard/config.py, dashboard/models.py, script/import_to_database.py, script/verify_dashboard_parity.mjs, script/export_dashboard_snapshot.mjs, script/build_pages_site.mjs
---

# Dashboard

The dashboard is the project's presentation layer. It reads the artifacts the pipeline already produces and renders them for a reader who will not run Python: attribution evidence per touchpoint, the reliability verdict that governs it, the recommended budget allocation, and the historical record all three were derived from.

It is deployable locally with one command and is the surface used for demonstrations.

```bash
./dashboard/run.sh          # macOS, Linux, Git Bash
dashboard\run.bat           # Windows
```

## The Rule That Shapes Everything Else <span class="status-label status-verified" aria-label="Verified"></span>

**The dashboard never computes an attribution share or a budget figure.** It reads them.

This is the constraint the whole module is built around. A presentation layer that recomputed a pipeline number would become a second, divergent implementation of it: the chart and the Comma-Separated Values (CSV) file would disagree, and nothing would say which one was wrong. Every number on screen therefore traces to an artifact under `modules/*/outputs/` or `modules/*/data/simulated/`, or to the database mirror of those files.

The one place the dashboard derives anything is the Campaign Optimizer's implied budget shift, which restates the recommended attribution as a spend split at constant total budget. It is labelled as a restatement wherever it appears, it does not predict the outcome of acting on it, it never overrides the pipeline's own allocation, and it is withheld entirely when the Outcome's verdict is UNRELIABLE.

## One Process, Two Halves <span class="status-label status-verified" aria-label="Verified"></span>

The dashboard is a Vue 3 client over a JavaScript Object Notation (JSON) Application Programming Interface (API) served by Express. One Node process serves both, so a local run is one command and one port.

| Half | Lives in | Knows about |
| --- | --- | --- |
| The API | `dashboard/server/` | Files, Structured Query Language (SQL), and `.env`. Nothing about rendering. |
| The client | `dashboard/src/` | The snapshot shape. Nothing about where it came from. |

The boundary is exact: `src/api/client.js` is the only module in the client that issues a request, and `server/data_source.js` is the only module on the server that opens a file or a connection. A view holds no file path, no SQL statement, and no `fetch` call.

### Why the whole snapshot arrives at once

`GET /api/dashboard` returns every loader's result in one response — roughly 720 KB of JSON, smaller than the artifacts it was read from. Sending it whole rather than paginating is what lets the six views share one read: two views on the same screen cannot show two different states of the same source, and switching views costs nothing because the data is already there.

`src/lib/useDashboard.js` holds that single copy. The six views mount together on first paint, so concurrent callers share one in-flight request rather than issuing six.

### Dependency boundary

The attribution, standard, and strategy modules use the Python standard library alone, and that property is worth keeping: it is what lets a reader reproduce every published number with no installation step. Nothing under `modules/` imports anything from `dashboard/`, and the dependency never points the other way — `dashboard/` reads the modules' output files, not their Python code.

The dashboard's own dependencies are `express`, `pg`, `vue`, and `plotly.js-dist-min`, installed by `npm install` in `dashboard/`. The remaining Python — `dashboard/config.py` and `dashboard/models.py` — exists for `script/import_to_database.py` alone and is installed with `uv sync --extra dashboard`.

## Two Data Sources, One Contract <span class="status-label status-verified" aria-label="Verified"></span>

A single switch in `.env` decides where the numbers come from. `sample.env` is the tracked template; `.env` itself is ignored and must never be committed.

| `DATABASE` | Reads from | Used for |
| --- | --- | --- |
| `false` | The committed CSV and JSON artifacts | Cloud demonstrations, and any checkout that has not run an import |
| `true` | The PostgreSQL schema in [Dashboard data model](../datasets/dashboard-data-model.md) | A deployment with a populated database |

`dashboard/server/data_source.js` is the only module that knows which mode is active. Every loader it exposes returns the **same fields, types, values, and row order in both modes**, so no view can tell them apart and no view contains a branch on the data source. `script/verify_dashboard_parity.mjs` asserts that property against a live database and exits non-zero on any difference.

Five real differences must be normalised for that contract to hold, and all five are handled in the loader rather than in a view:

- PostgreSQL folds unquoted identifiers to lowercase, so the advertising platform's camelCase field names survive only in file mode. Both modes are renamed to `snake_case`.
- The pipeline writes the reliability flags as the strings `true` and `false`. Every non-empty string is truthy in JavaScript, so a view filtering on the raw string would keep unreliable rows in one mode and drop them in the other. They are parsed to real booleans.
- Every numeric column arrives as text from a CSV and as a number from the database, and `pg` returns `numeric` as a string to protect precision. All are coerced to numbers, with a blank becoming `null` rather than `NaN` — `NaN` is not representable in JSON and would reach the browser as `null` anyway, so producing it would mean the two modes disagreed before serialisation and agreed after.
- A date read from a file is a string and from the database a `Date`. Both are pinned to `YYYY-MM-DD`.
- An absent text value is an empty string in a CSV and NULL in PostgreSQL. Both become `null`.

### Row order is part of the contract

The views render tables in the order the loader returns them, so two modes that agree on contents but disagree on order put the same four Campaigns on screen in two different sequences. A file loader returns the artifact's own order; a SQL query returns whatever it was told to.

Every query therefore orders by the **surrogate key**, not by the business key. `script/import_to_database.py` inserts rows in the artifact's order, so `id` reproduces it; `order by campaign_id` sorts alphabetically and does not. This is the specific defect that ordering rule exists to prevent: the four demonstration Campaigns are written `C_DEMO_SP, C_DEMO_SB, C_DEMO_SD, C_DEMO_DSP` and sort alphabetically to `C_DEMO_DSP, C_DEMO_SB, C_DEMO_SD, C_DEMO_SP`, so a reader comparing the two deployments would see the same numbers against different rows.

### What the database legitimately does not carry

Three groups of fields exist in the JSON artifacts and in no table: the capacity rules, the per-Campaign derivation breakdown, and the source file paths and counts. They are pipeline configuration and intermediate arithmetic rather than observations, and modelling them would mean the database stored figures the dashboard is forbidden to recompute. No view reads any of them. `verify_dashboard_parity.mjs` lists them explicitly, so the exemption is stated rather than assumed and a **new** absence is still a failure.

When `DATABASE=true` but the database is unreachable or empty, the API answers `503` with a named reason and the client renders it as a page stating both remedies, rather than surfacing a connection error from inside whichever chart happened to read it first.

## The Six Views <span class="status-label status-verified" aria-label="Verified"></span>

The navigation mirrors the reference prototype in `external/UI_design/brandlens-vue`, by Rouxin Jin. Each view is one Single-File Component under `dashboard/src/views/` that takes no props and reads the shared snapshot.

| View | Question it answers |
| --- | --- |
| Command Center | What was spent and returned, which touchpoints earned credit, and is that credit trustworthy? |
| Budget Manager | What daily budget does each Campaign get, and what derived it? |
| Campaigns | What actually happened, filtered and queried against the raw record? |
| Campaign Optimizer | Where do the two models disagree, and what spend shift does the recommendation imply? |
| Optimization Log | Which run produced these numbers, from which inputs, and can it be reproduced? |
| Knowledge Base | What do the terms mean and which rules do the numbers obey? |

Two of the prototype's views had no backing data in this project. Rather than ship placeholder content, each was pointed at the real record that answers the same question: Optimization Log shows run provenance and pipeline stage state, including the fact that the optimisation stage has **not** run; Knowledge Base is populated from the data in use, so it cannot drift from the charts beside it.

### Reliability is never a footnote

Every view that displays an attributed share displays its reliability verdict beside it, because an UNRELIABLE share must not be read as a fact. The verdict is the AND of the three flags, one false flag is enough to fail a row, and an UNRELIABLE Outcome carries an interval rather than a point value. The Campaign Optimizer refuses to show a budget shift for such an Outcome at all: an interval cannot carry a spend split.

## Visual Contract <span class="status-label status-recommendation" aria-label="Recommendation"></span>

`dashboard/src/theme.js` holds every colour, chart default, and value format, and `dashboard/src/style.css` reads the same values as custom properties, so a change lands everywhere at once and no view invents its own styling. The brand palette — navy rail, blue accent, light plane — is the prototype's. The series palette is a separate validated set, because the prototype contains no real charts and so could not supply one; it passes the lightness band, chroma floor, colourblind-separation, and normal-vision checks against the dashboard's white chart surface.

Three rules the views depend on:

- **Colour follows the entity, never its rank.** Markov is always the same blue and Shapley always the same orange, so filtering a chart never repaints the rows that survive and a reader who learned one association is never contradicted.
- **Status colour is reserved and never carries meaning alone.** A reliability pill always shows the status word itself.
- **One axis per chart.** Where two measures differ by orders of magnitude, as spend and sales do, both are indexed to their own window average and share one scale. A second y-axis would invent a correlation the data does not contain.

Every chart is paired with the values behind it — a table view, direct labels, or both — so no number is reachable only by hovering.

## Navigation Rail <span class="status-label status-verified" aria-label="Verified"></span>

The sidebar reproduces the prototype's rail: a navy column of stacked icon buttons, grouped under OVERVIEW, PLANNING, and INSIGHTS, with the active item filled.

`src/pages.js` is the single place a view is registered. A page key appears there, in `PAGE_GROUPS`, and in `App.vue`'s component map; `tests/dashboard.test.js` asserts the three agree, so the rail cannot offer a destination the shell cannot render.

The rail writes the selected page into the location hash, so a view is linkable and survives a refresh. It is written with `replaceState` rather than assignment, so switching views does not fill the browser's back stack with intermediate pages.

### The settings module

Everything about the dashboard's own plumbing is pinned to the foot of the rail, ruled off from the view navigation above it, so it never reads as a seventh place to navigate to. It shows the active source, a status dot, and whether logging is on, and opens a modal with two tabs:

| Tab | Contains |
| --- | --- |
| Data source | The `DATABASE` toggle and the PostgreSQL host, port, database, user, password, and Secure Sockets Layer (SSL) mode, with **Test connection** and **Save to `.env`** |
| Logging | The streaming-data log switch, its level, and the captured records |

**Test connection** opens a throwaway connection using what was typed rather than what is saved, so a correction can be validated before it is committed to `.env`. Saving rewrites `.env` in place — comments and unrelated keys are preserved, and a key already present is replaced rather than appended, so a file cannot end up with two values for one key and the winner decided by read order. Saving also drops the loader caches and disposes the connection pool, because both would otherwise hold the old mode until a restart.

**The password field is write-only.** The server never sends a stored password back, and an empty field means "keep the stored one" rather than "clear it", so the value is never rendered into the page. `config.safeSummary()` omits it by construction and is the only rendering of a connection the dashboard performs.

Logging is off by default, because recording every read costs time on each request. Enabled, it captures the actual data-source activity into a fixed-capacity ring buffer rather than a file: a demonstration machine's disk cannot be filled by leaving the dashboard open, and one long statement cannot dominate the buffer because each message is truncated.

### Links out of the app

The rail closes with **Docs** and **Repo**. A reader who arrives at the published dashboard has no other route to the specification or the source, so the app carries them. The documentation link is relative in the published build, where the documentation is a sibling directory, and absolute in a local run, where there is no sibling to point at.

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

Pages serves static files and cannot run the Express API, so the published client is built in **static mode**: `script/export_dashboard_snapshot.mjs` writes the same payload the API would return to `data/snapshot.json` at build time, and `src/api/client.js` fetches that file instead. A view sees no difference. This is the browser-side counterpart of the `DATABASE=true/false` contract — the same client source, a different data path, never a different codebase.

Three consequences follow, and each is handled rather than hidden:

- **The database source is unavailable.** A static host has no server to open a connection from. The export command pins file mode and **refuses to write a snapshot read from a database**, so a private deployment's data cannot be baked into a public artifact. The settings dialog replaces the credential form with the local-run instructions, so a visitor is never invited to type a real password into a page that cannot use it.
- **The base path is relative.** Pages serves a project site from a subdirectory, so `vite build --mode static` sets `base` to `./` and the snapshot is fetched at a relative path; an absolute path would resolve against the domain root.
- **Only the data the loaders read is published.** One snapshot of roughly 720 KB, exported from the eleven committed artifacts. The 2.8 MB synthetic-events extract is excluded because no view reads it.

The workflow is `.github/workflows/deploy-pages.yml`. It builds the client with `npm run build:static`, builds the documentation with its base path set to the Pages base plus `docs/` — because Pages performs no rewrites and every internal link is resolved at build time — then assembles both into `site/` and uploads that as the Pages artifact.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `server/config.js`

Source: `dashboard/server/config.js`

- Responsibility: Read `.env` at the repository root and expose the one switch that decides the data source, the PostgreSQL settings, and the artifact paths every other server module resolves against.
- Inputs: `.env` at the repository root, loaded without overriding real environment variables so a shell export or a container secret wins. `DATABASE` is true for any of `1`, `true`, `yes`, `on`, case-insensitively; anything else, including absence, is false. `DASHBOARD_HOSTED` uses the same vocabulary and is set only by the published build.
- Outputs: `useDatabase()`, `isHosted()`, `databaseSettings()`, `safeSummary()`, `serverPort()`; the path constants `REPO_ROOT`, `DASHBOARD_ROOT`, `SIMULATED_DIR`, `ATTRIBUTION_OUTPUT_DIR`, `STRATEGY_INPUT_DIR`, `STRATEGY_OUTPUT_DIR`; and `DESCRIPTION_ROW_MARKERS`, the exact first-cell values that identify the Chinese field-description row every reader must drop.
- Behavior contract: `databaseSettings()` throws naming **every** missing variable and pointing at `sample.env`, rather than failing later at connection time with a misleading network error. `safeSummary()` returns a display string that never contains the password, omitted by construction rather than masked, so no future edit can accidentally widen it. `useDatabase()` returns false whenever `isHosted()` is true, regardless of the switch — a static host has no socket to open, so the hosted flag decides before the switch is read. `.env` is read once and cached, so the mode is fixed for the life of the process; this is why `verify_dashboard_parity.mjs` probes the two modes in separate processes.
- Dependencies: `dotenv`. Installed with `npm install` in `dashboard/`.
- Verification: `node script/verify_dashboard_parity.mjs`, which exercises both modes.

### `server/csv.js`

Source: `dashboard/server/csv.js`

- Responsibility: Read the project's committed CSV artifacts into objects keyed by header name.
- Inputs: A path to one of the artifacts the pipeline writes.
- Outputs: `parseCsv(text)` returning rows of raw string cells, and `readCsv(path)` returning objects.
- Behavior contract: The parser covers exactly what those files contain — quoted fields, doubled quotes inside them, and both line endings — rather than pulling in a dependency. It **does no type inference**: every value comes back as a string and `data_source.js` coerces the columns it knows about, because inference is what makes a file read and a database read disagree. A Unicode Transformation Format 8-bit (UTF-8) byte-order mark is stripped, or it would become part of the first header name and every lookup of that column would miss. The Chinese field-description row is dropped by matching its exact marker from `config.DESCRIPTION_ROW_MARKERS`, not by heuristic: an earlier heuristic that tested for the absence of digits silently discarded a real data row from the files that have no such row. The empty row a trailing newline produces is discarded, or it would become a row of nulls in every chart.
- Dependencies: None beyond Node's `fs`.
- Verification: `dashboard/tests/dashboard.test.js`, which covers quoting, doubled quotes, Carriage Return Line Feed (CRLF), the byte-order mark, the description row in both the files that carry it and the files that do not, and the trailing newline.

### `server/data_source.js`

Source: `dashboard/server/data_source.js`

- Responsibility: Be the only module that knows whether the dashboard is reading files or a database, and return results a view cannot distinguish between the two.
- Inputs: `server/config.js` for the mode and the paths; the committed artifacts under `modules/*/`; or the PostgreSQL tables in `dashboard/models.py`.
- Outputs: Seven tabular loaders — `loadAdsDaily`, `loadAttributionResults`, `loadComparisonTouchpoints`, `loadComparisonSummary`, `loadRecommendedAttribution`, `loadEntityBridge`, `loadPathReport` — and three that return the JSON artifacts' own nested shape: `loadBudgetRecommendation`, `loadStrategyRequest`, `loadCandidatePool`. Also `loadSnapshot()`, which is the whole API payload; `formatDate()`; `TOUCHPOINT_SEGMENTS`; and `activeMode()`, `sourceLabel()`, `databaseAvailable()`, `clearCaches()`, `disposePool()`.
- Behavior contract: **Every loader returns identical fields, types, values, and row order in both modes.** A view must never branch on the data source, and none does. The five normalisations and the surrogate-key ordering rule are specified under [Two Data Sources, One Contract](#two-data-sources-one-contract). `formatDate()` is the single conversion for every date the API returns: a `Date` is formatted from its **local** components, because `toISOString()` converts to UTC first and so reports the previous day for any host east of Greenwich, and because `String(date).slice(0, 10)` yields `Tue Mar 31` — a weekday and a month name — rather than a date. `project()` pins an absent value to `null` in both modes and fixes the field order, so serialised rows can be compared directly. `databaseAvailable()` returns a `(usable, message)` pair instead of throwing, so the API can report a connection failure as a page rather than as a stack trace inside a chart. `pg` is imported lazily, so a file-mode run never loads the driver. Results are cached for ten minutes, which the Reload control clears.
- Dependencies: `pg`, plus `server/config.js` and `server/csv.js`.
- Verification: `node script/verify_dashboard_parity.mjs` against a populated database. The file-mode invariants — booleans, date format, null-not-empty-string, finite numbers, and JSON round-tripping — are covered by `dashboard/tests/dashboard.test.js`, which needs no database.

### `server/index.js`

Source: `dashboard/server/index.js`

- Responsibility: Serve the JSON API and the built client from one process.
- Inputs: HTTP requests. The client build in `dashboard/dist`, when one exists.
- Outputs: `createApp()`, and a listening server when run directly. `GET /api/dashboard`, `POST /api/reload`, `GET /api/settings`, `POST /api/settings`.
- Behavior contract: `GET /api/dashboard` checks `databaseAvailable()` before loading whenever `DATABASE=true` and answers `503` with `error: "database_unavailable"` and a named reason, so the client can state both remedies — correct the credentials, or run the import — rather than letting the failure surface inside whichever chart read it first. `POST /api/settings` is **refused with `403` whenever `isHosted()`**: a published build has no writable `.env` and no socket, so a change could not take effect and pretending otherwise would invite a real password into a page that cannot use it. An empty password field means "keep the stored one", because the dialog never receives the stored value to echo back. The static file branch is absent when `dashboard/dist` does not exist, which is what lets `npm run dev` serve the sources from Vite and proxy the API here; the server prints the command that builds it rather than serving nothing silently. Client routes resolve to one document, because the client routes on the hash.
- Dependencies: `express`, plus `server/config.js`, `server/data_source.js`, and `server/settings.js`.
- Verification: Started with `./dashboard/run.sh` and driven in a real browser; the six views were rendered against both a live PostgreSQL instance and the committed files with no console error and no failed request.

### `server/settings.js`

Source: `dashboard/server/settings.js`

- Responsibility: Back the settings module in the foot of the rail — edit the credentials this dashboard connects with, and capture the data access log while it streams.
- Inputs: `.env` at the repository root, the live environment as a fallback, and the reader's entries in the modal.
- Outputs: `readEnv()`, `writeEnv()`, `status()`, `testConnection()`, `applyLogging()`, `loggingEnabled()`, `logState()`, `log()`, `clearLog()`, `settingsState()`, and `RingBuffer`.
- Behavior contract: **No credential is written to a tracked file, to the API response, or to the log.** `.env` is git-ignored, `sample.env` is the tracked template and holds no real value, and the password is rendered only through `config.safeSummary()`, which omits it by construction. `writeEnv()` rewrites the file rather than appending to it, preserving comments and unrelated keys and replacing a key in place, so one key cannot end up with two values and the winner decided by read order; it does not accumulate a trailing blank line on repeated saves; and it then clears the loader caches and disposes the pool, because both would otherwise survive the edit. `testConnection()` connects with the values just typed rather than the values saved, and closes the client whether or not the probe succeeded, so a failed test cannot leave a socket open on a shared instance. The log is a fixed-capacity ring buffer, not a file, so an open dashboard cannot fill a disk; each message is truncated so one record cannot dominate it; and a record below the active level is dropped rather than stored and filtered on display. Logging is off by default because it costs time on every request.
- Dependencies: `pg` for the connection test, plus `server/config.js` and `server/data_source.js`.
- Verification: `dashboard/tests/dashboard.test.js`, which asserts `writeEnv()` preserves comments and unrelated keys, appends a missing key exactly once, does not grow a blank line on repeated saves, and writes every key the dialog sends; and that the buffer stays bounded, starts disabled, honours its level, and truncates. The tests redirect the path to a temporary file, so the real `.env` is never touched.

### `src/api/client.js` and `src/lib/useDashboard.js`

Source: `dashboard/src/api/client.js`, `dashboard/src/lib/useDashboard.js`

- Responsibility: Be the client's single route to the data, and hold the single shared copy of it.
- Inputs: `/api/dashboard` in a local run, or `data/snapshot.json` in the published build.
- Outputs: `IS_STATIC`, `fetchDashboard()`, `reloadData()`, `fetchSettings()`, `postSettings()`; and `useDashboard()`, returning `data`, `loading`, `error`, `loaded`, `ensureLoaded()`, and `reload()`.
- Behavior contract: `IS_STATIC` is baked in at build time by `vite build --mode static`, and it is the only thing that decides which of the two sources is read; **no view branches on it.** The static path is relative because Pages serves a project site from a subdirectory. A response that is not JSON — a proxy page or a 404 — is reported by status rather than as a parse error naming character 0. In the static build `fetchSettings()` returns the hosted state directly and `postSettings()` refuses, rather than issuing requests that would 404. `useDashboard()` holds one module-level snapshot, so the six views that mount together share one in-flight request rather than issuing six, and two views can never show two different reads. An empty snapshot is exposed until the first load resolves, so a view renders its own empty state rather than crashing on a missing field.
- Dependencies: Vue's reactivity.
- Verification: Driven in a real browser against both the API and the static snapshot; both render the six views identically with no console error.

### `src/pages.js`, `src/App.vue`, and `src/main.js`

Source: `dashboard/src/main.js`, `dashboard/src/App.vue`, `dashboard/src/pages.js`

- Responsibility: Register the six views, draw the shell around them, and dispatch to the selected one.
- Inputs: The location hash. Nothing else; each view reads the shared snapshot.
- Outputs: The rendered application. `PAGES` carries each view's title, breadcrumb, and inline icon; `PAGE_GROUPS` is the rail's grouping; `PAGE_KEYS` its flattening; `REPO_URL` and `DOCS_URL` are where the app points a reader who wants the source or the specification.
- Behavior contract: `src/pages.js` is the single place a view is registered, and `tests/dashboard.test.js` asserts that `PAGES`, `PAGE_GROUPS`, and `App.vue`'s component map agree, so the rail cannot offer a destination the shell cannot render. The two foot controls are drawn from the same icon set but are **not** navigable pages, and the test asserts that too. The page is written into the hash with `replaceState`, so a view is linkable and survives a refresh without filling the back stack. `App.vue` renders the loading, error, and loaded states itself rather than leaving each view to do it, so a failed load is one page naming both remedies rather than six broken charts. The report window and marketplace in the header are read from the data rather than fixed in the markup.
- Dependencies: Vue 3.
- Verification: `dashboard/tests/dashboard.test.js` for the registration contract; the rendered result was verified in a real browser for all six views.

### `src/theme.js` and `src/style.css`

Source: `dashboard/src/theme.js`, `dashboard/src/style.css`

- Responsibility: Hold every colour, chart default, and value format the dashboard uses, so a change lands everywhere at once and no view invents its own styling.
- Inputs: None. Constants and pure display helpers.
- Outputs: The brand constants, the reserved status colours and their tone classes, the `SERIES`, `SEQUENTIAL`, and `DIVERGING` palettes, the fixed `MODEL_COLORS` and `OUTCOME_COLORS` maps, `seriesColors()`, `layout()`, `PLOT_CONFIG`, and the `money()`, `compactMoney()`, `count()`, `percent()`, and `ratio()` formatters. `style.css` exposes the same brand values as custom properties for the markup.
- Behavior contract: `SERIES` is a fixed order assigned by slot and **never cycled**; a ninth series folds into "Other" rather than receiving a generated hue, which under colourblind simulation would be indistinguishable from an existing slot. `MODEL_COLORS` and `OUTCOME_COLORS` bind a colour to an entity rather than to a rank, so filtering a chart never repaints the rows that survive. The status colours are reserved for reliability state, are never reused as a series colour, and are always rendered with the status word beside them. `layout()` sets a hairline grid, solid axes, and a height that includes the axis band, so a chart card never grows an inner scrollbar; every chart is titled by the heading above it, so no figure carries a title of its own. Each formatter returns `--` for a value that is not finite, so a missing number is visibly missing rather than rendered as `NaN`. The series palette is not the prototype's: that design contains no real charts, so its three brand colours could not supply one.
- Dependencies: None.
- Verification: Rendered visually. The palette is checked with the data-visualisation validator against the white chart surface; three light-mode hues fall below 3:1 contrast, which is why every chart also ships direct labels or a table view.

### The six view components

Source: `dashboard/src/views/CommandCenter.vue`, `dashboard/src/views/BudgetManager.vue`, `dashboard/src/views/Campaigns.vue`, `dashboard/src/views/CampaignOptimizer.vue`, `dashboard/src/views/OptimizationLog.vue`, `dashboard/src/views/KnowledgeBase.vue`

The six share one contract and are specified together.

- Responsibility: Render the six pages of the dashboard, one component per view, in the prototype's navigation order.

  | Component | Content |
  | --- | --- |
  | `CommandCenter.vue` | Five headline tiles, spend against return over time, the per-Outcome reliability verdict, and attributed revenue by ad product for both models. |
  | `BudgetManager.vue` | Handoff state, the recommended daily budget per Campaign against its required minimum, the derivation that produced it, the score composition, and the Ad Group slots. |
  | `Campaigns.vue` | Three tabs over the historical record: filterable daily performance, the Campaign and Ad Group bridge, and searchable conversion paths. |
  | `CampaignOptimizer.vue` | Markov against Shapley per touchpoint, the governed recommendation, and the budget shift the recommendation implies. |
  | `OptimizationLog.vue` | Run identifiers, the report window, the input digests, the pipeline stage trail, and the per-touchpoint reliability flags. |
  | `KnowledgeBase.vue` | The five-segment vocabulary, the reliability contract, the Outcomes, capacity rules, the hierarchy, and the artifacts in use. |

- Inputs: None. Each component takes no props and reads the shared snapshot through `useDashboard()`, so a view never holds a file path, a SQL statement, or a `fetch` call.
- Outputs: The rendered page. Nothing is returned and nothing is written.
- Behavior contract: **No view computes an attribution share or a budget figure.** Every value displayed is read. The single exception is `CampaignOptimizer.vue`'s implied budget shift, which restates the recommended attribution as a spend split at constant total budget; it is labelled as a restatement, does not predict the result of acting on it, never overrides the allocation in `BudgetManager.vue`, and is refused outright when the Outcome's verdict is UNRELIABLE, because an interval cannot carry a spend split. Every view that shows an attributed share shows its reliability verdict beside it. Filters sit in one row above everything they scope, so all panels on a page show the same slice, and every chart is paired with a table view or direct labels, so no value is reachable only by hovering. `OptimizationLog.vue` and `KnowledgeBase.vue` back the two prototype views that had no data of their own: the first reports the real run record and states plainly that the optimisation stage has not run, and the second is populated from the data in use, so it cannot drift from the charts beside it.
- Dependencies: Vue 3 and Plotly, through `src/lib/useDashboard.js`, `src/lib/common.js`, `src/theme.js`, and the shared components.
- Verification: Rendered in a real browser in all three deployments — the API against PostgreSQL, the API against the committed files, and the static build — with no console error, no failed request, and no error card in any of the six.

### The shared components

Source: `dashboard/src/components/SidebarNav.vue`, `dashboard/src/components/TopBar.vue`, `dashboard/src/components/SettingsDialog.vue`, `dashboard/src/components/PlotlyChart.vue`, `dashboard/src/components/DataTable.vue`, `dashboard/src/components/TableView.vue`, `dashboard/src/components/MetricRow.vue`, `dashboard/src/components/KeyValuePanel.vue`, `dashboard/src/components/ReliabilityBanner.vue`

- Responsibility: Hold the chrome and the repeated display shapes, so two views cannot render the same thing differently.
- Inputs: Props from the view that mounts them.
- Outputs: The rendered fragment, plus events for the rail's navigation, reload, and settings actions.
- Behavior contract: `SidebarNav.vue` draws the rail from `src/pages.js` and pins the settings module to the foot, ruled off from the view navigation above it, so it never reads as a seventh destination. `SettingsDialog.vue` never renders a stored password and never sends one back; in the published build it replaces both forms with the local-run instructions rather than offering controls that could not take effect. `PlotlyChart.vue` is the only component that touches Plotly, so the chart defaults in `src/theme.js` cannot be bypassed, and it disposes the plot on unmount so switching views does not leak a chart instance. `TableView.vue` exists so that every chart can be paired with the values behind it, which is what keeps a tooltip an enhancement rather than the only way to read a number. `ReliabilityBanner.vue` always renders the status word beside its colour.
- Dependencies: Vue 3 and `plotly.js-dist-min`.
- Verification: Exercised in a real browser through the six views that mount them.

### `src/lib/common.js`

Source: `dashboard/src/lib/common.js`

- Responsibility: Hold the label vocabulary and the small aggregations more than one view needs, so two views cannot name the same thing differently.
- Inputs: Rows from the snapshot, plus the reader's selections.
- Outputs: The `OUTCOME_LABELS`, `OUTCOME_SHARE_COLUMNS`, and `OUTCOME_VALUE_COLUMNS` maps; `currencySymbol()`, `pretty()`, `shortTouchpoint()`, `shortDate()`, `statusTone()`; and the `sum()`, `groupSum()`, `distinct()`, and `sortBy()` helpers.
- Behavior contract: Only presentation lives here; **nothing in this module computes an attribution or budget number** — the values are read from the snapshot and these helpers group, sort, and format them. The three `OUTCOME_*` maps are the single binding between an Outcome key as the pipeline writes it, its display label, and the fields that carry it, so a renamed field is corrected in one place. `shortTouchpoint()` drops the `UNSPECIFIED` segments, which carry no information and would otherwise make every axis label the same length and unreadable. `groupSum()` returns an array in first-seen order rather than a Map, so a chart's category order is stable across reloads. `sortBy()` sorts a copy and pushes non-finite values last, so a missing number never wins a comparison.
- Dependencies: None.
- Verification: Exercised through the views that call it.

### `index.html` and `vite.config.js`

Source: `dashboard/index.html`, `dashboard/vite.config.js`

- Responsibility: Mount the client, and build it for the two deployments.
- Inputs: `src/main.js`. The build mode.
- Outputs: `dashboard/dist` for a local run, `dashboard/dist-static` for the published build.
- Behavior contract: One source tree serves both targets; the only difference is `base` and the `VITE_STATIC_BUILD` flag `src/api/client.js` reads. `base` is relative in the static build because Pages serves a project site from a subdirectory and an absolute asset path would resolve against the domain root. Plotly and Vue are split into their own chunks, so a change to a view leaves the visitor's cached copy of the 4.6 MB chart library intact. `manualChunks` is written as a **function**: Vite 8 bundles with Rolldown, which fails the build on the object form rather than normalising it. The dev server proxies `/api` to the Express server, so client work has hot reload against the real API.
- Dependencies: `vite`, `@vitejs/plugin-vue`.
- Verification: `npm run build` and `npm run build:static` in `dashboard/`, then serving each and driving it in a real browser.

### `tests/dashboard.test.js`

Source: `dashboard/tests/dashboard.test.js`

- Responsibility: Verify the contracts a clean checkout can check without a database.
- Inputs: The committed artifacts, and temporary files for the `.env` tests.
- Outputs: Pass or fail per test. Run with `npm test` in `dashboard/`.
- Behavior contract: The suite pins file mode **before** anything imports `server/config.js`, which caches the mode on first read, so a test run can never touch the operator's real database. It covers the CSV parser's quoting, line endings, byte-order mark, description row, and trailing newline; `writeEnv()`'s in-place replacement, single append, and stable output; the log buffer's bound, default-off state, level filtering, and truncation; the navigation registration contract; and the snapshot invariants — real booleans rather than the string `"false"`, dates as `YYYY-MM-DD`, absent text as `null` rather than `""`, finite numbers rather than strings, the five touchpoint segments, and that the whole snapshot survives JSON serialisation unchanged. `formatDate()` is tested directly against a `Date` object, because file mode never produces one and the database's shape would otherwise be unverifiable without a connection.
- Dependencies: Node's built-in test runner. No database.
- Verification: `npm test` in `dashboard/`. Twenty-seven tests pass against the committed artifacts.

### `verify_dashboard_parity.mjs`

Source: `script/verify_dashboard_parity.mjs`

- Responsibility: Assert that every loader returns the same fields, values, and row order whether `DATABASE` is true or false.
- Inputs: The committed artifacts, and a populated PostgreSQL instance configured in `.env`.
- Outputs: One line per loader, and a non-zero exit status naming every field that differs.
- Behavior contract: The two modes are probed in **separate child processes**, because `server/config.js` caches the mode after the first read and one process therefore cannot hold both. The child writes only the snapshot to standard output, so a log line cannot corrupt the payload. Differences are reported in full rather than at the first one, because a single normalisation bug usually shows up in many fields at once and the pattern across them identifies the cause. Row order is compared positionally, not as a set, because the views render in the order the loader returns. `ALLOWED_DB_ABSENCES` lists the fields the relational schema legitimately does not carry, so the exemption is explicit and a new absence is still a failure.
- Dependencies: Everything `server/data_source.js` needs.
- Verification: `node script/verify_dashboard_parity.mjs`. It is a command rather than a unit test because it requires a populated database, which a clean checkout does not have. It reports all ten loaders identical against the live instance.

### `export_dashboard_snapshot.mjs`

Source: `script/export_dashboard_snapshot.mjs`

- Responsibility: Write the dashboard snapshot to a JSON file for the published static build.
- Inputs: The committed CSV and JSON artifacts.
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
- Outputs: A running server, with its URL printed before it starts. On failure, a named cause, a remedy, and a bug-report block.
- Behavior contract: Both resolve the repository root from the script's own location rather than the working directory, so the command works from anywhere. Four steps run in order — toolchain, configuration, dependencies, client build — and each failure is reported by name rather than as the raw error of whatever ran last.

  Node is checked against **Vite's own engine range**, `^20.19.0 || >=22.12.0`, comparing the minor and patch numbers rather than the major alone. The precision matters: Vite's bundler binding is an optional dependency carrying that same range, so an unsupported version installs cleanly — npm skips the binding silently — and fails minutes later at build time with a missing-module error naming neither Node nor the version.

  `sample.env` is copied to `.env` when none exists, which is what makes a fresh clone start in file mode instead of failing on a missing variable; an existing `.env` is never overwritten, because it holds the operator's real credentials. `npm install` runs only when `node_modules/express` is absent — the package standing in for the whole tree, so an interrupted install is repaired rather than skipped — and `npm run build` only when `dist/index.html` is absent, or always with `--rebuild`. Both npm commands run from `dashboard/` rather than through `npm --prefix`, which sets where `node_modules` is written but not where the manifest is read from.

  An unrecognised argument or an out-of-range port exits 2, `--help` exits 0, and a failed step exits 1. The port is not probed here: the server binds it, so it is the process that can report a conflict precisely rather than racing a check made in advance.
- Dependencies: Node and npm. Nothing else is assumed present.
- Verification: Both were run against a simulated clean clone — `node_modules` and `dist` removed — on Node 26.5, which installed, built, and served the client and the API, and on Node 22.11, which is refused at step one with the range named. Every argument path was checked for its exit code, and the failure report was confirmed to carry the environment block and the tail of `dashboard/.run.log` from an install forced to fail. `dashboard\run.bat 8602` from a directory outside the repository served both the client and the API against the live PostgreSQL mirror with `DATABASE=true`.

### `config.py` and `models.py`

Source: `dashboard/config.py`, `dashboard/models.py`

- Responsibility: Define the PostgreSQL schema the dashboard reads and the `.env` contract the importer resolves against. The dashboard itself holds no Python; these two exist for `script/import_to_database.py`.
- Inputs: `.env` at the repository root, for `config.py`. Nothing at runtime for `models.py`.
- Outputs: `use_database()`, `database_settings()`, `DatabaseSettings.safe_summary()`, and the path constants; and `Base` plus eighteen mapped classes in four layers — entity, history, model output, and strategy. Field-level meaning is specified in [Dashboard data model](../datasets/dashboard-data-model.md).
- Behavior contract: `DatabaseSettings.url()` percent-encodes the user and password. This is required, not defensive: a password containing `@` or `/` otherwise corrupts the Uniform Resource Locator (URL) and fails as a misleading host-resolution error. `safe_summary()` never contains the password. These modules sit at the edge of the project: the attribution, standard, and strategy modules must never import them, because they read and write files and depend on the standard library alone. Every run-scoped table carries a foreign key to its run, so two report windows coexist rather than overwrite, and the `UniqueConstraint` on each output table is scoped by `run_pk`, which makes a re-import of the same window a conflict rather than a silent duplicate. **Every table carries a surrogate `id` primary key, and the row order the dashboard reads depends on it**: the importer inserts in the artifact's order, so `order by id` reproduces it.
- Dependencies: `python-dotenv` and SQLAlchemy 2.0. Installed with `uv sync --extra dashboard`.
- Verification: `uv run --extra dashboard python script/import_to_database.py --dry-run` reports the row count each class will receive without opening a connection.

### `import_to_database.py`

Source: `script/import_to_database.py`

- Responsibility: Read every committed artifact and write it into the PostgreSQL schema defined in `dashboard/models.py`, inside one transaction.
- Inputs: `modules/mta_attribution/data/simulated/*.csv`, `modules/mta_attribution/outputs/attribution/*.csv`, and the strategy module's JSON inputs and outputs. Connection settings come from `.env` through `dashboard/config.py`.
- Outputs: The eighteen populated tables, and a per-table row count printed on completion.
- Behavior contract: The command **refuses to overwrite a populated database** unless `--replace` is given, so an accidental second run cannot destroy existing rows; `--replace` drops and rebuilds every table, which is what a schema change requires. `--dry-run` reports the row count each table will receive without opening a connection. `--full-events` imports every synthetic event rather than the default bounded sample. `read_rows()` drops the Chinese field-description row by matching its exact first-cell marker; an earlier heuristic that tested for the absence of digits silently discarded a real touchpoint row from the files that have no description row. `Importer.touchpoint()` creates each `Touchpoint` on first sight and reuses it thereafter, which is what makes the five-segment key the join between spend and attribution. **Rows are inserted in each artifact's own order**, which is what the dashboard's `order by id` relies on to reproduce that order. The whole import runs in one session and commits once, so a failure part-way leaves the database untouched.
- Dependencies: SQLAlchemy, `psycopg`, and `python-dotenv`, plus `dashboard/config.py` and `dashboard/models.py`. Installed with `uv sync --extra dashboard`.
- Verification: `uv run --extra dashboard python script/import_to_database.py --dry-run`, then `node script/verify_dashboard_parity.mjs` against the loaded instance.
