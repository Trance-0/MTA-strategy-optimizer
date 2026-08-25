---
title: Recommendation Endpoint Configuration
description: Budget initialization and response-model optimization request contracts
compact: "Configures `POST /api/models/recommend` and `/api/models/optimize`: default or supplied strategy inputs, deterministic non-optimized Ad Group budget seed, research snapshot path, total budget, usage policy, Campaign floors and ceilings, and response-model result fields."
lang: en-US
---

# Recommendation Endpoint Configuration

## Deterministic Initializer

Call `POST /api/models/recommend`. An empty object reads the committed strategy
request, candidate pool, recommended attribution, and entity bridge. A caller
may instead supply `request`, `candidatePool`, `attributionRows`, and
`entityRows` as JavaScript Object Notation (JSON) values with the same
documented module schemas.

This result initializes Campaign and Ad Group counts and budgets. It always
returns `is_optimized: false`; it does not fit a response curve and must not be
described as an optimum.

## Campaign Optimizer

Call `POST /api/models/optimize`. `researchSnapshot` may name a
`simulation_research.json`; otherwise the endpoint uses the file under
`MTA_SIM_DATA_DIR`. The snapshot must observe the same Campaign at enough
distinct budget levels to fit its response.

`totalBudget` must be positive. When omitted, it is the sum of the configured
baseline allocations. `budgetUsagePolicy` is either `SPEND_FULL_BUDGET` or
`SPEND_UP_TO_BUDGET`. `minimumBudget` defaults to zero and `maximumBudget` may
be omitted. Floors and ceilings apply to each Campaign.

The response contains the currency, Initial Strategy, optimized strategy,
fitted response models, and observation count. Attribution is not a fitting
input: it may explain the Initial Strategy, but the optimizer learns only from
historical budget, spend, and revenue observations.
