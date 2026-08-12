---
title: Campaign Data Model
description: Campaign, Ad Group, rules, metrics, and operational schema reference
order: 50
---

# Campaign Data Model

This page translates and restructures the preserved Chinese schema analysis in `docs/zh/campaign-data-model.md`. The schema centers on Campaign and combines core entities, relationship tables, audit history, partitioned metrics, business rules, and read-oriented views.

## Architecture Overview

<DrawioDiagram base="./campaign-data-model" alt="Campaign data model architecture" />

| Layer | Responsibility | Representative tables |
| --- | --- | --- |
| Business grouping | Campaign Group scope, membership, conditions, and Key Performance Indicators (KPIs) | `campaign_group`, `campaign_group_relationship`, `campaign_group_condition_relationship`, `campaign_group_kpi` |
| Advertising entities | Campaign, Ad Group, Keyword, and Stock Keeping Unit (SKU) associations | `campaign`, `ad_group`, `ad_group_keyword`, `ad_group_sku`, `keyword`, `sku` |
| Rules and labels | Rule conditions/actions/schedules and Campaign classification | `campaign_rule_*`, `campaign_label`, `campaign_label_relationship` |
| Audit and operations | Snapshots, changes, uploads, negative Keywords, and harvesting | `campaign_audit`, `ad_group_audit`, `campaign_change_history`, `campaign_upload_record`, `negative_keywords_*`, `keyword_harvesting_*` |
| Time-series facts | Delivery, conversion, spend, profit, and placement metrics | `paid_search_traffic`, `paid_search_conversion`, `paid_search_metrics`, `campaign_spend`, `campaign_profit`, `daily_item_spots` |
| Read views | Common joins and derived KPIs | `vw_group_campaign_adgroup`, `vw_campaign_metadata`, `vw_campaign_kpi_metrics` |

## Core Advertising Entities

### `campaign`

| Field group | Meaning |
| --- | --- |
| Identity | Internal `id`, required `name`, and external `api_id`/`ers_id` |
| Schedule | `fiscal_year`, `start_date`, and nullable `end_date` |
| Advertising type | `sponsored_ads`, optional subtype, `targeting`, and `target_object_type` |
| Scope | `retailer_id`, `market_id`, and `account_id` |
| Control | `managed_by_search_planner`, platform `status`, update time, and pause reason |

Composite and partial indexes support common queries by status, retailer, advertising type, targeting mode, and active dates.

### `ad_group`

`ad_group` belongs to a Campaign through the schema's main database-enforced foreign key, `ad_group.campaign_id → campaign.id`. It carries platform identity and status fields plus Search Planner eligibility. `min_cpc` and `max_cpc` set Cost Per Click (CPC) bidding boundaries.

### Keyword and SKU associations

`ad_group_keyword` records Ad Group, Keyword, platform Keyword ID, status, match type, and update time. `ad_group_sku` records the equivalent Product association. These tables depend on logical uniqueness such as `(ad_group_id, keyword_id)` because the database does not supply primary-key protection.

The four entity levels—Campaign, Ad Group, association, and referenced Keyword or SKU—must all be enabled for an advertising object to be considered active.

## Campaign Groups

`campaign_group` represents Product Search Optimization (PSO) or standalone business scope. It stores primary and secondary KPI configuration, ordering, optional parent grouping, external authorization, active state, mode, and Search Planner activation.

Supporting tables separate concerns:

- `campaign_group_condition_relationship` defines which fiscal year, Retailer, Market, Category, Brand, and Segment conditions select Campaigns.
- `campaign_group_relationship` materializes the many-to-many Campaign Group-to-Campaign relationship.
- `campaign_group_kpi` stores current group-level targets.
- `campaign_group_daily_live_time_history`, `campaign_group_kpi_history`, and `campaign_group_history` preserve operational history.

## Rules, Labels, and Recommendations

`campaign_rule_info` is the rule definition root. Its category covers targeting, placement, or product identifiers; its application level may be Campaign, Brand, Campaign Group, or Label.

Child tables hold:

