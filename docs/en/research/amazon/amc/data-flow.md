---
title: AMC, MTA, and ROI Data Flow
lang: en-US
---

# AMC, MTA, and ROI Data Flow

## Two Input Types

The calculation uses two inputs. An AMC anonymous aggregate path report supplies the five-segment path, users, converted users, purchase count, and revenue to Markov and Shapley. The resulting five-segment interaction attribution is joined on the same touchpoint key to an Amazon Ads performance and spend report containing impressions, clicks, cost, and reported sales. That joined result supports [Return on Ad Spend (ROAS)](/en/reference/definitions#roas-return-on-ad-spend), [Return on Investment (ROI)](/en/reference/definitions#roi-return-on-investment), [Cost Per Acquisition (CPA)](/en/reference/definitions#cpa-cost-per-acquisition--cost-per-action), and cost-per-converted-user calculations.

AMC paths answer which combinations of touchpoints participated in conversion. Amazon Ads reporting answers how much was spent on each touchpoint. Cost does not naturally belong to a user path, so attribution is calculated first and cost is joined afterward at the same touchpoint grain.

## Current Project Semantics

- One AMC-style input row is one aggregate path class, not one user. Models calculate `converted_users`, `purchase_count`, and `revenue` independently.
- AMC paths and models use `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`; the final segment is `IMPRESSION` or `CLICK`.
- Amazon Ads cost uses the same complete key. CPC belongs only to `CLICK`, CPM only to `IMPRESSION`, and non-billable interactions have zero cost. Output never collapses back to four segments.
- `converted_users` counts unique purchasers; `purchase_count` counts orders. They are not interchangeable.
- The [current data contract](../../../datasets/amc-data-contract.md) defines the contiguous 14-day path, report window, and model constraints.

## Metrics

$$
\begin{aligned}
\operatorname{ROAS}&=\frac{\text{attributed revenue}}{\text{cost}},\\
\operatorname{ROI}&=\frac{\text{attributed revenue}-\text{cost}}{\text{cost}},\\
\operatorname{CPA}&=\frac{\text{cost}}{\text{attributed purchase count}},\\
\text{cost per converted user}&=\frac{\text{cost}}{\text{attributed converted users}}.
\end{aligned}
$$

The program rejects inputs mixing multiple accounts, marketplaces, or currencies. Such data must be partitioned by scope before execution and joining.
