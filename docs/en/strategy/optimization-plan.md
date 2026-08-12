---
title: From MTA Attribution to an Ad Group Budget Strategy
compact: "UNIMPLEMENTED research plan, no algorithm or code: problem framing on granularity breaks between touchpoints and new Ad Groups, attribution versus incrementality, missing product/SKU data, conflicting Outcome objectives. Read for open questions; never cite as current behavior."
lang: en-US
---

# From MTA Attribution to an Ad Group Budget Strategy: Problem Definition and Research Plan

## 1. Discussion Objective

This plan defines and analyzes one problem only. At the current stage, it does not propose a specific algorithm, budget formula, or technical solution:

> How can touchpoint-attribution results from an MTA model be combined with Campaign, Keyword, SKU, and other available data to formulate the Ad Group count and Ad Group-level budget-allocation strategy for every Campaign in the next Campaign Group?

Here, “strategy” primarily means:

1. how many Ad Groups each Campaign needs;
2. how the Campaign Group's total budget reaches each Campaign;
3. how each Campaign's budget reaches its internal new Ad Groups;
4. what historical evidence supports each budget recommendation and how credible it is.

## 2. Business Scope

The current business hierarchy is:

The decision hierarchy is Campaign Group → Campaign → Ad Group.

Established business conditions:

- One Campaign Group serves only one advertising platform.
- One Campaign Group contains four Campaigns.
- Each Campaign uses only one Ad Product.
- One Campaign may contain multiple Ad Groups.
- Keyword, SKU, Match Type, Target, Audience, and similar information belongs to advertising entities or strategy information.
- Campaign and Ad Group IDs in the next period may differ from historical IDs.

This problem concerns the initial budget strategy for the next Campaign Group. Whether the strategy is optimized further later does not change the current problem definition in this plan.

## 3. What Existing MTA Outputs Can Tell Us

Current MTA touchpoints are primarily composed of advertising fields:

The source attribution grain is `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`.

Each touchpoint can receive attribution results for several Outcomes, such as:

- `converted_users`;
- `purchase_count`;
- `revenue`.

These results state how much outcome credit each advertising touchpoint received within the historical observation window. They can describe the relative contribution of different Ad Products, Placements, Creatives, or Interaction Types in conversion paths.

However, this output does not itself contain:

- the Campaign and Ad Group business structure;
- Keyword, Match Type, Target, and Audience;
- SKU, ASIN, product category, price, and margin;
- inventory, salability status, promotion, and lifecycle;
- the Ad Groups that will be created in the next Campaign;
- the incremental outcomes that may result from increasing the budget of each Ad Group.

There is therefore a clear granularity break between MTA output and the final budget object.

## 4. What Other Relevant Data May Contain

Besides MTA, data involved in the current problem falls into the categories below. This section organizes only their roles and gaps; it does not prescribe a use.

| Data category | Possible content | Relationship to the budget problem |
| --- | --- | --- |
| Historical advertising structure | Campaign ID, Ad Group ID, Ad Product, platform | Shows which advertising structures carried historical touchpoints |
| Delivery entities | Keyword, Match Type, Target, Audience | Describes targeting objects inside Ad Groups |
| Product entities | SKU, ASIN, category, brand | Describes the products actually promoted by ads |
| Product operating data | Price, margin, inventory, salability, promotion | Indicates whether attributed results have business value and remain eligible for investment |
| Historical performance data | Impressions, clicks, cost, purchases, sales | Describes historical delivery scale and outcomes |
| Budget data | Budget, Spend, budget-limited status, pacing | Describes the relationship between budget settings and actual spend |
| Next-period input | Candidate Keyword/SKU counts or details, total budget, Campaign count | Defines objects and boundaries for the next budget strategy |

The most important current data fact is that MTA has touchpoint contribution but lacks product and delivery entities. Other data may have entity information, but whether its results can join reliably to MTA touchpoints still requires separate confirmation.

