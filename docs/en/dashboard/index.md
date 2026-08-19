---
title: Dashboard
description: The Vue dashboard's architecture, its dual data source contract, and where each topic is documented
compact: "Vue/Express dashboard: normalized file/database snapshots, loopback server binding, protected deployment configuration, canonical master/config records, immutable generated history, simulator research, and presentation-only similarity. `server/data_source.js` owns source branching; views never issue SQL or recompute attribution."
lang: en-US
source_files: dashboard/server/config.js, dashboard/server/csv.js, dashboard/server/data_source.js, dashboard/server/index.js, dashboard/src/api/client.js, dashboard/src/lib/useDashboard.js, dashboard/tests/dashboard.test.js, script/verify_dashboard_parity.mjs
---

# Dashboard

The dashboard is the project's presentation layer. It reads the artifacts the pipeline already produces and renders them for a reader who will not run Python: attribution evidence per touchpoint, the reliability verdict that governs it, the recommended budget allocation, and the historical record all three were derived from.

It is deployable locally with one command and is the surface used for demonstrations.

```bash
./dashboard/run.sh          # macOS, Linux, Git Bash
dashboard\run.bat           # Windows
```

See [Running locally and publishing](./deployment.md) for the full launcher contract, the Node version check, and the GitHub Pages build.

## The Rule That Shapes Everything Else <span class="status-label status-verified" aria-label="Verified"></span>

**The dashboard never computes an attribution share or a budget figure.** It reads them.

This is the constraint the whole module is built around. A presentation layer that recomputed a pipeline number would become a second, divergent implementation of it: the chart and the Comma-Separated Values (CSV) file would disagree, and nothing would say which one was wrong. Every number on screen therefore traces to an artifact under `modules/*/outputs/` or `modules/*/data/simulated/`, or to the database mirror of those files.

The one place the dashboard derives anything is the Campaign Optimizer's implied budget shift, which restates the recommended attribution as a spend split at constant total budget. It is labelled as a restatement wherever it appears, it does not predict the outcome of acting on it, it never overrides the pipeline's own allocation, and it is withheld entirely when the Outcome's verdict is UNRELIABLE.

## One Process, Two Halves <span class="status-label status-verified" aria-label="Verified"></span>

The dashboard is a Vue 3 client over a JavaScript Object Notation (JSON) Application Programming Interface (API) served by Express. One Node process serves both, so a local run is one command and one port.

The boundary is exact: `src/api/client.js` is the only module in the client that issues a request, and `server/data_source.js` is the only module on the server that opens a file or a connection. A view holds no file path, no SQL statement, and no `fetch` call.

### The API

Lives in `dashboard/server/`. Knows about files, Structured Query Language (SQL), and `.env`. Nothing about rendering.

### The client

Lives in `dashboard/src/`. Knows about the snapshot shape. Nothing about where it came from.

### Why the whole snapshot arrives at once

`GET /api/dashboard` returns every loader's result in one response — roughly 720 KB of JSON, smaller than the artifacts it was read from. Sending it whole rather than paginating is what lets the six views share one read: two views on the same screen cannot show two different states of the same source, and switching views costs nothing because the data is already there.

`src/lib/useDashboard.js` holds that single copy. The six views mount together on first paint, so concurrent callers share one in-flight request rather than issuing six.

### Dependency boundary

The attribution, standard, and strategy modules use the Python standard library alone, and that property is worth keeping: it is what lets a reader reproduce every published number with no installation step. Nothing under `modules/` imports anything from `dashboard/`, and the dependency never points the other way — `dashboard/` reads the modules' output files, not their Python code.

The dashboard's own dependencies are `express`, `pg`, `vue`, and `plotly.js-dist-min`, installed by `npm install` in `dashboard/`. The remaining Python — `dashboard/config.py` and `dashboard/models.py` — exists for `script/import_to_database.py` alone and is installed with `uv sync --extra dashboard`. See [Populating PostgreSQL](./database-import.md).

## Two Data Sources, One Contract <span class="status-label status-verified" aria-label="Verified"></span>

A single switch in `.env` decides where the numbers come from. `sample.env` is the tracked template; `.env` itself is ignored and must never be committed.

### `DATABASE=false`

Reads from the committed CSV and JSON artifacts. Used for cloud demonstrations, and any checkout that has not run an import.

When `MTA_SIM_DATA_DIR` names a generated run directory, the server reads the
three unchanged MTA-SIM CSV files plus `effective_configuration.json` and
`simulation_research.json` from that directory. Without it, the legacy
committed demonstration artifacts remain the file source.

### `DATABASE=true`

Reads from the PostgreSQL schema in [Dashboard data model](../market-simulation/dashboard-data-model.md). Used for a deployment with a populated database.

