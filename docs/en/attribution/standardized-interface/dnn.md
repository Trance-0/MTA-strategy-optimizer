---
title: DNN Credit Model
description: Architecture, features, training, and new-campaign prediction for DeepNeuralAttributionModel
compact: "Internals of model_id `dnn_credit` in `dnn_attribution_model.py`: 16/8 tanh listwise softmax scorer, hidden_sizes, epochs 400, learning_rate 0.5, seed 20260803, `build_touchpoint_features` (appearance_ratio, mean_relative_position, user_share), Shapley-share targets, `predict_new_campaign`, JSON persistence."
lang: en-US
source_files: modules/mta_attribution/src/dnn_attribution_model.py
---

# DNN Credit Model

## Model Intuition <span class="status-label status-verified" aria-label="Verified"></span>

Markov and Shapley both score a touchpoint by its **identity**: a touchpoint that never appeared in the historical path report has no removal effect and belongs to no coalition, so neither model can say anything about it. That is a hard limit when the question is about a campaign that has not run yet.

The DNN credit model scores a touchpoint by its **structure** instead. It consumes the four contract segments — `AD_PRODUCT`, `FORMAT`, `PLACEMENT`, `CREATIVE` — plus features derived from how similar touchpoints behaved in observed paths. Because those inputs exist for a touchpoint with no history, the trained network can rank a planned campaign's touchpoints before that campaign has produced a single path.

Implementation: class `DeepNeuralAttributionModel` in `modules/mta_attribution/src/dnn_attribution_model.py`.

## Architecture <span class="status-label status-verified" aria-label="Verified"></span>

The network is a **listwise** scorer, not a per-touchpoint regressor. It emits one logit per outcome for every touchpoint in a report, then applies a softmax across the touchpoint set, once per outcome.

Each encoded touchpoint passes through a 16-unit `tanh` layer, an 8-unit `tanh` layer, and a linear head for the three Outcomes. A separate softmax across the available touchpoints for each Outcome produces one `attribution_share` per touchpoint.

That choice matters for the output contract. A softmax always sums to one, so **share conservation holds by construction** rather than by a post-hoc rescale that could hide a defective model.

### `hidden_sizes`

- Default: `(16, 8)`
- Reason: Two hidden layers give the model interaction terms between segments without exceeding the evidence a report-scale dataset carries

### `epochs`

- Default: `400`
- Reason: Full-batch steps; fixed length keeps training deterministic

### `learning_rate`

- Default: `0.5`
- Reason: Plain gradient descent on an averaged batch gradient

### `seed`

- Default: `20260803`
- Reason: Seeds Glorot-uniform weight initialisation

The implementation uses only the Python standard library, matching the repository's existing zero-dependency constraint. It is a genuine multi-layer network trained by backpropagation, sized for report-scale touchpoint counts rather than for large-scale training.

## Features <span class="status-label status-verified" aria-label="Verified"></span>

`build_touchpoint_features()` derives every feature from the model-facing path rows. Ground truth is not reachable from the dataset, so no feature can encode the answer.

### Segment one-hots

One vocabulary per contract segment, with index 0 reserved for an unseen value.

### `appearance_ratio`

Share of paths containing the touchpoint.

### `mean_relative_position`

Average position within its paths, `0` first to `1` last; a single-touchpoint path scores `0.5`.

### `mean_path_length_ratio`

Average length of its paths, scaled by the longest observed path.

### `user_share`

Share of total path users on paths containing the touchpoint.

The reserved unknown bucket is what makes new-campaign prediction possible. A segment value the model never saw still encodes; it simply lands in the bucket the network learned as "unfamiliar."

## Training <span class="status-label status-verified" aria-label="Verified"></span>

Targets are path-level Shapley shares computed from the observed path report — data a contributor actually has — which keeps `simulation_ground_truth` reserved for evaluation.

```python
predicted = _softmax([row[position] for row in logits])              # 1
for index, touchpoint in enumerate(touchpoints):                     # 2
    gradients[index][position] = (                                   # 3
        predicted[index] - targets[outcome].get(touchpoint, 0.0)     # 4
    )
self._network.apply_gradients(                                       # 5
    activations_batch, gradients, self.learning_rate)
```

### Line 1 — Softmax the current logits across the touchpoint set

