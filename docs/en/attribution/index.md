---
title: Attribution Model Overview
description: MTA components, objectives, files, and output relationships
lang: en-US
---

# Attribution Model Overview

## What the Attribution Layer Solves <span class="status-label status-verified" aria-label="Verified"></span>

The attribution layer reads historical aggregated paths and answers: within the current observation window, how much historical credit should each five-segment touchpoint receive for converted users, purchase count, and revenue?

Its output granularity is:

The output grain is **touchpoint × Outcome**, with one attribution share for each combination.

It does not answer “how much incremental revenue will one more dollar of spend generate,” nor does it prove causal incrementality from advertising.

For background on reconstructing and interpreting customer journeys, read [Mapping the Customer Journey](/research/mta/Mapping%20the%20customer%20journey.pdf). For a broader comparison of data-driven attribution methods, read [Data-driven Multi-touch Attribution Models](/research/mta/Data-driven%20Multi-touch%20Attribution%20Models.pdf).

## Components, Files, and Objectives <span class="status-label status-verified" aria-label="Verified"></span>

| Component | Primary file | Objective |
| --- | --- | --- |
| Path and schema validation | `src/attribution_contract.py` | Read aggregated paths; validate counts, monetary values, and five-segment keys |
| Markov attribution | `src/markov_attribution_model.py` | Calculate contribution shares from the change in conversion probability when a touchpoint is removed |
| Shapley attribution | `src/shapley_attribution_model.py` | Allocate each Outcome fairly among unique touchpoints within each path, then aggregate across paths |
| Model comparison | `src/attribution_model_comparison.py` | Check calculation validity, data support, and model consistency |
| Pipeline | `script/run_pipeline.py` | Run and publish validated artifacts together |
| Attribution implementations | `modules/mta_attribution/` | Own the shared model interface and each concrete Markov, Shapley, uniform, and DNN model |
| Standardized framework | `modules/mta_standard/` | Load MTA-SIM data, resolve touchpoint grain, execute registered models, validate and score results |
| DNN credit model | `DeepNeuralAttributionModel` | Learn credit from touchpoint segment structure and predict a split for a campaign with no path history |

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

Continue with [Markov removal effect](./markov.md) and [Shapley path attribution](./shapley.md).

## Running Models Through One Interface <span class="status-label status-verified" aria-label="Verified"></span>

`modules/mta_standard/` provides the standardized loading and execution framework. The `fit`/`attribute` interface and every concrete model live in `modules/mta_attribution/`, so model owners can change one implementation without taking ownership of the framework. The standard Markov and Shapley adapters reproduce the original estimator numbers exactly.

The same interface admits models the original two cannot express. `dnn_credit` learns credit from touchpoint segment structure, which lets it predict a split for a campaign that has produced no paths yet.

Continue with [the standardized interface](./standardized-interface.md) and [the DNN credit model](./dnn.md). For how the four models are verified and scored against each other, see [model testing and comparison](./model-testing.md).

## References

- [Mapping the Customer Journey (PDF)](/research/mta/Mapping%20the%20customer%20journey.pdf)
- [Data-driven Multi-touch Attribution Models (PDF)](/research/mta/Data-driven%20Multi-touch%20Attribution%20Models.pdf)