`dashboard/server/data_source.js` is the only module that knows which mode is active. Legacy artifact loaders return the **same fields, types, values, and row order in both modes**. The additional `simulationResearch` object has the same normalized shape and types in file and database mode, while its row count reflects the selected generated run: a local 10,000-observation sidecar and a remote 100,000-observation database are not expected to contain identical rows. No view contains a source-mode branch.

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

Continue with [Populating PostgreSQL](./database-import.md) for the importer that writes this schema.

## The Six Views <span class="status-label status-verified" aria-label="Verified"></span>

The navigation mirrors the reference prototype in `external/UI_design/brandlens-vue`, by Rouxin Jin. Each view is one Single-File Component under `dashboard/src/views/` that takes no props and reads the shared snapshot.

### Command Center

What was spent and returned, which touchpoints earned credit, and is that credit trustworthy?

### Budget Manager

What daily budget does each Campaign get, and what derived it?

### Campaigns

What actually happened, filtered and queried against the raw record?

### Campaign Optimizer

Where do the two models disagree, and what spend shift does the recommendation imply?

### Optimization Log

Which run produced these numbers, from which inputs, and can it be reproduced?

### Knowledge Base

What do the terms mean and which rules do the numbers obey?

Continue with [Views and visual contract](./views.md) for the reliability rule every view honors, the colour and chart system, and the per-component specification. The rail that switches between them, and its settings module, are specified on [Navigation rail and settings](./navigation.md).

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `server/config.js`

Source: `dashboard/server/config.js`

- Responsibility: Read `.env` at the repository root and expose the switches that decide the data source, deployment mutability, server listener, PostgreSQL settings, and artifact paths every other server module resolves against.
- Inputs: `.env` at the repository root, loaded without overriding real environment variables so a shell export, `systemd` environment file, or container secret wins. `DATABASE`, `DASHBOARD_HOSTED`, and `DASHBOARD_CONFIG_READ_ONLY` accept `1`, `true`, `yes`, or `on`, case-insensitively. `DASHBOARD_HOST` and `DASHBOARD_PORT` configure the listener.
- Outputs: `useDatabase()`, `isHosted()`, `configReadOnly()`, `databaseSettings()`, `safeSummary()`, `serverHost()`, `serverPort()`, `simulatorDataDirectory()`; the legacy artifact path constants; and `DESCRIPTION_ROW_MARKERS`.
- Behavior contract: `databaseSettings()` throws naming **every** missing variable and pointing at `sample.env`, rather than failing later at connection time with a misleading network error. `safeSummary()` returns a display string that never contains the password, omitted by construction rather than masked, so no future edit can accidentally widen it. `useDatabase()` returns false whenever `isHosted()` is true, regardless of the switch — a static host has no socket to open, so the hosted flag decides before the switch is read. `serverHost()` defaults to `127.0.0.1`, so running the Node server does not expose settings or mutation routes on every interface by accident. `.env` is read once and cached, so the mode is fixed for the life of the process; this is why `verify_dashboard_parity.mjs` probes the two modes in separate processes.
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
- Inputs: `server/config.js`; committed legacy artifacts or an optional generated MTA-SIM run directory; and either the legacy PostgreSQL tables or direct `mta_sim_*` research tables.
- Outputs: The legacy loaders plus `loadCampaignStrategy()`, `loadSimulationResearch()`, and `loadSnapshot()`. `simulationResearch` contains runs, Provider profiles, Products, Campaigns, Ad Groups, structured Touchpoints, economics, links, budget/outcome history, delivery, configurations, and latent/observed Touchpoint pairs. `campaignStrategy` is the [Campaign budget optimizer](/en/strategy-recommendation/campaign-budget-optimizer.md) artifact in its own shape. The module also exposes master-draft upsert/archive operations, date normalization, source/status helpers, cache clearing, and pool disposal.
- Behavior contract: Legacy loaders preserve exact cross-mode parity. Research loaders normalize the same fields and types across modes and preserve the selected run's natural scale. `loadCampaignStrategy()` is mode-independent by construction: the optimizer's artifact is produced by a research command rather than by the import pipeline, so no table represents it and both modes read the same file, returning `{}` when it is absent. Generated history is read-only. Only `dashboard_master_object` accepts future-run drafts, and only in database mode; drafts never update the `mta_sim_*` observation tables. `formatDate()` is the single date conversion. `project()` pins absent values to `null`. `pg` is loaded lazily and results are cached for ten minutes until Reload.
- Dependencies: `pg`, plus `server/config.js` and `server/csv.js`.
- Verification: `node script/verify_dashboard_parity.mjs` against a populated database. The file-mode invariants — booleans, date format, null-not-empty-string, finite numbers, and JSON round-tripping — are covered by `dashboard/tests/dashboard.test.js`, which needs no database.

### `server/index.js`

Source: `dashboard/server/index.js`

