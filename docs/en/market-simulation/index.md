---
title: Market Simulation
description: The MTA-SIM contract, this project's inputs, and compatibility boundaries
compact: "Routing hub contrasting upstream MTA-SIM tables `amc_path_report`, `amazon_ads_daily_touchpoint_performance`, `simulation_ground_truth` with local inputs including `strategy_request.json` and `candidate_pool.json`. Explains four-segment versus five-segment incompatibility and what `modules/mta_standard/` adapter implements. Read to pick the right dataset page."
lang: en-US
---

# Market Simulation

This page adopts the documentation categories of the [Trance-0/MTA-SIM-dataset data contract](https://github.com/Trance-0/MTA-SIM-dataset/blob/main/ZheyuanWu/docs/DATA_CONTRACT.md) and [generation flow](https://github.com/Trance-0/MTA-SIM-dataset/blob/main/ZheyuanWu/docs/dataset-creation/generation-flow.md), and explains how they differ from this repository's current inputs.

For the translated operational schema references, see the [Product data model](product-data-model.md) and [Campaign data model](campaign-data-model.md). Each page includes editable, theme-aware Draw.io diagrams.

## MTA-SIM's Three Logical Tables <span class="status-label status-external" aria-label="External"></span>

### `amc_path_report`

- Purpose: Aggregated, ordered customer paths and observed Outcomes
- Training boundary: Primary path-attribution input

### `amazon_ads_daily_touchpoint_performance`

- Purpose: Daily touchpoint delivery, cost, and platform-reported results
- Training boundary: Optional feature, diagnostic, or reporting input

### `simulation_ground_truth`

- Purpose: Simulator-known incremental removal effects and credit shares for touchpoints
- Training boundary: **Evaluation only; prohibited as a training feature**

Purchases in the path table and platform-reported purchases in the Ads table must not be added together; they are Outcomes with different semantics.

## This Repository's Current Inputs <span class="status-label status-verified" aria-label="Verified"></span>

### `amc_mta_path_report_raw_sample.csv`

- Granularity: Aggregated path
- Role: Markov and Shapley input

### `amazon_ads_report_sample.csv`

- Granularity: Date × touchpoint
- Role: Cost and diagnostic metrics

### `amc_touchpoint_entity_aggregate_sample.csv`

- Granularity: Touchpoint × delivery entity
- Role: Bridge from touchpoint to Campaign/historical Ad Group

### `amc_mta_recommended_attribution.csv`

- Granularity: Touchpoint × Outcome
- Role: Attribution input for the strategy initializer

### `strategy_request.json`

- Granularity: Campaign Group request
- Role: Total budget, Outcome weights, and capacity rules

### `candidate_pool.json`

- Granularity: Campaign candidate counts
- Role: Calculate the new Ad Group count

## Why the Two Sets of Simulated Results Are Not Directly Compatible <span class="status-label status-verified" aria-label="Verified"></span>

The path-table column names currently match, but the touchpoint contracts differ:

| Item | MTA-SIM | This repository's current AMC MTA |
| --- | --- | --- |
| Normalized touchpoint | Four segments: `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE` | Five segments: adds `INTERACTION_TYPE` |
| Ads-specific fields | Includes `unitsSold` | Includes `interaction_type` and `cost_type`, but not `unitsSold` |
| Impression/click representation | Aggregated into four-segment touchpoint performance | Explicitly distinguished as the fifth segment of the touchpoint key |
| Strategy Bridge | Not one of the three core tables | Requires an additional entity-aggregate table |

Consequently, “derived from the same source-code concept” does not mean “has the same schema.” Passing four-segment touchpoint paths directly to an implementation that requires five-segment keys breaks the join between path and performance tables and leaves no way to determine `IMPRESSION` versus `CLICK`.

## Implemented Adaptation <span class="status-label status-verified" aria-label="Verified"></span>

The pinned submodule and explicit Dataset Adapter now:

1. Validate the input version and column order.
2. Generate `INTERACTION_TYPE` from real fields; never guess a default.
3. Preserve `unitsSold` as an optional diagnostic field instead of forcing a mapping.
4. Keep entity-Bridge generation as a separate strategy integration boundary.
5. Run attribution only after the complete data package passes validation.
6. Isolate `simulation_ground_truth` in the evaluation workflow.

The adapter runs the ZheyuanWu generator, preserves its original four-segment files, aggregates daily path windows into one local model scope, and preserves Ground Truth as an independent answer table. See [Generate MTA-SIM data](../introduction/environment/mta-sim-generation.md).

## Adapter Status <span class="status-label status-verified" aria-label="Verified"></span>

`modules/mta_standard/` implements the generation boundary and items 1, 2, 3, 5, and 6 above:

### Run the reviewed generator source

Where it is implemented: `mta_sim_generator_adapter` invokes the pinned `external/mta_sim_dataset/ZheyuanWu` pipeline.

### 1. Validate column order

Where it is implemented: `dataloader` requires the exact contract header for each table.

### 2. Never guess `INTERACTION_TYPE`

Where it is implemented: `SimulatorConfig` supplies it explicitly and rejects missing, ambiguous, or colliding mappings.

### 3. Preserve `unitsSold`

Where it is implemented: Kept verbatim on the annotated performance rows as a diagnostic.

### 5. Validate before attributing

Where it is implemented: Loading fails before any model runs; `validate_standard_output` guards the results.

### 6. Isolate Ground Truth

Where it is implemented: `MtaSimDataset` has no ground-truth field and the loader accepts no ground-truth path.

Item 4, the Campaign and Ad Group entity Bridge, remains the responsibility of the strategy module and is unchanged.

See [the standardized MTA interface](../attribution/standardized-interface/) for the adapter's contract, failure modes, and evaluation metrics.
