---
title: Complete AMC MTA Usage Guide
lang: en-US
---

# Complete AMC MTA Usage Guide

This document is the one-stop entry point for AMC MTA submission review and local demonstration. The module performs exploratory multi-touch attribution only within the current reporting window. It does not measure causal incrementality, allocate budgets, optimize activation, or execute automatically.

## 1. Capability Scope

The pipeline accepts AMC anonymous aggregated paths and Amazon Ads five-segment performance/cost data. It calculates Markov and path-level Shapley attribution for purchasing users, order count, and revenue, then generates a touchpoint comparison, Outcome summary, and management recommendations. Markov is the `official` display basis; Shapley is the model-sensitivity reference. They are not averaged and cannot replace one another.

In real AMC, event ordering, path construction, and privacy aggregation should occur inside the clean room, with only aggregated paths satisfying the privacy threshold exported. Local synthetic user events and conceptual events are for demonstration only and must not be treated as the format of real AMC user-level exports.

## 2. Inputs and Data Locations

Default demonstration inputs are under `modules/mta_attribution/data/simulated/`. See the [simulated data description](../datasets/amc-simulated-data.md) for file roles:

- Synthetic user events: local simulation only and the common source of the other dynamic samples.
- Anonymous conceptual events: aggregated from the master table by path template and used only for local path construction.
- AMC aggregated paths: direct input to attribution algorithms.
- Amazon Ads report: five-segment daily performance and cost aggregated from the master table.
- Touchpoint-entity aggregates: links to historical Campaign/Ad Group/Keyword/SKU entities for later strategy use.

One run accepts one marketplace, advertising account, and currency. Ads dates must be continuous, every day must have the same five-segment touchpoint set, and date/touchpoint combinations must be unique. The pipeline detects its window automatically from the earliest and latest Ads `reportDate`, so replacing the data does not require changing date configuration.

The [data contract](../datasets/amc-data-contract.md) is authoritative for complete fields, numeric relationships, and alignment conditions.

## 3. Five-Segment Touchpoints and Path Rules

The common join key is:

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

`INTERACTION_TYPE` may only be `IMPRESSION` or `CLICK`. They are independent touchpoints. CPC cost belongs only to clicks, CPM cost only to impressions, and non-billable interactions have zero cost.

Paths are traced backward from the final touchpoint before purchase. Gaps between adjacent touchpoints and from the last touchpoint to purchase must not exceed 14 days; exactly 14 days is valid. At the first longer gap, earlier touchpoints are truncated. The earliest retained touchpoint must be strictly later than the window start, and purchase must not be later than the window end. When one journey contains multiple purchases, a later purchase uses only new touchpoints after the previous purchase.

## 4. Models and Conservation

Markov uses path order and transition dependence. Path-level Shapley calculates participation credit over each path's unique touchpoint set, counting a repeated touchpoint only once within the same path. Both models separately calculate:

- `converted_users`: unique purchasing users;
- `purchase_count`: order count;
- `revenue`: revenue.

All three attributed values must separately conserve to their AMC totals, and shares must equal 1 for a nonzero Outcome. Outputs also join Amazon Ads performance, cost, and efficiency metrics:

```text
ROAS = attributed_revenue / cost
ROI  = (attributed_revenue - cost) / cost
CPA  = cost / attributed_purchase_count
cost_per_converted_user = cost / attributed_converted_users
```

When cost is 0, ROAS and ROI are empty. When attributed orders or attributed purchasing users are 0, CPA or `cost_per_converted_user`, respectively, is empty instead of infinite.

## 5. Reliability and Recommended Value

A `touchpoint + outcome` record is `RELIABLE` only when all three conditions are true:

1. `calculation_valid`: strict schema, set, numeric, and conservation validation passed.
2. `data_support_sufficient`: at least 30 purchases, 20 purchasing users, and 5 unique paths.
3. `models_consistent`: `gap_pp <= 1.0` and `relative_gap <= 0.20`.

`RELIABLE` means only that the current window meets these three evidence criteria. It does not mean causal validity or long-term stability and does not authorize automatic budget action. In the recommendation table, a reliable nonzero-Outcome record uses the single Markov `official_share`; an unreliable record uses the ascending closed interval of both model shares. This interval is not a statistical confidence interval. Recommended value is empty for a zero Outcome.

See [reliability assessment](reliability.md) and the [dual-model governance specification](model-governance.md) for details.

## 6. Execution and Atomic Group Publishing

Run from the repository root:

```bash
uv run python -X utf8 -B script/run_pipeline.py
uv run python -X utf8 -B script/validate_data_alignment.py
```

The complete pipeline first creates and validates one aggregated path report and five canonical outputs in a temporary location. It publishes only after all six derived artifacts succeed as a group. If inputs are invalid, paths are empty, validation fails, or publishing fails, raw inputs are not overwritten and the previous derived artifact group remains unchanged. See [running the module](../environment/amc-mta-usage.md) for custom paths and stepwise commands.

To validate module tests independently without running the pipeline, execute from the repository root:

```bash
python3 -B -m unittest discover -s modules/mta_attribution/tests -p 'test_*.py'
```

The expected result is 107 passing tests; this command does not publish or overwrite canonical CSV files.

## 7. Output Reading Order

Recommended order:

1. Markov primary results, to confirm the official display basis.
2. Shapley primary results, to observe model sensitivity.
3. Touchpoint comparison, to locate gaps and insufficient support.
4. Outcome summary, to inspect overall difference diagnostics.
5. Recommendation table, to obtain management display values or model ranges.

See the [canonical output index](output-reference.md) for keys, fields, and limits of each file.

## 8. Common Errors

| Symptom | Common cause | Resolution |
| --- | --- | --- |
| Input fails immediately | Empty/duplicate header after cleanup, missing/extra column, invalid number, or legacy field | Leading/trailing whitespace is tolerated directly; correct all other issues in the upstream export according to the data contract |
| Alignment fails | Window, account, currency, dates, or touchpoint set do not match | Run alignment validation first and ensure complete daily Ads coverage |
| Paths are empty | No valid conversions, gaps exceed the limit, or the window-start rule fails | Check event types, timestamps, and 14-day rules |
| Efficiency metric is empty | Cost is 0, or the attributed denominator of a CPA-style metric is 0 | Leave it empty; do not copy cost or output infinity |
| Result is unreliable | Support is insufficient or the two-model gap exceeds thresholds | Use the recommended range and explicitly state that evidence is currently insufficient |

After any failure, fix the input and rerun the complete group; never manually combine old and new batches.

## 9. Five-Minute Demo

1. Use the [AMC MTA module overview](amc-mta-module.md) to explain scope and the automatic window.
2. Show the five-segment key and 14-day rules in the [data contract](../datasets/amc-data-contract.md).
3. Run the complete pipeline and alignment validation.
4. Review all five results in the order in the [output index](output-reference.md).
5. Use the recommendation table to explain the boundaries of `official`, `RELIABLE`, and unreliable intervals.
6. Use the [submission manifest](../reference/submission-manifest.md) to confirm the boundary between the core package and supporting material.

## 10. Limitations and Further Validation

- There is currently no rolling-window, resampling, or 3/7/14-day sensitivity evidence.
- Results are not experimental incrementality, counterfactual causality, or long-term stable contribution.
- Concurrent publishing and strongly consistent reading still require separate design.
- Budget approval or automation requires separate governance artifacts and human approval mechanisms.
- Before new data goes live, repeat input alignment, atomic group publishing, tests, and interpretation review.
