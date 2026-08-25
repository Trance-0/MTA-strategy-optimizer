---
title: Strategy Evaluation Framework
description: Standardized strategy structure, loading, and evaluation — the strategy counterpart to the MTA evaluation layer
compact: "Entry point for `modules/mta_strategy_evaluation/`, the strategy counterpart to `mta_standard`: three assurance layers, the StrategyOutput data class, contributed models under contrib/, and the evaluation pipeline stage. The strategy registry and loader remain unbuilt."
lang: en-US
---

# Strategy Evaluation Framework

::: warning Two pages describe unbuilt design
[Recommended strategy structure](./strategy-structure.md) and [Strategy loader](./strategy-loader.md) specify a registry and a configuration-driven loader that do not exist yet; read them as targets to build against. Everything else in this section — the strategy output data class, the evaluation layers, the contributed-model boundary, and the evaluation pipeline stage — is built and running.
:::

## What This Layer Solves <span class="status-label status-recommendation" aria-label="Recommendation"></span>

The current [strategy initializer](../strategy-recommendation/module-overview/) produces a deterministic, unoptimized Ad Group count and budget seed. It has no standardized interface, no registry, and no evaluation against ground truth — unlike the Multi-Touch Attribution (MTA) layer, where [`modules/mta_standard/`](../attribution/standardized-interface/) provides a shared `fit`/`attribute` contract, a model registry, an output validator, and a ground-truth scorer.

The strategy evaluation layer closes that gap. It defines:

1. a **recommended strategy structure** — what every strategy must declare, accept, and return;
2. a **strategy loader** — how strategies are configured, validated, and registered; and
3. an **evaluation framework** — how strategies are scored against baselines and, when available, ground truth.

Together they give the optimizer the same hygiene the attribution layer already has: load a strategy by identifier, run it through a validated contract, and compare its output to known references.

## Relationship to Existing Modules <span class="status-label status-inference" aria-label="Inference"></span>

#### `mta_attribution`

This module contains concrete attribution models. It produces the
Multi-Touch Attribution (MTA) evidence that strategies consume.

#### `mta_standard`

This module owns the attribution interface, registry, and evaluation. It is
the architectural precedent for the strategy evaluation design.

#### `mta_strategy_recommendation`

This module contains the current budget initializer. That initializer is one
concrete strategy that would implement the new interface.

The strategy evaluation layer sits beside `mta_strategy_recommendation` the same way `mta_standard` sits beside `mta_attribution`: it owns the framework (loading, validation, scoring) but no concrete strategy mathematics.

## Three-Layer Strategy Assurance <span class="status-label status-verified" aria-label="Verified"></span>

Following the [attribution model testing](../attribution/model-testing.md) pattern, strategy evaluation provides three layers of assurance:

#### Unit and contract

This layer asks whether one strategy is internally correct and conserving. It
runs under `modules/mta_strategy_evaluation/tests/` and does not need ground
truth.

#### Governance comparison

This layer asks whether the strategy beats baselines and satisfies constraints.
It runs on every strategy execution and does not need ground truth.

#### Ground-truth evaluation

This layer asks whether the strategy recovers the simulator's optimal
allocation. It runs on demand with Multi-Touch Attribution Simulator
(MTA-SIM) data and requires ground truth.

The three layers are implemented in `modules/mta_strategy_evaluation/src/evaluation_episode.py`. The third does not run today, for the reason given under Boundaries below.

## Start Here

- [Strategy output](./strategy-output.md): the `StrategyOutput` data class every strategy produces, its conservation contract, and how the two committed artifacts are projected onto it.
- [Evaluation layers](./evaluation-layers.md): how a Campaign episode isolates ground truth, how a strategy evaluation episode wraps one, and how to add a fourth layer.
- [Running an evaluation](./running-an-evaluation.md): the `evaluation` pipeline stage, its command, its artifact, and its backend wiring.
- [Contributed models](./contributed-models/index.md): how externally contributed response models are stored verbatim under `contrib/` and reached through adapters.
- [Recommended strategy structure](./strategy-structure.md): the shared interface every strategy must satisfy, including identity, capabilities, inputs, outputs, and the conservation contract. Proposed, not built.
- [Strategy loader](./strategy-loader.md): JSON configuration, registry, validation, and how a strategy is instantiated by identifier. Proposed, not built.

## Boundaries <span class="status-label status-inference" aria-label="Inference"></span>

- The current [strategy initializer](../strategy-recommendation/module-overview/) is an unoptimized seed generator. The strategy evaluation framework does not change that — it provides the contract against which the initializer and future optimizers are both measured.
- Strategy evaluation does not answer "which strategy is best for this Campaign Group." It answers "does this strategy satisfy its contract, and how does it compare to baselines under known conditions?"
- Ground-truth evaluation requires a simulator that publishes an optimal allocation. MTA-SIM currently publishes attribution ground truth, not strategy ground truth. Strategy ground truth is a future requirement.

## References

- [Standardized MTA interface](../attribution/standardized-interface/)
- [Model testing and comparison](../attribution/model-testing.md)
- [Strategy optimization model](../strategy-recommendation/)
- [Campaign Group hierarchy](../research/campaign-data-hierarchy.md)
