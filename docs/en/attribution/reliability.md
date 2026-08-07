---
title: AMC MTA Single-Touchpoint Attribution Reliability
lang: en-US
---

# AMC MTA Single-Touchpoint Attribution Reliability

## Purpose

This document explains how to determine whether attribution for one five-segment touchpoint and specified Outcome is reliable in the current reporting window.

Five-segment touchpoint format:

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

`IMPRESSION` and `CLICK` are independent touchpoints and must be assessed separately. The three Outcomes also create separate records: `converted_users`, `purchase_count`, and `revenue`.

Reliability consists exclusively of three Boolean criteria:

1. Is the calculation valid?
2. Is data support sufficient?
3. Are Markov and Shapley consistent?

All three criteria must pass for `RELIABLE`; any failure produces `UNRELIABLE`. High/medium/low grades are no longer used, and no other conditions are added.

## 1. Is the Calculation Valid?

Field:

```text
calculation_valid
```

New results are generated only after the complete pipeline passes these strict validations:

- AMC, Amazon Ads, Markov, and Shapley use the same window, account, and five-segment touchpoint set.
- AMC `report_start_date` and `report_end_date` are valid ISO dates, and the start is not later than the end.
- Input fields are complete; values are finite, non-negative, and satisfy their relationships.
- Shares and attributed Outcomes separately conserve for both models.
- Cost, platform performance, and efficiency metrics match.
- Touchpoints are not duplicated; after CSV field names and values are normalized, headers are non-empty and unique and every row has the complete column count.

An output record that passed validation is `true`. Any validation failure causes the pipeline to fail fast without publishing new artifacts, so an invalid preview is never written as a canonical result.

## 2. Is Data Support Sufficient?

Field:

```text
data_support_sufficient
```

The same five-segment touchpoint must simultaneously satisfy:

```text
raw_purchase_count >= 30
raw_converted_users >= 20
raw_unique_paths >= 5
```

All three conditions produce `true`; any insufficient condition produces `false`. A value exactly equal to a threshold passes.

Support is calculated from raw AMC aggregated paths. If one touchpoint repeats within one normalized path, it counts only once toward support. One path may support multiple touchpoints, so support is not required to conserve across touchpoints. Existing `FULL_SUPPORT` and `LIMITED_SUPPORT` categories both reach the minimum thresholds; `LOW_SUPPORT` does not.

## 3. Are the Two Models Consistent?

Field:

```text
models_consistent
```

For a nonzero Outcome:

```text
gap_pp = 100 × |markov_share - shapley_share|
mean_share = (markov_share + shapley_share) / 2
relative_gap = |markov_share - shapley_share| / mean_share
```

Both conditions must hold for `true`:

```text
gap_pp <= 1.0
relative_gap <= 0.20
```

Exceeding either threshold produces `false`; a value exactly equal to a threshold passes. This test uses numeric values directly and is unaffected by the ordering of `LONG_TAIL`, `SMALL`, `MEDIUM`, or `LARGE` categories. A nonzero long-tail touchpoint may therefore have `models_consistent=true` when both gap thresholds pass. Threshold comparisons use the unrounded original decimal shares retained during parsing. They do not first round to displayed values or add a tolerance; every value strictly greater than `1.0` or `0.20` fails.

When an entire Outcome is legitimately zero, `calculation_valid=true`, but `data_support_sufficient=false` and `models_consistent=false`, so the final result is unreliable.

## Final Status and Reason

Output fields:

```text
calculation_valid
data_support_sufficient
models_consistent
reliability_status
reliability_reason
```

Composition rule:

```text
calculation_valid
AND data_support_sufficient
AND models_consistent
```

When all three are true:

```text
reliability_status = RELIABLE
reliability_reason = ALL_CRITERIA_PASSED
```

When any is false:

```text
reliability_status = UNRELIABLE
```

Failure reasons use only these three codes, joined in this fixed order:

```text
CALCULATION_INVALID
INSUFFICIENT_DATA_SUPPORT
MODELS_INCONSISTENT
```

For example, insufficient support and inconsistent models produce:

```text
reliability_reason = INSUFFICIENT_DATA_SUPPORT|MODELS_INCONSISTENT
```

## Where to Inspect the Fields

The five fields are written to three dual-model artifacts:

```text
amc_mta_model_comparison_touchpoints.csv
amc_mta_model_comparison_summary.csv
amc_mta_recommended_attribution.csv
```

The same `touchpoint + outcome` in the recommendation and touchpoint-comparison tables must have exactly the same five values. The summary aggregates by Outcome: it separately applies AND to `calculation_valid`, `data_support_sufficient`, and `models_consistent` over all touchpoints under that Outcome, then uses the same three-way AND formula to determine summary reliability.

The touchpoint table retains `gap_pp`, `relative_gap`, and the three raw-support amounts. The summary retains TVD, Spearman, and Top-K overlap. Those summary metrics do not enter reliability calculation; legacy statuses and gap grades are not in the current schema.

Raw Markov and Shapley single-model results do not contain reliability fields because reliability requires both models and raw AMC support.

The recommendation table also contains `recommended_value`. It does not enter the reliability calculation; it only converts final status into a more direct display. A reliable record for a nonzero Outcome uses the single Markov `official_share`, while an unreliable record uses the ascending closed interval `[low,high]` of both model shares. A zero Outcome has no interpretable distribution, so the field is empty; dual-zero shares for a nonzero Outcome may be represented as `[0.0,0.0]`.

## Current Sample

The current sample has 17 five-segment touchpoints and three Outcomes, or 51 touchpoint results:

- 51 records with `calculation_valid=true`;
- 51 records with `data_support_sufficient=true`;
- 51 records with `models_consistent=true`;
- final result `51 RELIABLE / 0 UNRELIABLE`;
- all three Outcome summaries are `RELIABLE`.

`RELIABLE` means only that the current window meets the three attribution-evidence criteria above. It does not mean causal incrementality, long-term stable contribution, or that results are suitable for automatic budget or activation execution.
