---
title: Environment Setup
description: Local execution, documentation development, and directory responsibilities
compact: "Setup and toolchain: Python, uv, Node prerequisites; module and documentation verification; GitHub/Gitea mirrors; local Flask dashboard startup; and Yunxiao AppStack full-stack container deployment through reviewable Kubernetes orchestration and protected environment variables."
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
uv run python -X utf8 -B script/generate_mta_sim_dataset.py
```

Initialize one level only. `external/campaign-optimizer-llm-integration` declares this repository as one of its own submodules, so `--recursive` re-enters the project and retrieves a stale copy of itself.

The generated bundle is stored under ignored `generated/mta_sim/`. See [Generate MTA-SIM data](mta-sim-generation.md) for custom configuration and output paths.

## Run the Attribution and Strategy Modules <span class="status-label status-verified" aria-label="Verified"></span>

Run from the repository root:

```bash
uv run python -X utf8 -B script/run_pipeline.py
uv run python -X utf8 script/validate_data_alignment.py
uv run python -X utf8 -B -m unittest discover -s modules/mta_attribution/tests -p "test_*.py"

uv run python -X utf8 -B -m unittest discover -s modules/mta_standard/tests -p "test_*.py"

uv run python -X utf8 -B script/generate_initial_budget.py --check-output
uv run python -X utf8 script/validate_simulated_hierarchy.py
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

Three maintained helpers back these commands. `script/export_drawio_diagrams.mjs` renders each editable `.drawio` source into the `.light.drawio.svg` and `.dark.drawio.svg` pair that `DrawioDiagram` selects between; run it after editing any diagram source. `script/copy_static_assets.mjs` runs at `buildEnd` to copy research attachments and map preserved Chinese routes to the construction placeholder. `script/static_pdf_dev_plugin.mjs` serves research PDFs with byte-range support during local development.

A source whose name ends in `-human.drawio` is a hand-authored counterpart of a diagram that also has an agent-authored version. Both files are tracked, because the pair is worth keeping side by side, but the exporter renders only the unsuffixed source and reports how many it skipped. Rendering both would give one page two published pictures of the same subject with nothing to say which is authoritative, so the unsuffixed name is the published diagram and the `-human` file is opened from the repository. To publish a hand-authored version instead, replace the unsuffixed source with it and re-run the command rather than adding a second embed.

On Windows, you can also run `run-doc-site.bat dev`; on macOS/Linux, run `sh run-doc-site.sh dev`.

The public site is built and deployed by `.github/workflows/deploy-pages.yml` after a push to `main`. The workflow obtains the repository-specific base path from GitHub Pages, runs `npm ci` and `npm run build`, uploads `docs/.vitepress/dist`, and deploys through the protected `github-pages` environment.

## Repository Mirrors <span class="status-label status-verified" aria-label="Verified"></span>

GitHub is the source of truth. `.github/workflows/mirror-to-gitea.yml` force-updates every branch and tag on its configured Gitea destination after a push, deletion, manual dispatch, or scheduled run, then compares the destination references with GitHub and fails unless they match exactly. When GitHub has `main` but no `master`, the destination's protected `master` is retained as an alias of `main`.

### The submodule snapshot branch

A mirror copies references, so a mirrored submodule arrives as the recorded commit identifier and nothing else. Gitea cannot reach `github.com`, so it cannot resolve that identifier into files. The same workflow therefore publishes one additional branch, `gitea-snapshot`, whose tree has the submodule content committed as ordinary tracked files and no `.gitmodules`. A Gitea checkout of that branch is self-contained and needs no submodule step.

That branch is the one destination reference that is deliberately not a copy of a GitHub reference. It is exempt from pruning and excluded from the exact-match verification; every other branch and tag still has to match GitHub exactly. It is generated, so it is never a place to commit: each run force-updates it, and its commit message records the pinned submodule commits it was built from. Bumping a submodule pin on GitHub is what changes it.

Submodules are initialized one level deep, never recursively. `external/campaign-optimizer-llm-integration` declares this repository as one of its own submodules, so a recursive update re-enters the project and retrieves a stale copy of itself; one level costs about 8 megabytes, while recursion costs about 62.

Configure the workflow with the `GITEA_USERNAME`, `GITEA_PASSWORD`, and `GITEA_REPOSITORY` repository secrets. `GITEA_REPOSITORY` accepts either of these credential-free forms:

- a complete secure address for any Gitea service, such as `https://git.example.com/owner/repository.git`;
- `owner/repository.git`, which uses `https://gitea.com` for backward compatibility.

Plain-text `http://` addresses, embedded credentials, query strings, fragments, nested repository paths, and unsupported characters are rejected before any network operation. The normalized secure Gitea base address and two-segment repository path are passed separately to the mirror step, which reconstructs the destination without placing credentials in the remote address. `.github/workflows/mirror-to-gitee.yml` remains the separate gitee.com-only mirror and uses the corresponding `GITEE_*` secrets.

## Dashboard Backend and Production Deployment <span class="status-label status-verified" aria-label="Verified"></span>

The local launchers build Vue and start the Flask backend on one port. Install
the backend independently with `uv sync --extra backend`, or use
`dashboard/run.sh` on macOS/Linux and `dashboard/run.bat` on Windows.

Production no longer transfers an interactive host script or a real `.env`.
Alibaba Cloud Yunxiao AppStack builds `deploy/appstack/Dockerfile`, pushes the
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

### `script/`

Run every maintained project data, attribution, strategy, or documentation command.

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
