---
title: Ad Group Counts and Output
compact: "Detailed initializer arithmetic for capacity-derived Ad Group counts, equal within-Campaign budget splits, minimum budget effects, no-total-budget shares, conservation equations, and field-by-field reading of an Ad Group result."
lang: en-US
---

# Ad Group Counts and Output

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
