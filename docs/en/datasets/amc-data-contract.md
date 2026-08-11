---
title: AMC MTA Data Contract
lang: en-US
---

# AMC MTA Data Contract

This document is the source of truth for current inputs, path rules, and attribution definitions.

## CSV Whitespace and Structure Rules

Every CSV entry point applies `strip()` semantics to remove leading and trailing whitespace from field names and values. Spaces inside strings are preserved exactly; they are neither removed nor collapsed. After cleanup, headers must be non-empty and unique. If two original fields become identical after cleanup, the program raises an error immediately. Every row must have exactly the same number of columns as the header. Extra or missing columns are never padded, discarded, or silently accepted.

Strict entry points such as AMC paths and model results still require field order and the complete schema to match the corresponding contract exactly after normalization. Whitespace tolerance does not relax numeric, set, conservation, or business-relationship validation. The five canonical outputs continue to be written as normalized CSV without leading or trailing whitespace, with unchanged field names, row counts, and numeric contracts.

## Simulated Data Layers and Canonical Attribution Input

| Data | Purpose |
| --- | --- |
| `synthetic_user_events_sample.csv` | Integrated fact source for local simulation only; one synthetic user event per row |
| `amc_touchpoint_events_sample.csv` | Used only to demonstrate local path construction; does not represent user detail exportable from AMC |
| `amc_mta_path_report_raw_sample.csv` | Anonymous aggregated paths; direct input to the attribution algorithms |
| `amazon_ads_report_sample.csv` | Amazon Ads cost and performance used to calculate efficiency metrics |
| `amc_touchpoint_entity_aggregate_sample.csv` | Anonymous aggregated evidence from touchpoints to historical Campaign/Ad Group/Keyword/SKU entities |

`synthetic_user_id` from the master table must not enter any of the latter four data types. Entity aggregation currently uses a local demonstration threshold of at least five synthetic users; this value is not an official Amazon privacy threshold. A real application should sort events, construct paths, and perform privacy aggregation inside the AMC clean room, exporting only aggregates that satisfy platform privacy rules.

The master table also stores historical Campaign/Ad Group values, applicable Keyword/Match Type/Target values, SKU/ASIN values, per-event costs, and journey results. These are historically observed facts. They do not replace the candidate pool, budget, Campaign count, capacity, or platform policy supplied at strategy runtime.

## Field Definitions

A conceptual `TOUCHPOINT` event must provide `journey_id`, `event_time`, `ad_product`, `format`, and `interaction_type`; empty `placement` and `creative` values are normalized to `UNSPECIFIED`. `interaction_type` may only be:

`interaction_type` may only be `IMPRESSION` or `CLICK`.

A missing, empty, or other value terminates path construction. This interaction type comes from the AMC event-normalization layer; the program does not reconstruct user paths from aggregate `impressions` and `clicks` values in the Amazon Ads report.

A `CONVERSION` must provide:

| Field | Meaning |
| --- | --- |
| `users` | Unique users covered by the path |
| `converted_users` | Unique users who purchased at least once |
| `purchase_count` | Number of orders/purchase events; may exceed the number of purchasers |
| `revenue` | Purchase revenue |

The AMC aggregated path table used for attribution retains only these four metrics plus the window, account, and `path` fields. `new_to_brand_purchases` and `avg_days_to_purchase` do not enter the aggregated path output.

Count fields must be finite non-negative integers, revenue must be a finite non-negative number, and the following constraints must hold:

$$
\begin{aligned}
0&\le \text{converted users}\le \text{users},\\
\text{purchase count}&\ge \text{converted users},\\
\text{new-to-brand purchases}&\le \text{purchase count}.
\end{aligned}
$$

In addition, `converted_users` must be positive whenever `purchase_count` or `revenue` is positive.

The legacy AMC field `purchases` is no longer accepted, preventing confusion between purchasing-user count and order count. The native Amazon Ads `purchases` field is retained and renamed `reported_purchases` in outputs.

## Five-Segment Interaction Key and Ads Billing Rules

AMC paths and attribution models use a five-segment interaction key:

The key is `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`.

The preceding advertising-attribute segments are uppercased and may contain only letters, digits, and underscores. `INTERACTION_TYPE` may only be `IMPRESSION` or `CLICK`. If the same ad is first viewed and then clicked, both events are retained as ordered, distinct five-segment touchpoints in the path.

The Amazon Ads report must use the same five-segment key and provide `interaction_type`, `cost_type`, and an exactly matching `normalizedTouchpoint`. For DSP, `FORMAT` comes from `inventoryType`; for Sponsored Ads, it comes from `adType`.

`cost_type` may only be `CPC` or `CPM`: a CPC-billed row must be `CLICK`, and a CPM-billed row must be `IMPRESSION`. A non-billable interaction for the same ad may participate in alignment and attribution as its own five-segment row, but its cost must be 0. Platform `purchases` and `sales` are assigned only to `CLICK` rows. The program does not copy costs, allocate costs backward from attribution, or infer AMC user paths from aggregate Ads metrics.

## Path Rules

