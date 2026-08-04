---
title: Development and Verification Guide
lang: en-US
---

# Development and Verification Guide

## Environment

- Python 3.10 or newer;
- Node.js only for checking or running `_bmad/wds/scripts/` and the documentation site;
- Git;
- no third-party Python package is required by AMC MTA itself.

Some installed-tool tests use `pytest`, but the audited repository had no unified Python dependency file. Installing it is unnecessary unless those `.agents` tool tests are being maintained.

## Run the Business Pipeline

```bash
python3 -B modules/mta_attribution/run_pipeline.py
python3 modules/mta_attribution/scripts/validate_data_alignment.py
```

The pipeline derives its window from the earliest through latest Amazon Ads `reportDate`; adding data should not require changing configured dates. See [AMC MTA execution](../environment/amc-mta-usage.md) for custom input and output arguments.

Canonical attribution output is stored in:

```text
modules/mta_attribution/outputs/attribution/
```

Five CSV files are retained as the canonical model/governance outputs. Other generated output is excluded by `.gitignore`.

## Run Business Tests

```bash
python3 -m unittest discover -s modules/mta_attribution/tests -p 'test*.py'
```

The migration-source audit recorded 107 passing tests. Always treat the current test run, rather than that historical count, as ground truth.

## Validate the Campaign Group Initial-Strategy Sample

```bash
python3 -B modules/mta_strategy_recommendation/scripts/generate_initial_budget.py --check-output
python3 modules/mta_strategy_recommendation/scripts/validate_simulated_hierarchy.py
python3 -B -m unittest discover -s modules/mta_strategy_recommendation/tests -p 'test_*.py'
```

The initializer reads AMC recommended attribution and touchpoint-entity aggregates without modifying them. It uses the request's hashes, window, and scope to block drift. Validation covers one Campaign Group, four Campaigns, capacity-derived new-group counts, every touchpoint bridge, budget conservation, and the missing-budget-baseline behavior. It neither validates nor generates specific Keyword/SKU allocations. The migration-source audit recorded 34 passing tests.

## Validate BMad Configuration

```bash
python3 -m unittest discover -s _bmad/scripts/tests -p 'test*.py'
```

The source audit recorded one passing configuration test. `_bmad/config.toml` and `_bmad/config.user.toml` are installer-managed; persistent overrides belong under `_bmad/custom/`.

## Tool-Code Checks

The full-workspace audit used these read-only check categories:

```text
Python: ast.parse every .py file
JavaScript: node --check every .js file
Bash: bash -n story-automator
Markdown: existence of local links in project-authored documentation
JSON/TOML: parse real configuration and data files
```

Recorded tool-layer limitations were:

- one plugin-naming assertion failure in `.agents/skills/bmad-module-builder/scripts/tests/test-scaffold-standalone-module.py`;
- an undeclared `pytest` dependency in `.agents/skills/bmad-workflow-builder/scripts/tests/test_memlog.py`.

These belong to installed-tool maintenance and should not be merged into AMC MTA regression results.

## Change Principles

- Follow [workspace file-location management](file-management.md) before adding, moving, or archiving files.
- Extend attribution capability under `modules/mta_attribution`; extend initial-strategy capability under `modules/mta_strategy_recommendation`.
- When input fields, the five-segment key, or output columns change, update code, samples, tests, and module contracts together.
- External originals in `docs/research` are not runtime inputs.
- Preserve `design-artifacts` and completed specifications as historical records; add status explanations instead of rewriting earlier intent.
- Treat `.agents` and `_bmad` as installed tool assets; determine whether a problem belongs to project customization or an upstream package before editing them.
- Do not restore the removed legacy `modules/mta` directory.

## Engineering Processes Not Present

The audited repository had no continuous integration/deployment, container configuration, deployment manifest, database migration, web service, or package-publication configuration. There is therefore no production-deployment procedure to document. Productionization should begin with dependency locking and a continuous-integration test gate.
