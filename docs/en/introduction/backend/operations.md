---
title: Backend Jobs and Settings
description: Pipeline job polling and protected runtime settings contracts
compact: "Contracts for `/api/jobs`, `/api/settings`, and `/api/schema-operations`: server-declared model datasets, direct-interpreter subprocesses, database report/research preparation, protected configuration, isolated outputs, bounded logs, termination, cache invalidation, and capability refusals."
lang: en-US
source_files: backend/api/jobs.py, backend/api/settings.py, backend/api/schema_operations.py, backend/services/jobs.py, backend/services/model_datasets.py, backend/services/settings.py, backend/services/schema_operations.py, backend/tests/test_jobs.py, backend/tests/test_settings.py, backend/tests/test_schema_operations.py
---

# Backend Jobs and Settings

## Pipeline Jobs

`GET /api/jobs` returns all three dashboard-runnable model stage definitions,
current runs, and the six
most recent completed runs. `POST /api/jobs/<stage>` validates options before
spawning a fixed argument vector with no shell. `DELETE` requests termination
of a running stage. Output keeps at most 600 lines and reports the number
dropped.

Each stage descriptor carries `datasets` and `defaultDataset`. Dataset
identifiers are opaque server-issued choices, not browser-supplied paths.
Attribution choices name a report window, marketplace, and advertiser scope.
Optimization and evaluation choices name a Multi-Touch Attribution Simulator
(MTA-SIM) research run and marketplace. A stage is available only when
execution and database mode are enabled and at least one compatible dataset
exists.

`POST` requires `datasetId`. The service resolves it again against current
database state immediately before starting, then writes the selected rows to
an isolated input directory below `PIPELINE_OUTPUT_DIR`. Attribution receives
one aggregated path report and matching daily performance dataset. Research
selections contain observed budget, delivery, and outcome records;
evaluation-only simulator outcomes are excluded from model input. No arbitrary
schema, query, or filesystem path reaches the command line from the client.

Attribution runs `script/run_attribution_models.py` against path and daily
performance files materialized from the selected database report scope.
Optimization runs `script/generate_campaign_strategy.py` against the selected
research run and marketplace. Strategy evaluation runs
`script/evaluate_strategies.py` against the same kind of selected research
scope and the current strategy artifacts.
File-mode deployments and server deployments with `PIPELINE_RUNS_ENABLED=false`
cannot start jobs. `DASHBOARD_CONFIG_READ_ONLY=true` protects connection and
logging configuration only; it does not refuse a pipeline run. Conflating the
two permissions made AppStack advertise a database-backed writable dashboard
while every job start returned `403`.

Model jobs invoke the already-running environment's `sys.executable` directly
instead of nesting `uv run`. The container image has already installed the
locked environment; resolving `uv` again adds no dependency isolation and made
online runs fail before Python started when the executable was absent from the
deployed path. Strategy evaluation's numerical dependencies are installed in
every pipeline-enabled runtime image.

The runner keeps active jobs and bounded logs in process memory. A deployment
that enables it therefore runs exactly one application process in exactly one
pod. Otherwise a start request and its following poll can reach different
memories, making a live run disappear. Generated artifacts are written inside
the configured `PIPELINE_OUTPUT_DIR` and survive for that pod or volume's
lifetime; AppStack uses the ephemeral `/pipeline-output` mount, while the
two-container stack uses a named volume. A preparation or permission failure
becomes a terminal failed job with its error in the bounded log instead of an
uncaught server error.

## Settings

`GET /api/settings` returns non-secret connection state, source status, logging
state, bounded diagnostics, and `backendIdentity`. It never returns the stored
password. Its
`connection` object carries `PG_SCHEMA`, and a top-level `schemas` key carries
the census of schemas the connected server offers. The census is enumerated
only in database mode: in file mode there is no connection to ask, and opening
one to populate a dropdown nobody requested would make every settings request
pay for a round trip.

`POST /api/settings` supports `logging`, `clearLog`, `test`, and `save` actions.
Connection tests use submitted values without persisting them. Save writes the
root `.env` atomically, preserves a stored password when the form submits an
empty password, disposes the old pool, invalidates configuration caches, and
clears the snapshot.

`backendIdentity` carries the repository-root project `version`, full build
`commit`, and a `runtime` object containing detected `python` and `flask`
versions. The backend resolves a supplied container `PROJECT_COMMIT` first and
uses the checkout's Git `HEAD` only in a local source run. Missing metadata is
the literal `unknown`, so the client cannot mistake absence for agreement.

### Schema selection

`PG_SCHEMA` is written to `.env` alongside the other connection values, and a
successful `test` returns `schemas` for the server just reached — the only
moment the list is knowable for credentials that have not been saved, so the
dialog fills its dropdown from the connection under test rather than from the
stored one. A `test` also counts tables in the selected schema rather than
always in `public`, so the number it reports describes what selecting it would
read.

