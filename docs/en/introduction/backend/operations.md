---
title: Backend Jobs and Settings
description: Pipeline job polling and protected runtime settings contracts
compact: "Specifies `/api/jobs` and `/api/settings`: validated subprocess argument vectors, bounded logs and history, three runnable model stages including strategy evaluation, stop semantics, cache invalidation, connection testing, the `PG_SCHEMA` census and its `invalid_schema` refusal, protected `.env` writes, read-only AppStack behavior, and diagnostics."
lang: en-US
source_files: backend/api/jobs.py, backend/api/settings.py, backend/services/jobs.py, backend/services/settings.py, backend/tests/test_settings.py
---

# Backend Jobs and Settings

## Pipeline Jobs

`GET /api/jobs` returns all three dashboard-runnable model stage definitions,
current runs, and the six
most recent completed runs. `POST /api/jobs/<stage>` validates options before
spawning a fixed argument vector with no shell. `DELETE` requests termination
of a running stage. Output keeps at most 600 lines and reports the number
dropped.

Attribution runs `script/run_pipeline.py`. Optimization runs
`script/generate_campaign_strategy.py` and requires a research snapshot.
Strategy evaluation runs `script/evaluate_strategies.py` without requiring a
research snapshot,
because it can use the response observations in `campaign_strategy.json`.
Read-only or file-mode deployments cannot start publishing jobs.

## Settings

`GET /api/settings` returns non-secret connection state, source status, logging
state, and bounded diagnostics. It never returns the stored password. Its
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

## Source Files

### `backend/api/jobs.py` and `backend/services/jobs.py`

Source: `backend/api/jobs.py`, `backend/services/jobs.py`

- Responsibility: Validate stage requests, expose polling state, spawn fixed
  `uv run python` commands, capture bounded output, advance regex-based phases,
  stop processes, and clear caches after success.
- Inputs: Stage key, International Organization for Standardization (ISO)
  date range, positive budget, and declared budget policy.
- Outputs: `202` start responses, job snapshots, or specific refusal objects.
- Dependencies: Root scripts, subprocess, research snapshot configuration.
- Verification: Backend route tests plus direct job-service unit tests when a
  stage contract changes.

### `backend/api/settings.py` and `backend/services/settings.py`

Source: `backend/api/settings.py`, `backend/services/settings.py`

- Responsibility: Serve protected settings actions, atomic environment-file
  changes, database probes, the schema census, and a 400-entry in-memory
  diagnostic ring.
- Inputs: Logging settings or connection fields, including `PG_SCHEMA`; stored
  credentials are never echoed.
- Outputs: Sanitized settings state carrying `connection.PG_SCHEMA` and a
  `schemas` census, a probe result carrying the same census, or an
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
