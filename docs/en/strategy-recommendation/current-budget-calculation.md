---
title: Current Ad Group Initial-Budget Calculation
compact: "Step-by-step walkthrough of the IMPLEMENTED deterministic initializer with worked numbers: MTA `recommended_value`, AMC entity bridge with `assisted_*` and clicks/impressions/unique_users fallback, capacity ceiling formula, `CAMPAIGN_MTA_EQUAL_SPLIT`. Read to trace or reproduce an exact budget figure."
lang: en-US
---

# Current Ad Group Initial-Budget Calculation

## 1. Document Purpose

This document explains in detail how the current `mta_strategy_recommendation` module derives the initial daily budget for each new Ad Group from MTA attribution results.

The current implementation can be stated precisely as follows:

> First use MTA attribution results to calculate budget shares for four Campaigns. Next calculate how many Ad Groups each Campaign needs from candidate counts. Finally split the Campaign budget equally among its new Ad Groups.

The current model therefore does not predict the performance of individual new Ad Groups or calculate different performance scores for new groups in the same Campaign. Its output is a deterministic initial-budget starting point:

The output records `recommendation_type` as `INITIAL_SEED`, `is_optimized` as `false`, and `allocation_basis` as `CAMPAIGN_MTA_EQUAL_SPLIT`.

## 2. Data Used by the Current Calculation

Strategy-model paths in the following table are relative to the `modules/mta_strategy_recommendation` module root; MTA source-data paths are relative to the workspace root.

### Strategy request

- **Current file:** `data/simulated/strategy_request.json`
- **Content entering the calculation:** Campaign Group daily budget, four Campaigns, Outcome weights, capacity rules, and minimum daily budget per group

### Candidate pool

- **Current file:** `data/simulated/candidate_pool.json`
- **Content entering the calculation:** Eligible Keyword-unit, SKU, valid-Pair, Target, and Audience counts for each Campaign

### MTA attribution

- **Current file:** `../mta_attribution/outputs/attribution/amc_mta_recommended_attribution.csv`
- **Content entering the calculation:** `recommended_value` and reliability status for every touchpoint and Outcome

### AMC entity aggregate

- **Current file:** `../mta_attribution/data/simulated/amc_touchpoint_entity_aggregate_sample.csv`
- **Content entering the calculation:** Relationships between touchpoints and historical Campaigns/Ad Groups, plus supporting metrics for the Bridge

### Canonical result

- **Current file:** `outputs/initial_budget_recommendation.json`
- **Content entering the calculation:** Score, count, and budget of four Campaigns, plus each anonymous new group's budget

The current sample Campaign Group has a daily budget of 1,000 USD and contains four Campaigns:

### `C_DEMO_SP`

Ad Product: Sponsored Products

### `C_DEMO_SB`

Ad Product: Sponsored Brands

### `C_DEMO_SD`

Ad Product: Sponsored Display

### `C_DEMO_DSP`

Ad Product: Amazon DSP

## 3. Overall Calculation Flow

<DrawioDiagram base="./current-budget-calculation-flow" alt="Current initial-budget calculation flow" />

The entire process can be summarized in one final formula:

$$
B_{c,g}=B_{\mathrm{group}}
\times \frac{S_c}{\sum_j S_j}
\times \frac{1}{N_c}
$$

Here, $B_{c,g}$ is the initial daily budget of a new Ad Group in Campaign $c$, $B_{\mathrm{group}}$ is the Campaign Group total daily budget, $S_c$ is the Campaign MTA score, and $N_c$ is the recommended Ad Group count.

The following sections explain where every term in this formula comes from.

## 4. Step One: Read the Attribution Value of Each MTA Touchpoint

The MTA file's granularity is:

Each MTA row has the grain **touchpoint × Outcome**.

The current touchpoint is a five-segment combination of advertising attributes:

The five-segment touchpoint key is `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`.

Three Outcomes are currently used:

- `converted_users`;
- `purchase_count`;
- `revenue`.

Each row uses the MTA output's `recommended_value`:

- when `reliability_status=RELIABLE`, use the point value directly;
- when `reliability_status=UNRELIABLE`, `recommended_value` is `[low,high]`, and the current implementation uses the interval midpoint;
- when an interval midpoint is used, add the `UNRELIABLE_MTA_RANGE_MIDPOINT_USED` warning.

For each Outcome, numeric `recommended_value` values over every available touchpoint must satisfy this condition within a `1e-9` tolerance:

$$
\sum_t \operatorname{RecommendedValue}_{t,o}=1
$$

Thus, `recommended_value` represents the Outcome's attribution share across all MTA touchpoints. For an `UNRELIABLE` row, the value included in the sum is the midpoint of `[low,high]`, not the original string.

