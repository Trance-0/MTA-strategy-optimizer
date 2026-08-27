---
title: Backend Setup and Deployment
description: Local Flask startup and Yunxiao AppStack deployment configuration
compact: "Flask and AppStack setup: local commands, Gunicorn image, backend project and commit identity, Python and Flask detection, PostgreSQL schema census, protected deployment values, probes, ingress, connectivity, and Docker build metadata without copied Git history."
lang: en-US
source_files: backend/app.py, backend/config.py, backend/database.py, backend/services/schemas.py, backend/wsgi.py, backend/tests/test_app.py, backend/tests/test_schemas.py, deploy/appstack/Dockerfile, deploy/appstack/orchestration.yaml, deploy/appstack/values.example.yaml, .dockerignore
---

# Backend Setup and Deployment

## Local Setup

From the repository root, install the locked backend environment and build the
client:

```powershell
uv sync --extra backend
Set-Location dashboard
npm ci
npm run build
Set-Location ..
uv run --extra backend python -m backend.app
```

The platform-specific `dashboard/run.sh` and `dashboard/run.bat` launchers do
those checks and start the same Flask module. The default address is
`http://127.0.0.1:8501`. `BACKEND_HOST` and `BACKEND_PORT` override the bind;
`DASHBOARD_HOST` and `DASHBOARD_PORT` remain compatibility fallbacks.

Copy `sample.env` to `.env`. `DATABASE=false` reads committed files without a
database. `DATABASE=true` requires `PG_HOST`, `PG_PORT`, `PG_DATABASE`,
`PG_USER`, `PG_PASSWORD`, and `PG_SSLMODE`. Configuration is loaded by
`dashboard/config.py` so the import command and backend share one definition.

For client hot reload, run `npm run dev` in `dashboard/` and run the Flask
backend separately. Vite proxies `/api` to port 8501.

## Schema Selection

One PostgreSQL instance commonly holds several schemas, one per scenario, and
they are not interchangeable. `PG_SCHEMA` names the single schema every
connection reads and `script/import_to_database.py` writes. It defaults to
`public`, which is what every deployment predating the setting was reading.

### The connection carries the selection

A non-default `PG_SCHEMA` is applied through the libpq connect option
`-csearch_path=<schema>`, set once by `DatabaseSettings.connect_args()` in
`dashboard/config.py` and passed to the single engine in `backend/database.py`.
Applying it to the connection rather than to each statement is required,
because statements are built two ways: from `dashboard/models.py`, which names
no schema, and as reflective reads of the external `mta_sim_*` tables, which
name none either. One connection-level setting makes both follow the selection
without a second definition of where a table lives.

### The selected schema is the whole search path

Nothing sits behind the selection. `-csearch_path=mta` does not fall back to
`public`. The forgiving choice would be wrong here: a schema holding research
history but not this project's own tables would resolve the rest from `public`
and place one scenario's attribution beside another's history, with nothing on
the page saying so. A missing table must read as missing. `pg_catalog` is
searched implicitly and holds every function these statements call, so pinning
costs a read nothing.

When the selected schema does not contain `attribution_result`,
`database_available()` returns unusable with a message naming both remedies:
select a schema that carries the dashboard tables, or derive one per scenario
from this one. The derivation is named rather than the fixture import, because
a schema reached this way already holds another account's history and the
importer carries its own advertiser and Campaigns with it. That is distinguished
from a schema whose `attribution_result` exists but is empty, because the two
need different fixes.

### A schema name is an identifier, never a bound value

A schema names an object, so it cannot be passed as a query parameter. It is
validated instead. `valid_schema_name()` in `dashboard/config.py` accepts only
an unquoted PostgreSQL identifier — a letter or underscore, then up to
sixty-two letters, digits, underscores, or dollar signs. Anything else is
refused at three points before it can reach a connection: `POST /api/settings`
returns `400 invalid_schema` before writing `.env`, `test_connection()` refuses
before opening a socket, and `connect_args()` raises rather than building an
option that could close and open another.

### The census decides what may be selected

`backend/services/schemas.py` enumerates schemas over `pg_namespace` and
`pg_class` in one round trip, filtered by
`has_schema_privilege(current_user, ..., 'USAGE')`, so the list can never
advertise a schema the connected role cannot read. Each entry reports a
capability rather than a name: the fourteen tables the dashboard's loaders read
directly must all be present for the schema to be selectable. An incomplete
schema is still listed, marked unselectable, and carries the tables it lacks
and the command that would populate it.

The same census drives schema setup without changing the stricter selection
rule. Each entry classifies itself as `dashboard`, `source`, `partial_source`,
`empty`, or `other`; `canInitialize` and `canDerive` state which setup action is
safe. `SIMULATOR_SOURCE_TABLES` contains the complete parsing prerequisite, so
a partly uploaded source is visible but cannot start a parser that is already
known to fail. These fields are capability data rather than a hard-coded menu,
so an additional readable schema appears automatically.

