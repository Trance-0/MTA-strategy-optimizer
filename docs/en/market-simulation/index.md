---
title: Market Simulation
description: The MTA-SIM contract, this project's inputs, and compatibility boundaries
compact: "Routes MTA-SIM native five-segment tables, legacy four-segment compatibility, simulator-local versus `mta_common` models, Provider missingness, Campaign/Product budget experiments, 10k CSV and 100k PostgreSQL modes, and the centralized `modules/mta_standard/` boundary."
lang: en-US
source_files: modules/mta_standard/src/mta_sim_research_adapter.py
---

# Market Simulation

This page adopts the documentation categories of the [Trance-0/MTA-SIM-dataset data contract](https://github.com/Trance-0/MTA-SIM-dataset/blob/main/ZheyuanWu/docs/DATA_CONTRACT.md) and [generation flow](https://github.com/Trance-0/MTA-SIM-dataset/blob/main/ZheyuanWu/docs/dataset-creation/generation-flow.md), and explains how they differ from this repository's current inputs.

For the translated operational schema references, see the [Product data model](product-data-model.md) and [Campaign data model](campaign-data-model.md). Each page includes editable, theme-aware Draw.io diagrams.

## MTA-SIM's Three Logical Tables <span class="status-label status-external" aria-label="External"></span>

### `amc_path_report`

- Purpose: Aggregated, ordered customer paths and observed Outcomes
- Training boundary: Primary path-attribution input

### `amazon_ads_daily_touchpoint_performance`

- Purpose: Daily touchpoint delivery, cost, and platform-reported results
- Training boundary: Optional feature, diagnostic, or reporting input

### `simulation_ground_truth`

- Purpose: Simulator-known incremental removal effects and credit shares for touchpoints
- Training boundary: **Evaluation only; prohibited as a training feature**

Purchases in the path table and platform-reported purchases in the Ads table must not be added together; they are Outcomes with different semantics.

## This Repository's Current Inputs <span class="status-label status-verified" aria-label="Verified"></span>

### `amc_mta_path_report_raw_sample.csv`

- Granularity: Aggregated path
- Role: Markov and Shapley input

### `amazon_ads_report_sample.csv`

- Granularity: Date × touchpoint
- Role: Cost and diagnostic metrics

### `amc_touchpoint_entity_aggregate_sample.csv`

- Granularity: Touchpoint × delivery entity
- Role: Bridge from touchpoint to Campaign/historical Ad Group

### `amc_mta_recommended_attribution.csv`

- Granularity: Touchpoint × Outcome
- Role: Attribution input for the strategy initializer

### `strategy_request.json`

- Granularity: Campaign Group request
- Role: Total budget, Outcome weights, and capacity rules

### `candidate_pool.json`

- Granularity: Campaign candidate counts
- Role: Calculate the new Ad Group count

## Native and Legacy Compatibility <span class="status-label status-verified" aria-label="Verified"></span>

The path-table column names currently match, but the touchpoint contracts differ:

| Item | MTA-SIM | This repository's current AMC MTA |
| --- | --- | --- |
| Normalized touchpoint | Native five segments: `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`; old fixtures may contain four | Native five segments |
| Ads-specific fields | Preserves the sixteen existing columns, including `unitsSold`; interaction is encoded in `normalizedTouchpoint` | Includes explicit `interaction_type` and `cost_type`, but not `unitsSold` |
| Impression/click representation | Separate ordered events and interaction-specific rows; old aggregate fixtures remain compatibility input | Explicitly distinguished as the fifth segment of the touchpoint key |
| Strategy Bridge | Not one of the three core tables | Requires an additional entity-aggregate table |

Native MTA-SIM rows now pass through unchanged after canonical validation.
Historical four-segment fixtures still require an explicit `SimulatorConfig`;
the adapter never derives interaction identity from Cost Per Click (CPC), Cost
Per Mille (CPM), impressions, or clicks.

## Implemented Adaptation <span class="status-label status-verified" aria-label="Verified"></span>

The pinned submodule and explicit Dataset Adapter now:

1. Validate the input version and column order.
2. Preserve a native fifth segment; adapt an old four-segment key only from an explicit compatibility mapping.
3. Preserve `unitsSold` as an optional diagnostic field instead of forcing a mapping.
4. Keep entity-Bridge generation as a separate strategy integration boundary.
5. Run attribution only after the complete data package passes validation.
6. Isolate `simulation_ground_truth` in the evaluation workflow.

The adapter runs the ZheyuanWu generator, preserves the three original file
schemas while accepting native five-segment values, aggregates daily path
windows into one local model scope, and preserves Ground Truth as an
independent answer table. See [Generate MTA-SIM data](../introduction/environment/mta-sim-generation.md).

## Adapter Status <span class="status-label status-verified" aria-label="Verified"></span>

`modules/mta_standard/` implements the generation boundary and items 1, 2, 3, 5, and 6 above:

### Run the reviewed generator source

Where it is implemented: `mta_sim_generator_adapter` invokes the pinned `external/mta_sim_dataset/ZheyuanWu` pipeline.

### 1. Validate column order

Where it is implemented: `dataloader` requires the exact contract header for each table.

### 2. Never guess `INTERACTION_TYPE`

Where it is implemented: native keys are validated directly. `SimulatorConfig`
is required only for historical four-segment input and rejects missing,
ambiguous, or colliding mappings.

### 3. Preserve `unitsSold`

Where it is implemented: Kept verbatim on the annotated performance rows as a diagnostic.

### 5. Validate before attributing

Where it is implemented: Loading fails before any model runs; `validate_standard_output` guards the results.

### 6. Isolate Ground Truth

Where it is implemented: `MtaSimDataset` has no ground-truth field and the loader accepts no ground-truth path.

Item 4, the Campaign and Ad Group entity Bridge, remains the responsibility of the strategy module and is unchanged.

## Independent Domain Models and the Mapping Boundary

MTA-SIM owns its own Provider, Touchpoint, Product, Campaign, budget, delivery,
outcome, and lineage dataclasses. It does not import this repository. The
loader maps the file representation into `modules/mta_common/`; Provider is
supplied from run metadata because the five-segment key omits it, and an
`UNSPECIFIED` placement or creative becomes `NOT_PROVIDED` because the file
cannot recover the more detailed absence reason.

Latent simulator truth remains evaluation-only. Provider-observed incomplete
Touchpoints are ordinary historical input; the complete latent Touchpoint and
organic/incremental truth do not become attribution or strategy features.

`load_mta_sim_research_snapshot` reads the optional
`simulation_research.json` sidecar and constructs canonical `mta_common`
Provider capabilities, Products, Product Economics, Campaigns, Ad Groups,
Campaign-Product links, Budgets, Deliveries, Outcomes, and lineage. Synthetic
MTA-SIM profile names map to canonical `Provider.GENERIC`; the adapter retains
the original profile name separately because that provider conversion is
lossy. Structured Touchpoint availability is read from the sidecar directly,
so `NOT_PROVIDED`, `NOT_APPLICABLE`, `UNKNOWN`, and `REDACTED` remain distinct.
The unchanged CSV-only boundary cannot recover that distinction.

Simulator-only research context that has no field on the canonical value
object—Campaign identifiers on delivery/outcome records, Product identifiers
on outcomes, and budget-level multipliers—is kept in parallel immutable
context mappings on the adapter result. It is not added to, or confused with,
the canonical dataclasses.

## Research Generation Modes

### Local comma-separated value mode

`research-10k.json` produces 10,000 Campaign × marketplace × day × budget-level
observations plus the unchanged three Comma-Separated Value (CSV) files and an
effective configuration snapshot. This mode supports local analysis.

### Direct PostgreSQL mode

`research-100k-postgresql.json` produces 100,000 observations and writes them
in bounded batches through the simulator's explicit PostgreSQL adapter. It
does not stage a temporary CSV. Replacement requires the explicit database
reset flag; normal startup and generation never drop tables.

See [the standardized MTA interface](../attribution/standardized-interface/) for the adapter's contract, failure modes, and evaluation metrics.

## Source Files

### `mta_sim_research_adapter.py`

Source: `modules/mta_standard/src/mta_sim_research_adapter.py`

- Responsibility: Convert the independent MTA-SIM research-sidecar representation into existing `mta_common` objects while preserving simulator-only join context and evaluation-only classification at the integration boundary.
- Inputs: A UTF-8 `simulation_research.json` file produced by MTA-SIM generator version 2.
- Outputs: `MtaSimResearchSnapshot`, whose domain-record fields contain canonical `mta_common` objects and whose context fields preserve non-canonical run/profile/join metadata.
- Dependencies: Python standard library and `modules/mta_common`; it has no import from the MTA-SIM repository.
- Verification: `modules/mta_standard/tests/test_mta_sim_research_adapter.py`.
