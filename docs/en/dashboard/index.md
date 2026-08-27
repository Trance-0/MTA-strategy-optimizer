---
title: Dashboard
description: The Vue dashboard's architecture, its dual data source contract, and where each topic is documented
compact: "Vue/Flask dashboard boundary: Python owns file/PostgreSQL access and the 14-key snapshot; browser views issue no SQL. `client.js` covers snapshots, models, jobs, settings, and polled schema initialization/parsing through `/api`."
lang: en-US
source_files: dashboard/src/api/client.js, dashboard/src/lib/useDashboard.js, dashboard/tests/dashboard.test.js, backend/repository/coercion.py, backend/tests/test_coercion.py, backend/tests/test_settings.py
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

The dashboard is a Vue 3 client over a JavaScript Object Notation (JSON)
Application Programming Interface (API) served by Flask. One Python process
serves both, so a local or AppStack run is one service and one port.

The boundary is exact: `src/api/client.js` is the only module in the client
that issues a request, and `backend/repository/` is the only runtime layer that
opens an artifact or database connection. A view holds no file path, no
Structured Query Language (SQL) statement, and no direct `fetch` call.

The client half is a browser application and nothing else. It ships no server,
reads no `.env`, and carries no PostgreSQL driver: `dashboard/package.json`
declares Vue and Plotly and no other runtime dependency. Every credential and
every query lives behind the API, so the only thing a deployment has to give
the client is a URL — see [Running Locally and Publishing](./deployment.md) for
the two-container stack that does exactly that.

### The API

Lives in `backend/`. Knows about files, SQLAlchemy queries, external simulator
tables, model modules, and deployment configuration. Nothing about rendering.

### The client

Lives in `dashboard/src/`. Knows about the snapshot shape. Nothing about where it came from.

### Why the whole snapshot arrives at once

`GET /api/dashboard` returns every loader's result in one response — roughly 720 KB of JSON, smaller than the artifacts it was read from. Sending it whole rather than paginating is what lets the six views share one read: two views on the same screen cannot show two different states of the same source, and switching views costs nothing because the data is already there.

`src/lib/useDashboard.js` holds that single copy. The six views mount together on first paint, so concurrent callers share one in-flight request rather than issuing six.

### Dependency boundary

Nothing under `modules/` imports the backend or dashboard. The backend may
invoke the module contracts, and the dashboard client may invoke only the
backend HTTP contract; dependencies never point from business logic toward a
command wrapper or presentation component.

Vue and Plotly are installed by `npm ci` in `dashboard/`. Flask, SQLAlchemy,
Psycopg, and Gunicorn are installed with `uv sync --extra backend`.
`dashboard/config.py` and `dashboard/models.py` remain the shared environment
and schema declarations used by both the importer and Flask. See
[Populating PostgreSQL](./database-import.md).

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

`backend/repository/snapshot.py` assembles the runtime payload and its owning
repositories decide which mode is active. They return the **same fields,
types, values, and row order in both modes**. The additional
`simulationResearch` object has the same normalized shape and types in file
and database mode, while its row count reflects the selected generated run: a
local 10,000-observation sidecar and a remote 100,000-observation database are
not expected to contain identical rows. No view contains a source-mode branch.

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

Three groups of fields exist in the JSON artifacts and in no table: the capacity rules, the per-Campaign derivation breakdown, and the source file paths and counts. They are pipeline configuration and intermediate arithmetic rather than observations, and modelling them would mean the database stored figures the dashboard is forbidden to recompute. No view reads any of them.

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

### `src/api/client.js` and `src/lib/useDashboard.js`

Source: `dashboard/src/api/client.js`, `dashboard/src/lib/useDashboard.js`