The current sample has 17 touchpoints and 3 Outcomes, so it reads 51 MTA rows; all 51 are `RELIABLE`.

## 5. Step Two: Bridge to Historical Campaigns through the AMC Entity Table

### 5.1 Why the Bridge Is Needed

MTA touchpoints contain advertising attributes such as Ad Product, Format, Placement, Creative, and Interaction Type. Budget output, by contrast, is organized by Campaign and new Ad Group. The AMC entity-aggregate table identifies the Campaign and historical Ad Group that carried a historical touchpoint.

### 5.2 Allocation within a Touchpoint

For touchpoint `t` and Outcome `o`, the code first finds AMC entity rows satisfying both conditions:

An entity row matches when `entity.touchpoint` equals $t$ and its `campaign_id` identifies the Campaign corresponding to the Ad Product.

It then chooses an allocation metric by Outcome:

#### `converted_users`

First-priority allocation metric: `assisted_converted_users`

#### `purchase_count`

First-priority allocation metric: `assisted_purchase_count`

#### `revenue`

First-priority allocation metric: `assisted_revenue`

If the sum of the corresponding `assisted_*` metric is zero, weighting falls back in this order:

The fallback order is `clicks`, then `impressions`, then `unique_users`, and finally an equal split.

The touchpoint credit received by one historical entity row is:

$$
\operatorname{EntityCredit}(t,o,e)
=\operatorname{MTARecommendedValue}(t,o)
\times \frac{\operatorname{EntityMetric}(e)}
{\sum_{e'\in E_{t,o}}\operatorname{EntityMetric}(e')}
$$

The code first aggregates entity-row credit to historical Ad Group and checks that the touchpoint credit conserves completely:

$$
\sum_g \operatorname{HistoricalAdGroupCredit}(t,o,g)
=\operatorname{MTARecommendedValue}(t,o)
$$

It then aggregates historical Ad Group credit to Campaign.

### 5.3 The Bridge's Actual Role in the Current Budget

Currently, exactly one Campaign corresponds to each Ad Product. Therefore, after a touchpoint is allocated among historical entities and then aggregated back to Campaign, its total still equals the original MTA attribution value.

The AMC Bridge currently performs three main functions:

1. validates data relationships among MTA touchpoints and historical Campaigns/Ad Groups;
2. records the Campaign's historical Ad Group count, touchpoint count, and allocation methods;
3. guarantees that touchpoint credit is neither lost nor duplicated during aggregation.

Historical Ad Group weights in the Bridge are not passed directly to future new Ad Groups. New groups in the output use new anonymous `ad_group_slot_id` values and are not continuations of historical Ad Groups.

## 6. Step Three: Obtain the Three Outcome Contributions for Each Campaign

For Campaign `c` and Outcome `o`:

$$
\operatorname{CampaignOutcomeContribution}(c,o)
=\sum_{e:\,\operatorname{campaign}(e)=c}\operatorname{EntityCredit}(t,o,e)
$$

The current canonical results are:

### SP

- **Converted Users:** 0.242017
- **Purchase Count:** 0.241830
- **Revenue:** 0.234920

### SB

- **Converted Users:** 0.298984
- **Purchase Count:** 0.299673
- **Revenue:** 0.293010

### SD

- **Converted Users:** 0.235849
- **Purchase Count:** 0.234967
- **Revenue:** 0.231124

### DSP

- **Converted Users:** 0.223150
- **Purchase Count:** 0.223530
- **Revenue:** 0.240946

### Total

- **Converted Users:** 1.000000
- **Purchase Count:** 1.000000
- **Revenue:** 1.000000

For example, SP's `converted_users=0.242017` means that, in the current MTA results, 24.2017% of attribution credit for converted users aggregates to the SP Campaign after the AMC Bridge.

It does not mean 0.242017 real users, nor is it a prediction of incremental conversions after a budget increase.

## 7. Step Four: Combine Three Outcomes into the Campaign MTA Score

Current input weights are:

The current weights are 0.4 for `converted_users`, 0.3 for `purchase_count`, and 0.3 for `revenue`.

Weights must sum to 1. The Campaign composite score is:

$$
S_c=0.4C_{c,\mathrm{converted\ users}}
+0.3C_{c,\mathrm{purchase\ count}}
+0.3C_{c,\mathrm{revenue}}
$$

For SP:

$$
\begin{aligned}
S_{\mathrm{SP}}
&=0.4(0.242017)+0.3(0.241830)+0.3(0.234920)\\
&=0.0968068+0.0725490+0.0704760\\
&=0.2398318
\end{aligned}
$$

The four Campaign results are:

### SP

Result: 0.2398318

### SB

Result: 0.2973985

### SD

Result: 0.2341669

### DSP

