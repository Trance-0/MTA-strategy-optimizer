---
title: Project Structure and Data Flow
description: Model architecture, data pipeline, and corresponding source code
lang: en-US
---

# Project Structure and Data Flow

## Model Architecture <span class="status-label status-verified" aria-label="Verified"></span>

<DrawioDiagram base="./project-structure" alt="Project model architecture" />

## Directory Responsibilities <span class="status-label status-verified" aria-label="Verified"></span>

| Directory | Project responsibility | Key entry point |
| --- | --- | --- |
| `modules/mta_attribution/` | Build aggregated paths, run both attribution models, compare them, and publish recommended attribution | `src/attribution_contract.py` |
| `modules/mta_standard/` | Run the pinned ZheyuanWu generator, load MTA-SIM tables, adapt four-segment keys, run any model through one interface, and score results against ground truth | `src/mta_sim_generator_adapter.py`, `src/model_registry.py` |
| `modules/mta_strategy_recommendation/` | Bridge touchpoint attribution to Campaigns and calculate the new Ad Group count and initial budget | `src/budget_recommender.py` |
| `external/mta_sim_dataset/` | Pin the external MTA-SIM-dataset repository and its ZheyuanWu generator | Git submodule |
| `script/` | Hold all maintained project command-line entry points | `generate_mta_sim_dataset.py`, `run_pipeline.py` |
| `docs/` | Current VitePress documentation, GitHub Pages build input, and research attachments | This site |
| `docs/en/introduction/specifications.md` | Project-level English catalog of implementation intent and historical verification records | [Specification catalog](./specifications.md) |
| `docs/zh/specifications/` | Preserved Chinese specification sources for future translation; excluded from the current build | Unpublished source backup |
| `docs/research/` | External research PDFs, reports, and indexes; referenced only by relevant pages and not used when models run | Research attachments |
| `design-artifacts/` | Historical Product Briefs, product requirements documents, and decision records | Traceability material |
| `_bmad-output/` | Completed or deferred specifications and implementation records | Traceability material |
| `.agents/`, `_bmad/` | Local development workflow tools | Not used when models run |

## Data Pipeline <span class="status-label status-verified" aria-label="Verified"></span>

| Stage | Input | Processing | Output |
| --- | --- | --- | --- |
| Synthetic generation | Pinned ZheyuanWu source and caller configuration | Simulate, validate, and store four-segment MTA tables | Original path, performance, ground-truth, manifest, and validation files |
| Standard adaptation | Generated daily-window path and performance tables | Aggregate one model scope and add interaction type from explicit billing configuration | `MtaSimDataset`; ground truth remains evaluation-only |
| Path preparation | Synthetic events and Amazon Ads-style daily report | Build anonymous aggregated five-segment paths | AMC path report and touchpoint-entity aggregate |
| Attribution | Aggregated paths | Markov removal effect and path-level Shapley | Two model result files |
| Governance | Two model result files | Validity, support, and consistency checks | Recommended attribution and comparison summary |
| Strategy initialization | Recommended attribution, entity Bridge, candidate counts, and budget | Campaign scoring, capacity calculation, and equal split within Campaign | Initial-budget JSON |
| Optimization (planned) | Ad Group features, historical performance, and candidate budget values | A single response model plus constrained search | Budget plan under a revenue objective |

The attribution and strategy layers are connected by `amc_mta_recommended_attribution.csv` and `amc_touchpoint_entity_aggregate_sample.csv`. The strategy layer does not treat historical Ad Groups as future new Ad Groups.
