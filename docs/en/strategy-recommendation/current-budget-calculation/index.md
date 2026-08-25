---
title: Current Ad Group Initial-Budget Calculation
compact: "Step-by-step walkthrough of the implemented deterministic initializer with worked numbers: governed MTA values, entity bridge, Outcome scores, budget shares, capacity ceilings, equal Ad Group split, conservation, output reading, and explicit limits."
lang: en-US
---

# Current Ad Group Initial-Budget Calculation

## 1. Document Purpose

This document explains in detail how the current `mta_strategy_recommendation` module derives the initial daily budget for each new Ad Group from MTA attribution results.

The current implementation can be stated precisely as follows:

> First use MTA attribution results to calculate budget shares for four Campaigns. Next calculate how many Ad Groups each Campaign needs from candidate counts. Finally split the Campaign budget equally among its new Ad Groups.

The current model therefore does not predict the performance of individual new Ad Groups or calculate different performance scores for new groups in the same Campaign. Its output is a deterministic initial-budget starting point:

The output records `recommendation_type` as `INITIAL_SEED`, `is_optimized` as `false`, and `allocation_basis` as `CAMPAIGN_MTA_EQUAL_SPLIT`.

The walkthrough continues from [inputs through Campaign scores](./inputs-and-scores.md), then [Ad Group counts through output interpretation](./groups-and-output.md). [Boundaries and locations](./boundaries-and-locations.md) state what the arithmetic does not claim and where its code and artifacts live.
