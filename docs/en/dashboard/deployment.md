---
title: Running Locally and Publishing
compact: "Dashboard delivery contract: launchers, build identity, Docker results, static resources, byte-pinned Ontology Review source/release provenance and materialization, repeated Pages validation, container publishing, AppStack, and reproducible revision labels."
lang: en-US
source_files: dashboard/index.html, dashboard/package.json, dashboard/vite.config.js, dashboard/run.sh, dashboard/run.bat, deploy/docker/compose.yaml, deploy/docker/defaults.env, deploy/docker/run.sh, deploy/docker/run.bat, deploy/docker/Dockerfile.api, deploy/docker/Dockerfile.dashboard, .github/workflows/publish-containers.yml, script/build_pages_site.mjs, script/export_dashboard_snapshot.py, script/import_ontology_review_fixtures.mjs, dashboard/tests/ontology_review_fixtures.test.js
---

# Running Locally and Publishing

## Running Locally

```bash
./dashboard/run.sh          # macOS, Linux, Git Bash
dashboard\run.bat           # Windows
./dashboard/run.sh 8600     # a different port
./dashboard/run.sh --help   # complete usage
```

The launchers require Node.js in Vite's supported range and `uv`. They resolve
the repository root, copy `sample.env` to `.env` only when absent, install the
locked Node and Flask dependencies, build `dashboard/dist`, and start
`backend.app`. The backend serves the Application Programming Interface (API)
and built client on one port. `--rebuild` removes only the generated client
build before rebuilding it.

For client hot reload, start Flask from the repository root and Vite from
`dashboard/`:

```powershell
uv run --extra backend python -m backend.app
Set-Location dashboard
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8501`. The client therefore exercises
the real Python backend while Vue modules reload in place.

### Build identity

`dashboard/vite.config.js` reads the repository-root `VERSION` and resolves the
frontend commit from `BUILD_COMMIT`, `GITHUB_SHA`, or the checkout's Git
`HEAD`, in that order. It injects both as compile-time constants. A browser
bundle is immutable, so reading a server environment variable at runtime would
describe the container serving it rather than the source that produced it.

The local launchers build from the checkout and need no extra input. The
Docker launchers export `PROJECT_COMMIT` from Git and Compose passes it to both
image builds as `BUILD_COMMIT`. Registry publishing passes the workflow commit
to the same argument while retaining the Open Container Initiative (OCI)
revision label. `.git` remains excluded from Docker contexts; copying it into
an image to recover a commit would disclose repository history and destroy
layer-cache stability. A build performed without either Git or `BUILD_COMMIT`
uses `unknown`, which Settings reports as incomplete identity.

## Two-Container Docker Stack

`deploy/docker/` runs the client and the API as separate containers, so each
can be rebuilt, restarted, and read on its own. It is a testing counterpart to
AppStack, which deploys one image serving both.

```bash
./deploy/docker/run.sh          # build both images and start
./deploy/docker/run.sh pull     # pull the published images and start
./deploy/docker/run.sh down     # stop and remove them
./deploy/docker/run.sh logs     # follow both containers
```

`deploy\docker\run.bat` is the Windows equivalent. Both read the
repository-root `VERSION` file into `PROJECT_VERSION` and tag the two images
with it, so bumping `VERSION` is the only thing that rolls the tag. `up` stops
the previous run first: a rebuilt image does not replace a container that is
already running, and the old one still holds the published ports. Both modes
wait for the health checks with `compose up -d --wait`, so a script that
continues to a request is not racing the start.

`up` builds from this checkout; `pull` fetches the images already published
for this `VERSION` and builds nothing. Use `pull` on a machine that only runs
the stack, and `up` when the sources have changed — a build is the only way to
see an edit that is not yet released. Because the tag is the `VERSION` file
rather than `latest`, `pull` is exact: it fetches the images built from this
checkout's version, not whatever was published most recently.

### Published Images

Both services name a GitHub Container Registry (GHCR) image in `compose.yaml`,
so a locally built image and a pulled one are the same name at the same
version and `compose up` cannot silently mix them:

```text
ghcr.io/trance-0/mta-backend:<VERSION>
ghcr.io/trance-0/mta-dashboard:<VERSION>
```

