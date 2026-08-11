---
title: Project Overview
description: Objectives, boundaries, and end-to-end workflow of Marketing ROI Analysis
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

| Component | Current output | Not currently included |
| --- | --- | --- |
| AMC MTA | Markov, path-level Shapley, model comparison, reliability status, and recommended attribution shares | Proof of causal incrementality or automated activation |
| MTA Strategy Recommender | New Ad Group count, Campaign budget shares, and an initial budget split equally within each Campaign | Ad Group performance prediction, marginal-return estimation, or mathematically optimal budgets |
| Strategy Optimizer | Not yet implemented | The project cannot currently claim revenue maximization or optimal return on investment (ROI) |

Current outputs should be understood as **historical evidence and a budget starting point**, not production-grade causal attribution or automated budget optimization.

## Continue Reading

- [Project structure and data flow](./project-structure.md)
- [Progress and todos](./progress.md)
- [Datasets and compatibility](../datasets/index.md)
- [Attribution model overview](../attribution/index.md)
- [Strategy optimization model](../strategy/index.md)
