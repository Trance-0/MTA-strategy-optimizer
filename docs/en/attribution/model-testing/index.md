---
title: Model Testing and Comparison
description: How each attribution model is tested, and how the four are compared against each other
compact: "Attribution assurance layers: shared model conformance, per-run Markov versus Shapley governance, evaluation against simulation_ground_truth, and the generator adapter that preserves uploads while producing one aggregated model path scope for pipeline execution."
lang: en-US
---

# Model Testing and Comparison

Attribution assurance has three distinct responsibilities: internal model conformance, agreement-based publication governance, and recovery of simulation ground truth. The evaluation page owns scoring and the unit-contract page owns the generator adapter, so each can be read with only its relevant assurance layer.

- [Layer 1 — Unit and Contract Tests](./unit-contract-tests.md): Model conformance and unit acceptance cases, conservation, adapters, keys, report windows and reproducibility.
- [Layer 2 — Governance Comparison](./governance-comparison.md): Per-run Markov and Shapley agreement, reliability thresholds and publication behavior.
- [Layer 3 — Ground-Truth Evaluation](./ground-truth-evaluation.md): Isolated simulator truth and standard credit error, rank, overlap, conservation and runtime metrics.
- [Adding a Model to the Comparison](./adding-a-model.md): Registering a model in shared conformance, governance and ground-truth evaluation loops.

Four models ship in this repository. This page explains how each one is verified in isolation, how two of them are compared in production, and how all four are scored against a known answer.

## `markov_removal_effect`

- Implementation: `mta_attribution/src/markov_standard_attribution_model.py`
- Compared in production: Yes — official basis
- Scored against ground truth: Yes

## `path_level_shapley`

- Implementation: `mta_attribution/src/shapley_standard_attribution_model.py`
- Compared in production: Yes — sensitivity reference
- Scored against ground truth: Yes

## `uniform_credit`

- Implementation: `mta_attribution/src/uniform_attribution_model.py`
- Compared in production: No
- Scored against ground truth: Yes — baseline

## `dnn_credit`

- Implementation: `mta_attribution/src/dnn_attribution_model.py`
- Compared in production: No
- Scored against ground truth: Yes

## Three Layers of Assurance <span class="status-label status-verified" aria-label="Verified"></span>

The three layers answer different questions, and none substitutes for another.

<DrawioDiagram base="./model-testing-layers" alt="Three layers of model assurance" />

### Unit and contract

- Question: Is one model internally correct and conserving?
- Where it runs: `modules/*/tests/`
- Needs ground truth: No

### Governance comparison

- Question: Do Markov and Shapley agree enough to publish a point estimate?
- Where it runs: Every pipeline run
- Needs ground truth: No

### Ground-truth evaluation

- Question: Does a model recover the simulator's mechanism?
- Where it runs: On demand, MTA-SIM data
- Needs ground truth: Yes

> [!IMPORTANT]
> Layer 2 runs on **every** pipeline run because it gates what gets published. Layer 3 cannot: real reports have no ground truth. That is why reliability governance is built on cross-model agreement rather than on accuracy.

---

## References

- [Standardized MTA interface](/en/attribution/standardized-interface/)
- [Model comparison governance](/en/attribution/model-governance.md)
- [Touchpoint reliability](/en/attribution/reliability.md)
- [Module and script data flow](/en/reference/data-flow.md)