Both are public, so `docker pull` needs no login. A fork sets `IMAGE_NAMESPACE`
to its own owner to run its own images; the scripts fold it to lowercase,
because a registry path must be lowercase and a GitHub owner need not be.

The stack can therefore be run on a host with neither a toolchain nor the
sources, given `compose.yaml`, `defaults.env`, and `nginx.conf`:

```bash
docker pull ghcr.io/trance-0/mta-backend:0.9.30
docker pull ghcr.io/trance-0/mta-dashboard:0.9.30
```

### Publishing on a Version Change

`.github/workflows/publish-containers.yml` builds and pushes both images. It
triggers on a push to `main` that changes `VERSION`, not on every commit: a
published image is identified by the version it was built from, so rebuilding
on each push would produce many images claiming to be the same version and
leave the tag meaning "whichever build ran last".

`paths: VERSION` restricts the workflow to pushes that touch the file, and a
first job asks the registry whether both tags already resolve. If they do the
run stops there, so a push that touches `VERSION` without changing its content
publishes nothing. `workflow_dispatch` takes a `force` input for the one case
that must overwrite a tag deliberately.

The four jobs run in order, and each is a gate on the next:

#### `version`

Reads `VERSION`, rejects anything that is not `major.minor.patch` before a
build can fail on a malformed tag, folds the owner to lowercase once, and
decides whether to publish.

#### `test`

Runs the suites owning the code each image ships — the five module suites and
the backend suite for `mta-backend`, the dashboard suite for `mta-dashboard` —
then builds the client. A failure publishes nothing. The client build runs
here as well as in the image, because a failure costs seconds here and a full
layer cache miss there.

The checkout deliberately omits Git submodules because `.dockerignore`
excludes `external/` from both image contexts. The one backend integration
case that executes the external MTA-SIM toy pipeline skips explicitly when its
pinned checkout is absent. Every request-boundary, availability, route, and
credential test remains active, including the assertion that an unavailable
preset returns a bounded 503 instead of an unhandled exception.

#### `build`

One matrix job per image, from the same two Dockerfiles the local stack uses.
Each pushes the version tag and `latest`, and carries an
`org.opencontainers.image.source` label, which is what attaches the package to
this repository and lets it inherit repository visibility rather than being an
orphan in the owner's namespace. The workflow also passes the same full commit
identifier as `BUILD_COMMIT`, so the visible application identity and image
label cannot disagree.

#### `verify`

Pulls both images on a runner that never built them and starts them through
`run.sh pull` — the same file a developer runs, rather than a second
description of it. It then asserts `/api/health` directly and through the
client's proxy, that the client document is served, and that
`/api/dashboard` returns its full snapshot. The build job proves an image was
pushed; only a pull from a machine that never built it proves it can be
consumed.

The client is served by NGINX on `http://localhost:8090` and proxies `/api` to
the API container by service name. The API is also published on
`http://localhost:8501` so it can be exercised with `curl`, but the browser
never uses that port — **the only thing the client is given is a URL.** No
credential and no database driver exists on the client side of the stack.

The dashboard container waits for the API's `service_healthy` condition rather
than for its start, because NGINX resolves the upstream name once at worker
start. The API's health check calls `/api/health` with `urllib`, since the slim
Python image carries no `curl` or `wget`.

The API image runs one Gunicorn worker. Job state and its bounded log are held
in process memory, so multiple workers could accept a start in one process and
send the following poll to another. `compose.yaml` mounts the named
`pipeline-output` volume at `/pipeline-output` and sets
`PIPELINE_OUTPUT_DIR` to that path. Generated attribution, strategy, and
evaluation results therefore survive an API container replacement without
making the source tree writable; removing the volume deliberately resets them.
For a direct local backend, omitting `PIPELINE_OUTPUT_DIR` instead selects and
write-probes the ignored `generated/pipeline-output` directory. A configured
path that cannot be written makes pipeline capability unavailable rather than
falling back elsewhere.

### The data source is detected, not configured

`compose.yaml` layers two application environment files, last value winning:

- `deploy/docker/defaults.env` is tracked and holds `DATABASE=false` with empty
  `PG_*` values, so a clean checkout with no `.env` starts and serves the
  committed CSV and JSON files.
