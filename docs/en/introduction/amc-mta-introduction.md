---
title: AMC MTA Project Introduction
compact: "Plain-language statement of what the runnable attribution module does and explicitly does not claim, including the five-segment key, CPC/CPM cost rules, and the converted_users versus purchase_count distinction."
lang: en-US
---

# AMC MTA Project Introduction

AMC MTA is this repository's runnable attribution implementation: a reproducible multi-touch-attribution and dual-model diagnostic demonstration for Amazon advertising. It estimates how impressions and clicks on AMC-style anonymous aggregate paths contribute to converted users, purchase count, and revenue, then joins Amazon Ads cost and efficiency metrics at the same five-segment interaction grain. Its output is upstream evidence for the [MTA Strategy Initializer](../strategy-recommendation/module-overview.md).

Model results allocate contribution under a specified attribution method. They are not causal incremental effects.

Current reading entry points:

- [Project overview](./)
- [Architecture](./amc-mta-architecture.md)
- [Capability assessment](./amc-mta-capability.md)
- [Module execution](../attribution/amc-mta-module.md)

## How the Project Works

The project processes AMC-style anonymous aggregate paths that distinguish impressions and clicks, runs Markov and Shapley multi-touch attribution, reports contribution by all five touchpoint segments, joins Amazon Ads cost on that complete key, and calculates five-segment ROI, ROAS, CPA, and cost per converted user.

The project neither exports nor processes real AMC user-level behavior. Real use should order events, build paths, and enforce privacy aggregation inside the AMC clean room, supplying this project only anonymous aggregates that satisfy privacy thresholds.

AMC path touchpoints use:

The key is `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`.

`INTERACTION_TYPE` is either `IMPRESSION` or `CLICK`, allowing an ad's exposure and click to appear separately in paths and cost results. Amazon Ads uses the same key. Cost per click (CPC) belongs only to `CLICK`; cost per mille (CPM) belongs only to `IMPRESSION`; non-billable interaction rows have zero cost, preventing duplicated spend.

Amazon Ads `impressions` and `clicks` are aggregate performance metrics and are not used to reconstruct customer paths. Upstream AMC interaction events must provide the interaction type explicitly.

Path construction looks backward from purchase. Every adjacent touchpoint and the final touchpoint-to-purchase edge may span at most 14 days; exactly 14 days is valid. The first gap above 14 days removes the earlier prefix. Total path duration has no separate cap when every adjacent edge qualifies.

Inputs distinguish `converted_users`, the unique users who purchased at least once, from `purchase_count`, the number of orders. Markov and Shapley allocate those measures and revenue independently. Each model produces a five-segment result containing interaction type, contribution, cost, and efficiency. The pipeline also produces touchpoint comparison, overall summary, and governed recommendation files—five canonical outputs total. CPA uses purchase count; cost per converted user is reported separately. See the [data contract](../datasets/amc-data-contract.md).

The recorded 90-day sample had 51 recommendation records under a compact 15-column contract. `recommended_value` held the Markov point for reliable records and the ascending closed interval between Markov and Shapley shares for unreliable records; all recorded sample rows were `RELIABLE`. See [model-comparison governance](../attribution/model-governance.md).

Current-window reliability evaluates only calculation validity, minimum raw support, and model consistency. The recorded sample passed all three criteria for all 51 touchpoint/Outcome rows, yielding `51 RELIABLE / 0 UNRELIABLE`. Outcome summaries AND-aggregate each Boolean over all touchpoints; overall difference measures remain diagnostic. See the [touchpoint reliability guide](../attribution/reliability.md).

## Project Value

- Adds multi-touch path contribution to information unavailable in last-touch reporting.
- Compares Markov and path-level Shapley to expose sensitivity to model assumptions.
- Separates impression and click contribution while joining cost uniquely through CPC/CLICK and CPM/IMPRESSION rules.
- Connects attributed revenue with advertising cost to expose ROI, ROAS, order CPA, and cost per converted user.
- Provides a reproducible diagnostic basis for manual budget discussion, advertising-mix review, and later integration of real AMC aggregates.

The project does not currently provide performance prediction, budget optimization, activation execution, causal-incrementality estimation, or artificial-intelligence question answering.