`GET /api/settings` returns the census under `schemas`, enumerated only in
database mode. A connection test returns the census for the server just
reached, which is the only moment the list is knowable for credentials that
have not been saved.

### Deployment

`deploy/appstack/orchestration.yaml` binds `PG_SCHEMA` from the `pgSchema`
placeholder. That deployment sets `DASHBOARD_CONFIG_READ_ONLY=true`, so the
browser cannot change the schema: it is chosen in the AppStack environment and
takes effect on restart.

## Production Process

Build `deploy/appstack/Dockerfile` with the repository root as its build
context. Its Node stage produces `dashboard/dist`; its Python stage installs
the locked `backend` dependency extra and runs Gunicorn as unprivileged user
`10001`. The image contains no Node runtime and no environment file.

Pass the source revision while building:

```bash
docker build --build-arg BUILD_COMMIT="$(git rev-parse HEAD)" \
  -f deploy/appstack/Dockerfile -t marketing-roi-analysis .
```

The Dockerfile copies `VERSION` into both the client build context and runtime
image, bakes `BUILD_COMMIT` into the Vue bundle, and exposes it to Python as
`PROJECT_COMMIT`. If the build platform supplies its checkout revision under a
different name, map that value to `BUILD_COMMIT`; do not copy `.git` into the
context.

The production entry point is:

```text
gunicorn --bind 0.0.0.0:8501 --workers 2 --threads 4 --timeout 120 backend.wsgi:application
```

`GET /api/health` is the liveness and readiness probe. It proves that the
process routes requests and deliberately does not require a populated
database. `GET /api/dashboard` separately returns `503` when database mode is
configured but unusable.

## Yunxiao AppStack

Alibaba Cloud Yunxiao AppStack accepts native Kubernetes orchestration and
extracts placeholders written as <code>&#123;&#123; .Values.name &#125;&#125;</code>. Create an AppStack
application from the container/Kubernetes template, bind the repository, set
the image build file to `deploy/appstack/Dockerfile`, and set the build context
to the repository root. Paste or import `deploy/appstack/orchestration.yaml` as
the application orchestration template, then choose **Extract Placeholders**.

Bind the resulting placeholders at the environment level. The non-secret
shape and safe sample values are in `deploy/appstack/values.example.yaml`.
Mark `pgPassword` as a private password variable. A real password must never
be written to the example file, repository, build log, or image.

`imagePullSecret` names the namespace-local Docker registry Secret that can
pull the private Alibaba Cloud Container Registry image. AppStack or the
cluster administrator must create it before rollout; it is referenced, not
materialized with credentials in this template.

The orchestration creates one ConfigMap, one Secret, a rolling Deployment, a
ClusterIP Service, and an Ingress. The pod has a read-only root filesystem,
drops Linux capabilities, and mounts only `/tmp` as writable. Set
`DASHBOARD_CONFIG_READ_ONLY=true`; deployed settings and pipeline mutations
must be managed through AppStack rather than through the browser.

The optional simulator data directory is mounted from the Persistent Volume
Claim named by `mtaSimPvc` at `/data/mta-sim`. The claim must exist in the
target namespace before deployment. Use an empty read-only claim when model
research inputs are intentionally unavailable; the catalogue will report the
corresponding capabilities as unavailable.

The Ingress requires an existing Transport Layer Security (TLS) Secret and an
NGINX basic-auth Secret. This is mandatory because the application has no
built-in user authentication and includes data-mutation routes. The PostgreSQL
host must be reachable through the same Virtual Private Cloud (VPC), with its
firewall or security group allowing the pod network.

## Validation Sequence

AppStack must run these gates in order:

1. Run backend `unittest` discovery and the existing module suites.
2. Run `npm test` and `npm run build` in `dashboard/`.
3. Build and push the image to Alibaba Cloud Container Registry (ACR).
4. Deploy the orchestration to the target Kubernetes environment.
5. Wait for the Deployment rollout, then request `/api/health` through the authenticated TLS address.
6. Request `/api/dashboard` and `GET /api/models`; database mode is validated only when the dashboard response is `200` and names `mode: database`.

A local build validates code and image composition. Only the final AppStack
rollout proves Resource Access Management (RAM), registry pull, Persistent
Volume Claim, Ingress, TLS, authentication, Virtual Private Cloud routing, and
PostgreSQL credentials in the Alibaba account.

## Source Files

### `backend/app.py` and `backend/wsgi.py`

Source: `backend/app.py`, `backend/wsgi.py`

- Responsibility: Create the Flask application, register all blueprints,
  serve `dashboard/dist`, cap requests at 256 kibibytes, return JSON errors,
  and expose the production Web Server Gateway Interface (WSGI) object.
- Inputs: Environment bind values and optional built client assets.
- Outputs: One HTTP service; non-API client paths resolve to `index.html`.
- Dependencies: Backend blueprints and Flask.
- Verification: `backend/tests/test_app.py` and an image health request.

