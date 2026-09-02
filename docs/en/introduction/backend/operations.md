---
title: Backend Jobs and Settings
description: Pipeline job polling and protected runtime settings contracts
compact: "Contracts for jobs, artifact upload/download/database import, default writable runtime storage, settings, INFO logging, schema selection and recovery, current-interpreter child operations, bounded logs, termination, cache invalidation, and independent capability flags."
lang: en-US
source_files: backend/api/jobs.py, backend/api/settings.py, backend/api/schema_operations.py, backend/api/schema_recovery.py, backend/services/jobs.py, backend/services/model_datasets.py, backend/services/model_outputs.py, backend/services/settings.py, backend/services/schema_operations.py, backend/services/schema_recovery.py, backend/tests/test_jobs.py, backend/tests/test_model_outputs.py, backend/tests/test_settings.py, backend/tests/test_schema_operations.py, backend/tests/test_schema_recovery.py
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
Optimization choices name a Multi-Touch Attribution Simulator (MTA-SIM)
research run and marketplace. Evaluation offers those scopes when present and
always offers the current strategy artifacts because its research input is
optional. In file mode choices are fixed server-owned committed or configured inputs;
the browser still receives only an opaque identifier. A stage is available when
execution is enabled, the Python backend has a writable runtime directory, and
at least one compatible dataset exists. A static build has no backend and keeps
Run disabled.

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
File-mode deployments may start jobs and download their outputs. Server
deployments with `PIPELINE_RUNS_ENABLED=false` cannot start jobs.
`DASHBOARD_CONFIG_READ_ONLY=true` protects connection and
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

When `PIPELINE_OUTPUT_DIR` is unset, a local backend creates and verifies the
ignored `generated/pipeline-output` directory below the repository. A configured
value must resolve to a directory the process can create and write. A failed
probe makes the stage unavailable with the configuration remedy; the server
never falls back to a tracked module output directory.

### Model artifacts

Each stage declares an exact output allow-list. Attribution has its five
Comma-Separated Values (CSV) files; optimization has
`campaign_strategy.json`; evaluation has `strategy_evaluation.json`.
`GET /api/jobs/<stage>/artifacts/<filename>` downloads only an allow-listed,
currently valid artifact. `POST /api/jobs/<stage>/artifacts` accepts one
complete multipart set, bounds total bytes, rejects path-like names,
duplicates, unexpected names, malformed UTF-8, wrong CSV headers, and invalid
JSON shapes. Only after the complete set validates does it publish each member
through a temporary-file replacement below the runtime directory.
The dashboard may therefore ingest model output files without giving the
browser filesystem or query authority.

Every backend deployment offers download and upload. When `DATABASE=true`, a
successful validation also enables `POST /api/jobs/<stage>/artifacts/import`.
That explicit action stores the complete stage set in the optional
`model_artifact` table in one transaction, replacing the previous set for that
stage. The route creates that one optional table if an older dashboard schema
does not have it; normal reads and schema readiness do not require the table.
Database import is never attempted by frontend code directly. The backend owns
the transaction, digest, media type, and active schema.
Before evaluation starts, the backend restores a complete imported optimization
set into its runtime strategy directory when no live optimizer output is there,
so database persistence participates in the next stage rather than serving as
download storage only.

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

