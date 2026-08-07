---
title: Environment Setup
description: Local execution, documentation development, and directory responsibilities
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
git submodule update --init --recursive
uv sync --locked
uv run python -X utf8 -B script/generate_mta_sim_dataset.py
```

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
npm run cloudflare:dev # Test the Cloudflare Worker with Wrangler
```

On Windows, you can also run `run-doc-site.bat dev`; on macOS/Linux, run `sh run-doc-site.sh dev`.

## Directory Quick Reference <span class="status-label status-verified" aria-label="Verified"></span>

| Directory | When to use it |
| --- | --- |
| `modules/mta_attribution/src/` | Modify attribution algorithms and aggregation logic |
| `modules/mta_standard/src/` | Modify the submodule adapter, shared model interface, or evaluation logic |
| `external/mta_sim_dataset/` | Inspect the pinned external generator source; update only through Git submodule workflows |
| `script/` | Run every maintained project data, attribution, strategy, or documentation command |
| `modules/mta_attribution/data/simulated/` | Inspect this repository's synthetic demonstration inputs |
| `modules/mta_attribution/outputs/` | Inspect current attribution outputs |
| `modules/mta_strategy_recommendation/src/` | Modify budget-initialization logic |
| `modules/mta_strategy_recommendation/data/simulated/` | Inspect the strategy request and candidate pool |
| `modules/mta_strategy_recommendation/outputs/` | Inspect the canonical initial-budget JSON |
| `docs/.vitepress/` | Modify site configuration and theme |
| `docs/research/` | Store and display research attachments on the site; not runtime input |

Do not commit credentials, customer-level data, production account identifiers, or real generated data to this repository.
