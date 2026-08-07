---
title: AMC MTA Canonical Output Index
lang: en-US
---

# AMC MTA Canonical Output Index

The five canonical CSV files are in `modules/mta_attribution/outputs/attribution/`. They share five-segment touchpoint semantics but have different responsibilities. Do not mix files from different runs, and do not interpret `RELIABLE` as causal validity.

## Recommended Reading Order

| Order | File | Granularity and primary key | Purpose |
| --- | --- | --- | --- |
| 1 | `amc_markov_attribution_results.csv` | One row per five-segment `touchpoint` | Three sets of attribution, Ads performance, cost, and efficiency from the official display model |
| 2 | `amc_shapley_attribution_results.csv` | One row per five-segment `touchpoint` | Reference-model results used to assess model sensitivity |
| 3 | `amc_mta_model_comparison_touchpoints.csv` | `touchpoint + outcome`; currently 51 rows | Compare shares, gaps, raw support, and touchpoint-level reliability |
| 4 | `amc_mta_model_comparison_summary.csv` | `outcome`; always three rows | Summarize TVD, Spearman, Top-K, and overall reliability |
| 5 | `amc_mta_recommended_attribution.csv` | `touchpoint + outcome`; currently 51 rows | Provide the official Markov value, Shapley reference value, and final display value |

`touchpoint` already contains the interaction type; the separate `interaction_type` field makes filtering easier. Both fields must agree. The three Outcomes are `converted_users`, `purchase_count`, and `revenue`.

## Field Groups

Each single-model file has 18 columns:

- Identity: `attribution_model`, `touchpoint`, `interaction_type`.
- Share: `converted_user_share`, `purchase_count_share`, `revenue_share`.
- Attributed value: `attributed_converted_users`, `attributed_purchase_count`, `attributed_revenue`.
- Ads: `impressions`, `clicks`, `cost`, `reported_purchases`, `reported_sales`.
- Efficiency: `roas`, `roi`, `cpa`, `cost_per_converted_user`.

The touchpoint-comparison file has 14 columns. In addition to the primary key and both model shares, it contains `gap_pp`, `relative_gap`, three raw-support values, and five reliability fields. The 13-column summary contains the reporting window, maximum path gap, touchpoint count, TVD, Spearman, Top-K overlap, and five reliability fields. The 15-column recommendation file contains `official_model/share`, `recommended_value`, `benchmark_model/share`, the gap, and five reliability fields. See the [governance specification](model-governance.md) for exact field order.

## Interpretation Limits

- `official_model` is fixed to Markov; Shapley is a reference only.
- `RELIABLE` means only that the current window passes the three criteria of calculation validity, data support, and model consistency.
- An interval in `recommended_value` is the range of both model shares, not a confidence interval.
- TVD, Spearman, and Top-K in the summary are diagnostic only and do not enter the reliability calculation.
- Efficiency metrics are empty for zero-cost rows. CPA-style metrics are also empty when their denominator is zero. Non-billable interactions do not copy cost.
- None of the five outputs is a budget allocation, automated activation instruction, or causal-incrementality conclusion.

See the [data contract](../datasets/amc-data-contract.md) for input, conservation, and cost rules, and the [complete usage guide](complete-guide.md) for the full review process.
