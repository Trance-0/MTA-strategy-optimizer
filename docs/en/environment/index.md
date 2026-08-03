---
title: Environment Setup
description: Local execution, documentation development, and directory responsibilities
lang: en-US
---

# Environment Setup

## Prerequisites <span class="status-label status-recommendation" aria-label="Recommendation"></span>

- Python 3.11 or newer.
- Node.js 20 or a newer Long-Term Support release, and npm.
- Git; use network access only when the remote repository must be synchronized.

The current Python modules use only the standard library. Documentation dependencies are recorded in `docs/package-lock.json`.

The current AMC MTA CSV reader uses Python's process-default text encoding, while the demonstration CSV files are UTF-8. On Windows systems with a non-UTF-8 locale, enable UTF-8 mode before running the Python commands below:

```powershell
$env:PYTHONUTF8 = "1"
```

Alternatively, invoke Python with `python -X utf8 ...`. Without UTF-8 mode, Chinese description rows may raise `UnicodeDecodeError`.

## Run the Attribution and Strategy Modules <span class="status-label status-verified" aria-label="Verified"></span>

Run from the repository root:

```bash
python -B modules/amc_mta/run_pipeline.py
python modules/amc_mta/scripts/validate_data_alignment.py
python -B -m unittest discover -s modules/amc_mta/tests -p "test_*.py"

python -B -m unittest discover -s modules/mta_standard/tests -p "test_*.py"

python -B modules/mta_strategy_recommender/scripts/generate_initial_budget.py --check-output
python modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py
python -B -m unittest discover -s modules/mta_strategy_recommender/tests -p "test_*.py"
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
| `modules/amc_mta/src/` | Modify attribution algorithms and aggregation logic |
| `modules/amc_mta/scripts/` | Generate, run, compare, or validate attribution artifacts |
| `modules/amc_mta/data/simulated/` | Inspect this repository's synthetic demonstration inputs |
| `modules/amc_mta/outputs/` | Inspect current attribution outputs |
| `modules/mta_strategy_recommender/src/` | Modify budget-initialization logic |
| `modules/mta_strategy_recommender/data/simulated/` | Inspect the strategy request and candidate pool |
| `modules/mta_strategy_recommender/outputs/` | Inspect the canonical initial-budget JSON |
| `docs/.vitepress/` | Modify site configuration and theme |
| `docs/research/` | Store and display research attachments on the site; not runtime input |

Do not commit credentials, customer-level data, production account identifiers, or real generated data to this repository.
