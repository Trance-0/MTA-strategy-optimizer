---
title: Recommendation Endpoint Configuration
description: Budget initialization and response-model optimization request contracts
compact: "Configures `POST /api/models/recommend` and `/api/models/optimize`: default or supplied strategy inputs, deterministic non-optimized Ad Group budget seed, research snapshot path, total budget, usage policy, Campaign floors and ceilings, campaign-scoped observed-history fitting and response-model result fields."
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


### Selected Campaign preview

`POST /api/models/optimize` also accepts `campaignId`, required `marketplace`,
and optional `datasetId`. This branch uses only the named registered dataset
or the configured legacy source; it never falls back to another source. It
ignores chart filters and fits all available history for that Campaign and
marketplace. An unknown, empty or inactive identity is refused. No artifact is written.

The backend adapts one ordinary budget-period observation into
`CampaignResponseObservation`, then fits the existing response model and solver.
Database reads join budget records to summed **non-evaluation** outcomes by run,
Campaign, marketplace, date and budget level. Registered and file inputs join
ordinary outcomes by full reporting scope and budget level. Budget and spend
are counted once while revenue is summed across observed products/touchpoints.
Missing, negative or nonfinite budget, spend or revenue is refused, as are
mixed advertisers or currencies and non-daily periods. No attribution,
similarity score or evaluation-only outcome enters fitting. Observation counts
and dates describe this exact Campaign's evidence.

The default authorized budget and per-Campaign ceiling are the largest observed
configured budget, avoiding extrapolation unless the caller explicitly supplies
a larger ceiling. Only this Campaign is optimized; unsupported fits are refused
instead of borrowing another Campaign's history. The result adds `campaign_id`,
`marketplace`, `dataset_id`, `response_observations`, and `observation_count`.
It is the revenue-maximizing allocation under the fitted model and budget limit,
not a claim of a causal or globally optimal real-world strategy.

Database observation tables whose ordinary outcomes do not identify the varied
budget levels cannot support this preview; evaluation-only arms are never
substituted for missing ordinary evidence.

The public response observation projection contains Campaign, marketplace,
currency, start/end dates, `report_date` (the start), intervention identity,
configured budget, spend and total revenue. Delivery counts are not loaded by
this adapter, are unused by the fitter, and are omitted from public observations.