- The repository-root `.env` is optional and overrides any of those. It is
  passed to the **API container only**, at run time. `.dockerignore` excludes
  `.env` from the build context, so no credential is baked into an image layer.

`run.sh` prints which of the two was resolved, so a stack reading the wrong
source is visible at startup rather than at the first empty chart.

`DATABASE=true` needs a host the container can reach. `localhost` in the root
`.env` names the container itself; a database on the Docker Desktop host is
`host.docker.internal`. Stack knobs — `DASHBOARD_PORT`, `API_PORT` — go in an
ignored `deploy/docker/.env` instead, so the root file's `DASHBOARD_PORT`,
which is where the *local* server binds, cannot silently move the published
port.

## Static GitHub Pages Build

GitHub Pages cannot run Flask, so the published client uses static mode.
`script/export_dashboard_snapshot.py` forces local-file mode and writes the
same core JavaScript Object Notation (JSON) object as Flask to
one generated file per allow-listed resource below
`dashboard/public/data/resources/`. `vite build --mode static` copies them
into the build and sets the one client flag that makes
`dashboard/src/api/client.js` fetch the relative data file.

The exporter must never publish database data. It sets `DATABASE=false` and
`DASHBOARD_HOSTED=true` before loading any repository and refuses a snapshot
whose mode is not `local files`. This makes accidental private-data inclusion
a failed build rather than a review convention.

### Canonical Ontology Review fixtures

The tracked `dashboard/fixtures/ontology_review/canonical_r5_v3/` directory is
an immutable public reference input. It contains exactly the upstream source
manifest and five regular fixture files, with no links or additional entries.
Path-scoped Git attributes preserve their raw bytes across operating systems.
The release review confirms that all fields are synthetic and contain no
customer or personal identity, credential, token, connection string, raw
proprietary identifier, or unreviewed free text.

The source manifest remains byte-identical to upstream. The preparation command
verifies the pinned source and release provenance, manifest order, sizes,
SHA-256 digests, release identity, demo client, plan/review linkage, and R5
identity. It then atomically writes copied payloads and a distinct generated
release manifest containing `import_identity` below the ignored
`dashboard/public/data/ontology-review/` directory. Routine builds require no
sibling repository, network fetch, submodule, or absolute developer path.
Refreshing the tracked input is a separate human-gated action that resolves
both commits in the canonical Git repository, compares the exact-six bytes
with the pinned release commit, confirms that the manifest records the pinned
source commit, and proves that source is a Git ancestor of release. The source
commit identifies the ontology snapshot; the fixture directory is introduced by
the release commit.

The same preparation runs before development, normal Vue, and static builds.
After Vite builds, the exact generated bundle is reverified in `dist-static`.
`script/build_pages_site.mjs` verifies it again after copying to final
`site/`. A missing, extra, linked, converted, or altered input or output makes
the command fail; a successful Pages build without review data is forbidden.

If preparation reports an existing `.ontology-review.lock`, first confirm that no
Dashboard start or build still owns it. Preserve the lock under a named recovery
path before retrying; never delete it automatically. A failed old-bundle cleanup
likewise preserves the `.backup-*` directory while the newly verified bundle
remains installed, so inspect both before removing that recovery copy.

Run the dashboard static build from `dashboard/`:

```powershell
npm run build:static
```

The Pages workflow installs Python, `uv`, Node, dashboard dependencies, and
documentation dependencies. It builds the dashboard and English VitePress
site, then `script/build_pages_site.mjs` assembles the dashboard at `/` and the
documentation at `/docs/` in the ignored `site/` directory. GitHub Pages is
the only maintained documentation deployment target. Before a release is
called done, the deployed project-base URL must return the generated manifest
and all five fixtures successfully and the `#/knowledge/ontology-review` view must expose all
five cases. Generated public data, `dist*`, and `site/` remain untracked.

## Production Deployment

The retired `deploy/run.sh` host bundle no longer exists. Production builds
one full-stack container and deploys it through Alibaba Cloud Yunxiao AppStack.
The exact image, placeholders, Kubernetes resources, credential boundary,
health probes, and validation sequence are specified in
[Backend Setup and Deployment](/en/introduction/backend/setups).

