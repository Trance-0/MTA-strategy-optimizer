---
title: Module Inventory
lang: en-US
---

# Module Inventory

`modules/` contains the currently runnable business implementations. Each module manages its own code, inputs, outputs, tests, and usage documentation.

| Module | Purpose | Status | Entry point |
| --- | --- | --- | --- |
| AMC MTA | Five-segment interaction attribution and dual-model diagnostics from AMC anonymous aggregated paths | Runnable attribution module | [AMC MTA module](../attribution/amc-mta-module.md) |
| MTA Strategy Initializer | Generate the new Ad Group count and initial budget using Campaign Group as the top level | Runnable generator, canonical output, and validator are implemented | [Strategy initializer](../strategy/module-overview.md) |

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

See the [English documentation home](/en/) for the current architecture, capability assessment, and reading order. External papers and references are stored under `docs/research/` and are not mixed with module runtime inputs.

The boundary between the two modules is: AMC MTA outputs five-segment touchpoint evidence within Group scope; for four fixed Campaigns under one Campaign Group, the strategy initializer produces only the new Ad Group count and budget `INITIAL_SEED`. It does not assign specific candidates or perform later optimization.

The removed legacy general-purpose MTA module is outside the current project scope. It is not restored, assessed, or used as an entry point for new development.
