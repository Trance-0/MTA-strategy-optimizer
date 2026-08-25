---
title: Initializer Boundaries and Locations
compact: "Explicit non-claims of the current budget initializer and the repository locations for attribution inputs, entity bridge, candidate pool, request, implementation, output artifact, command, and validators."
lang: en-US
---

# Initializer Boundaries and Locations

## 15. What the Current Calculation Does Not Do

To avoid misinterpretation, the current budget boundaries are explicit:

- It does not predict conversions, purchases, or revenue for each new Ad Group.
- It does not score new groups individually using specific Keywords or SKUs.
- It does not treat historical Ad Groups directly as future new Ad Groups.
- It does not estimate marginal return from one more dollar of budget.
- It does not search for the highest ROI or a mathematically optimal budget.
- It does not output specific Keyword, SKU, Match Type, Target, or Audience activation plans.

The real source of each current Ad Group budget is therefore:

In short, MTA determines relative budgets among Campaigns, candidate counts determine each Campaign's new-group count, and the Campaign budget is split equally among those groups.

This is the full meaning of the output field `CAMPAIGN_MTA_EQUAL_SPLIT`.

## 16. Corresponding Code and Result Locations

- Core calculation: `src/budget_recommender.py`
- Generation entry point: `script/generate_initial_budget.py`
- Strategy input: `data/simulated/strategy_request.json`
- Candidate counts: `data/simulated/candidate_pool.json`
- Canonical output: `outputs/initial_budget_recommendation.json`
- Automated validation: `src/hierarchy_validator.py`