Result: 0.2286028

### Total

Result: 1.0000000

Because Campaign contributions sum to 1 for each Outcome and Outcome weights also sum to 1, the current `campaign_score_total=1.0`.

## 8. Step Five: Convert Campaign Scores to Budget Shares

The Campaign budget share is:

$$
\operatorname{CampaignBudgetShare}_c=\frac{S_c}{\sum_j S_j}
$$

The current total score equals 1 exactly, so each Campaign's budget share is numerically equal to its MTA composite score:

### SP

- **Campaign budget share:** 0.2398318
- **Percentage:** 23.98318%

### SB

- **Campaign budget share:** 0.2973985
- **Percentage:** 29.73985%

### SD

- **Campaign budget share:** 0.2341669
- **Percentage:** 23.41669%

### DSP

- **Campaign budget share:** 0.2286028
- **Percentage:** 22.86028%

### Total

- **Campaign budget share:** 1.0000000
- **Percentage:** 100%

The Campaign Group total daily budget is 1,000 USD, so:

$$
\operatorname{CampaignBudget}_c
=\operatorname{CampaignBudgetShare}_c\times 1000
$$

This produces:

### SP

Campaign initial daily budget (displayed to 4 decimal places): 239.8318 USD

### SB

Campaign initial daily budget (displayed to 4 decimal places): 297.3985 USD

### SD

Campaign initial daily budget (displayed to 4 decimal places): 234.1669 USD

### DSP

Campaign initial daily budget (displayed to 4 decimal places): 228.6028 USD

### Total

Campaign initial daily budget (displayed to 4 decimal places): 1,000.0000 USD

## 9. Step Six: Calculate How Many Ad Groups Each Campaign Needs

MTA scores do not determine the Ad Group count; candidate counts and capacity rules do.

### 9.1 SP and SB

Search ad products use:

$$
N=\max\!\left(
N_{\min},
\left\lceil\frac{K}{K_{\max}}\right\rceil,
\left\lceil\frac{Q}{Q_{\max}}\right\rceil,
\left\lceil\frac{P}{P_{\max}}\right\rceil
\right)
$$

Here, $K$, $Q$, and $P$ are the eligible Keyword-unit, SKU, and legal-Pair counts; the corresponding subscripted maximums are their per-group capacities.

Current SP:

$$
N_{\mathrm{SP}}=\max\!\left(1,\left\lceil\frac{3}{50}\right\rceil,\left\lceil\frac{3}{20}\right\rceil,\left\lceil\frac{3}{100}\right\rceil\right)=1
$$

Current SB:

$$
N_{\mathrm{SB}}=\max\!\left(1,\left\lceil\frac{4}{50}\right\rceil,\left\lceil\frac{4}{20}\right\rceil,\left\lceil\frac{4}{100}\right\rceil\right)=1
$$

### 9.2 SD and DSP

Display ad products use:

$$
N=\max\!\left(
N_{\min},
\left\lceil\frac{Q}{Q_{\max}}\right\rceil,
\left\lceil\frac{T}{T_{\max}}\right\rceil,
\left\lceil\frac{A}{A_{\max}}\right\rceil
\right)
$$

Here, $Q$, $T$, and $A$ are the eligible SKU, Target, and Audience counts.

Current SD:

$$
N_{\mathrm{SD}}=\max\!\left(1,\left\lceil\frac{4}{20}\right\rceil,\left\lceil\frac{4}{50}\right\rceil,\left\lceil\frac{2}{50}\right\rceil\right)=1
$$

Current DSP:

$$
N_{\mathrm{DSP}}=\max\!\left(1,\left\lceil\frac{4}{20}\right\rceil,\left\lceil\frac{8}{50}\right\rceil,\left\lceil\frac{2}{50}\right\rceil\right)=1
$$

The current output is therefore:

The resulting new Ad Group counts are SP = 1, SB = 1, SD = 1, and DSP = 1.

This is the capacity lower bound and initial count recommendation derived from aggregate candidate counts. There are currently no specific candidate entities or new-group assignments, so this count does not prove that all valid Pairs will necessarily fit into these groups under real grouping constraints.

If any capacity calculation exceeds `max_ad_groups`, the input is rejected rather than truncated to the maximum.

## 10. Step Seven: Split Equally among New Ad Groups within Each Campaign

The current candidate pool contains only counts of Keywords, SKUs, Targets, Audiences, and similar objects. It contains no specific candidate IDs and no mapping between candidates and future `ad_group_slot_id` values.

New groups in the same Campaign therefore have no features that the current model can use to distinguish their budgets. The code uses a strict equal split:

