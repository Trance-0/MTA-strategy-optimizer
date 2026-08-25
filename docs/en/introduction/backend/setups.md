---
title: Backend Setup and Deployment
description: Local Flask startup and Yunxiao AppStack deployment configuration
compact: "Setup contract for Flask and Yunxiao AppStack: `uv sync --extra backend`, Vue production build, Gunicorn image, AppStack value placeholders, ConfigMap and Secret inputs, health probes, authenticated Transport Layer Security ingress, and PostgreSQL connectivity."
lang: en-US
source_files: backend/app.py, backend/config.py, backend/database.py, backend/wsgi.py, backend/tests/test_app.py, deploy/appstack/Dockerfile, deploy/appstack/orchestration.yaml, deploy/appstack/values.example.yaml, .dockerignore
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

## Production Process

Build `deploy/appstack/Dockerfile` with the repository root as its build
context. Its Node stage produces `dashboard/dist`; its Python stage installs
the locked `backend` dependency extra and runs Gunicorn as unprivileged user
`10001`. The image contains no Node runtime and no environment file.

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
  transactional write results.
- Dependencies: `dashboard/config.py`, `dashboard/models.py`, SQLAlchemy, and
  Psycopg.
- Verification: Snapshot tests in file mode plus the AppStack database-mode
  dashboard request.

### `backend/tests/test_app.py`

Source: `backend/tests/test_app.py`

- Responsibility: Verify liveness independence, JSON routing errors, and the
  request-size boundary.
- Inputs: Flask test-client requests.
- Outputs: `unittest` assertions.
- Dependencies: The application factory.
- Verification: Backend discovery command.

### AppStack build and orchestration files

Source: `.dockerignore`, `deploy/appstack/Dockerfile`,
`deploy/appstack/orchestration.yaml`, `deploy/appstack/values.example.yaml`

- Responsibility: Build one credential-free full-stack image and declare its
  Kubernetes configuration, secret injection, rollout, probes, service, and
  authenticated TLS ingress.
- Inputs: Repository root build context, AppStack placeholder values, an image
  registry, and pre-existing registry-pull, TLS, authentication, and storage
  Secrets/claims.
- Outputs: One deployable image and one AppStack orchestration template.
- Dependencies: Node 22.23.0, Python 3.12.11, uv 0.8.13, ACR, Kubernetes, and
  an NGINX Ingress controller.
- Verification: Render placeholders with the example values, validate the
  resulting Kubernetes resources, build the image, and complete the AppStack
  validation sequence.