Algorithm mapping and reason: Turns raw scores into a share distribution comparable to the target.

### Lines 2-4 — Set the gradient to `predicted - target`

Algorithm mapping and reason: This is exactly `d(cross entropy)/d(logit)` for a softmax, so no separate loss derivative is needed.

### Line 5 — Apply one averaged full-batch step

Algorithm mapping and reason: Averaging before the update makes the step independent of touchpoint order.

An outcome whose observed total is zero is excluded from training entirely: there is no distribution to learn, and fabricating one would violate the zero-outcome rule in the output contract.

Determinism is a declared capability. Weight initialisation is seeded, the batch is full, the epoch count is fixed, and touchpoints are visited in sorted order, so fitting the same dataset twice produces bit-identical parameters and bit-identical rows.

## Predicting a New Campaign <span class="status-label status-verified" aria-label="Verified"></span>

`predict_new_campaign()` is the capability the two wrapped estimators cannot offer.

```python
model = build_model("dnn_credit").fit(dataset)
predicted = model.predict_new_campaign([
    "SPONSORED_PRODUCTS:PRODUCT_AD:REST_OF_SEARCH:UNSPECIFIED",
    "AMAZON_DSP:DISPLAY:UNSPECIFIED:IMAGE",
])
```

Unseen segment values fall into the reserved unknown bucket, and the path-derived numeric features fall back to their training means, so a touchpoint with no history still receives a score. The result is normalized across the supplied touchpoints, once per outcome, and is independent of the order in which they were passed.

## Interpretation <span class="status-label status-inference" aria-label="Inference"></span>

Read `predict_new_campaign()` as a **relative split of one planned campaign**, and nothing more:

- It is not a forecast of conversions, purchases, or revenue. It carries no observed outcome, only proportions.
- It extrapolates from segment structure. A campaign whose segments are entirely unfamiliar produces a prediction resting almost wholly on the unknown bucket, which is a weak basis for a decision.
- Because the model is trained on Shapley shares, it inherits Shapley's assumptions. It is a learned surrogate of an observational attribution method, not an independent causal estimate.
- Deep networks are the most flexible model in this repository and therefore the easiest to overfit at report scale. Treat its agreement with `path_level_shapley` as a sanity check, not as corroboration from an independent method.

The model is a **sample** third algorithm demonstrating that the standardized interface admits a learned, persistent, generalizing model. It is not proposed as the official display basis; [model comparison governance](../model-governance.md) still names Markov for that role.

## Persistence <span class="status-label status-verified" aria-label="Verified"></span>

Unlike the closed-form wrappers, this model has real learned state, so `save()` writes hyperparameters, encoder vocabularies, layer sizes, weights, and biases as JSON. `load()` refuses a file written by a different model or version, which keeps a restored model from silently changing a report's provenance. A round trip reproduces both attribution rows and new-campaign predictions exactly.

## Formulas

For touchpoint (t) and outcome (o), with network logit (z):

$$
\text{share}_o(t) = \frac{e^{z_o(t)}}{\sum_j e^{z_o(j)}}
$$

Training minimises cross-entropy against the path-level Shapley target (\hat{s}):

$$
\mathcal{L} = -\sum_o \sum_t \hat{s}_o(t) \log \text{share}_o(t)
$$

whose logit gradient reduces to:

$$
\frac{\partial \mathcal{L}}{\partial z_o(t)} = \text{share}_o(t) - \hat{s}_o(t)
$$

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the Python files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `dnn_attribution_model.py`

Source: `modules/mta_attribution/src/dnn_attribution_model.py`

- Responsibility: Learn segment-based attribution shares from path-level Shapley targets and score unseen campaign touchpoints.
- Inputs: Native five-segment interaction-aware dataset features; simulation ground truth is excluded.
- Outputs: Standard attribution rows and optional persisted network state.
- Dependencies: Attribution interface, Shapley implementation, and `mta_standard` contracts, plus `NULL` and `safe_float` from `attribution_contract.py` and `OUTCOME_FIELDS` from `attribution_model_comparison.py`.
- Verification: `modules/mta_attribution/tests/test_dnn_attribution_model.py`.

## References

- [Standardized MTA interface](./index.md)
- [Path-level Shapley](./shapley.md)
- [Model comparison governance](../model-governance.md)