Logging starts enabled at minimum severity `INFO`. Each bounded record carries
an ISO 8601 Coordinated Universal Time (UTC) timestamp, severity, source,
truncated English message, and optional numeric `durationMs`. Changing the
display's source or severity filter and
copying visible records are client-only actions; changing capture level and
clearing the ring remain server actions. This adapts Trance-0's public
[Notechondria logging configuration](https://github.com/Trance-0/notechondria/blob/main/backend/notechondria/settings.py)
while retaining this service's in-memory-only storage policy.

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

### Runtime schema selection

`POST /api/settings/schema-selection` accepts `{ "schema": string }` only in
database mode. It is independent of protected deployment configuration because
it changes neither credentials nor `.env`. The service re-runs the live census,
requires an exact entry with `selectable: true`, sets that schema as the
process-local runtime override, disposes every existing engine, clears core and
research caches, and returns fresh Settings state.

The route rejects a source, partial, empty, unrelated, missing, or malformed
schema before any dashboard query is run. If the target cannot serve a probe
snapshot, the service restores the prior schema, clears the failed target's
state, and reports the failure. `GET /api/settings` marks the runtime selection
active and carries the configured schema separately so the dialog can state
that a restart returns to deployment configuration.

AppStack sets `DASHBOARD_CONFIG_READ_ONLY=true`, so deployed save and test
actions return `403`; operators change environment variables through AppStack
and roll the Deployment. The schema is chosen there through the `pgSchema`
value and takes effect on restart.

## Schema Operations

`GET /api/schema-operations` returns the running or most recent schema
operation. `POST /api/schema-operations` accepts `initialize` or `derive`, a
validated schema name, and an explicit Boolean `replace`. `DELETE
/api/schema-operations` requests termination. Hosted and file-mode deployments
refuse starts before spawning a process. `SCHEMA_SETUP_ENABLED` governs the
write capability independently of `DASHBOARD_CONFIG_READ_ONLY`: protecting
credentials does not by itself prohibit using the database connection the
deployment already supplied.

Initialization accepts a nonexistent or empty schema. It accepts a complete
dashboard schema only with `replace: true`, and always refuses a populated
simulator, partial, or unrelated schema. Derivation accepts only a source that
currently holds every simulator source table required by
`derive_scenario_schemas.py`. This classification is repeated immediately
before the process starts rather than trusting an earlier browser census.

Both actions spawn the documented root script as a fixed argument vector with
no shell. The vector begins with the already-running environment's
`sys.executable`; it never performs an environment-manager lookup, because a
deployed runtime has already installed the required backend dependencies and
need not carry `uv` on its executable path. Standard output and standard error
are combined in order,
timestamped, truncated to 500 characters per line, and bounded to 600 retained
lines with a dropped-line count. The response is `202` once the process exists;
the client polls the `GET` route until `succeeded`, `failed`, or `stopped`. A
successful operation disposes the database pool and clears snapshot caches
before the next census.

## Schema Recovery

When the configured schema cannot serve the snapshot, `GET
/api/schema-recovery` turns the live census into browser actions. It excludes
the failing active schema, incomplete and unrelated schemas, and any write
action prohibited by `SCHEMA_SETUP_ENABLED`. It may offer:

- `select` for another dashboard-ready schema;
- `derive` for a complete MTA-SIM source schema; or
- `initialize` for an empty schema.

The route is read-only and grants no capability. `SchemaRecovery.vue` sends a
chosen action to the existing schema-selection or schema-operation route, which
repeats identifier, census, permission, and replacement validation immediately
before acting. Recovery never proposes replacement; destructive rebuilding
remains an explicit Settings action.

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
  of `DASHBOARD_CONFIG_READ_ONLY`; file mode uses only fixed server-owned
  inputs, while database mode materializes an opaque selected scope. Because
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

### `backend/services/model_outputs.py`

Source: `backend/services/model_outputs.py`

- Responsibility: Define each stage's exact artifact manifest, validate
  complete bounded uploads, publish runtime files, serve resolved downloads,
  and import a validated set through the optional database table.
- Inputs: A known stage plus multipart files whose exact basenames match that
  stage, or the existing validated runtime set.
- Outputs: Artifact capability descriptors, fixed runtime files, downloads, or
  one transactional `model_artifact` replacement.
- Behavior contract: Browser input never becomes a path, table, schema, or
  query. CSV headers and JSON root shapes are parsed before publication; a
  missing, duplicate, unexpected, oversized, or malformed file rejects the
  whole request. Database import is explicit and available only in database
  mode.
- Dependencies: `dashboard/models.py`, SQLAlchemy, and the configured runtime
  directory.
- Verification: `backend/tests/test_model_outputs.py` and backend discovery.

### `backend/api/settings.py` and `backend/services/settings.py`

Source: `backend/api/settings.py`, `backend/services/settings.py`

- Responsibility: Serve protected settings actions, atomic environment-file
  changes, database probes, the schema census, confirmed process-local schema
  selection, and a 400-entry in-memory diagnostic ring.
- Inputs: Logging settings, connection fields including `PG_SCHEMA`, or an
  exact dashboard-ready schema name; stored credentials are never echoed.
- Outputs: Sanitized settings state carrying `connection.PG_SCHEMA`, a
  `schemas` census, and `backendIdentity` project/runtime versions and commit;
  a probe result carrying the same census; or an
  action-specific refusal including `400 invalid_schema`.
- Behavior contract: `ENV_KEYS` includes `PG_SCHEMA`, so a selection persists
  across a restart rather than appearing to save and being forgotten. A schema
  name is validated before `.env` is read or written, because it becomes an
  identifier in a connect option rather than a bound value. An absent or blank
  schema resolves to `public`, which keeps every deployment that predates the
  setting working unchanged. Runtime selection rechecks `selectable: true`,
  disposes the pool, clears caches, probes the target snapshot, and restores
  the prior schema on failure without rewriting `.env`. Logging starts enabled
  at INFO and retains only bounded ISO 8601 UTC records; passwords and
  submitted connection values never enter the ring.
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
  vector beginning with `sys.executable`, never an environment-manager lookup.
  An initializer never writes to a populated non-dashboard schema; a
  parser never writes to its source; replacement is absent unless explicitly
  requested. Logs retain 600 lines of at most 500 characters each and report
  truncation.
- Dependencies: `script/import_to_database.py`,
  `script/derive_scenario_schemas.py`, database pool disposal, and snapshot
  cache invalidation.
- Verification: `backend/tests/test_schema_operations.py` proves argument
  construction, capability refusals, bounded logs, lifecycle state, and route
  protection without opening a live database.

### `backend/api/schema_recovery.py` and `backend/services/schema_recovery.py`

Source: `backend/api/schema_recovery.py`,
`backend/services/schema_recovery.py`

- Responsibility: Convert the current schema census into safe, actionable
  recovery choices for a dashboard data-load failure.
- Inputs: Database mode, the configured schema, `SCHEMA_SETUP_ENABLED`, and the
  live schema census.
- Outputs: A non-secret state containing the active schema, capability reason,
  and zero or more select, derive, or initialize options.
- Behavior contract: The active failing schema is never offered for selection.
  Incomplete and unrelated schemas are omitted. Write options disappear when
  setup is disabled, and every returned option has `replace: false`. The route
  neither writes nor authorizes; the action route revalidates everything.
- Dependencies: `backend/services/schemas.py` and backend configuration.
- Verification: `backend/tests/test_schema_recovery.py`.

### `backend/tests/test_schema_recovery.py`

Source: `backend/tests/test_schema_recovery.py`

- Responsibility: Prove recovery choice filtering and the read-only route.
- Inputs: Mocked schema census and capability flags; no live database.
- Outputs: `unittest` assertions.
- Dependencies: Flask test client and `backend/services/schema_recovery.py`.
- Verification: Backend discovery command.
