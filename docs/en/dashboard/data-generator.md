---
title: Data Generator
description: Dashboard workflow for configured MTA-SIM generation, preview, CSV download, and backend-only PostgreSQL export
compact: "Data Generator contract for `DataGenerator.vue` and `/api/data-generator`: bounded structured/JSON configuration, pinned MTA-SIM availability and execution, two 20-row previews, CSV downloads, write-only PostgreSQL credentials, and backend-only export."
lang: en-US
source_files: dashboard/src/views/DataGenerator.vue, backend/api/data_generator.py, backend/services/data_generator.py, backend/tests/test_data_generator.py
---

# Data Generator

The Data Generator is the second navigation destination, immediately after
Command Center. It is a controlled interface to the pinned
[MTA-SIM (Multi-Touch Attribution Simulator)](/en/reference/definitions#mta-sim-multi-touch-attribution-simulator)
package under `external/mta_sim_dataset`; it is not a second simulation
implementation in Vue or Flask.

The backend calls the reviewed generator function. The browser selects or
edits configuration, starts work, reads bounded status and previews, and asks
the backend to export a completed run. The browser never imports a database
driver, opens a database socket, builds Structured Query Language (SQL), or
receives a stored credential.

## Availability and ownership

The feature is available only when a Flask backend is present and pipeline
runs are enabled, and when the pinned simulator submodule has been initialized.
The static documentation deployment explains that generation requires a local
or team-server backend and does not simulate a successful run.

An ordinary backend test or image-publishing checkout may intentionally omit
Git submodules because external source does not enter those images. In that
environment, the overview remains a successful capability response with
`available: false`, an empty initial configuration, and a bounded reason. A
request for an allow-listed preset returns `503 generator_unavailable`; it must
not become an unhandled server error or reveal an absolute checkout path. The
one integration test that executes a real toy simulation skips when the pinned
checkout is absent. Request validation, route behavior, and credential tests
remain active and must not depend on that checkout.

One backend process owns at most one active generation or export operation.
A second start request receives a conflict response naming the active run.
Completed runs remain available until process restart through an opaque run
identifier. Generated files live only under the ignored
`generated/dashboard-generator/` runtime directory and must never be added to
Git automatically.

## Configuration editors

The page offers two editor modes over one configuration value. Changing modes
does not discard a valid edit.

### Guided editor

The guided editor exposes the parameters needed for a small controlled run:

- generator variant and reviewed preset;
- integer random seed and synthetic advertiser identifier;
- inclusive report start and end dates;
- marketplace code and International Organization for Standardization (ISO)
  currency code;
- base product price and Campaign replication count.

The remaining reviewed preset fields stay intact. A guided edit changes only
the named field in the same JavaScript Object Notation (JSON) object that the
advanced editor displays.

### Configuration-file editor

The advanced editor is a monospaced JSON text editor with validation feedback,
line-preserving input, and a **Format JSON** action. It is intentionally a
native text editor rather than an embedded Integrated Development Environment
(IDE): generation needs JSON validation, not another runtime dependency and
multi-megabyte editor bundle.

The server accepts an object, never a client filesystem path. Configuration
inheritance through `extends` is refused because a browser-supplied path could
otherwise make the server read an unrelated local file. The request is also
bounded by the application body limit and by generator-specific limits on the
reporting window, touchpoints, path scenarios, and Campaign replication.

The server writes the accepted object to the run's ignored directory and gives
that path to the pinned generator. Validation and simulation remain owned by
MTA-SIM.

## Generation lifecycle

`GET /api/data-generator` returns availability, reviewed presets, the default
variant and preset, and the initial self-contained configuration object when
the pinned simulator is present. Its absence is represented by the capability
response described above.

`GET /api/data-generator/presets/<variant>/<preset>` returns one allow-listed,
resolved, self-contained configuration. An unknown pair returns `404
unknown_preset`; a known pair whose pinned source is unavailable returns the
bounded `503 generator_unavailable` response.

`POST /api/data-generator/runs` accepts `variant` and `configuration`. It
validates the request boundary, allocates an opaque run identifier, starts one
background operation, and returns immediately.

`GET /api/data-generator/runs/<run_id>` returns only bounded state:

- `queued`, `running`, `completed`, or `failed` generation status;
- a short phase and bounded error message;
- generator name and version, row counts, and selected reporting scope after
  completion;
- the two preview objects and their download names;
- `idle`, `running`, `completed`, or `failed` PostgreSQL export status.

The response never returns a server path, complete configuration, database
connection string, password, or simulation ground truth.

## Preview contract

A completed run exposes exactly two previews, each retaining the generator's
declared column order and at most the first 20 rows:

### Amazon Marketing Cloud path report

The preview comes from `amc_path_report.csv`. It preserves daily report
windows and the ordered five-segment paths emitted by MTA-SIM.

### Amazon Ads daily touchpoint performance

The preview comes from
`amazon_ads_daily_touchpoint_performance.csv`. It preserves the daily delivery,
cost, and reported-outcome fields emitted by MTA-SIM.

`simulation_ground_truth.csv` is evaluation-only. It is generated for the
model evaluation boundary but is neither previewed nor downloadable from this
workflow.

## Export stage

After generation completes, the page presents the next-stage choices.

### Comma-Separated Values downloads

`GET /api/data-generator/runs/<run_id>/files/<table>` accepts only the two
declared public table keys and sends the matching generated Comma-Separated
Values (CSV) file as an attachment. A path supplied by the browser is never
joined to the filesystem.

### PostgreSQL export

`POST /api/data-generator/runs/<run_id>/postgresql` accepts a host, port,
database, user, write-only password, Secure Sockets Layer (SSL) mode, existing
schema, and explicit replacement Boolean. The backend:

1. validates the port, SSL mode, and schema identifier;
2. opens a direct probe connection and confirms the schema exists and the role
   can use and create objects in it;
3. constructs the connection information with Psycopg rather than string
   interpolation;
4. reruns the same deterministic accepted configuration through MTA-SIM's
   explicit `PostgreSqlResearchWriter` adapter; and
5. clears the password and connection information from operation state as soon
   as the writer has been started.

Credentials exist only in the Transport Layer Security (TLS)-protected request
and the backend operation's local memory. They are not saved in `.env`, a run
directory, application logs, an Application Programming Interface (API)
response, or browser storage. A deployment served over plain Hypertext Transfer
Protocol (HTTP) must not offer PostgreSQL export to a remote browser; localhost
development is the only HTTP exception. A forwarded HTTPS protocol is honored
only when the backend deployment explicitly enables its one trusted reverse
proxy hop; an arbitrary caller-supplied forwarding header is ignored.

Replacement is false by default. When false, MTA-SIM refuses a target already
holding simulator runs. When true, the page displays a separate destructive
confirmation and the backend passes the explicit reset flag to the writer.

## Source Files

### `DataGenerator.vue`

Source: `dashboard/src/views/DataGenerator.vue`

- Responsibility: Render guided and JSON editors, generation state, two
  previews, CSV download controls, and the PostgreSQL export form.
- Inputs: Only the `/api/data-generator` contract through `src/api/client.js`.
- Outputs: Configuration and export requests; no direct filesystem or database
  operation.
- Behavior contract: The two editors share one configuration. Preview tables
  declare their received columns and render at most 20 rows. The password field
  is never refilled, saved, or written to browser storage. A replacement export
  requires a separate confirmation naming the target schema.
- Dependencies: Vue 3 and the shared `DataTable.vue` component.
- Verification: `dashboard/tests/dashboard.test.js` and a browser exercise of
  the default preset through preview and CSV download.

### `backend/api/data_generator.py` and `backend/services/data_generator.py`

Source: `backend/api/data_generator.py`, `backend/services/data_generator.py`

- Responsibility: Own every generator route, run boundary, ignored artifact,
  preview, download resolution, and PostgreSQL connection.
- Inputs: A self-contained configuration object and, only for export, one
  write-only PostgreSQL credential form.
- Outputs: Bounded run state, two previews, two declared CSV attachments, and
  export status.
- Behavior contract: The service invokes the pinned MTA-SIM functions and does
  not reproduce simulation logic. Missing pinned source is capability state,
  not an unhandled exception; preset routes return a bounded 503 without an
  absolute path. One operation runs at a time. Paths and external writers
  cannot come from the client. Ground truth remains absent from responses.
  Credentials are never retained in state or logs. PostgreSQL export targets
  only an existing validated schema and reset requires the explicit Boolean.
- Dependencies: Python standard library, Flask, Psycopg from the backend extra,
  and the pinned MTA-SIM submodule.
- Verification: `backend/tests/test_data_generator.py`.

### `backend/tests/test_data_generator.py`

Source: `backend/tests/test_data_generator.py`

- Responsibility: Pin request limits, asynchronous state, preview bounds,
  declared downloads, hidden ground truth, missing-submodule behavior,
  credential non-retention, and PostgreSQL export delegation.
- Inputs: Temporary directories, synthetic configurations, and patched writer
  boundaries; never a real database credential.
- Outputs: Backend pass or fail.
- Dependencies: Python `unittest` and the backend dependency extra. Only the
  real toy-run integration case depends on the initialized submodule and skips
  explicitly when it is absent; all boundary and route cases are hermetic.
- Verification: `uv run --extra backend python -X utf8 -m unittest
  backend.tests.test_data_generator -v`.