## Source Files

### `dashboard/run.sh` and `dashboard/run.bat`

Source: `dashboard/run.sh`, `dashboard/run.bat`

- Responsibility: Validate local Node and uv toolchains, initialize safe file
  configuration, install dependencies, build Vue, and launch Flask.
- Inputs: Optional port, `--no-open`, `--rebuild`, and root `.env`.
- Outputs: `dashboard/dist` and one local backend process.
- Dependencies: Node.js, npm, uv, and the locked project files.
- Verification: `bash -n dashboard/run.sh`, `dashboard\run.bat --help`, and a
  local `/api/health` request after startup.

### The two-container test stack

Source: `deploy/docker/compose.yaml`, `deploy/docker/defaults.env`,
`deploy/docker/Dockerfile.api`, `deploy/docker/Dockerfile.dashboard`,
`deploy/docker/nginx.conf`, `deploy/docker/run.sh`, `deploy/docker/run.bat`

- Responsibility: Build or pull the client and API as two containers, tagged
  from `VERSION`, reading whichever data source the checkout is configured for.
- Inputs: The repository root as build context; `defaults.env`; the optional
  root `.env`; the optional `deploy/docker/.env` for ports; `IMAGE_NAMESPACE`
  for the registry owner, defaulting to `trance-0`.
- Outputs: `marketing-roi-analysis-dashboard` on 8090 and
  `marketing-roi-analysis-api` on 8501, both with health checks.
- Behavior contract: `run.sh up` builds and `run.sh pull` fetches, and both
  start through the same `compose.yaml` with `up -d --wait`, so the command
  returns only once both health checks pass. Each service's `image` is the
  GHCR reference in both modes, so a built image and a pulled one cannot be
  confused; `pull` fails with the remedy rather than falling back to a build,
  because silently building a version that was supposed to be released hides
  the thing worth knowing. Neither script pushes: the workflow is the only
  writer of the registry. `Dockerfile.api` deliberately does **not** copy
  `dashboard/dist`, so `client_dist_directory()` returns None and the service
  registers API routes only — the client is the other image. It builds with
  `npm run build`, not `--mode static`, which would bake a snapshot and make
  Flask unreachable. The runtime installs both the `backend` and
  `strategy-evaluation` dependency extras, and model jobs invoke that
  environment's Python interpreter directly; no runtime uv cache or writable
  home directory is required. Gunicorn uses one worker because live job state
  is process-local.
  The named `pipeline-output` volume is the writable artifact root and
  `defaults.env` enables the runner independently from settings protection.
  The root `.env` is layered over `defaults.env` at run time and never copied
  into an image. The client container holds no credential and reaches the API
  by service name.
- Dependencies: Docker with Compose v2. No local Node or uv.
- Verification: `./deploy/docker/run.sh up`, then both containers reach
  `healthy`; `/api/health` answers directly and through the proxy;
  `/api/dashboard` returns fifteen keys; and the seven views render in a browser
  with no console, page, or network error. Verified in both file mode and
  against the live PostgreSQL instance. `./deploy/docker/run.sh pull` reaches
  the same state without building, and reports a missing version rather than
  building one.

### `.github/workflows/publish-containers.yml`

Source: `.github/workflows/publish-containers.yml`

- Responsibility: Test, build, publish, and verify `mta-backend` and
  `mta-dashboard` on GHCR when `VERSION` changes on `main`.
- Inputs: The `VERSION` file; the repository root as build context; the
  workflow commit as `BUILD_COMMIT`; the two `deploy/docker/` Dockerfiles;
  `GITHUB_TOKEN` with `packages: write`.
- Outputs: Two public images tagged with the version and `latest`, each
  labelled with its source repository, revision, and version, and each carrying
  the same revision inside its application identity.