A schema name reaches PostgreSQL as an identifier inside a libpq connect
option, never as a bound value. Both routes therefore refuse a name that is not
a plain identifier: `POST /api/settings` returns `400` with
`error: invalid_schema` **before** `.env` is read or written, and
`test_connection()` refuses before opening a socket. The dialog offers a list,
so a name failing this check arrived from something other than the dropdown.
The census, its `selectable` rule, and the `search_path` behavior are specified
in [Backend Setup and Deployment](./setups.md#schema-selection).

AppStack sets `DASHBOARD_CONFIG_READ_ONLY=true`, so deployed save and test
actions return `403`; operators change environment variables through AppStack
and roll the Deployment. The schema is chosen there through the `pgSchema`
value and takes effect on restart.

## Schema Operations

`GET /api/schema-operations` returns the running or most recent schema
operation. `POST /api/schema-operations` accepts `initialize` or `derive`, a
validated schema name, and an explicit Boolean `replace`. `DELETE
/api/schema-operations` requests termination. Hosted, protected, and file-mode
deployments refuse starts before spawning a process.

Initialization accepts a nonexistent or empty schema. It accepts a complete
dashboard schema only with `replace: true`, and always refuses a populated
simulator, partial, or unrelated schema. Derivation accepts only a source that
currently holds every simulator source table required by
`derive_scenario_schemas.py`. This classification is repeated immediately
before the process starts rather than trusting an earlier browser census.

Both actions spawn the documented root command as a fixed argument vector with
no shell. Standard output and standard error are combined in order,
timestamped, truncated to 500 characters per line, and bounded to 600 retained
lines with a dropped-line count. The response is `202` once the process exists;
the client polls the `GET` route until `succeeded`, `failed`, or `stopped`. A
successful operation disposes the database pool and clears snapshot caches
before the next census.

## Source Files

### `backend/api/jobs.py`, `backend/services/jobs.py`, and `backend/services/model_datasets.py`

Source: `backend/api/jobs.py`, `backend/services/jobs.py`, `backend/services/model_datasets.py`

- Responsibility: Discover and revalidate stage-compatible datasets, prepare
  marketplace-scoped model inputs, validate requests, expose polling state,
  spawn the fixed current-interpreter command, capture bounded output, advance
  regex-based phases, stop processes, and clear caches after success.
- Inputs: Stage key, server-issued dataset identifier, positive budget, and
  declared budget policy.
- Outputs: `202` start responses, job snapshots, or specific refusal objects.
- Behavior contract: `PIPELINE_RUNS_ENABLED` governs execution independently
  of `DASHBOARD_CONFIG_READ_ONLY`; database mode is still required. Because
  active state and artifacts are local to one application process, an enabled
  deployment must use one pod and one Gunicorn worker. Outputs are isolated
  below `PIPELINE_OUTPUT_DIR`; every submitted dataset identifier is resolved
  from the current catalogue and prepared as one model scope. The subprocess
  begins with `sys.executable`, never a shell or environment-manager lookup. A successful child
  clears the snapshot cache; a preparation failure is retained as a failed
  job. AppStack falls back to committed image artifacts when a rollout removes
  its runtime volume.
- Dependencies: Root scripts, subprocess, database repositories, and the
  configured runtime output directory.
- Verification: `backend/tests/test_jobs.py` and the backend discovery command.

### `backend/api/settings.py` and `backend/services/settings.py`

Source: `backend/api/settings.py`, `backend/services/settings.py`

- Responsibility: Serve protected settings actions, atomic environment-file
  changes, database probes, the schema census, and a 400-entry in-memory
  diagnostic ring.
- Inputs: Logging settings or connection fields, including `PG_SCHEMA`; stored
  credentials are never echoed.
- Outputs: Sanitized settings state carrying `connection.PG_SCHEMA`, a
  `schemas` census, and `backendIdentity` project/runtime versions and commit;
  a probe result carrying the same census; or an
  action-specific refusal including `400 invalid_schema`.
- Behavior contract: `ENV_KEYS` includes `PG_SCHEMA`, so a selection persists
  across a restart rather than appearing to save and being forgotten. A schema
  name is validated before `.env` is read or written, because it becomes an
  identifier in a connect option rather than a bound value. An absent or blank
  schema resolves to `public`, which keeps every deployment that predates the
  setting working unchanged.
- Dependencies: Shared dashboard configuration, `backend/services/schemas.py`,
  database pool disposal, and snapshot cache invalidation.
- Verification: `backend/tests/test_settings.py`, plus Flask settings requests
  in writable and read-only test environments.

### `backend/api/schema_operations.py` and `backend/services/schema_operations.py`

Source: `backend/api/schema_operations.py`,
`backend/services/schema_operations.py`

- Responsibility: Validate schema setup requests, recheck live schema
  capabilities, run the canonical initializer or simulator parser, expose a
  bounded polling log, and terminate the active process on request.
- Inputs: Operation action, valid source or target schema name, explicit
  replacement Boolean, saved PostgreSQL connection settings, and the live
  schema census.
- Outputs: `202` operation snapshots, `400` validation errors, `403` deployment
  refusals, `409` capability or concurrency refusals, and terminal operation
  state with exit code and detailed output.
- Behavior contract: Browser input is passed only through a fixed argument
  vector. An initializer never writes to a populated non-dashboard schema; a
  parser never writes to its source; replacement is absent unless explicitly
  requested. Logs retain 600 lines of at most 500 characters each and report
  truncation.
- Dependencies: `script/import_to_database.py`,
  `script/derive_scenario_schemas.py`, database pool disposal, and snapshot
  cache invalidation.
- Verification: `backend/tests/test_schema_operations.py` proves argument
  construction, capability refusals, bounded logs, lifecycle state, and route
  protection without opening a live database.