- metric comparisons in `campaign_rule_statement`;
- resulting actions and targets in `campaign_rule_action`;
- execution cadence and data windows in `campaign_rule_frequency`;
- included and excluded dates in `campaign_rule_date`;
- external attachment targets in `campaign_rule_relationship`;
- current and recommended values in `campaign_rule_recommendation`;
- daily KPI snapshots and execution decisions in `campaign_rule_history`.

Labels use `campaign_label` and `campaign_label_relationship`. Negative Keyword management uses a list, its Campaign bindings, the Keyword records, and failure records for rejected platform operations.

## Time-Series Metrics

| Table | Partitioning | Role |
| --- | --- | --- |
| `paid_search_traffic` | Monthly range on `date` | Impressions, clicks, budget, entity IDs, and platform IDs |
| `paid_search_conversion` | Monthly range on `date` | Sales and unit-sales facts |
| `paid_search_metrics` | Monthly historical partitions | Older combined delivery and conversion facts |
| `campaign_spend` | Unpartitioned | Platform campaign spend basis |
| `campaign_profit` | Unpartitioned | Campaign profit basis |
| `daily_item_spots` | Monthly range on `date` | Keyword/SKU item spots and advertising type |

The partitioned fact tables are append-oriented and do not have primary keys. New monthly partitions must exist before ingestion. Prefer existing covering indexes before adding new single-column indexes, because extra indexes amplify write cost.

`paid_search_traffic.budget` and `campaign_spend.budget` are separate business measurements and may not reconcile exactly. New consumers should prefer the split traffic and conversion facts plus governed views over the older combined `paid_search_metrics` table.

## Read Views

| View | Responsibility |
| --- | --- |
| `vw_group_campaign_adgroup` | Expands currently active Campaign Group → Campaign → Ad Group membership |
| `vw_campaign_group_metadata` | Group-level fiscal year, Retailer, Market, Category, and Campaign metadata |
| `vw_campaign_metadata` | Expands active manual Campaign × Ad Group × Keyword × SKU combinations and calculates optimization eligibility |
| `vw_sku_keyword_kpi_metrics` | Aggregates traffic and conversion at date, Campaign, Ad Group, SKU, and Keyword grain |
| `vw_campaign_kpi_metrics` | Produces daily Campaign KPIs from traffic, conversion, and campaign-spend sources |

These are ordinary views, not materialized views. Their query load reaches underlying tables, so partition pruning and index use remain important.

## Audit and Integration

- `campaign_audit` and `ad_group_audit` capture daily entity snapshots and use attribute hashes for idempotent loading.
- `campaign_change_history` records Campaign changes, success, and error details.
- `campaign_scope_daily_snapshot` records the Campaign membership of a group by batch and date.
- `campaign_upload_record` retains detailed payload fields for Sponsored Brands, Sponsored Products, Sponsored Display, and Sponsored Brands Video operations.
- `keyword_harvesting_batch_tracking` models harvesting workflow dependencies and status; `keyword_deep_scrape_history` stores the collected detail.
- `integration_api_call_log` records cross-service calls.

## Eligibility and Integrity Rules

1. Except for `ad_group.campaign_id`, most relationships are logical foreign keys; application-layer validation is mandatory.
2. Enforce uniqueness for relationship rows that have no primary key.
3. Require enabled status at Campaign, Ad Group, Keyword association, and SKU association levels.
4. A Campaign is algorithm-supported only when it is either a Sponsored Product with Keyword targeting, or a Sponsored Brand Product Collection with Keyword targeting.
5. Product Search Optimization additionally requires Search Planner management on both Campaign and Ad Group.
6. Use external platform `api_id` fields for retailer integrations, `auth_id` for AutoBidder, and `ers_id` for the external ERS mapping.
7. Distinguish traffic-derived spend from platform Campaign spend in reports and validation.

## Core Entity Relationships

<DrawioDiagram base="./campaign-data-model-er" alt="Core Campaign data model entity relationships" />

The editable diagrams are maintained beside this page so schema ownership and visual documentation remain together.
