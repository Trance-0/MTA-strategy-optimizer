---
title: Project Structure and Data Flow
description: Model architecture, data pipeline, and corresponding source code
compact: "Directory responsibilities and entry-point files per module, plus the stage-by-stage data pipeline from synthetic generation through attribution, governance, and strategy initialization. Read when locating which module owns a stage."
lang: en-US
---

# Project Structure and Data Flow

## Model Architecture <span class="status-label status-verified" aria-label="Verified"></span>

<DrawioDiagram base="./project-structure" alt="Project model architecture" />

## Directory Responsibilities <span class="status-label status-verified" aria-label="Verified"></span>

### `modules/mta_attribution/`

- Project responsibility: Build aggregated paths, run both attribution models, compare them, and publish recommended attribution
- Key entry point: `src/attribution_contract.py`

### `modules/mta_standard/`

- Project responsibility: Run the pinned ZheyuanWu generator, load MTA-SIM tables, adapt four-segment keys, run any model through one interface, and score results against ground truth
- Key entry point: `src/mta_sim_generator_adapter.py`, `src/model_registry.py`

### `modules/mta_strategy_recommendation/`

- Project responsibility: Bridge touchpoint attribution to Campaigns and calculate the new Ad Group count and initial budget
- Key entry point: `src/budget_recommender.py`

### `external/mta_sim_dataset/`

- Project responsibility: Pin the external MTA-SIM-dataset repository and its ZheyuanWu generator
- Key entry point: Git submodule

### `script/`

- Project responsibility: Hold all maintained project command-line entry points
- Key entry point: `generate_mta_sim_dataset.py`, `run_pipeline.py`

### `docs/`

- Project responsibility: Current VitePress documentation, GitHub Pages build input, and research attachments
- Key entry point: This site

### `docs/en/<section>/`

- Project responsibility: Code-level specification, carried in the Source Files section of the page that describes the file; no separate implementation section exists
- Key entry point: [Attribution](../attribution/index.md), [Strategy](../strategy-recommendation/module-overview.md), [Dashboard](../dashboard/index.md)

### `docs/zh/specifications/`

- Project responsibility: Preserved Chinese specification sources recording historical intent; excluded from the current build
- Key entry point: Unpublished source backup

### `docs/research/`

- Project responsibility: External research PDFs, reports, and indexes; referenced only by relevant pages and not used when models run
- Key entry point: Research attachments

### `design-artifacts/`

- Project responsibility: Historical Product Briefs, product requirements documents, and decision records
- Key entry point: Traceability material

### `_bmad-output/`

- Project responsibility: Completed or deferred specifications and implementation records
- Key entry point: Traceability material

### `.agents/`, `_bmad/`

- Project responsibility: Local development workflow tools
- Key entry point: Not used when models run

## Data Pipeline <span class="status-label status-verified" aria-label="Verified"></span>

### Synthetic generation

- Input: Pinned ZheyuanWu source and caller configuration
- Processing: Simulate, validate, and store four-segment MTA tables
- Output: Original path, performance, ground-truth, manifest, and validation files

### Standard adaptation

- Input: Generated daily-window path and performance tables
- Processing: Aggregate one model scope and add interaction type from explicit billing configuration
- Output: `MtaSimDataset`; ground truth remains evaluation-only

### Path preparation

- Input: Synthetic events and Amazon Ads-style daily report
- Processing: Build anonymous aggregated five-segment paths
- Output: AMC path report and touchpoint-entity aggregate

### Attribution

- Input: Aggregated paths
- Processing: Markov removal effect and path-level Shapley
- Output: Two model result files

### Governance

- Input: Two model result files
- Processing: Validity, support, and consistency checks
- Output: Recommended attribution and comparison summary

### Strategy initialization

- Input: Recommended attribution, entity Bridge, candidate counts, and budget
- Processing: Campaign scoring, capacity calculation, and equal split within Campaign
- Output: Initial-budget JSON

### Optimization (planned)

- Input: Ad Group features, historical performance, and candidate budget values
- Processing: A single response model plus constrained search
- Output: Budget plan under a revenue objective

The attribution and strategy layers are connected by `amc_mta_recommended_attribution.csv` and `amc_touchpoint_entity_aggregate_sample.csv`. The strategy layer does not treat historical Ad Groups as future new Ad Groups.
