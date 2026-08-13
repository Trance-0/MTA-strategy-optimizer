---
title: Module Inventory
compact: "One-table summary of the three runnable modules, their status and entry points, plus the standard `data/`, `outputs/`, `src/`, `tests/` subdirectory convention. Read for orientation; per-file specification lives under implementation."
lang: en-US
---

# Module Inventory

`modules/` contains the currently runnable business implementations. Each module owns reusable source code, inputs, outputs, and tests; all maintained commands are centralized under project-level `script/`.

| Module | Purpose | Status | Entry point |
| --- | --- | --- | --- |
| MTA Attribution (`modules/mta_attribution/`) | Shared model interface; concrete Markov, Shapley, uniform, and DNN implementations; five-segment paths and governance comparison | Runnable model package | [AMC MTA module](../attribution/amc-mta-module.md) |
| MTA Standard (`modules/mta_standard/`) | Framework-only MTA-SIM dataloader, four-to-five segment adapter, model registry and pipeline, output contract, and evaluator | Runnable framework package | [Standardized MTA interface](../attribution/standardized-interface/) |
| MTA Strategy Recommendation (`modules/mta_strategy_recommendation/`) | Generate the new Ad Group count and initial budget using Campaign Group as the top level | Runnable generator, canonical output, and validator are implemented | [Strategy initializer](../strategy_recommendation/module-overview.md) |

## Directory Convention

Every `modules/<module>/` directory uses these standard subdirectories:

| Directory | Responsibility |
| --- | --- |
| `data/` | Module-specific inputs and samples |
| `outputs/` | Reproducible runtime results |
| `src/` | Core implementation |
| `tests/` | Automated tests, when present |

For what each file receives and hands to the next, see [module and script data flow](data-flow.md). See the [English documentation home](/en/) for the current architecture, capability assessment, and reading order. External papers and references are stored under `docs/research/` and are not mixed with module runtime inputs.

The project-level `script/` directory contains the data-generation, attribution, strategy, validation, and documentation entry points. `external/mta_sim_dataset/` pins the ZheyuanWu generator used by the MTA Standard adapter.

The boundary between the attribution and strategy modules is: MTA Attribution outputs five-segment touchpoint evidence within Group scope; for four fixed Campaigns under one Campaign Group, the strategy initializer produces only the new Ad Group count and budget `INITIAL_SEED`. It does not assign specific candidates or perform later optimization.

`MTA Standard` sits beside `MTA Attribution` rather than above it: it adapts MTA-SIM's four-segment contract onto the existing five-segment estimators, reproduces their numbers exactly, and adds a shared output and evaluation contract so a new model can be compared against them.

The removed legacy general-purpose MTA module is outside the current project scope. It is not restored, assessed, or used as an entry point for new development.
