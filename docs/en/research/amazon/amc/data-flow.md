---
title: AMC, MTA, and ROI Data Flow
lang: en-US
---

# AMC, MTA, and ROI Data Flow

## Two Input Types

```text
AMC anonymous aggregate path report
  five-segment path + users + converted_users + purchase_count + revenue
                    │
                    ▼
            Markov / Shapley
                    │
                    ▼
five-segment interaction attribution
                    │
                    ├── join the same five-segment touchpoint
                    │
Amazon Ads performance and spend report
  impressions + clicks + cost + reported sales
                    │
                    ▼
               ROAS / ROI / CPA
```

AMC paths answer which combinations of touchpoints participated in conversion. Amazon Ads reporting answers how much was spent on each touchpoint. Cost does not naturally belong to a user path, so attribution is calculated first and cost is joined afterward at the same touchpoint grain.

## Current Project Semantics

- One AMC-style input row is one aggregate path class, not one user. Models calculate `converted_users`, `purchase_count`, and `revenue` independently.
- AMC paths and models use `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`; the final segment is `IMPRESSION` or `CLICK`.
- Amazon Ads cost uses the same complete key. CPC belongs only to `CLICK`, CPM only to `IMPRESSION`, and non-billable interactions have zero cost. Output never collapses back to four segments.
- `converted_users` counts unique purchasers; `purchase_count` counts orders. They are not interchangeable.
- The [current data contract](../../../datasets/amc-data-contract.md) defines the contiguous 14-day path, report window, and model constraints.

## Metrics

```text
ROAS = attributed_revenue / cost
ROI  = (attributed_revenue - cost) / cost
CPA  = cost / attributed_purchase_count
cost_per_converted_user = cost / attributed_converted_users
```

The program rejects inputs mixing multiple accounts, marketplaces, or currencies. Such data must be partitioned by scope before execution and joining.