### `backend/config.py` and `backend/database.py`

Source: `backend/config.py`, `backend/database.py`

- Responsibility: Extend the shared dashboard configuration with service-only
  values, create one lazy SQLAlchemy engine, and separate read from transaction
  helpers. Queries for owned tables use `dashboard/models.py`; textual SQL is
  restricted to external `mta_sim_*` tables and table-existence probes.
- Inputs: `.env` or deployment environment variables.
- Outputs: Safe non-secret source labels, paths, ORM row mappings, and
  transactional write results, plus `backend_identity()` containing project
  version, commit identifier, Python version, and Flask version.
- Behavior contract: `project_version()` reads the tracked root `VERSION` file.
  `project_commit()` prefers `PROJECT_COMMIT`, then `GITHUB_SHA`, then a local
  `git rev-parse HEAD`, and returns `unknown` when none is valid. Runtime
  dependency versions are detected from the running interpreter and installed
  Flask distribution rather than copied from dependency declarations.
- Dependencies: `dashboard/config.py`, `dashboard/models.py`, SQLAlchemy, and
  Psycopg.
- Verification: Snapshot tests in file mode plus the AppStack database-mode
  dashboard request.

### `backend/services/schemas.py`

Source: `backend/services/schemas.py`

- Responsibility: Enumerate every schema the connected role may read and report
  what each can serve. `REQUIRED_TABLES` is the fourteen tables a schema must
  hold to be selectable; `RESEARCH_TABLES` is the four external history tables
  whose presence distinguishes a scenario awaiting an import from an unrelated
  schema; and `SIMULATOR_SOURCE_TABLES` is the full parser prerequisite.
  `available_schemas()` reads through the service engine and
  `probe_schemas()` through a throwaway engine for credentials not yet saved.
  Neither raises: each returns `{schemas, selected, error}` so an unreachable
  database renders as a dialog that says so rather than a settings page that
  fails to load. The probe deliberately pins no search path, since asking which
  schemas exist must not depend on the answer.
- Inputs: The configured connection, or a candidate `PG_*` mapping.
- Outputs: Per schema — `name`, `selectable`, `selected`, `tableCount`,
  `missingTables` (capped at eight), `missingCount`, `hasResearchTables`, and a
  `kind`, `canInitialize`, `canDerive`, `sourceMissingCount`, and `detail`
  string naming its capability and safe next action. `tableCount` is the
  schema's whole relation count, not the matched
  subset the census filters on: reporting the subset would describe a
  fifty-three-table schema as holding fourteen, and a reader comparing that
  against their database client would reasonably conclude the connection was
  pointing elsewhere. The command offered depends on what the schema already
  holds — one carrying research history is offered
  `script/derive_scenario_schemas.py`, and only an empty one is offered
  `script/import_to_database.py`, because the importer writes its own
  advertiser and Campaigns and would otherwise attach them to another
  account's observations. Selectable entries sort first, then by name. A schema
  whose name is not a plain identifier is dropped rather than offered and later
  refused. No `detail` describes how the account's history was produced.
- Dependencies: `backend/config.py`, `backend/database.py`, SQLAlchemy.
- Verification: `backend/tests/test_schemas.py`.

### `backend/tests/test_app.py` and `backend/tests/test_schemas.py`

Source: `backend/tests/test_app.py`, `backend/tests/test_schemas.py`

- Responsibility: Verify liveness independence, JSON routing errors, and the
  request-size boundary; and separately that a schema name is accepted only as
  a plain identifier, that the selected schema is the whole search path with no
  fallback behind it, and that a schema is offered as selectable only when it
  holds every required table.
- Inputs: Flask test-client requests, and recorded census rows rather than a
  live server, so the classification is proven without a database.
- Outputs: `unittest` assertions.
- Dependencies: The application factory, `dashboard/config.py`,
  `backend/services/schemas.py`.
- Verification: Backend discovery command.

### AppStack build and orchestration files

Source: `.dockerignore`, `deploy/appstack/Dockerfile`,
`deploy/appstack/orchestration.yaml`, `deploy/appstack/values.example.yaml`

- Responsibility: Build one credential-free full-stack image and declare its
  Kubernetes configuration, secret injection, rollout, probes, service, and
  authenticated TLS ingress.
- Inputs: Repository root build context, `BUILD_COMMIT`, AppStack placeholder
  values, an image registry, and pre-existing registry-pull, TLS,
  authentication, and storage Secrets/claims.
- Outputs: One deployable image and one AppStack orchestration template.
- Dependencies: Node 22.23.0, Python 3.12.11, uv 0.8.13, ACR, Kubernetes, and
  an NGINX Ingress controller.
- Verification: Render placeholders with the example values, validate the
  resulting Kubernetes resources, build the image, and complete the AppStack
  validation sequence.
