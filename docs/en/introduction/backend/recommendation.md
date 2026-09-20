---
title: Recommendation Endpoint Configuration
description: Budget initialization and response-model optimization request contracts
compact: "Configures `POST /api/models/recommend` and `/api/models/optimize`: default or supplied strategy inputs, deterministic non-optimized Ad Group budget seed, research snapshot path, total budget, usage policy, Campaign floors and ceilings, initialBudget and similarityThreshold controls, null-budget-level outcome joining, lossy GENERIC provider mapping, full-history transfer and empirical fallback and response-model result fields."
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

`POST /api/models/optimize` accepts `campaignId`, required `marketplace`, optional
`datasetId`, and `historyMode` (`full` by default or `campaign`). Only the named
source is read. Full mode searches its entire recorded date range for comparable
Campaigns with the same advertiser, marketplace, currency, provider and ad product;
campaign mode uses the target alone. Chart dates and similarity-display thresholds
do not truncate this evidence. Unknown or inactive targets are refused.

Ordinary outcomes are aggregated before joining to budgets on run, Campaign,
advertiser, marketplace, currency, date and budget level. A null outcome budget
level denotes the day's ordinary observation under whichever single budget arm
was active: the simulator emits exactly one budget observation per
Campaign-day, so a null-level outcome joins that day's budget row at any level.
Exact explicit-level outcomes take precedence over the null-level fallback.
Registered/file records follow the same rule using complete reporting scopes.
Evaluation-only outcomes are never read. Invalid or unmatched rows are excluded,
not allowed to invalidate the entire history; repeated budget identities remain
an error. All model observations must be finite, nonnegative and daily.

Compatibility filtering compares the source's raw provider profile strings, so
a synthetic profile such as `SYNTHETIC_FULL` only ever matches itself. The
serialized observation then maps that profile to the canonical `Provider`
vocabulary lossily — `AMAZON_ADS` stays itself, everything else becomes
`GENERIC` — mirroring the research adapter, instead of refusing the request.

Fit the target's own usable history first. If it cannot support a response curve,
full mode fits the comparable history and labels the transferred response
`POOLED_TRANSFER`, retaining the donor Campaign identifiers. The allocation always
belongs only to the selected Campaign. Donors retain their original identities in
`response_observations`; `history_selection` reports the mode, target and reference
counts and donor identifiers. No cross-currency or cross-account transfer occurs.

When valid observations exist but lack sufficient budget variation for a curve,
return a successful `HISTORICAL_BASELINE` recommendation with `is_optimized: false`.
Its `historical_recommendation` contains the target, recommended budget, observed
mean spend and revenue, and an explicit insufficient-variation explanation. Use
target observations when available, otherwise the comparable pool. Choose the
observed budget with greatest mean revenue (ties choose the smaller budget),
within the authorized budget and floors/ceilings. Never claim predicted uplift
or a fitted optimum for this fallback. No valid evidence or no feasible observed
budget still yields an actionable refusal.

Default authorization and ceiling use the maximum valid selected historical
budget. `initial_strategy` and any optimized allocation name only the target.
Public response observations expose original Campaign identity, marketplace,
currency, dates including `report_date`, intervention identity, budget, spend and
ordinary revenue; unavailable delivery counts are omitted. No artifact is written.


#### Initial budget and optimizer similarity threshold

Scoped requests accept optional `initialBudget` (finite positive number) and
`similarityThreshold` (finite number from zero to one, default zero). Blank or
omitted initial budget keeps the historical comparison baseline. A supplied
initial budget replaces the target initial/current allocation and marks its
basis `USER_SPECIFIED`; it does not change the authorized budget or ceiling.
The response's `initial_strategy` records the effective value.

Full-history references keep the existing exact account, marketplace, currency,
provider and ad-product boundaries. Within those boundaries, donor observations
must have budget proximity `max(0, 1 - abs(budget - reference) / max(budget, reference, 1))`
at least the threshold. The reference is `initialBudget` when supplied, otherwise
the target's positive configured baseline from metadata, falling back to the mean
of its valid positive budget records. Own observations are never threshold-filtered.
`history_selection` reports `similarity_threshold` and `reference_budget`.
In campaign-only mode the threshold has no effect. No surviving evidence yields
an actionable refusal. These selection parameters do not become model features.

When a Campaign has no budget observation of its own, a supplied `initialBudget`
is sufficient to initialize it. The selected Campaign's provider and ad product
setup define the compatible touchpoint-history segment; donor observations supply
the empirical reference, while the allocation and recommendation remain named
for the selected Campaign. The supplied budget becomes the authorized default
and is never silently replaced by a donor's observed budget.