- Responsibility: Serve the JSON API and the built client from one process.
- Inputs: HTTP requests. The client build in `dashboard/dist`, when one exists.
- Outputs: `createApp()`, a listening server when run directly, the existing dashboard/reload/settings routes, and `PUT`/`DELETE /api/master/:entityType/:entityId` for future-run master drafts.
- Behavior contract: `GET /api/dashboard` checks database availability and returns a named `503` reason on failure. Master writes are refused outside database mode, validate the supported entity type and JSON object payload, and upsert or archive only `dashboard_master_object`; no route mutates generated observations. Hosted settings remain read-only, and `DASHBOARD_CONFIG_READ_ONLY=true` makes every settings mutation return the named `read_only_configuration` error while retaining the live server and its configured data source. When run directly, the server binds the configured host and port and prints that exact address.
- Dependencies: `express`, plus `server/config.js`, `server/data_source.js`, and `server/settings.js`.
- Verification: Started with `./dashboard/run.sh` and driven in a real browser; the six views were rendered against both a live PostgreSQL instance and the committed files with no console error and no failed request.

### `src/api/client.js` and `src/lib/useDashboard.js`

Source: `dashboard/src/api/client.js`, `dashboard/src/lib/useDashboard.js`

- Responsibility: Be the client's single route to the data, and hold the single shared copy of it.
- Inputs: `/api/dashboard` in a local run, or `data/snapshot.json` in the published build.
- Outputs: `IS_STATIC`, dashboard/reload/settings calls, `saveMasterObject()`, `archiveMasterObject()`; and `useDashboard()`, including an empty `simulationResearch` shape before loading.
- Behavior contract: `IS_STATIC` is baked in at build time by `vite build --mode static`, and it is the only thing that decides which of the two sources is read; **no view branches on it.** The static path is relative because Pages serves a project site from a subdirectory. A response that is not JSON — a proxy page or a 404 — is reported by status rather than as a parse error naming character 0. In the static build `fetchSettings()` returns the hosted state directly and `postSettings()` refuses, rather than issuing requests that would 404. `useDashboard()` holds one module-level snapshot, so the six views that mount together share one in-flight request rather than issuing six, and two views can never show two different reads. An empty snapshot is exposed until the first load resolves, so a view renders its own empty state rather than crashing on a missing field.
- Dependencies: Vue's reactivity.
- Verification: Driven in a real browser against both the API and the static snapshot; both render the six views identically with no console error.

### `tests/dashboard.test.js`

Source: `dashboard/tests/dashboard.test.js`

- Responsibility: Verify the contracts a clean checkout can check without a database.
- Inputs: The committed artifacts, and temporary files for the `.env` tests.
- Outputs: Pass or fail per test. Run with `npm test` in `dashboard/`.
- Behavior contract: The suite pins file mode **before** anything imports `server/config.js`, which caches the mode on first read, so a test run can never touch the operator's real database. It covers the CSV parser's quoting, line endings, byte-order mark, description row, and trailing newline; `writeEnv()`'s in-place replacement, single append, and stable output; the log buffer's bound, default-off state, level filtering, and truncation; loopback as the default server host; rejection of settings writes in protected deployment mode; the navigation registration contract; and the snapshot invariants — real booleans rather than the string `"false"`, dates as `YYYY-MM-DD`, absent text as `null` rather than `""`, finite numbers rather than strings, the five touchpoint segments, and that the whole snapshot survives JSON serialisation unchanged. `formatDate()` is tested directly against a `Date` object, because file mode never produces one and the database's shape would otherwise be unverifiable without a connection.
- Dependencies: Node's built-in test runner. No database.
- Verification: `npm test` in `dashboard/`. Thirty-four tests pass against the committed artifacts.

### `verify_dashboard_parity.mjs`

Source: `script/verify_dashboard_parity.mjs`

- Responsibility: Assert that every loader returns the same fields, values, and row order whether `DATABASE` is true or false.
- Inputs: The committed artifacts, and a populated PostgreSQL instance configured in `.env`.
- Outputs: One line per loader, and a non-zero exit status naming every field that differs.
- Behavior contract: The two modes are probed in **separate child processes**, because `server/config.js` caches the mode after the first read and one process therefore cannot hold both. The child writes only the snapshot to standard output, so a log line cannot corrupt the payload. Differences are reported in full rather than at the first one, because a single normalisation bug usually shows up in many fields at once and the pattern across them identifies the cause. Row order is compared positionally, not as a set, because the views render in the order the loader returns. `ALLOWED_DB_ABSENCES` lists the fields the relational schema legitimately does not carry, so the exemption is explicit and a new absence is still a failure.
- Dependencies: Everything `server/data_source.js` needs.
- Verification: `node script/verify_dashboard_parity.mjs`. It is a command rather than a unit test because it requires a populated database, which a clean checkout does not have. It reported all ten loaders identical against the live instance as of version 0.9.20; `campaignStrategy` is the eleventh and is parity-safe by construction, since both modes read the one artifact file.
