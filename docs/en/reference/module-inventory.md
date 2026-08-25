---
title: Module Inventory
compact: "Summary of the four runnable modules, including strategy evaluation contracts, contributed-model adapters, status, entry points, and the standard data, outputs, src, and tests convention. Read for orientation; per-file specifications live on owning pages."
lang: en-US
---

# Module Inventory

`modules/` contains the currently runnable business implementations. Each module owns reusable source code, inputs, outputs, and tests; all maintained commands are centralized under project-level `script/`.

## MTA Attribution (`modules/mta_attribution/`)

- **Purpose:** Shared model interface; concrete Markov, Shapley, uniform, and DNN implementations; five-segment paths and governance comparison
- **Status:** Runnable model package
- **Entry point:** [AMC MTA module](../attribution/amc-mta-module.md)

## MTA Standard (`modules/mta_standard/`)

- **Purpose:** Framework-only MTA-SIM dataloader, four-to-five segment adapter, model registry and pipeline, output contract, and evaluator
- **Status:** Runnable framework package
- **Entry point:** [Standardized MTA interface](../attribution/standardized-interface/)

## MTA Strategy Recommendation (`modules/mta_strategy_recommendation/`)

- **Purpose:** Generate the new Ad Group count and initial budget using Campaign Group as the top level, and optimize Campaign budgets against fitted response curves where budget variation has been observed
- **Status:** Runnable generator, canonical output, and validator are implemented; the Campaign response model and constrained budget optimizer are implemented, and Ad Group-level optimization is not
- **Entry point:** [Strategy initializer](../strategy-recommendation/module-overview/) and [Campaign budget optimizer](../strategy-recommendation/campaign-budget-optimizer.md)

## MTA Strategy Evaluation (`modules/mta_strategy_evaluation/`)

- **Purpose:** Project strategy artifacts into one `StrategyOutput` contract, check allocation conservation, compare observed baselines, isolate unavailable strategy ground truth, and adapt contributed response models without modifying contributor files
- **Status:** Runnable evaluation package and fourth pipeline stage; the current contributed network is retained with its negative held-out fit as a blocking caveat
- **Entry point:** [Strategy evaluation](../strategy-evaluation/) and [running an evaluation](../strategy-evaluation/running-an-evaluation.md)

## Directory Convention

Every `modules/<module>/` directory uses these standard subdirectories:

### `data/`

Module-specific inputs and samples.

### `outputs/`

Reproducible runtime results.

### `src/`

Core implementation.

### `tests/`

Automated tests, when present.

For what each file receives and hands to the next, see [module and script data flow](data-flow.md). See the [English documentation home](/en/) for the current architecture, capability assessment, and reading order. External papers and references are stored under `docs/research/` and are not mixed with module runtime inputs.

The project-level `script/` directory contains the data-generation, attribution, strategy, validation, and documentation entry points. `external/mta_sim_dataset/` pins the ZheyuanWu generator used by the MTA Standard adapter.

The boundary between the attribution and strategy modules is: MTA Attribution outputs five-segment touchpoint evidence within Group scope; for four fixed Campaigns under one Campaign Group, the strategy initializer produces only the new Ad Group count and budget `INITIAL_SEED`. It does not assign specific candidates or perform later optimization.

`MTA Standard` sits beside `MTA Attribution` rather than above it: it validates MTA-SIM's native five-segment contract, retains an explicit bridge for historical four-segment fixtures, reproduces existing model numbers exactly, and adds shared output and evaluation contracts.

The removed legacy general-purpose MTA module is outside the current project scope. It is not restored, assessed, or used as an entry point for new development.
