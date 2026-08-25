---
title: Dashboard Data Model
description: The eighteen relational classes the dashboard reads when DATABASE=true
compact: "PostgreSQL mirror contract in `dashboard/models.py`: eighteen ordered entity, history, model-output, and strategy tables populated by `script/import_to_database.py` and read by Flask repositories in database mode. Covers keys, constraints, lineage, nullability, rounding, and file/database parity."
order: 60
---

# Dashboard Data Model

The dashboard reads the same numbers in two ways. With `DATABASE=false` it reads the committed CSV and JSON artifacts directly, which is the mode used for a cloud demo and for any checkout that has not run an import. With `DATABASE=true` it reads the PostgreSQL schema on this page, which `script/import_to_database.py` populates from those same artifacts.

This schema is a **mirror, not a source**. Nothing computes an attribution share or a budget figure here; every value originates in a pipeline artifact. A table exists on this page only because some view needs to read it, and the import command is the only writer.

## Why the Database Is Optional

The attribution, standard, and strategy modules never import these classes. They read and write files, and they depend on the Python standard library alone. The database and the classes that define it belong to the dashboard, so a reader can reproduce every published number without a database at all.

### `DATABASE=false`

- Reads: `modules/*/data/simulated/*`, `modules/*/outputs/**`
- Requires: Nothing beyond the repository

### `DATABASE=true`

- Reads: The eighteen tables below
- Requires: A populated PostgreSQL instance

