---
title: Environment Setup
description: Local execution, documentation development, and directory responsibilities
compact: "Python module and Node package commands; documentation build modules in docs/.vitepress; inline GitHub-to-Gitea materialized main publication; deploy/yunxiao/pipeline.yaml with inline commands and operator settings, plus the separate AppStack deployment."
lang: en-US
---

# Environment Setup

## Prerequisites <span class="status-label status-recommendation" aria-label="Recommendation"></span>

- [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer.
- Node.js 20 or a newer Long-Term Support release, and npm.
- Git with submodule support; use network access only when a remote must be synchronized.

The current Python modules and the pinned ZheyuanWu generator use only the standard library. Documentation dependencies are recorded in `docs/package-lock.json`. The root uv project is deliberately non-package and exists only to run and test the workspace.

The current AMC MTA CSV reader uses Python's process-default text encoding, while the demonstration CSV files are UTF-8. On Windows systems with a non-UTF-8 locale, enable UTF-8 mode before running the Python commands below:

```powershell
$env:PYTHONUTF8 = "1"
```

Alternatively, invoke Python with `python -X utf8 ...`. Without UTF-8 mode, Chinese description rows may raise `UnicodeDecodeError`.

## Initialize and generate data <span class="status-label status-verified" aria-label="Verified"></span>

```bash
git submodule update --init
uv sync --locked
uv run python -X utf8 -B -m modules.mta_standard.src.generate_mta_sim_dataset
```

Initialize one level only. `external/campaign-optimizer-llm-integration` declares this repository as one of its own submodules, so `--recursive` re-enters the project and retrieves a stale copy of itself.

The generated bundle is stored under ignored `generated/mta_sim/`. See [Generate MTA-SIM data](mta-sim-generation.md) for custom configuration and output paths.

## Run the Attribution and Strategy Modules <span class="status-label status-verified" aria-label="Verified"></span>

Run from the repository root:

```bash
uv run python -X utf8 -B -m modules.mta_attribution.src.run_pipeline
uv run python -X utf8 -m modules.mta_attribution.src.validate_data_alignment
uv run python -X utf8 -B -m unittest discover -s modules/mta_attribution/tests -p "test_*.py"

uv run python -X utf8 -B -m unittest discover -s modules/mta_standard/tests -p "test_*.py"

uv run python -X utf8 -B -m modules.mta_strategy_recommendation.src.generate_initial_budget --check-output
uv run python -X utf8 -m modules.mta_strategy_recommendation.src.validate_simulated_hierarchy
uv run python -X utf8 -B -m unittest discover -s modules/mta_strategy_recommendation/tests -p "test_*.py"

uv run python -X utf8 -B -m unittest discover -s modules/mta_strategy_evaluation/tests -p "test_*.py"
```

## Local Documentation Site <span class="status-label status-verified" aria-label="Verified"></span>

```bash
cd docs
npm install
npm run dev
```

Open the local address shown in the terminal. PDF reference links in the documentation body open the files directly from their original locations under `docs/research/`; the development server does not require moving them to `public/`.

Other commands:

```bash
npm run build          # Build the static site and copy research attachments
npm run preview        # Preview the production build
npm run diagrams       # Re-render every .drawio source to its light and dark SVG pair
```

Three maintained VitePress modules back these commands. `docs/.vitepress/export_drawio_diagrams.mjs` renders each editable `.drawio` source into the `.light.drawio.svg` and `.dark.drawio.svg` pair that `DrawioDiagram` selects between; run it after editing any diagram source. `docs/.vitepress/copy_static_assets.mjs` runs at `buildEnd` to copy research attachments and map preserved Chinese routes to the construction placeholder. `docs/.vitepress/static_pdf_dev_plugin.mjs` serves research PDFs with byte-range support during local development.

A source whose name ends in `-human.drawio` is a hand-authored counterpart of a diagram that also has an agent-authored version. Both files are tracked, because the pair is worth keeping side by side, but the exporter renders only the unsuffixed source and reports how many it skipped. Rendering both would give one page two published pictures of the same subject with nothing to say which is authoritative, so the unsuffixed name is the published diagram and the `-human` file is opened from the repository. To publish a hand-authored version instead, replace the unsuffixed source with it and re-run the command rather than adding a second embed.

On Windows, you can also run `run-doc-site.bat dev`; on macOS/Linux, run `sh run-doc-site.sh dev`.

The `.vitepress` source directory is tracked. Root `.gitignore` excludes only its `cache/` and `dist/` outputs; its configuration and build modules must be included in every checkout. `.dockerignore` excludes `.vitepress` from application images because GitHub Pages builds documentation directly from the checkout.

The public site is built and deployed by `.github/workflows/deploy-pages.yml` after a push to `main`. The workflow obtains the repository-specific base path from GitHub Pages, installs both Node packages, builds the static dashboard and documentation, assembles `site/` through `docs/.vitepress/build_pages_site.mjs`, uploads that combined artifact, and deploys through the protected `github-pages` environment.

## Repository Mirrors <span class="status-label status-verified" aria-label="Verified"></span>

GitHub is the only source of authored changes. Gitea is a generated mirror;
never edit code there. `.github/workflows/mirror-to-gitea.yml` synchronizes
branches and tags after a push, deletion, manual dispatch, or scheduled run.
The default branch (`main`) contains one generated child of the GitHub commit,
with its pinned submodules expanded into ordinary files. When GitHub has no
`master`, Gitea `master` aliases that same completed snapshot. Other branches
and tags match GitHub exactly. Yunxiao deploys Gitea `main` only.

### Materialized submodules on main

A raw Git mirror transfers a submodule's commit identifier without its files.
The GitHub runner downloads the recorded submodule revisions and builds the
complete snapshot **before updating any Gitea branch**. It publishes all final
branch and tag references in one atomic push, including pruning obsolete
references, and verifies the resulting reference set. A failed snapshot or a
rejected push leaves the previous deployment references intact. No intermediate
`main` containing GitHub submodule links is published to trigger deployment.

There is no separate deployment snapshot branch. Gitea `main` contains no root
`.gitmodules` and no Git links anywhere in its tree. Its commit message records
every top-level pin, and its sole parent is the exact GitHub default-branch
revision used to build it. Fixed identity and timestamps make an unchanged
source produce the same snapshot commit, so scheduled synchronization is a
no-op. See [Mirror publication](./repository-mirror.md) for the command contract
and failure verification.

Submodules are initialized one level deep, never recursively. `external/campaign-optimizer-llm-integration` declares this repository as one of its own submodules, so a recursive update re-enters the project and retrieves a stale copy of itself; one level costs about 8 megabytes, while recursion costs about 62.

Configure the workflow with the `GITEA_USERNAME`, `GITEA_PASSWORD`, and `GITEA_REPOSITORY` repository secrets. `GITEA_REPOSITORY` accepts either of these credential-free forms:

- a complete secure address for any Gitea service, such as `https://git.example.com/owner/repository.git`;
- `owner/repository.git`, which uses `https://gitea.com` for backward compatibility.

Plain-text `http://` addresses, embedded credentials, query strings, fragments, nested repository paths, and unsupported characters are rejected before any network operation. The normalized secure Gitea base address and two-segment repository path are passed separately to the mirror step, which reconstructs the destination without placing credentials in the remote address. `.github/workflows/mirror-to-gitee.yml` remains the separate gitee.com-only mirror and uses the corresponding `GITEE_*` secrets.

## Dashboard Backend and Production Deployment <span class="status-label status-verified" aria-label="Verified"></span>

The local launchers build Vue and start the Flask backend on one port. Install
the backend independently with `uv sync --extra backend`, or use
`dashboard/run.sh` on macOS/Linux and `dashboard/run.bat` on Windows.

The existing Yunxiao host pipeline deploys Gitea `main` to an
[Elastic Compute Service (ECS)](/en/definitions#ecs-elastic-compute-service)
machine without containers. Its [host deployment contract](../backend/yunxiao-ecs.md)
owns `deploy/yunxiao/pipeline.yaml`: clone, preflight, tests, source activation
and service checks. Copy that file into the existing cloud job. It never
downloads source from GitHub. The host's `.env` stays on the host.

The separate Alibaba Cloud Yunxiao AppStack option builds `deploy/appstack/Dockerfile`, pushes the
image to Alibaba Cloud Container Registry (ACR), and applies the native
Kubernetes orchestration in `deploy/appstack/orchestration.yaml`. AppStack
environment placeholders inject PostgreSQL configuration; the password is a
private variable and never enters the repository or image.

See [Backend Setup and Deployment](/en/introduction/backend/setups) for the
complete local commands, AppStack placeholder list, authenticated Transport
Layer Security ingress, health probes, and Alibaba validation sequence.

## Directory Quick Reference <span class="status-label status-verified" aria-label="Verified"></span>

### `modules/mta_attribution/src/`

Modify attribution algorithms and aggregation logic.

### `modules/mta_standard/src/`

Modify loading, adaptation, registry, execution, output validation, or evaluation logic.

### `modules/mta_attribution/src/`

Modify the model interface or an individual attribution implementation.

### `external/mta_sim_dataset/`

Inspect the pinned external generator source; update only through Git submodule workflows.

### Native package entry points

Run model operations with `python -m modules.<module>.src.<entry>` and database operations with `python -m backend.<entry>`; frontend and documentation commands remain npm package tasks.

### `deploy/`

Build and deploy the AppStack full-stack image and Kubernetes orchestration.

### `modules/mta_attribution/data/simulated/`

Inspect this repository's synthetic demonstration inputs.

### `modules/mta_attribution/outputs/`

Inspect current attribution outputs.

### `modules/mta_strategy_recommendation/src/`

Modify budget-initialization logic.

### `modules/mta_strategy_recommendation/data/simulated/`

Inspect the strategy request and candidate pool.

### `modules/mta_strategy_recommendation/outputs/`

Inspect the canonical initial-budget JSON.

### `docs/.vitepress/`

Modify site configuration and theme.

### `docs/research/`

Store and display research attachments on the site; not runtime input.

Do not commit credentials, customer-level data, production account identifiers, or real generated data to this repository.
