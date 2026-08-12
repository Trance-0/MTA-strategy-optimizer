---
title: Implementation Specification Catalog
description: Project-level catalog of preserved attribution and strategy implementation specifications
lang: en-US
---

# Implementation Specification Catalog

This project-level catalog organizes the implementation specifications that were previously isolated in BMad implementation-artifact folders. The approved source records remain unchanged under `_bmad-output/implementation-artifacts/`, and exact Chinese mirrors are preserved under `docs/zh/specifications/source/` for future bilingual publication.

Specifications record the intent, boundary, acceptance criteria, and verification state at the time of implementation. They are historical evidence. Current code, tests, data contracts, and capability pages take precedence when an older path, field, test count, or design has been superseded.

## Current strategy and workspace delivery

| Specification | Recorded purpose | Source backup |
| --- | --- | --- |
| MTA-driven new Ad Group count and budget model | Replace fixed group counts and concrete activation plans with a deterministic, MTA-informed count and initial budget seed. | `docs/zh/specifications/source/spec-mta-driven-ad-group-budget-allocation.md` |
| Workspace structure and current budget entry point | Align root navigation, architecture, development guidance, output location, and terminology with the implemented budget-only workflow. | `docs/zh/specifications/source/spec-workspace-structure-cleanup.md` |

## Shared data lineage and strategy evolution

| Specification | Recorded purpose | Current interpretation | Source backup |
| --- | --- | --- | --- |
| Unified synthetic user-event pipeline | Derive Amazon Marketing Cloud events, Amazon Ads performance, entity relationships, and strategy evidence from one synthetic behavioral source. | Implemented data-lineage foundation. | `docs/zh/specifications/source/spec-unified-synthetic-user-event-pipeline.md` |
| Campaign Group hierarchy migration | Standardize the hierarchy as `Campaign Group → Campaign → Ad Group → Keyword/Stock Keeping Unit (SKU)` and introduce candidate-pool examples. | Implemented hierarchy foundation. | `docs/zh/specifications/source/spec-campaign-group-hierarchy-migration.md` |
| Align strategy data with Amazon Marketing Cloud evidence | Replace handwritten or incorrectly mapped strategy values with evidence-aligned entities, targeting, attribution values, and budgets. | Implemented evidence alignment. | `docs/zh/specifications/source/spec-align-strategy-data-with-amc.md` |
| Simplify strategy simulated data | Replace seven small tables and a handwritten output with explicit request, candidate-pool, evidence, and deterministic-output responsibilities. | Superseded by the current budget-only v4 contract, but retained as evolution history. | `docs/zh/specifications/source/spec-simplify-strategy-simulated-data.md` |

## Attribution data contracts and execution

| Specification | Recorded purpose | Source backup |
| --- | --- | --- |
| Five-segment interaction granularity | Upgrade the complete flow to `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`. | `docs/zh/specifications/source/amc_mta/completed/spec-add-interaction-type-granularity-2.md` |
| Annotated path-report sample | Add a Chinese field-description row to the Amazon Marketing Cloud path sample for consistency with the Amazon Ads sample. | `docs/zh/specifications/source/amc_mta/completed/spec-annotate-amc-path-report.md` |
| Automatic report-window detection | Infer the processing window from supplied Amazon Ads dates so new data does not require a configuration edit. | `docs/zh/specifications/source/amc_mta/completed/spec-auto-detect-amc-report-window.md` |
| Remove units sold | Remove `unitsSold` and `units_sold` because they were not used by attribution or efficiency calculations. | `docs/zh/specifications/source/amc_mta/completed/spec-remove-units-sold.md` |
| Expand the simulated sample | Extend the then-current Amazon Marketing Cloud sample so all related inputs covered the intended reporting period. | `docs/zh/specifications/source/amc_mta/completed/spec-expand-amc-sample-to-one-year.md` |
| Ignore edge whitespace in CSV input | Normalize leading and trailing field/value whitespace while preserving internal spaces and strict schema validation. | `docs/zh/specifications/source/amc_mta/completed/spec-tolerate-csv-edge-whitespace.md` |

## Attribution model governance and outputs

| Specification | Recorded purpose | Source backup |
| --- | --- | --- |
| Evaluate all dual-model outputs | Apply governance to every touchpoint and outcome, including support, differences, cost context, and auditable actions. | `docs/zh/specifications/source/amc_mta/completed/spec-evaluate-all-mta-outputs.md` |
| Five-segment-only governance | Remove four-segment parent summaries and reasons from final model-comparison outputs. | `docs/zh/specifications/source/amc_mta/completed/spec-five-part-only-model-governance.md` |
| Simplify model-comparison fields | Remove empty, derived, repeated, and obsolete governance fields from the dual-model CSV artifacts. | `docs/zh/specifications/source/amc_mta/completed/spec-simplify-amc-output-fields.md` |
| Simplify reliability judgment | Use calculation validity, sufficient support, and model consistency to produce binary `RELIABLE` or `UNRELIABLE` status. | `docs/zh/specifications/source/amc_mta/completed/spec-simplify-amc-reliability-judgment.md` |
| Add the final recommended value | Emit a reliable official point or an unreliable closed interval so consumers do not need to reconstruct the policy. | `docs/zh/specifications/source/amc_mta/completed/spec-add-recommended-value-field.md` |

## Engineering organization and submission history

| Specification | Recorded purpose | Source backup |
| --- | --- | --- |
| Clean and reconcile the workspace | Remove stale inconsistencies and align the workspace with the then-current model boundary. | `docs/zh/specifications/source/amc_mta/completed/spec-clean-workspace.md` |
| Focus on Amazon Marketing Cloud MTA | Consolidate the then-current project around one formal attribution implementation. | `docs/zh/specifications/source/amc_mta/completed/spec-focus-project-on-amc-mta.md` |
| Establish file-location governance | Update indexes, inventories, scanning records, and directory responsibilities. | `docs/zh/specifications/source/amc_mta/completed/spec-organize-workspace-files.md` |
| Prepare the Markdown submission package | Consolidate module explanations, output-reading entry points, and traceability material for review. | `docs/zh/specifications/source/amc_mta/completed/spec-prepare-amc-mta-submission-package.md` |

## Deferred work

The preserved deferred-work record covers scope isolation, timezone rules, complete Amazon Ads schema validation, currency validation, numeric precision, zero-user paths, concurrent publication, duplicate headers, Markov removal semantics, output/input path collisions, path timing boundaries, and strong-consistency publication. Some items are marked resolved or superseded in the source; unresolved items still require separate design decisions.

Source backup: `docs/zh/specifications/source/amc_mta/deferred/deferred-work.md`.

## Adapter and migration status

The current repository no longer places business descriptions inside module-local documentation folders. Runtime modules contain code, data, outputs, scripts, and tests. Project documentation lives under `docs/en/`, while `modules/mta_standard/` provides the explicit adapter between MTA-SIM's four-segment contract and this project's five-segment interaction-aware models.

See the [standardized interface](../attribution/standardized-interface/), [module data flow](../reference/data-flow.md), and [current progress](../introduction/progress.md) for the implemented state after these historical specifications.
