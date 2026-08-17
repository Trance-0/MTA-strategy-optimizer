---
title: Strategy Evaluation Framework
description: Standardized strategy structure, loading, and evaluation — the strategy counterpart to the MTA evaluation layer
compact: "Entry point for the PROPOSED, unbuilt `modules/mta_strategy_evaluation/` layer mirroring `mta_standard`: three assurance layers, relationship to `mta_strategy_recommendation`, links to strategy-structure and strategy-loader. Read for design intent; no code exists yet."
lang: en-US
---

# Strategy Evaluation Framework

::: warning Specification ahead of implementation
This section specifies a layer that has not been built. `modules/mta_strategy_evaluation/` exists as an empty placeholder directory, and `script/evaluate_strategies.py` does not exist yet. Every path, identifier, and command named in this section is a target to build against, not a description of current code. Build to this specification rather than inferring the design from the absent implementation.
:::

## What This Layer Solves <span class="status-label status-recommendation" aria-label="Recommendation"></span>

The current [strategy initializer](../strategy-recommendation/module-overview.md) produces a deterministic, unoptimized Ad Group count and budget seed. It has no standardized interface, no registry, and no evaluation against ground truth — unlike the Multi-Touch Attribution (MTA) layer, where [`modules/mta_standard/`](../attribution/standardized-interface/) provides a shared `fit`/`attribute` contract, a model registry, an output validator, and a ground-truth scorer.

The strategy evaluation layer closes that gap. It defines:

1. a **recommended strategy structure** — what every strategy must declare, accept, and return;
2. a **strategy loader** — how strategies are configured, validated, and registered; and
3. an **evaluation framework** — how strategies are scored against baselines and, when available, ground truth.

Together they give the optimizer the same hygiene the attribution layer already has: load a strategy by identifier, run it through a validated contract, and compare its output to known references.

## Relationship to Existing Modules <span class="status-label status-inference" aria-label="Inference"></span>

| Existing module | Responsibility | Relationship to strategy evaluation |
| --- | --- | --- |
| `mta_attribution` | Concrete attribution models | Produces the MTA evidence that strategies consume |
| `mta_standard` | Attribution interface, registry, evaluation | Architectural precedent for the strategy evaluation design |
| `mta_strategy_recommendation` | Current budget initializer | One concrete strategy that would implement the new interface |

The strategy evaluation layer sits beside `mta_strategy_recommendation` the same way `mta_standard` sits beside `mta_attribution`: it owns the framework (loading, validation, scoring) but no concrete strategy mathematics.

## Three-Layer Strategy Assurance <span class="status-label status-recommendation" aria-label="Recommendation"></span>

Following the [attribution model testing](../attribution/model-testing.md) pattern, strategy evaluation provides three layers of assurance:

| Layer | Question | Where it runs | Needs ground truth |
| --- | --- | --- | --- |
| Unit and contract | Is one strategy internally correct and conserving? | `modules/mta_strategy_evaluation/tests/` | No |
| Governance comparison | Does the strategy beat baselines and satisfy constraints? | Every strategy run | No |
| Ground-truth evaluation | Does the strategy recover the simulator's optimal allocation? | On demand, Multi-Touch Attribution Simulator (MTA-SIM) data | Yes |

## Start Here

- [Recommended strategy structure](./strategy-structure.md): the shared interface every strategy must satisfy, including identity, capabilities, inputs, outputs, and the conservation contract.
- [Strategy loader](./strategy-loader.md): JSON configuration, registry, validation, and how a strategy is instantiated by identifier.

## Boundaries <span class="status-label status-inference" aria-label="Inference"></span>

- The current [strategy initializer](../strategy-recommendation/module-overview.md) is an unoptimized seed generator. The strategy evaluation framework does not change that — it provides the contract against which the initializer and future optimizers are both measured.
- Strategy evaluation does not answer "which strategy is best for this Campaign Group." It answers "does this strategy satisfy its contract, and how does it compare to baselines under known conditions?"
- Ground-truth evaluation requires a simulator that publishes an optimal allocation. MTA-SIM currently publishes attribution ground truth, not strategy ground truth. Strategy ground truth is a future requirement.

## References

- [Standardized MTA interface](../attribution/standardized-interface/)
- [Model testing and comparison](../attribution/model-testing.md)
- [Strategy optimization model](../strategy-recommendation/)
- [Campaign Group hierarchy](../research/campaign-data-hierarchy.md)
