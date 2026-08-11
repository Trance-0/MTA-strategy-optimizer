---
title: Ad Group Initial-Budget Output Data Contract
lang: en-US
---

# Ad Group Initial-Budget Output Data Contract (v4)

The canonical result is always saved at `modules/mta_strategy_recommendation/outputs/initial_budget_recommendation.json`. It is also the only submission baseline for automated tests; no second copy is maintained under `tests/`. Numeric values preserve the generator's original JSON numbers. A presentation layer may format decimals, but this version does not round to the currency's smallest unit or redistribute remainders.

## 1. Current Sample

| Data | Count or definition |
| --- | ---: |
| Campaign Group | 1 |
| Campaign | 4 |
| Recommended new Ad Groups | 4 (`1/1/1/1`) |
| AMC MTA touchpoints | 17 (all used) |
| AMC entity-aggregate rows | 34 |
| Group daily-budget baseline | 1,000 USD |

## 2. Top-Level Fields

| Field | Meaning |
| --- | --- |
| `schema_version` | Fixed to `4.0` |
| `campaign_group_id`, `candidate_pool_id`, `mta_batch_id` | Input lineage |
| `mta_source_snapshot` | AMC window, marketplace, account, and both file SHAs |
| `budget_derivation` | Bridge formula, weights, row counts, fallback order, and total score |
| `recommendation_type` | `INITIAL_SEED` |
| `handoff_status` | `READY_FOR_OPTIMIZATION` |
| `is_optimized` | `false` |
| `warnings` | Shares-only, insufficient-budget, and similar statuses |
| `budget_seed_total` | Present when a Group budget baseline is supplied |
| `campaigns` | Count and budget for four Campaigns |

The budget normalization scope is fixed to `ALL_AVAILABLE_MTA_TOUCHPOINTS`; six touchpoints are no longer selected manually.

## 3. Campaign Output

```json
{
  "campaign_id": "C_DEMO_SP",
  "recommended_ad_group_count": 1,
  "count_rationale": {
    "eligible_keyword_unit_count": 3,
    "eligible_sku_count": 3,
    "eligible_legal_pair_count": 3,
    "keyword_capacity_count": 1,
    "sku_capacity_count": 1,
    "legal_pair_capacity_count": 1,
    "final_recommended_count": 1
  },
  "outcome_contributions": {
    "converted_users": 0.242017,
    "purchase_count": 0.24183,
    "revenue": 0.23492
  },
  "campaign_mta_score": 0.2398318,
  "budget_seed_share": 0.2398318,
  "campaign_budget_seed": 239.8318,
  "execution_status": "EXECUTABLE"
}
```

`bridge_summary.historical_ad_group_count` discloses only the number of historical groups participating in the Bridge, not their IDs. `method_counts` discloses the `assisted_*` or fallback weight used for each touchpoint/Outcome.

`budget_derivation.mta_value_policy` is fixed to `RELIABLE_POINT_OR_UNRELIABLE_RANGE_MIDPOINT`: reliable rows use a point; unreliable rows use the midpoint of the AMC `[low,high]` range and output `UNRELIABLE_MTA_RANGE_MIDPOINT_USED`. The midpoint is only a representative initial-budget value, not an optimum or statistical-confidence conclusion.

## 4. Ad Group Output

```json
{
  "ad_group_slot_id": "C_DEMO_SP_NEW_AG_01",
  "allocation_basis": "CAMPAIGN_MTA_EQUAL_SPLIT",
  "budget_seed_share": 0.2398318,
  "initial_daily_budget": 239.8318
}
```

A new group is only an anonymous budget-recipient slot. Output must not contain specific candidate IDs, Targeting, Audiences, activation actions, strategy roles, or historical Ad Group IDs.

## 5. Conservation and Defaults

$$
\begin{aligned}
\sum_{g\in c}s_{c,g}&=s_c,\\
\sum_c s_c&=1,\\
\sum_t a_{t,o}&=1 &&\text{for each MTA Outcome }o,\\
\sum_{g\in c}B_{c,g}&=B_c,\\
\sum_c B_c&=B_{\mathrm{group}}.
\end{aligned}
$$

Without `total_daily_budget`, omit every absolute amount, retain shares, and output `NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY`. When the budget is insufficient, output `INSUFFICIENT_BUDGET_FOR_MINIMUMS` without changing the count required by capacity.