## 5. Main Breaks from MTA Touchpoints to Ad Group Budgets

### 5.1 Touchpoint and Ad Group Granularity Differ

MTA attributes combinations of advertising properties, while the budget recipient is a newly created Ad Group in the next period. The same touchpoint may appear in several historical Ad Groups, and one historical Ad Group may contain several Keywords, SKUs, or Targets. The relationship is not naturally one-to-one.

Without explaining which entities and historical Ad Groups relate to a touchpoint's attribution result, there is no basis for deciding how that credit should affect a new Ad Group in the next period.

### 5.2 Historical and Next-Period Structures Differ

Historical Campaign and Ad Group IDs primarily represent historical data lineage. The next activation may recreate Campaigns, change the Ad Group count, or alter Keyword/SKU combinations, so historical IDs cannot directly represent future budget recipients.

The central issue is not whether IDs can be preserved, but whether historical evidence remains comparable after future structural changes.

### 5.3 MTA Attribution Is Not Budget Incrementality

MTA explains historical outcome credit; it does not directly answer marginal-budget questions:

The response model must answer two separate questions: how much actual Spend changes after an Ad Group budget increase, and how conversions, purchases, or revenue change after Spend increases.

A touchpoint may have a high attribution share because its historical budget was high, it appeared close to conversion, it reached more people, or it genuinely performed better. Attribution share alone cannot distinguish these causes.

It is therefore necessary to distinguish explicitly among:

- historical credit allocation;
- historical correlation;
- budget response;
- causal incrementality.

These four concepts are not equivalent.

### 5.4 Campaign-Level Contribution and Within-Campaign Differences

If several new Ad Groups in the same Campaign differ only by count and have no distinguishing Keyword, SKU, Target, Audience, or other features, the data cannot distinguish them.

In that situation, evidence may establish relative importance among the four Campaigns, but it cannot further determine which new Ad Group within one Campaign should receive more budget.

### 5.5 Ad Group Count and Budget Allocation Affect Each Other

Ad Group count is a discrete structural problem, while budget amount is a continuous allocation problem. Counts of candidate Keywords, SKUs, Targets, and Audiences affect the required number of Ad Groups. Changing the Ad Group count then changes the minimum budget unit, data density within each group, and minimum budget available per group.

It is therefore necessary to determine whether current data can identify these relationships:

- whether count depends only on capacity and candidate-pool size;
- whether count should also reflect historical contribution, product differences, or data sparsity;
- whether count and budget should be treated as two independent problems;
- whether different Ad Products have different definitions of Ad Group capacity.

### 5.6 Multiple Outcomes Do Not Have Identical Objectives

MTA provides results for converted users, purchase count, revenue, and similar Outcomes at the same time. They may imply different budget tendencies:

- converted users emphasizes reach and the number of people converted;
- purchase count emphasizes transaction frequency;
- revenue emphasizes sales scale;
- adding margin later may change the ranking again.

Without an explicit business objective and weights, a “better budget strategy” has no unique mathematical definition.

## 6. Specific Problems Caused by Missing Product Information

All current MTA touchpoint fields are advertising attributes. Missing product information directly creates these uncertainties:

1. The specific SKUs promoted by a high-attribution touchpoint are unknown.
2. Touchpoint contribution cannot be separated into product appeal versus the advertising touchpoint itself.
3. There is no way to know whether a historically high-contribution SKU remains salable, in stock, or sufficiently profitable next period.
4. There is no way to determine whether a Keyword–SKU relationship is a real delivery relationship or an apparent relationship produced by data combination.
5. The budget evidence for a new Ad Group cannot be attributed clearly to advertising attributes, Keyword, SKU, or historical Ad Group.
6. Cold-start cases for a new SKU, Keyword, or combination cannot be handled.

Product data is not a simple supplement to MTA fields. It changes the business object underlying the final budget strategy, so a stable, verifiable relationship between product data and advertising touchpoints is one of the core prerequisites for this problem.
