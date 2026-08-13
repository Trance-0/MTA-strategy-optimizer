---
title: AMC MTA Dual-Model Comparison and Reliability Specification
compact: "Source of truth for exact column order of the 14-column touchpoint comparison, 13-column summary, and 15-column recommendation CSVs. Defines gap_pp, relative_gap, tvd, spearman_rho, top_k_overlap_rate, and the `[low,high]` recommended_value union type."
lang: en-US
source_files: modules/mta_attribution/src/attribution_model_comparison.py
---

# AMC MTA Dual-Model Comparison and Reliability Specification

This document is the source of truth for current Markov and path-level Shapley comparison outputs.

## Model Roles

- Markov is the official display model and measures path order and transition dependence.
- Path-level Shapley is the reference model and measures participation by unique touchpoints in a path.
- Neither is a causal-incrementality model. They are not averaged, and one Outcome cannot replace another.
- The three Outcomes are `converted_users`, `purchase_count`, and `revenue`.

## Strict Input Validation

Before comparison, leading and trailing whitespace is removed from field names and values while spaces inside strings are preserved. The resulting header must equal the 18-column contract exactly and may contain neither empty nor duplicate names; each row must have the same number of columns as the header. Touchpoint sets must match and contain no duplicate rows. Shares and attributed values must be finite and non-negative, and platform performance, cost, and efficiency fields must match. Shares for each nonzero Outcome separately conserve to 1, attributed values conserve to AMC totals, and a zero Outcome must be zero in both models. The AMC report must also contain exactly one valid date window. Any invalid input raises `ValueError` and fails fast without publishing partial results. A file-publishing failure continues to raise the original `OSError`, and the atomic publishing layer restores the entire old artifact group. Headers and values in all five canonical outputs remain normalized without leading or trailing whitespace.

## Touchpoint Gap

For the same touchpoint and Outcome:

$$
\begin{aligned}
g_{\mathrm{pp}}&=100\lvert m-s\rvert,\\
\bar{s}&=\frac{m+s}{2},\\
g_{\mathrm{rel}}&=
\begin{cases}
0,&\bar{s}=0,\\
\dfrac{\lvert m-s\rvert}{\bar{s}},&\bar{s}>0,
\end{cases}
\end{aligned}
$$

Here, $m$ and $s$ are the Markov and Shapley shares for the same touchpoint and Outcome.

Display values may be rounded, but model consistency uses the original decimal shares retained during parsing, without adding epsilon.

## Three Reliability Criteria

Reliability is composed exclusively by AND over these three Booleans:

1. `calculation_valid`: is `true` in current canonical artifacts because rows are generated only after all strict validation passes.
2. `data_support_sufficient`: the Outcome is nonzero and `raw_purchase_count >= 30`, `raw_converted_users >= 20`, and `raw_unique_paths >= 5`.
3. `models_consistent`: the Outcome is nonzero and exact `gap_pp <= 1.0` and `relative_gap <= 0.20`.

When all three are true, `reliability_status=RELIABLE` and the reason is `ALL_CRITERIA_PASSED`; otherwise, status is `UNRELIABLE`. Failed reasons are joined with `|` in the fixed order `CALCULATION_INVALID`, `INSUFFICIENT_DATA_SUPPORT`, `MODELS_INCONSISTENT`. The latter two Booleans are `false` for a zero Outcome.

## Overall Evidence

The summary retains only three overall descriptive metrics, none of which enters the reliability decision:

- `tvd = 0.5 × Σ|M-S|`;
- Spearman rho, using average ranks for ties and empty when undefined;
- `top_k_overlap_rate`, where `k=min(5,touchpoint_count)` and ties are sorted by the normalized touchpoint key.

For all touchpoints under one Outcome, the summary separately AND-aggregates the three underlying Booleans, then reuses the same reliability composition.

## Exact Output Contract

Touchpoint comparison: 14 columns and currently 51 sample rows:

```csv
touchpoint,outcome,markov_share,shapley_share,gap_pp,relative_gap,raw_unique_paths,raw_converted_users,raw_purchase_count,calculation_valid,data_support_sufficient,models_consistent,reliability_status,reliability_reason
```

Overall summary: 13 columns and currently 3 sample rows:

```csv
outcome,report_start_date,report_end_date,max_touchpoint_gap_days,touchpoint_count,tvd,spearman_rho,top_k_overlap_rate,calculation_valid,data_support_sufficient,models_consistent,reliability_status,reliability_reason
```

Recommended results: 15 columns and currently 51 sample rows:

```csv
touchpoint,interaction_type,outcome,official_model,official_share,recommended_value,benchmark_model,benchmark_share,gap_pp,relative_gap,calculation_valid,data_support_sufficient,models_consistent,reliability_status,reliability_reason
```

Recommended results fix `official_model=MARKOV` and `benchmark_model=PATH_LEVEL_SHAPLEY`. For a nonzero Outcome, `official_share` equals the Markov share, including a legitimate `0.0` touchpoint; for a zero Outcome, `official_share` is empty. Shares, gaps, and the five reliability fields for the same key must match between the recommendation and touchpoint tables. Both single-model files retain 18 columns and do not add reliability fields.

`recommended_value` is a CSV textual union type chosen by `reliability_status`. A `RELIABLE` row for a nonzero Outcome contains the single `official_share`; an `UNRELIABLE` row contains the ascending, space-free, closed interval `[low,high]` of both model shares. A zero Outcome has no interpretable distribution, so the field is empty. When both shares are zero for a nonzero Outcome, the degenerate interval `[0.0,0.0]` is allowed. This is a model-result range, not a statistical confidence interval.

## Current Sample

The current 17 five-segment touchpoints × 3 Outcomes produce 51 records. All have valid calculations, sufficient support, and consistent models, yielding `51 RELIABLE / 0 UNRELIABLE`; all three summaries are also `RELIABLE`. For `converted_users`, `purchase_count`, and `revenue` respectively, TVD is 1.9451%, 1.9750%, and 2.0585%; Spearman is 0.8890, 0.9111, and 0.9314; Top-5 overlap is 60%, 60%, and 80%. These values reproduce `amc_mta_model_comparison_summary.csv` over the 2026-01-01 through 2026-03-31 window.

These results support only model comparison in the current window. They do not prove causal incrementality, long-term stability, or fitness for automatic budgeting.

## Future Research

Rolling windows, resampling, and 3/7/14-day sensitivity may be future research, but they are neither current reliability conditions nor current CSV fields. If decision approval or automated governance is needed later, design a separate artifact instead of widening the existing 14/13/15 contracts.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the Python files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `attribution_model_comparison.py`

Source: `modules/mta_attribution/src/attribution_model_comparison.py`

- Responsibility: Compare Markov and Shapley outputs, calculate reliability, and build recommendation artifacts.
- Inputs: Two model result sets and the governed path report.
- Outputs: Touchpoint comparison, summary, and recommended-attribution rows.
- Dependencies: `attribution_contract.py` and `touchpoint_key.py`.
- Verification: `modules/mta_attribution/tests/test_attribution_model_comparison.py`.

