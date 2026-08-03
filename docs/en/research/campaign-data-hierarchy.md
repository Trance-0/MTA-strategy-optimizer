---
title: Campaign Group Hierarchy and Finest Performance Grain
lang: en-US
---

# Campaign Group Hierarchy and Finest Performance Grain

This page defines the current business semantics used by the Strategy Initializer. The entity tree has four levels:

```text
Campaign Group
└── Campaign
    └── Ad Group
        ├── Keyword
        └── SKU
```

`ad_product` is an intrinsic single-value field on a Campaign, not an independent hierarchy level between Campaign and Ad Group. Keyword and stock keeping unit (SKU) attach in parallel to a real Ad Group; neither is the other's parent. The current initializer outputs only new-group counts and budgets and does not choose their entity assignments.

## 1. Top-Level Business View

```text
Campaign Group: Amazon US Running Shoes FY2026
├── Group scope
│   ├── campaign_group_id = CG001
│   ├── retailer/platform = Amazon
│   ├── marketplace = US
│   ├── advertiser/account = Account A
│   ├── category = Running Shoes
│   ├── brand = Nike
│   └── segment = Running
│
├── Campaign: C001
│   ├── ad_product = SPONSORED_PRODUCTS
│   ├── targeting = MANUAL
│   ├── status = enabled
│   ├── Ad Group: AG001
│   │   ├── Keyword: women running shoes / EXACT
│   │   ├── Keyword: lightweight running shoes / PHRASE
│   │   ├── SKU: AMZ-US-PEG41-BLK-38
│   │   └── SKU: AMZ-US-PEG41-WHT-38
│   └── Ad Group: AG002
│       ├── Keyword set
│       └── SKU set
│
├── Campaign: C002
├── Campaign: C003
└── Campaign: C004
```

Amazon, US, Campaign names, Keywords, and SKUs in the example only illustrate relationships. One current recommendation task fixes one Campaign Group to one platform and contains four Campaigns carrying SP, SB, SD, and DSP respectively.

## 2. Business Responsibilities

| Level | Primary responsibility | Relationship to next level |
| --- | --- | --- |
| Campaign Group | set one platform, marketplace, account, category, brand, and Segment scope; filter the bounded candidate pool | current task contains exactly four Campaigns |
| Campaign | hold campaign configuration; `ad_product` is one required single-value field | one Campaign contains multiple Ad Groups |
| Ad Group | hold executable configuration; initializer recommends only new-group count and budget slots | many-to-many with Keywords and SKUs in the activation platform |
| Keyword | express search demand and Match Type | may enter multiple Ad Groups, with duplicate control within a Campaign |
| SKU | identify a sellable item in one platform and marketplace | belongs to a Product and may enter multiple strategy groups |
| Product | identify the merchandise concept across selling environments | one Product may map to multiple SKUs |

Current recommendation relationships are:

```text
Campaign Group 1 ── 4 Campaign
Campaign       1 ── N Ad Group
Ad Group       N ── N Keyword
Ad Group       N ── N SKU
Product        1 ── N SKU
```

Campaign and Campaign Group do not directly own SKUs. The complete product chain is:

```text
Campaign Group
→ campaign_group_relationship
→ Campaign
→ Ad Group
→ ad_group_sku
→ SKU
→ Product
```

## 3. Bounded Candidate Pool and Actual Assignment

Upstream preparation filters a bounded pool by platform, marketplace, account, brand, category, inventory, sellable state, and compliance. The current model receives counts aggregated by Campaign:

- SP/SB: Keyword units, SKUs, and valid Keyword-SKU pairs;
- SD/DSP: SKUs, Targets, and Audiences.

Each Campaign further filters content according to its ad product. The initializer uses counts and capacity limits to determine the number of new Ad Groups but does not select candidates, choose Match Types, or assign entities to a group. Actual assignment belongs to downstream activation preparation.

Allowed combination provenance is:

```text
EXISTING     a real existing activation relationship
VALIDATED    rules or human review validated the combination
EXPLORATION  bounded test combination
BLOCKED      prohibited from assignment
```

## 4. Finest Paid-Search Performance Record

```text
date           = 2026-07-01
campaign_id    = C001
ad_group_id    = AG001
keyword_id     = K001
sku_id         = S001
impressions    = 10000
clicks         = 250
traffic_budget = 500
sales          = 2000
unit_sales     = 20
```

The record represents one real Keyword-by-SKU combination's aggregate result on one day within a specific Campaign and Ad Group. The finest described performance grain is:

```text
Date × Campaign × Ad Group × Keyword × SKU
```

It is not user-event grain and cannot be expanded to `User × Search × Impression × Click × Order`. Parallel fact tables may exist at `date × sku`, `date × keyword × sku`, or `date × campaign`; similarly named budget fields at different grains cannot be interchanged.

A Keyword-by-SKU Cartesian product expanded from relationship tables is not automatically a real touchpoint. A combination counts as an eligible candidate only if fact data observes it, business review validates it, or it is explicitly marked for bounded exploration.

## 5. Meaning for the Strategy Initializer

The MTA five-segment key is an attribution-observation dimension, not the business-entity tree. The initializer uses:

```text
Campaign Group scope and bounded candidate counts
              ↓
four fixed Campaigns
              ↓
new Ad Group counts from candidate capacity
              ↓
all MTA touchpoints rolled through the AMC bridge into Campaign shares
              ↓
anonymous new groups within a Campaign split the INITIAL_SEED equally
              ↓
handoff to later optimization
```

The module supplies an explainable initial count and budget. It neither assigns activation entities nor predicts a global optimum or continuously optimizes budgets.