The canonical pipeline automatically determines the reporting window from the earliest through latest `reportDate` in the Amazon Ads input, inclusive. It supports a single day, any duration, cross-year windows, and leap days without relying on fixed configuration dates. The current deterministic local simulated dataset covers `2026-01-01` through `2026-03-31`, or 90 days.

- Look backward starting from the last touchpoint before a purchase; touchpoints are ordered by timestamp.
- Gaps between adjacent touchpoints and from the last touchpoint to purchase must all be `<= 14 days`; exactly 14 days is valid.
- At the first gap `> 14 days`, exclude the touchpoint to its left and all earlier touchpoints.
- There is no upper bound on total path duration.
- The earliest retained touchpoint must be strictly later than `report_start_date`; otherwise, the entire path is omitted.
- A purchase must not be later than `report_end_date`; a purchase without a valid touchpoint is omitted.
- Every `CONVERSION` must be inside the automatically detected Ads window. An out-of-window conversion terminates the entire run rather than being cropped. Raw touchpoints may precede the window so that the existing start-boundary test can be applied.
- When one journey contains several purchases, a later purchase uses only new touchpoints after the previous purchase.

For example, `A --19 days--> B --9 days--> C --9 days--> D --purchase` produces `B > C > D`.

## Alignment Requirements

One current run accepts only one `marketplace + advertiser_id + currency` scope. AMC and Ads must have:

- the same account and marketplace;
- the same report start and end dates; AMC dates must be valid ISO dates and the start must not be later than the end;
- exactly the same set of five-segment interaction touchpoints; and
- Ads data for every five-segment interaction touchpoint on every day in the window.

Ads dates must be continuous from earliest to latest, with exactly the same five-segment touchpoint set every day. A `reportDate + normalizedTouchpoint` combination must not be duplicated. The program does not shorten the window based on event dates or silently fill gaps in Ads dates with zeros.

Any missing or extra date, mixed account scope, or mismatched key terminates attribution instead of being silently zero-filled.

## Models and Outputs

Markov builds separate Outcome models for purchasing users, order count, and revenue. The purchasing-user model uses `converted_users` as the conversion endpoint and `users - converted_users` as Null; the order and revenue models use `purchase_count` and `revenue`, respectively, as path weights.

Shapley computes a unanimity game over the unique touchpoint set of each path and separately allocates the three Outcomes. A repeated touchpoint is counted only once within one path.

Both models output three sets of shares and attribution values at five-segment interaction granularity. Each result conserves separately:

$$
\begin{aligned}
\sum_t \widehat{U}_t&=U,\\
\sum_t \widehat{P}_t&=P,\\
\sum_t \widehat{R}_t&=R,
\end{aligned}
$$

where the hatted values are attributed converted users, purchases, and revenue by touchpoint, and $U$, $P$, and $R$ are the corresponding input totals.

Each model outputs one five-segment primary result containing `touchpoint`, `interaction_type`, three sets of attribution metrics, Amazon Ads performance and cost, and efficiency metrics. The Markov and Shapley model files remain separate. The pipeline generates three additional governance artifacts: a complete 51-row five-segment comparison, a five-segment overall summary for the three Outcomes, and 51 management recommendation records. Model attribution, support, gap diagnostics, and recommendations all use the full five-segment key.

After trimming leading and trailing whitespace, comparison-input headers must exactly equal the complete contract. The two models must have identical touchpoint sets, costs, and platform performance, and shares and attribution totals must separately conserve for every nonzero Outcome. The three dual-model artifacts have fixed schemas of 14/13/15 columns and include five reliability fields: `calculation_valid`, `data_support_sufficient`, `models_consistent`, `reliability_status`, and `reliability_reason`. A result is `RELIABLE` only when the calculation is valid, raw support simultaneously reaches `30` purchases, `20` purchasing users, and `5` unique paths, and the model gap for a nonzero Outcome simultaneously satisfies `gap_pp<=1.0` and `relative_gap<=0.20`. For each Outcome, the summary aggregates the three underlying Boolean values with AND across all touchpoints, then derives summary reliability with the same formula. TVD, Spearman correlation, and Top-K overlap describe the summary only; they do not enter the reliability calculation. Both single-model results retain 18 columns. Legacy stability, status, decision, review, automation, reason-code, and duplicate-efficiency fields no longer enter dual-model artifacts.

The recommendation table chooses the display form of `recommended_value` from reliability on the same row. For a nonzero Outcome, a reliable result contains the Markov `official_share`; an unreliable result contains an ascending closed interval of the Markov and Shapley shares, `[low,high]`. A zero Outcome has no interpretable distribution, so the value remains empty. This field does not change Markov's identity as the official model, and it is neither a confidence interval nor permission for automated budget changes.

ROAS, ROI, CPA, and cost per converted user are empty on zero-cost rows.

Efficiency metrics:

$$
\begin{aligned}
\operatorname{ROAS}&=\frac{\text{attributed revenue}}{\text{cost}},\\
\operatorname{ROI}&=\frac{\text{attributed revenue}-\text{cost}}{\text{cost}},\\
\operatorname{CPA}&=\frac{\text{cost}}{\text{attributed purchase count}},\\
\text{cost per converted user}&=\frac{\text{cost}}{\text{attributed converted users}}.
\end{aligned}
$$
