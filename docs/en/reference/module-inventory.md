---
title: Module Inventory
lang: en-US
---

# Module Inventory

`modules/` contains the currently runnable business implementations. Each module manages its own code, inputs, outputs, tests, and usage documentation.

| Module | Purpose | Status | Entry point |
| --- | --- | --- | --- |
| MTA Attribution (`modules/mta_attribution/`) | Five-segment interaction attribution and dual-model diagnostics from AMC anonymous aggregated paths | Runnable attribution module | [AMC MTA module](../attribution/amc-mta-module.md) |
| MTA Standard (`modules/mta_standard/`) | Standardized MTA-SIM dataloader, four-to-five segment adapter, model interface, output contract, and evaluator | Runnable library; wraps AMC MTA without changing it | [Standardized MTA interface](../attribution/standardized-interface.md) |
| MTA Strategy Recommendation (`modules/mta_strategy_recommendation/`) | Generate the new Ad Group count and initial budget using Campaign Group as the top level | Runnable generator, canonical output, and validator are implemented | [Strategy initializer](../strategy/module-overview.md) |

## Directory Convention

```text
modules/<module>/
├── data/       # Module-specific inputs and samples
├── docs/       # Data contracts and usage documentation
├── outputs/    # Reproducible runtime results
├── scripts/    # Command-line scripts
├── src/        # Core implementation
└── tests/      # Automated tests, when present
```

For what each file receives and hands to the next, see [module and script data flow](data-flow.md). See the [English documentation home](/en/) for the current architecture, capability assessment, and reading order. External papers and references are stored under `docs/research/` and are not mixed with module runtime inputs.

`MTA Standard` follows the same convention without a `scripts/` directory, because it is a library consumed by contributors rather than a command-line pipeline.

The boundary between the attribution and strategy modules is: MTA Attribution outputs five-segment touchpoint evidence within Group scope; for four fixed Campaigns under one Campaign Group, the strategy initializer produces only the new Ad Group count and budget `INITIAL_SEED`. It does not assign specific candidates or perform later optimization.

`MTA Standard` sits beside `MTA Attribution` rather than above it: it adapts MTA-SIM's four-segment contract onto the existing five-segment estimators, reproduces their numbers exactly, and adds a shared output and evaluation contract so a new model can be compared against them.

The removed legacy general-purpose MTA module is outside the current project scope. It is not restored, assessed, or used as an entry point for new development.
