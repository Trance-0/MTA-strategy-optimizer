---
title: Development and Verification Guide
compact: "Python module entry points and Node package commands after removal of root script/: six Python suites, frontend tests, manual specification checks, inline deployment validation, live/static builds and database operations."
lang: en-US
---

# Development and Verification Guide

## Environment

- Python 3.12, selected by `.python-version`;
- Node.js 22 for the Vue dashboard and documentation build modules;
- Git;
- no third-party Python package is required by AMC MTA itself.

Preserved `.agents` and `_bmad` files are historical tool assets. Their scripts and tests are not part of the Trance-0 development or verification workflow.

## Run the Business Pipeline

```bash
uv run python -X utf8 -B -m modules.mta_attribution.src.run_pipeline
uv run python -X utf8 -m modules.mta_attribution.src.validate_data_alignment
```

The pipeline derives its window from the earliest through latest Amazon Ads `reportDate`; adding data should not require changing configured dates. See [AMC MTA execution](./environment/amc-mta-usage.md) for custom input and output arguments.

Attribution outputs are written under `modules/mta_attribution/outputs/attribution/`.

Five CSV files are retained as the canonical model/governance outputs. Other generated output is excluded by `.gitignore`.

## Run Product Tests

```bash
uv run python -X utf8 -B -m unittest discover -s modules/mta_common/tests -t . -p 'test_*.py'
uv run python -X utf8 -B -m unittest discover -s modules/mta_attribution/tests -t . -p 'test_*.py'
uv run python -X utf8 -B -m unittest discover -s modules/mta_standard/tests -t . -p 'test_*.py'
uv run python -X utf8 -B -m unittest discover -s modules/mta_strategy_recommendation/tests -t . -p 'test_*.py'
uv run --extra strategy-evaluation python -X utf8 -B -m unittest discover -s modules/mta_strategy_evaluation/tests -t . -p 'test_*.py'
uv run --extra backend python -X utf8 -B -m unittest discover -s backend/tests -t . -p 'test_*.py'
Set-Location dashboard
npm test
```

Always treat the current test run, rather than a historical count in a release
note, as ground truth.

## Validate the Campaign Group Initial-Strategy Sample

```bash
uv run python -X utf8 -B -m modules.mta_strategy_recommendation.src.generate_initial_budget --check-output
uv run python -X utf8 -m modules.mta_strategy_recommendation.src.validate_simulated_hierarchy
python3 -B -m unittest discover -s modules/mta_strategy_recommendation/tests -p 'test_*.py'
```

The initializer reads AMC recommended attribution and touchpoint-entity aggregates without modifying them. It uses the request's hashes, window, and scope to block drift. Validation covers one Campaign Group, four Campaigns, capacity-derived new-group counts, every touchpoint bridge, budget conservation, and the missing-budget-baseline behavior. It neither validates nor generates specific Keyword/SKU allocations. The migration-source audit recorded 34 passing tests.

## Tool-Code Checks

The full-workspace audit used these read-only check categories:

- Python: parse every `.py` file with `ast.parse`.
- JavaScript: run `node --check` for every `.js` file.
- Bash: run `bash -n` for the story automator.
- Markdown: verify local links in project-authored documentation exist.
- JSON/TOML: parse actual configuration and data files.

Historical tool-layer checks are not run or counted with product verification. Use the module entry points, product tests and documentation build described on this page. One-off inspection helpers stay local and are deleted after use.

## Change Principles

- Follow [workspace file-location management](file-management.md) before adding, moving, or archiving files.
- Extend attribution capability under `modules/mta_attribution`; extend initial-strategy capability under `modules/mta_strategy_recommendation`.
- When input fields, the five-segment key, or output columns change, update code, samples, tests, and module contracts together.
- External originals in `docs/research` are not runtime inputs.
- Preserve `design-artifacts` and completed specifications as historical records; add status explanations instead of rewriting earlier intent.
- Treat `.agents`, `_bmad`, and `_bmad-output` as preserved reference assets. Do not use their workflows or scripts for Trance-0 development unless a task explicitly requests BMad.
- Do not restore the removed legacy `modules/mta` directory.

## Specification and release verification

Use [Specification Workflow and Retrieval](./specification-workflow.md) to
retrieve compact contracts and select their tests. Inspect owning metadata and
source contracts before considering a change complete. The verification workflow runs product suites and both frontend
build targets. [Deployment preflight](./backend/deployment-preflight.md) rejects
incomplete external generator checkouts before release tests.

[Backend setup](./backend/setups.md) specifies Flask and AppStack;
[Dashboard deployment](/en/dashboard/deployment) specifies static Pages and
the separate container stack. Database migration automation remains a
[planned contract](./backend/database-migrations.md), not an implemented ledger.