$$
\begin{aligned}
\operatorname{AdGroupBudgetShare}_{c,g}
&=\frac{\operatorname{CampaignBudgetShare}_c}{N_c},\\
\operatorname{AdGroupInitialDailyBudget}_{c,g}
&=\operatorname{AdGroupBudgetShare}_{c,g}\times B_{\mathrm{group}}.
\end{aligned}
$$

Equivalently:

$$
\operatorname{AdGroupInitialDailyBudget}_{c,g}
=\frac{\operatorname{CampaignBudget}_c}{N_c}
$$

All four current Campaigns have one new group, so each new-group budget equals its Campaign budget:

### `C_DEMO_SP_NEW_AG_01`

- **Campaign:** SP
- **Initial budget share:** 0.2398318
- **Initial daily budget (displayed to 4 decimal places):** 239.8318 USD

### `C_DEMO_SB_NEW_AG_01`

- **Campaign:** SB
- **Initial budget share:** 0.2973985
- **Initial daily budget (displayed to 4 decimal places):** 297.3985 USD

### `C_DEMO_SD_NEW_AG_01`

- **Campaign:** SD
- **Initial budget share:** 0.2341669
- **Initial daily budget (displayed to 4 decimal places):** 234.1669 USD

### `C_DEMO_DSP_NEW_AG_01`

- **Campaign:** DSP
- **Initial budget share:** 0.2286028
- **Initial daily budget (displayed to 4 decimal places):** 228.6028 USD

### 10.1 Calculation with Multiple New Groups

Suppose SP candidate counts cross a capacity boundary and the recommendation becomes two groups while its MTA score and the Campaign Group total budget remain unchanged:

For example, if the SP Campaign budget is 239.8318 USD and $N_{\mathrm{SP}}=2$, each new SP Ad Group receives $239.8318/2=119.9159$ USD.

Both new groups receive the same budget. The model does not fabricate a budget difference merely because an anonymous number is `NEW_AG_01` versus `NEW_AG_02`.

## 11. How the Minimum Budget Affects Results

The current `minimum_daily_budget_per_ad_group` is 25 USD for every Ad Product.

The Campaign's minimum executable budget is:

$$
\operatorname{MinimumRequiredCampaignBudget}_c
=N_c\times\operatorname{MinimumDailyBudgetPerAdGroup}_c
$$

Each current Campaign has one group, so its minimum executable daily budget is 25 USD. All four Campaign allocations exceed 25 USD, so every status is:

All four current allocations therefore have `execution_status` set to `EXECUTABLE`.

The minimum budget currently checks execution status only. If a Campaign's allocation is insufficient, the model:

- retains the Ad Group count calculated from capacity rules;
- retains the original budget allocation;
- marks `INSUFFICIENT_BUDGET_FOR_MINIMUMS`;
- does not automatically reduce the Ad Group count or transfer budget from other Campaigns.

## 12. Result without a Total Budget

If the input omits `campaign_group.total_daily_budget`, the model can still calculate:

- relative Campaign budget shares;
- the recommended Ad Group count for each Campaign;
- the relative budget share of each new Ad Group.

It does not output:

- `budget_seed_total`;
- `campaign_budget_seed`;
- `initial_daily_budget`;
- `minimum_required_daily_budget`.

It also adds:

It also adds the warning `NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY`.

## 13. Budget Conservation Relationships

The current generator and validator check:

$$
\begin{aligned}
\sum_t a_{t,o}&=1 &&\text{for every Outcome }o,\\
\sum_c s_c&=1,\\
\sum_{g\in c}s_{c,g}&=s_c,\\
\sum_c\sum_{g\in c}s_{c,g}&=1,\\
\sum_c B_c&=B_{\mathrm{group}},\\
\sum_{g\in c}B_{c,g}&=B_c.
\end{aligned}
$$

Budget amounts of the four new groups in the current output sum to:

$$
239.8318+297.3985+234.1669+228.6028=1000.0000\ \mathrm{USD}
$$

JSON stores the original Python floating-point values, so a field may appear as `234.16689999999994`. This is a floating-point representation effect; the current version does not round to the currency's smallest unit or redistribute remainders.

## 14. How to Read an Ad Group Output

Using the new SP group as an example:

```json
{
  "ad_group_slot_id": "C_DEMO_SP_NEW_AG_01",
  "allocation_basis": "CAMPAIGN_MTA_EQUAL_SPLIT",
  "budget_seed_share": 0.23983179999999998,
  "initial_daily_budget": 239.8318
}
```

Field meanings:

### `ad_group_slot_id`

Anonymous new-group slot for the next activation, not a historical Ad Group ID

### `allocation_basis`

First calculate the Campaign budget from MTA, then split equally within Campaign

### `budget_seed_share`

The new group's share of the Campaign Group total budget

### `initial_daily_budget`

Initial daily-budget amount for the new group

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
