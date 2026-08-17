---
title: Budget Strategy Output Contract
compact: "Scope boundary for the IMPLEMENTED initializer: the five questions output must answer, the forbidden ones such as Keyword/SKU/Target assignment, ROI, and causal incrementality, plus `count_rationale` and `allocation_basis=CAMPAIGN_MTA_EQUAL_SPLIT` rules. Read when judging whether a proposed field belongs."
lang: en-US
---

# Budget Strategy Output Contract

In this model, “strategy” means only the new Ad Group count and initial-budget allocation, not a specific advertising activation plan.

## Must Answer

1. Do eligible-candidate counts require a Campaign to be split into groups?
2. How many new Ad Groups are recommended for each Campaign?
3. How much relative value do the three MTA Outcomes assign to the Campaign after the AMC Bridge?
4. How much share and amount does each anonymous new group receive?
5. Did a Bridge fallback or minimum-budget shortfall occur?

## Must Not Answer

- Which Keyword, SKU, or Match Type should enter which group.
- Which Target, Audience, Placement, or activation action to use.
- Which historical Ad Group is the future new group.
- The highest ROI, causal incrementality, or optimized budget.

## Count Basis

`count_rationale` stores input counts, the capacity lower bound for each dimension, and the final maximum. SP/SB calculate Keyword units, SKUs, and valid Pairs; SD/DSP calculate SKUs, Targets, and Audiences. The current sample outputs `1/1/1/1`.

## Budget Basis

Campaign budgets use all MTA touchpoints and Outcome weights. AMC `assisted_*` only allocates the same touchpoint's contribution among historical entities before aggregating to Campaign. New groups have no stable mapping, so budgets are strictly equal within Campaign and save `allocation_basis=CAMPAIGN_MTA_EQUAL_SPLIT`.

If new groups in one Campaign must receive different budgets in the future, first add a stable candidate/historical-entity-to-new-slot mapping, then change this contract. Anonymous slot numbers alone must not be used to fabricate differences.