The Flask repositories under `backend/repository/` guarantee that both modes
return identical fields, types, values, and row order, so a view cannot tell
which one it is reading. Five differences make parity non-trivial and are
normalized in the loaders rather than in any view; they are specified in full
under [Two Data Sources, One Contract](../dashboard/index.md#two-data-sources-one-contract).

One of them constrains this schema directly. **Row order is part of the contract**, because the views render in the order the loader returns, and a file loader returns the artifact's own order. Every table therefore carries a surrogate `id` primary key, `script/import_to_database.py` inserts rows in each artifact's order, and every query the dashboard issues orders by that key rather than by the business key — `order by campaign_id` sorts alphabetically and would put the same Campaigns on screen in a different sequence than file mode does.

## Layers

The classes group into four layers that mirror the project's own stages. Each layer depends only on the ones above it.

### Entity

- Question it answers: What exists?
- Classes: `Advertiser`, `CampaignGroup`, `Campaign`, `AdGroup`, `Touchpoint`, `TargetingCandidate`

### History

- Question it answers: What was observed?
- Classes: `AdsDailyPerformance`, `PathReport`, `TouchpointEntityBridge`, `SyntheticUserEvent`

### Model output

- Question it answers: What did the models conclude?
- Classes: `AttributionRun`, `AttributionResult`, `ModelComparisonTouchpoint`, `ModelComparisonSummary`, `RecommendedAttribution`

### Strategy

- Question it answers: What was recommended?
- Classes: `BudgetRecommendationRun`, `CampaignBudgetRecommendation`, `AdGroupBudgetSlot`

Every table that belongs to a run carries a foreign key to that run, so two report windows can be loaded side by side without one overwriting the other.

## Entity Layer

### `Advertiser`

Table `advertiser`. The root of the hierarchy: one advertising account in one marketplace, holding `advertiser_id`, `marketplace`, and `currency`. One attribution run covers exactly one advertiser.

### `CampaignGroup`

Table `campaign_group`. The top level of the advertising hierarchy and the level at which a single `total_daily_budget` is set; the strategy module divides that total among the group's Campaigns. Alongside `group_name`, `platform`, and `currency`, it carries the identifiers of the strategy request it was read from — `sample_version`, `candidate_pool_id`, and `mta_batch_id` — so a group can be traced to the request and the attribution batch that supplied its evidence.

### `Campaign`

Table `campaign`. One Campaign, carrying exactly one `ad_product` plus `campaign_name` and `status`. Because a Campaign has a single ad product, the ad product is the level at which attribution evidence is bridged into budget shares.

### `AdGroup`

Table `ad_group`. The level at which budget is actually set. Only **historical** Ad Groups appear here, because only they have an identifier and a history; the new Ad Groups the strategy module proposes are anonymous slots and live in `ad_group_budget_slot` instead.

### `Touchpoint`

Table `touchpoint`. The five-segment interaction vocabulary, and the join key that lets attribution and spend meet without a key of their own. `touchpoint_key` is the canonical `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` string, unique across the table. The five segments are also stored individually as `ad_product`, `format`, `placement`, `creative`, and `interaction_type`, so the dashboard can group by any one of them without parsing the key. `cost_type` is nullable and is filled from whichever spend row first reports it.

### `TargetingCandidate`

Table `targeting_candidate`, unique on `(campaign_pk, candidate_kind)`. One row per Campaign per kind of eligible targeting object — keyword unit, SKU, legal pair, target, or audience — with its `eligible_count`. These counts drive the capacity calculation that decides how many new Ad Groups a Campaign can support. `candidate_usage_policy` and `sample_version` carry the source artifact's own provenance, so the dashboard states the policy it operated under rather than assuming one.

## History Layer

### `AdsDailyPerformance`

Table `ads_daily_performance`, unique on `(report_date, touchpoint_pk)`. One day of platform-reported delivery for one touchpoint: `impressions`, `clicks`, `cost`, `purchases`, `sales`, plus `marketplace`, `account_id`, and `currency`.

This table is the source of spend and of the report window itself: the pipeline infers the window from the earliest and latest `report_date` present here rather than from configuration. Cost per click applies only to CLICK rows and cost per mille only to IMPRESSION rows, so spend is never double counted.

### `PathReport`

Table `path_report`. One anonymous aggregated conversion path, where `path` is a `>`-joined sequence of native five-segment interaction-aware touchpoints and `path_length` is its step count, with `users`, `converted_users`, `purchase_count`, and `revenue`. Rows arrive already aggregated to satisfy privacy thresholds; no user-level detail is stored or implied.

### `TouchpointEntityBridge`

Table `touchpoint_entity_bridge`. The link that carries attribution from the touchpoint vocabulary into the advertising hierarchy: it names both a touchpoint and the `campaign_id` and `ad_group_id` it was delivered through, along with the keyword, target, audience, ASIN, and SKU identifiers that qualified it.

Its `assisted_converted_users`, `assisted_purchase_count`, and `assisted_revenue` credit **every** touchpoint on a converting journey, so they deliberately sum to more than the reported total. They apportion a total; they do not add up to one.

### `SyntheticUserEvent`

Table `synthetic_user_event`. One simulated advertising or purchase event, keyed by `synthetic_user_id` and `journey_instance_id`, with `event_type`, `event_time`, `touch_position`, and the `converted`, `purchase_count`, and `revenue` outcome fields. Its `campaign_id`, `ad_group_id`, and `touchpoint_pk` are nullable, because a purchase event belongs to no touchpoint.

This is the single fact source every other simulated table is derived from, and by far the largest table. It is a local demonstration fixture: it is **not** evidence that user-level events can be exported from a clean room. The import command caps it at a bounded sample unless `--full-events` is given, because the dashboard only aggregates it.

## Model Output Layer

### `AttributionRun`

Table `attribution_run`. One execution of the attribution pipeline over one window, identified by a unique `batch_id` and describing `report_start_date`, `report_end_date`, `marketplace`, `advertiser_id`, and `max_touchpoint_gap_days`. Every result, comparison, and recommendation row points back to a run, which is what lets two windows coexist.

### `AttributionResult`

Table `attribution_result`, unique on `(run_pk, attribution_model, touchpoint_pk)`. One model's verdict for one touchpoint. It holds the three share columns and the three attributed totals — one pair per Outcome — beside the delivery and cost figures for the same touchpoint and the derived efficiency measures `roas`, `roi`, `cpa`, and `cost_per_converted_user`.

Each Outcome is attributed independently. A touchpoint can lead on revenue and trail on converted users, and neither figure is derived from the other.

### `ModelComparisonTouchpoint`

Table `model_comparison_touchpoint`, unique on `(run_pk, touchpoint_pk, outcome)`. Markov against Shapley for one touchpoint and one Outcome: `markov_share`, `shapley_share`, `gap_pp`, and `relative_gap`, with the raw counts that support them.

It also carries the three reliability flags — `calculation_valid`, `data_support_sufficient`, and `models_consistent` — and the `reliability_status` and `reliability_reason` derived from them. The verdict is the **AND** of the three flags: one false flag makes the row UNRELIABLE no matter how closely the two models happen to agree.

### `ModelComparisonSummary`

Table `model_comparison_summary`, unique on `(run_pk, outcome)`. One whole-Outcome diagnostic row: `touchpoint_count`, `tvd`, `spearman_rho`, and `top_k_overlap_rate`, plus the same flag and status columns.

The diagnostics inform a reader; they never change the verdict, which AND-aggregates the per-touchpoint booleans.

### `RecommendedAttribution`

Table `recommended_attribution`, unique on `(run_pk, touchpoint_pk, outcome)`. The governed view a consumer is meant to read, naming the `official_model` and its `official_share`, the `benchmark_model` and its `benchmark_share`, and the gap between them.

`recommended_value` is a text union type. A RELIABLE row holds the official point value as a string; an UNRELIABLE row holds the closed interval `[low,high]` between the two model shares instead. It is a governance output, not a third model, and an interval grants no budgeting authority.

## Strategy Layer

### `BudgetRecommendationRun`

Table `budget_recommendation_run`. One execution of the budget initializer, holding `schema_version`, `recommendation_type`, `handoff_status`, the `formula_version` and `normalization_universe` that derived it, the three outcome weights, and `budget_seed_total`.

`is_optimized` is false for every current run: this is a deterministic seed derived from historical attribution, not an optimizer result. The `source_*` columns pin the provenance of the evidence consumed — the window, marketplace, advertiser, and the SHA-256 digests of the attribution and entity input files — so a recommendation can be traced back to the exact attribution output that justified it.

### `CampaignBudgetRecommendation`

Table `campaign_budget_recommendation`, unique on `(run_pk, campaign_id)`. One Campaign's outcome: its three normalised `score_*` contributions, the `campaign_mta_score` that weights them, the `budget_seed_share` that renormalises the score, and the resulting `campaign_budget_seed`.

`minimum_required_daily_budget` is the per-Ad-Group floor times the recommended slot count, and `execution_status` records whether the recommended budget clears it. The bridge columns record how much evidence stood behind the score and whether a fallback was needed. `campaign_mta_score` is stored at full float precision to match the JSON artifact; only money fields are rounded.

### `AdGroupBudgetSlot`

Table `ad_group_budget_slot`. One proposed new Ad Group: its `ad_group_slot_id`, the `allocation_basis` that justified it, its `budget_seed_share` within the Campaign, and its `initial_daily_budget`.

A slot is anonymous by construction. A proposed Ad Group has no history yet, so it carries no historical identifier and never joins to `ad_group`. For the same reason the Campaign seed is split equally among its slots: nothing distinguishes one proposed group from another, and `allocation_basis` records that rule rather than leaving the equal split implicit.

## Loading the Schema

```bash
uv run --extra dashboard python script/import_to_database.py --dry-run
uv run --extra dashboard python script/import_to_database.py
```

The command reads every artifact, creates the tables, and writes them inside one transaction. It refuses to overwrite a populated database unless `--replace` is given, so an accidental second run cannot destroy existing rows; `--replace` drops and rebuilds every table, which is what a schema change requires. Connection settings come from `.env`, for which `sample.env` is the tracked template.

Two source files carry a Chinese field-description row directly beneath the header. It is documentation, not data, and both the import command and the file-mode reader drop it by matching its exact first-cell marker rather than by guessing, because a heuristic silently discards a real data row from the files that have no such row.
