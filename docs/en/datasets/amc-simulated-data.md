---
title: AMC MTA Simulated Data
lang: en-US
---

# AMC MTA Simulated Data

All dynamic metrics in this directory derive from one user-event master table used only for local demonstration:

```text
synthetic_user_events_sample.csv
├── amc_touchpoint_events_sample.csv
│   └── amc_mta_path_report_raw_sample.csv
├── amazon_ads_report_sample.csv
└── amc_touchpoint_entity_aggregate_sample.csv
```

| File | Purpose |
| --- | --- |
| `synthetic_user_events_sample.csv` | The single simulated fact source; one synthetic user's touchpoint or outcome event per row |
| `amc_touchpoint_events_sample.csv` | Anonymous conceptual events aggregated from the same path templates for local path construction |
| `amc_mta_path_report_raw_sample.csv` | Five-segment aggregated paths generated from anonymous conceptual events for attribution input |
| `amazon_ads_report_sample.csv` | Five-segment daily performance, platform last-click outcomes, and cost aggregated from the master table |
| `amc_touchpoint_entity_aggregate_sample.csv` | Privacy-safe aggregated relationship between touchpoints and historical Campaign/Ad Group/Keyword/SKU entities |

The sample window is `2026-01-01` through `2026-03-31`, or 90 days. The master table contains 11,147 events, 2,400 synthetic users, and 3,547 journeys. It derives 645 anonymous conceptual events, 153 unique paths, 1,530 Ads daily rows, and 34 entity aggregates. A user may have multiple journeys; non-converting journeys are retained to form Null paths. Entity aggregation requires at least five synthetic users, but this is only a local simulation threshold and does not represent Amazon's actual privacy threshold.

`synthetic_user_id` may exist only in the master table and must not enter any aggregate or attribution artifact. A real application should not obtain or export such user-level CSV data. It should process events inside the AMC clean room and receive only aggregated results that meet platform privacy requirements.

All five data types use the same five-segment `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` touchpoint. CPC cost is assigned only to CLICK and CPM cost only to IMPRESSION; non-billable interactions have zero cost. Platform purchases and sales derive from the last eligible CLICK in each journey. Historical Keyword/SKU values are observed facts, not the future candidate pool frozen by the strategy module.

Reconciliation follows metric semantics. Impressions, clicks, and cost conserve exactly between the master table and Ads aggregates. Ads purchases and sales equal only the subset of outcomes with a valid last click inside the 14-day window; they do not equal all conversions in the master table. `assisted_*` in the entity table means that an entity participated in a journey. One outcome may therefore support several entities, so values must not be summed across entities. The entity table's `reported_*` values still follow last-click rules. No entity group is hidden by the privacy threshold in this sample, so entity-table impressions, clicks, and cost also align exactly with the master table.

Regenerate and validate:

```bash
uv run python -X utf8 -B script/regenerate_simulated_dataset.py
uv run python -X utf8 -B script/validate_data_alignment.py
```

Complete regeneration publishes all ten artifacts atomically; any failed step rolls back the operation, and fixed inputs reproduce byte-for-byte.
