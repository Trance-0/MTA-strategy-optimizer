---
title: MTA-Driven Ad Group Count and Budget Model
lang: en-US
---

# MTA-Driven Ad Group Count and Budget Model

## 1. Objective and Boundary

Using one Campaign Group as the recommendation unit, the model answers two questions: how many new Ad Groups does each supplied Campaign need, and how much initial budget does each new group receive?

The model does not output specific Keywords, SKUs, Match Types, Targets, Audiences, actions, or strategy roles. Results are fixed to `INITIAL_SEED` and `is_optimized=false` for later teams to iterate.

## 2. Count Calculation

SP/SB:

```text
N = max(
  min_ad_groups,
  ceil(keyword_units / keyword_capacity),
  ceil(skus / sku_capacity),
  ceil(legal_pairs / pair_capacity)
)
```

SD/DSP:

```text
N = max(
  min_ad_groups,
  ceil(skus / sku_capacity),
  ceil(targets / target_capacity),
  ceil(audiences / audience_capacity)
)
```

Reject the input if `N > max_ad_groups`. Current sample counts after filtering by ad product do not cross capacity boundaries, so all four Campaigns receive one group. Changing any relevant count across a boundary deterministically increases the corresponding count. Inputs use strict v4 fields and JSON numeric types. For SP/SB, valid-Pair count must not exceed the Cartesian-product upper bound of Keyword units and SKUs, and the minimum daily budget per group must be positive.

## 3. MTA and AMC Bridge

Each touchpoint and Outcome uses the MTA `recommended_value`. Within each touchpoint, the AMC entity table allocates that value using the corresponding `assisted_converted_users`, `assisted_purchase_count`, or `assisted_revenue`, then aggregates to historical Ad Groups and only afterward to Campaign. Historical IDs do not enter the output. When the denominator is zero, weighting falls back in order to clicks, impressions, unique users, and equal split, and the output discloses the fallback.

Both attribution and entity Bridge require non-empty five-segment touchpoint keys. Duplicate entity rows, orphan entity touchpoints absent from attribution, and Campaign associations inconsistent with the ad product are rejected.

A `RELIABLE` row uses `recommended_value` directly. An `UNRELIABLE` row uses the midpoint of the AMC `[low,high]` interval and outputs a warning. This midpoint is only an unoptimized initial point.

```text
CampaignOutcome = Σ TouchpointMTAValue × EntityBridgeShare
CampaignScore = Σ OutcomeWeight × CampaignOutcome
CampaignShare = CampaignScore / Σ CampaignScore
```

`assisted_*` is only a Bridge weight. It cannot be added across entities and does not represent entity-level attribution or causal effect.

## 4. New-Group Budget

Candidate inputs contain counts only; there is no stable “historical entity/candidate → new-group slot” mapping. New groups inside the same Campaign are therefore indistinguishable. The model explicitly uses:

```text
AdGroupShare = CampaignShare / N
allocation_basis = CAMPAIGN_MTA_EQUAL_SPLIT
```

When a Group daily budget is provided, the amount is the share multiplied by total budget; otherwise, only relative shares are output. If a Campaign's amount is below `N × minimum_daily_budget_per_ad_group`, retain N and mark it non-executable instead of silently reducing the group count.

## 5. Output

The output contains lineage, budget formula, Campaign capacity basis, MTA scores, Bridge summary, budget shares, and shares/amounts for anonymous `ad_group_slot_id` values. Campaign and Group budgets are aggregated bottom-up from Ad Groups and conserve.
