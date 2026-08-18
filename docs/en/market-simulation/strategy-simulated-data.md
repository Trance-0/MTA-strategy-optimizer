---
title: Simulated Inputs for Ad Group Count and Budget
compact: "Governs the two v4 strategy inputs `strategy_request.json` and `candidate_pool.json`, Ad Group capacity counting for SP/SB from Keyword/SKU/Pair and SD/DSP from SKU/Target/Audience, `candidate_usage_policy=USE_ALL_ELIGIBLE`, and the canonical `initial_budget_recommendation.json`. Read for budget initialization inputs."
lang: en-US
---

# Simulated Inputs for Ad Group Count and Budget

This directory contains only two v4 input JSON files and this explanation. It does not store AMC data or model output.

The deterministic canonical result is at `modules/mta_strategy_recommendation/outputs/initial_budget_recommendation.json`.

## `strategy_request.json`

Purpose: Group, four Campaigns, AMC file SHA/scope, Outcome weights, capacity for each ad product, and minimum budget.

## `candidate_pool.json`

Purpose: Count of eligible Keyword units, SKUs, valid Pairs, Targets, and Audiences for each Campaign.

Counting rules:

- SP/SB use the maximum of the three capacity lower bounds for Keyword units, SKUs, and valid Pairs.
- SD/DSP use the maximum of the three capacity lower bounds for SKUs, Targets, and Audiences.
- With `candidate_usage_policy=USE_ALL_ELIGIBLE`, every supplied count enters the capacity calculation.
- Inputs contain only counts, not specific candidate IDs, so the output is not an activation plan.

After filtering by ad product, the current sample counts are Keyword/SKU/Pair=`3/3/3` for SP and `4/4/4` for SB, and SKU/Target/Audience=`4/4/2` for SD and `4/8/2` for DSP.

Budget evidence reads only these AMC files:

- `modules/mta_attribution/outputs/attribution/amc_mta_recommended_attribution.csv`
- `modules/mta_attribution/data/simulated/amc_touchpoint_entity_aggregate_sample.csv`

Historical `campaign_id`/`ad_group_id` values exist only inside the AMC Bridge. The output uses new anonymous slot IDs and does not treat historical groups as future new groups.
