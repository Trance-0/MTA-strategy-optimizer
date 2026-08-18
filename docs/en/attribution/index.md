---
title: Attribution Model Overview
description: MTA components, objectives, files, and output relationships
compact: "Orientation map of the attribution layer: which source file owns what, from `attribution_contract.py` and `markov_attribution_model.py` to `modules/mta_standard/`. Names the three Outcomes and the Markov-official / Shapley-reference rule. Read first; skip once you know the layout."
lang: en-US
source_files: modules/mta_attribution/src/touchpoint_key.py, modules/mta_attribution/src/attribution_contract.py, modules/mta_attribution/src/path_report_builder.py
---

# Attribution Model Overview

## What the Attribution Layer Solves <span class="status-label status-verified" aria-label="Verified"></span>

The attribution layer reads historical aggregated paths and answers: within the current observation window, how much historical credit should each five-segment touchpoint receive for converted users, purchase count, and revenue?

Its output granularity is:

The output grain is **touchpoint × Outcome**, with one attribution share for each combination.

It does not answer “how much incremental revenue will one more dollar of spend generate,” nor does it prove causal incrementality from advertising.

For background on reconstructing and interpreting customer journeys, read [Mapping the Customer Journey](/research/mta/Mapping%20the%20customer%20journey.pdf). For a broader comparison of data-driven attribution methods, read [Data-driven Multi-touch Attribution Models](/research/mta/Data-driven%20Multi-touch%20Attribution%20Models.pdf).

## Components, Files, and Objectives <span class="status-label status-verified" aria-label="Verified"></span>

### Path and schema validation

- Primary file: `src/attribution_contract.py`
- Objective: Read aggregated paths; validate counts, monetary values, and five-segment keys

### Markov attribution

- Primary file: `src/markov_attribution_model.py`
- Objective: Calculate contribution shares from the change in conversion probability when a touchpoint is removed

### Shapley attribution

- Primary file: `src/shapley_attribution_model.py`
- Objective: Allocate each Outcome fairly among unique touchpoints within each path, then aggregate across paths

### Model comparison

- Primary file: `src/attribution_model_comparison.py`
- Objective: Check calculation validity, data support, and model consistency

### Pipeline

- Primary file: `script/run_pipeline.py`
- Objective: Run and publish validated artifacts together

### Attribution implementations

- Primary file: `modules/mta_attribution/`
- Objective: Own the shared model interface and each concrete Markov, Shapley, uniform, and DNN model

### Standardized framework

- Primary file: `modules/mta_standard/`
- Objective: Load MTA-SIM data, resolve touchpoint grain, execute registered models, validate and score results

### DNN credit model

- Primary file: `DeepNeuralAttributionModel`
- Objective: Learn credit from touchpoint segment structure and predict a split for a campaign with no path history

> The correct terms are **Shapley value** and **Markov chain**. Shapely is a different Python library for geometric computation, not this project's attribution model.

## Three Outcome Types <span class="status-label status-verified" aria-label="Verified"></span>

- `converted_users`: number of unique converted users;
- `purchase_count`: number of purchases or orders;
- `revenue`: revenue or sales.

Each Outcome is normalized separately, and its touchpoint shares sum to 1. The three Outcome types must not be added together.

## Dual-Model Governance <span class="status-label status-verified" aria-label="Verified"></span>

Markov is the current official display basis, and Shapley is the sensitivity reference. The system does not simply average them:

- when reliable, the recommended value uses the Markov `official_share`;
- when unreliable, it uses the ascending closed interval formed by both model shares;
- if the strategy module receives an interval, it currently uses only its midpoint and emits a Warning.

Continue with [Markov removal effect](./standardized-interface/markov.md) and [Shapley path attribution](./standardized-interface/shapley.md).

## Running Models Through One Interface <span class="status-label status-verified" aria-label="Verified"></span>

`modules/mta_standard/` provides the standardized loading and execution framework. The `fit`/`attribute` interface and every concrete model live in `modules/mta_attribution/`, so model owners can change one implementation without taking ownership of the framework. The standard Markov and Shapley adapters reproduce the original estimator numbers exactly.

The same interface admits models the original two cannot express. `dnn_credit` learns credit from touchpoint segment structure, which lets it predict a split for a campaign that has produced no paths yet.

Continue with [the standardized interface](./standardized-interface/) and [the DNN credit model](./standardized-interface/dnn.md). For how the four models are verified and scored against each other, see [model testing and comparison](./model-testing.md).


## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the Python files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `touchpoint_key.py`

Source: `modules/mta_attribution/src/touchpoint_key.py`

- Responsibility: Define and canonicalize the native five-segment touchpoint key.
- Inputs: Touchpoint components or Amazon Ads rows.
- Outputs: Canonical `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` keys.
- Dependencies: Python standard library only.
- Verification: `modules/mta_attribution/tests/test_touchpoint_key.py`.

### `attribution_contract.py`

Source: `modules/mta_attribution/src/attribution_contract.py`

- Responsibility: Own AMC path/Ads schemas, CSV boundaries, row validation, result dataclasses, spend aggregation, and conservation-preserving publication.
- Inputs: Aggregated path rows and Amazon Ads rows.
- Outputs: Validated rows, `AttributionResult`, `TouchpointSpend`, and published model-row dictionaries.
- Dependencies: `touchpoint_key.py`; Python standard library only.
- Verification: `modules/mta_attribution/tests/test_attribution_contract.py` and end-to-end pipeline tests.

### `path_report_builder.py`

Source: `modules/mta_attribution/src/path_report_builder.py`

- Responsibility: Convert ordered journey events into privacy-safe aggregated paths.
- Inputs: Touchpoint and conversion event rows plus report-window rules.
- Outputs: Aggregated path-report rows.
- Dependencies: `touchpoint_key.py`.
- Verification: `modules/mta_attribution/tests/test_path_report_builder.py`, with end-to-end coverage in `modules/mta_attribution/tests/test_end_to_end_pipeline.py` and report-window inference in `modules/mta_attribution/tests/test_auto_report_window.py`.

## References

- [Mapping the Customer Journey (PDF)](/research/mta/Mapping%20the%20customer%20journey.pdf)
- [Data-driven Multi-touch Attribution Models (PDF)](/research/mta/Data-driven%20Multi-touch%20Attribution%20Models.pdf)