- Responsibility: Be the client's single route to the data, and hold the single shared copy of it.
- Inputs: `/api/dashboard` in a local run, or `data/snapshot.json` in the published build.
- Outputs: `IS_STATIC`, dashboard/reload/settings calls, `saveMasterObject()`, `archiveMasterObject()`, `fetchJobs()`, `startJob()`, `stopJob()`, `fetchSchemaOperation()`, `startSchemaOperation()`, and `stopSchemaOperation()`; and `useDashboard()`, including empty `simulationResearch` and `strategyEvaluation` shapes before loading.
- Behavior contract: `IS_STATIC` is baked in at build time by `vite build --mode static`, and it is the only thing that decides which of the two sources is read; **no view branches on it.** The static path is relative because Pages serves a project site from a subdirectory. A response that is not JSON — a proxy page or a 404 — is reported by status rather than as a parse error naming character 0. In the static build settings and schema-operation functions return hosted refusals without issuing requests that would 404. Live schema starts send only `action`, `schema`, and an explicit replacement Boolean; errors retain the backend message. `useDashboard()` holds one module-level snapshot, so the six views that mount together share one in-flight request rather than issuing six, and two views can never show two different reads. An empty snapshot is exposed until the first load resolves, so a view renders its own empty state rather than crashing on a missing field.
- Dependencies: Vue's reactivity.
- Verification: Driven in a real browser against both the API and the static snapshot; both render the six views identically with no console error.

### `tests/dashboard.test.js`

Source: `dashboard/tests/dashboard.test.js`

- Responsibility: Verify the contracts a clean checkout can check without a database.
- Inputs: The committed artifacts, and temporary files for the `.env` tests.
- Outputs: Pass or fail per test. Run with `npm test` in `dashboard/`.
- Behavior contract: Every test runs without a database and without a browser, so a clean checkout can run the whole suite. It covers the navigation registration contract; the entity table's paging and identity-keyed selection; the run options and refusals; and the snapshot invariants — real booleans rather than the string `"false"`, dates as `YYYY-MM-DD`, absent text as `null` rather than `""`, finite numbers rather than strings, the five touchpoint segments, and that the whole snapshot survives JSON serialisation unchanged. Several tests assert against **source text** rather than a rendered component, because the suite runs without a Document Object Model (DOM): they pin contracts a reader cannot see in a screenshot — that a progress bar's `aria-valuenow` and its visible percentage read one value, that a phase pattern still matches a line the Python actually prints, that the offered budget policies are the ones the enum declares. Two of those read Python sources directly, because the contract they pin is now owned by `backend/services/`; the reader is the client, so the test stays here.
- Dependencies: Node's built-in test runner. No database.
- Verification: `npm test` in `dashboard/`. Twenty-six tests pass against the committed artifacts.

### `backend/tests/test_coercion.py` and `backend/tests/test_settings.py`

Source: `backend/tests/test_coercion.py`, `backend/tests/test_settings.py`

- Responsibility: Hold the reader and settings contracts that the deleted Node
  suite proved, so removing that code did not remove the coverage.
- Inputs: Temporary files only. Neither test reads the repository's own `.env`
  or opens a connection.
- Outputs: Pass or fail per test, under `uv run --extra backend python -m unittest`.
- Behavior contract: `read_csv` drops the Chinese field-description row by
  matching its exact marker rather than by heuristic — an earlier heuristic
  that tested for the absence of digits silently discarded a real data row from
  the files that carry no such row — strips a Unicode Transformation Format
  8-bit (UTF-8) byte-order mark that would otherwise become part of the first
  header name, keeps quoting, embedded newlines, and Carriage Return Line Feed
  (CRLF) intact, discards the empty row a trailing newline produces, and
  returns no rows rather than raising for an artifact that has not been
  produced. `write_env` replaces a key in place, appends a missing one exactly
  once, preserves comments and unrelated keys, does not grow the file over
  repeated saves, and keeps a password containing `=` intact. Diagnostic
  logging is off by default, drops records below the active level rather than
  storing and filtering them on display, truncates one message at 400
  characters, and bounds the buffer at `LOG_CAPACITY`.
- Dependencies: The backend dependency extra. No database.
- Verification: `uv run --extra backend python -m unittest discover -s backend/tests -t .`. Thirty-two tests pass.
