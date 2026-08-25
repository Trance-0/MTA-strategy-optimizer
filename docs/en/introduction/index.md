---
title: Project Overview
description: Objectives, boundaries, workspace structure, and end-to-end workflow of Marketing ROI Analysis
compact: "Entry point for the whole project. Objectives, the three-stage attribution-to-budget approach, the current delivery boundary, workspace partitions, and the reading order into every other section. Read first when orienting; skip when you already know which module you need."
lang: en-US
---

# Project Overview

This project is intended for marketing analytics, data science, and engineering teams that need to turn historical Multi-Touch Attribution (MTA) results into advertising budget decisions for the next period.

## Overall Objective <span class="status-label status-recommendation" aria-label="Recommendation"></span>

The overall approach has three stages with clearly separated responsibilities:

1. **Historical attribution**: estimate each touchpoint's historical share of converted users, purchase count, and revenue from aggregated customer paths.
2. **Strategy initialization**: for a new Campaign, combine MTA shares, Campaign/Ad Group entity relationships, candidate targeting objects, and budget constraints to produce the Ad Group count and an explainable initial budget.
3. **Budget optimization**: predict outcomes at different budgets in a separate Ad Group-level model and maximize expected revenue within business constraints. This stage has not yet been implemented.

<DrawioDiagram base="./mta-to-budget-roadmap" alt="MTA evidence to budget strategy roadmap" />

## Current Delivery Boundary <span class="status-label status-verified" aria-label="Verified"></span>

### AMC MTA

- Current output: Markov, path-level Shapley, model comparison, reliability status, and recommended attribution shares
- Not currently included: Proof of causal incrementality or automated activation

### MTA Strategy Recommender

- Current output: New Ad Group count, Campaign budget shares, and an initial budget split equally within each Campaign
- Not currently included: Ad Group performance prediction, marginal-return estimation, or mathematically optimal budgets

### Strategy Optimizer

- Current output: Campaign budgets optimized against fitted response curves where budget variation has been observed, plus a strategy evaluation stage that checks allocation conservation and compares each strategy against observed baselines
- Not currently included: The project cannot currently claim revenue maximization or optimal return on investment (ROI); the optimizer fits an association between budget and revenue, not a causal one, and no simulator publishes a true optimal allocation to score against

Current outputs should be understood as **historical evidence and a budget starting point**, not production-grade causal attribution or automated budget optimization.

## Reading Order

1. [Project structure and data flow](./project-structure.md): directories, entry points, and the stage-by-stage pipeline.
2. [Canonical data model](./data-models/index.md): the provider-independent domain model shared across attribution, strategy, and dashboard modules, and its legacy compatibility bridge.
3. [Progress and todos](./progress.md): what is implemented, what is limited, and what comes next.
4. [Backend API](./backend/index.md): live data access, model endpoints, local setup, and AppStack deployment.
5. [AMC MTA project introduction](./amc-mta-introduction.md): what the runnable attribution module does and does not claim.
6. [AMC MTA architecture](./amc-mta-architecture.md): algorithms, contracts, and output architecture.
7. [AMC MTA capability assessment](./amc-mta-capability.md): maturity, sample results, risks, and implementation order.
8. [Workspace architecture](./workspace-architecture.md): the business, knowledge, and tool layers.
9. [Development and verification guide](./development-guide.md): run the project and reproduce verification.
10. [Workspace file-location management](./file-management.md): adding, moving, and archiving files.
11. [Workspace assessment](./assessment.md): audited health, scale, and risks.
12. [Work log roster](../../worklog/index.md): who is involved, their area, and their day-by-day record.

## Entry Points by Topic

### Top-level architecture and partitions

[Workspace architecture](./workspace-architecture.md)

### Provider-independent canonical data model

[Canonical data model](./data-models/index.md)

### File locations and movement rules

[Workspace file-location management](./file-management.md)

### Runnable modules and commands

[AMC MTA module](../attribution/amc-mta-module.md)

### Per-file code-level specification

On the page describing that file: see the Source Files section of [Attribution](../attribution/index.md), [the standardized interface](../attribution/standardized-interface/index.md), [Strategy](../strategy-recommendation/module-overview/source-files.md), or [Dashboard](../dashboard/index.md)

### Campaign Group initial strategy

[Strategy Initializer](../strategy-recommendation/module-overview/)

### Initial-strategy plan and contract

[Overall model plan](../strategy-recommendation/model-plan.md)

### Current budget calculation

[Step-by-step Ad Group initial-budget calculation](../strategy-recommendation/current-budget-calculation/)

### Future budget optimization research

[Problem definition and research plan](../strategy-recommendation/optimization-plan.md)

### Input fields, paths, and cost rules

[AMC MTA data contract](../market-simulation/amc-data-contract.md)

### Markov/Shapley gaps and decision status

[Model-comparison governance](../attribution/model-governance.md)

### Individual-touchpoint reliability

[Touchpoint reliability guide](../attribution/reliability.md)

### Campaign Group data hierarchy

[Campaign Group hierarchy and finest performance grain](../research/campaign-data-hierarchy.md)

### Full file-by-file inventory

[Workspace file inventory](../../workspace-file-inventory.json)

## Workspace Partitions

### `modules/`

Attribution, standard adapter, and strategy modules; code, data, and outputs only

### `external/mta_sim_dataset/`

Pinned external MTA-SIM-dataset repository and its generator

### `script/`

Maintained project command-line entry points

### `docs/`

English documentation, preserved Chinese sources, and research originals

### `design-artifacts/`

Historical product vision

### `_bmad-output/`

Completed specifications and deferred work

### `.agents/`, `_bmad/`

Installed development tools; not on the runtime path

`modules/mta_attribution/` contains `src/` for path and attribution logic, `tests/` for automated checks, `data/` for the simulated source and derived datasets, and `outputs/` for canonical generated CSVs. `modules/mta_strategy_recommendation/` uses the same layout for its inputs, count/budget implementation, tests, and canonical initial-budget JSON.

Within `docs/`, `index.md` redirects to the active English site, `en/` contains the complete published English documentation, `zh/` preserves unpublished Chinese sources, and `research/` holds external binary originals that are not runtime inputs.

## Authority Order

Documentation under `docs/en/` states the intent this project is built to satisfy. Within that documentation, authority descends from per-file implementation specifications and data contracts, through architecture and capability assessments, project introductions, and research notes, to historical product documents and preserved specification sources. Reproducible outputs and tests are evidence that the code meets the specification; they do not redefine it.

Historical material under `design-artifacts/`, `_bmad-output/`, and `docs/zh/specifications/` records the context in which earlier decisions were made. Four-segment grains, `units_sold`, and removed `modules/mta` paths in those sources are historical, not current.

## Continue Reading

- [Market simulation and compatibility](../market-simulation/index.md)
- [Attribution model overview](../attribution/index.md)
- [Strategy optimization model](../strategy-recommendation/index.md)
- [Dashboard](../dashboard/index.md)
