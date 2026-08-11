---
title: Development and Verification Guide
lang: en-US
---

# Development and Verification Guide

## Environment

- Python 3.10 or newer;
- Node.js only for the documentation site and its maintained root `script/` helpers;
- Git;
- no third-party Python package is required by AMC MTA itself.

Preserved `.agents` and `_bmad` files are historical tool assets. Their scripts and tests are not part of the Trance-0 development or verification workflow.

## Run the Business Pipeline

```bash
uv run python -X utf8 -B script/run_pipeline.py
uv run python -X utf8 script/validate_data_alignment.py
```

The pipeline derives its window from the earliest through latest Amazon Ads `reportDate`; adding data should not require changing configured dates. See [AMC MTA execution](../environment/amc-mta-usage.md) for custom input and output arguments.

Canonical attribution output is stored in:

Attribution outputs are written under `modules/mta_attribution/outputs/attribution/`.

Five CSV files are retained as the canonical model/governance outputs. Other generated output is excluded by `.gitignore`.

## Run Business Tests

```bash
python -X utf8 -B -m unittest discover -s modules/mta_attribution/tests -t . -p 'test_*.py'
python -X utf8 -B -m unittest discover -s modules/mta_standard/tests -t . -p 'test_*.py'
python -X utf8 -B -m unittest discover -s modules/mta_strategy_recommendation/tests -t . -p 'test_*.py'
```

The migration-source audit recorded 107 passing tests. Always treat the current test run, rather than that historical count, as ground truth.

## Validate the Campaign Group Initial-Strategy Sample

```bash
uv run python -X utf8 -B script/generate_initial_budget.py --check-output
uv run python -X utf8 script/validate_simulated_hierarchy.py
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

Historical tool-layer checks are not run or counted with product verification. Future development uses the module tests, maintained root scripts, and documentation build described on this page.

## Change Principles

- Follow [workspace file-location management](file-management.md) before adding, moving, or archiving files.
- Extend attribution capability under `modules/mta_attribution`; extend initial-strategy capability under `modules/mta_strategy_recommendation`.
- When input fields, the five-segment key, or output columns change, update code, samples, tests, and module contracts together.
- External originals in `docs/research` are not runtime inputs.
- Preserve `design-artifacts` and completed specifications as historical records; add status explanations instead of rewriting earlier intent.
- Treat `.agents`, `_bmad`, and `_bmad-output` as preserved reference assets. Do not use their workflows or scripts for Trance-0 development unless a task explicitly requests BMad.
- Do not restore the removed legacy `modules/mta` directory.

## Engineering Processes Not Present

The audited repository had no continuous integration/deployment, container configuration, deployment manifest, database migration, web service, or package-publication configuration. There is therefore no production-deployment procedure to document. Productionization should begin with dependency locking and a continuous-integration test gate.
