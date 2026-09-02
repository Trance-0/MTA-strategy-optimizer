---
title: Dashboard Data Endpoints
description: Snapshot, reload, master-object, and repository behavior
compact: "Specifies allow-listed dashboard resources, loader caches, research slices, structured load timing, reload invalidation, compatibility snapshot assembly, runtime/imported-artifact precedence, immutable observations, editable master drafts, SQLAlchemy queries, and normalized JSON types."
lang: en-US
source_files: backend/api/dashboard.py, backend/repository/attribution.py, backend/repository/coercion.py, backend/repository/evaluation.py, backend/repository/history.py, backend/repository/master_data.py, backend/repository/research.py, backend/repository/snapshot.py, backend/repository/strategy.py, backend/tests/test_snapshot.py
---

# Dashboard Data Endpoints

## Resource Contract

`GET /api/dashboard/resources/<resource>` accepts only a key in the repository
`RESOURCE_LOADERS` registry. It never accepts a path, table name, column name,
or query from the browser. An unknown key returns `404 resource_not_found` and
does not call a repository loader.

Each response is a mergeable JavaScript Object Notation (JSON) object. The
`shell` resource returns `mode`, `source`, and `dashboardContext`. The other
resources return one coherent part of the former snapshot: `performance`,
`attribution`, `budget`, `strategy`, `evaluation`, `entity-bridge`,
`path-report`, or one named `research-*` slice. A research slice nests its
fields below `simulationResearch`, so the client can merge one catalogue
without replacing catalogues loaded earlier. Row ordering and scalar types
match the established repository contract.

The route registry, not the backend, decides which resources a subsection
needs. The backend registry decides what each accepted name can expose. This
two-sided allow-list means a hash fragment cannot become a storage operation.
Results are cached for ten minutes by underlying loader key. Research history
has a separate cache from research catalogues, so loading Providers cannot
execute observation queries.

`load_snapshot()` remains an internal compatibility assembly for schema
validation and Python parity tests; the Vue client does not call the legacy
whole-snapshot route. `POST /api/reload` and a successful model job clear every
loader cache together.

`POST /api/reload` clears every loader cache. A successful pipeline stage also
clears it. Database mode first probes reachability and a non-empty attribution
result; failure returns `503 database_unavailable` as a page-level state.

That state names no shell command. A schema is one of the reasons the probe
fails, and it is the reason a reader can act on, so the client answers the
error card with the actionable schemas from
[`GET /api/schema-recovery`](./operations.md#schema-recovery) instead of an
instruction that assumes a terminal.

When `PIPELINE_OUTPUT_DIR` is configured, repositories prefer completed
runtime model artifacts so a deployed run is visible without rewriting the
image or importing generated files into PostgreSQL. Attribution switches only
after all five Markov, Shapley, comparison, and recommendation files exist;
this atomic-set rule prevents a request during publication from mixing one
run's files with another source. Strategy and evaluation switch when their
single JSON artifact exists. Until then, database rows or committed files
remain the fallback. Runtime outputs never change the snapshot's database
`mode`; they are model results for the connected deployment, not a new data
source configuration.

## Master Objects

`PUT /api/master/<entity_type>/<entity_id>` saves a future-run draft and
`DELETE` archives it. Valid types are provider, product, campaign, ad group,
touchpoint, product economics, and generation configuration. Generated
delivery, outcome, budget, and path observations have no mutation route.

File mode is read-only. Database drafts live in `dashboard_master_object` and
never rewrite external `mta_sim_*` evidence tables.

## Source Files

### `backend/api/dashboard.py` and `backend/repository/snapshot.py`

Source: `backend/api/dashboard.py`, `backend/repository/snapshot.py`

- Responsibility: Serve health, compatibility snapshot, lazy resources,
  reload, and master routes; expose only registered resource payloads and keep
  the ordered compatibility snapshot for server-side validation.
- Inputs: Data-source mode and repository loader results.
- Outputs: Mergeable JSON responses with exact stable keys and status-specific
  error objects; unknown resource names return a bounded 404 before loading.
- Behavior contract: A successful resource request emits one structured INFO
  record whose `durationMs` is measured with the monotonic performance clock;
  the response payload contains no diagnostic field.
- Dependencies: Backend repositories, settings log, and database probe.
- Verification: `backend/tests/test_snapshot.py`.

### Attribution, history, strategy, and evaluation repositories

Source: `backend/repository/attribution.py`,
`backend/repository/history.py`, `backend/repository/strategy.py`,
`backend/repository/evaluation.py`

- Responsibility: Reproduce each existing file loader in local mode and build
  database statements from the shared SQLAlchemy models in database mode;
  prefer a completed result below `PIPELINE_OUTPUT_DIR` after a deployed run.
- Inputs: Committed CSV/JSON artifacts or PostgreSQL rows.
- Outputs: Normalized lists and documents in stable first-seen or declared order.
- Dependencies: `dashboard/models.py`, backend database helpers, and coercions.
- Behavior contract: Attribution requires its complete five-file runtime set
  before switching. Strategy and evaluation require their named JSON artifact.
  When runtime is absent, a complete optional `model_artifact` database set is
  validated and restored below the runtime directory before reading. An absent
  or partial runtime/database result falls back without mixing sources.
- Verification: Snapshot row counts, runtime-precedence tests, and exact
  cross-language value comparison.

### `backend/repository/coercion.py`

Source: `backend/repository/coercion.py`

- Responsibility: Normalize numbers, booleans, dates, projected fields,
  touchpoint segments, naming, CSV, and JSON consistently across sources.
- Inputs: Mutable row dictionaries, Comma-Separated Values (CSV), JavaScript
  Object Notation (JSON), and declared field lists.
- Outputs: JSON-safe values; blank numerics become `null`, measured zero stays zero.
- Dependencies: Python standard library only.
- Verification: Snapshot parity test and zero-impression regression test.

### `backend/repository/master_data.py` and `backend/repository/research.py`

Source: `backend/repository/master_data.py`, `backend/repository/research.py`

- Responsibility: Derive account master data from reports, read configured
  simulator research, reflect external Multi-Touch Attribution Simulator
  (MTA-SIM) tables, split metadata from lazy observations without changing row
  shapes, and isolate editable future-run drafts from immutable observations.
- Inputs: Normalized reports, optional simulator sidecars, external tables,
  and validated master payloads.
- Outputs: The `simulationResearch` object and saved/archived draft records.
- Dependencies: Backend repositories and database execution boundary.
- Verification: Snapshot parity and master-route refusal tests.

### `backend/tests/test_snapshot.py`

Source: `backend/tests/test_snapshot.py`

- Responsibility: Assert the full key set, fixture row counts, cache clearing,
  and measured-zero behavior.
- Inputs: Local committed artifacts and Flask test requests.
- Outputs: `unittest` assertions.
- Dependencies: Application factory and public repository functions.
- Verification: Backend discovery command.
