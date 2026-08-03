---
title: Datasets
description: The MTA-SIM contract, this project's inputs, and compatibility boundaries
lang: en-US
---

# Datasets

This page adopts the documentation categories of the [Trance-0/MTA-SIM-dataset data contract](https://github.com/Trance-0/MTA-SIM-dataset/blob/main/ZheyuanWu/docs/DATA_CONTRACT.md) and [generation flow](https://github.com/Trance-0/MTA-SIM-dataset/blob/main/ZheyuanWu/docs/dataset-creation/generation-flow.md), and explains how they differ from this repository's current inputs.

## MTA-SIM's Three Logical Tables <span class="status-label status-external" aria-label="External"></span>

| Table | Purpose | Training boundary |
| --- | --- | --- |
| `amc_path_report` | Aggregated, ordered customer paths and observed Outcomes | Primary path-attribution input |
| `amazon_ads_daily_touchpoint_performance` | Daily touchpoint delivery, cost, and platform-reported results | Optional feature, diagnostic, or reporting input |
| `simulation_ground_truth` | Simulator-known incremental removal effects and credit shares for touchpoints | **Evaluation only; prohibited as a training feature** |

Purchases in the path table and platform-reported purchases in the Ads table must not be added together; they are Outcomes with different semantics.

## This Repository's Current Inputs <span class="status-label status-verified" aria-label="Verified"></span>

| File | Granularity | Role |
| --- | --- | --- |
| `amc_mta_path_report_raw_sample.csv` | Aggregated path | Markov and Shapley input |
| `amazon_ads_report_sample.csv` | Date × touchpoint | Cost and diagnostic metrics |
| `amc_touchpoint_entity_aggregate_sample.csv` | Touchpoint × delivery entity | Bridge from touchpoint to Campaign/historical Ad Group |
| `amc_mta_recommended_attribution.csv` | Touchpoint × Outcome | Attribution input for the strategy initializer |
| `strategy_request.json` | Campaign Group request | Total budget, Outcome weights, and capacity rules |
| `candidate_pool.json` | Campaign candidate counts | Calculate the new Ad Group count |

## Why the Two Sets of Simulated Results Are Not Directly Compatible <span class="status-label status-verified" aria-label="Verified"></span>

The path-table column names currently match, but the touchpoint contracts differ:

| Item | MTA-SIM | This repository's current AMC MTA |
| --- | --- | --- |
| Normalized touchpoint | Four segments: `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE` | Five segments: adds `INTERACTION_TYPE` |
| Ads-specific fields | Includes `unitsSold` | Includes `interaction_type` and `cost_type`, but not `unitsSold` |
| Impression/click representation | Aggregated into four-segment touchpoint performance | Explicitly distinguished as the fifth segment of the touchpoint key |
| Strategy Bridge | Not one of the three core tables | Requires an additional entity-aggregate table |

Consequently, “derived from the same source-code concept” does not mean “has the same schema.” Passing four-segment touchpoint paths directly to an implementation that requires five-segment keys breaks the join between path and performance tables and leaves no way to determine `IMPRESSION` versus `CLICK`.

## Recommended Adaptation <span class="status-label status-recommendation" aria-label="Recommendation"></span>

Build an explicit Dataset Adapter:

1. Validate the input version and column order.
2. Generate `INTERACTION_TYPE` from real fields; never guess a default.
3. Preserve `unitsSold` as an optional diagnostic field instead of forcing a mapping.
4. Generate the entity Bridge required by this project.
5. Run attribution only after the complete data package passes validation.
6. Isolate `simulation_ground_truth` in the evaluation workflow.

This lets the two generated tables support prediction and attribution validation while preserving Ground Truth as an independent “answer table.”