- Behavior contract: The trigger is `paths: VERSION` on `main` plus manual
  dispatch, never every commit. The `version` job rejects a `VERSION` that is
  not `major.minor.patch` and skips the run when both tags already resolve in
  the registry, so a tag is written once unless dispatched with `force`. The
  registry is asked rather than the GitHub API, because the registry is what a
  `docker pull` consults. The source-only checkout omits submodules; only the
  real external-generator integration test skips, while hermetic backend tests
  verify the unavailable capability and 503 preset response. Tests gate the
  build, and the build gates a `verify` job that pulls both images on a runner
  that never built them and exercises the running stack. The concurrency group
  queues rather than cancels, since a cancelled publish can leave a manifest
  half-written.
- Dependencies: `actions/checkout`, `actions/setup-node`,
  `actions/setup-python`, `astral-sh/setup-uv`, `docker/login-action`,
  `docker/setup-buildx-action`, and `docker/build-push-action`.
- Verification: Both images published at `0.9.30` and consumed on a runner that
  never built them — pulled, started through `run.sh pull`, both `healthy`,
  `/api/health` answering `{"ok":true}` directly and proxied, and
  `/api/dashboard` returning fifteen keys. The commit raising `VERSION` to
  `0.9.30` started a run on its own; six later commits that did not touch
  `VERSION` started none, so the filter holds in both directions.

### `dashboard/index.html` and `dashboard/vite.config.js`

Source: `dashboard/index.html`, `dashboard/vite.config.js`

- Responsibility: Provide the Vue document and configure API/static builds,
  output directories, chunking, and the development proxy.
- Inputs: Build mode and client source modules.
- Outputs: `dist` for Flask or `dist-static` for Pages.
- Dependencies: Vite and Vue plugin.
- Verification: `npm test`, `npm run build`, and `npm run build:static` in
  `dashboard/`.

### `script/export_dashboard_snapshot.py`

Source: `script/export_dashboard_snapshot.py`

- Responsibility: Export the Flask snapshot repositories in forced file mode
  to the generated static-client data path using an atomic replacement.
- Inputs: Committed module artifacts only.
- Outputs: One minified UTF-8
  `dashboard/public/data/resources/<resource>.json` file per registered
  resource, each replaced atomically. The exporter removes obsolete generated
  resource files and the two pre-0.9.37 whole-snapshot files before writing, so
  a static build cannot carry stale data contracts beside the active one.
- Dependencies: `backend.repository.snapshot` and the backend dependency extra.
- Verification: `uv run --extra backend python -X utf8 -B -m script.export_dashboard_snapshot`;
  assert the result reports `mode: local files` and fourteen keys.

### Canonical Ontology Review build inputs and verification

Source: `dashboard/package.json`, `script/import_ontology_review_fixtures.mjs`, `dashboard/tests/ontology_review_fixtures.test.js`

- Responsibility: Prepare and verify the canonical Ontology Review browser
  bundle before any Dashboard start or build.
- Inputs: The tracked exact-six reference directory. A separate refresh mode
  accepts an explicitly selected canonical Git checkout after human approval.
- Outputs: One generated release manifest and five byte-identical payloads
  under ignored `dashboard/public/data/ontology-review/`.
- Behavior contract: Reject missing, extra, non-regular, linked, converted, or
  altered entries and any mismatch in provenance, manifest order, sizes,
  hashes, release identity, demo client, plan/review linkage, or R5 identity. The
  source manifest has a pinned raw size and hash; the generated release manifest
  has one deterministic byte serialization whose raw bytes are rechecked.
  Preparation is local and deterministic; refresh additionally proves the two
  upstream commits and their content relationship.
- Dependencies: Node's standard library and the tracked canonical reference
  bundle; after normal toolchain dependencies are installed, no canonical-source network access, sibling repository, runtime API, or credential.
- Verification: Dashboard fixture tests plus an isolated tracked-files-only
  checkout with no generated data or canonical repository beside it.

### `script/build_pages_site.mjs`

Source: `script/build_pages_site.mjs`

- Responsibility: Validate both production builds, copy them into one Pages
  artifact, add `.nojekyll`, and reverify the final canonical review bundle.
- Inputs: `dashboard/dist-static` and `docs/.vitepress/dist`.
- Outputs: Ignored `site/` with dashboard root and `/docs/` documentation.
- Dependencies: Node's standard library.
- Verification: Run after both builds; it reports the assembled file count and
  size only after the final manifest and five payloads pass verification.
