---
title: Uniform Credit Baseline
description: Equal-split reference model for baseline comparison
compact: "Full source of `UniformCreditModel` in `uniform_attribution_model.py`: model_id `uniform_credit`, requires_fit true, supports_persistence false, share 1.0/count, zero-outcome share 0.0, spearman_rho None by design. Read as the MAE floor; no path logic here."
lang: en-US
order: 200
source_files: modules/mta_attribution/src/uniform_attribution_model.py
---

# Uniform Credit Baseline

## Model Intuition <span class="status-label status-verified" aria-label="Verified"></span>

Uniform credit is the simplest possible attribution model: split every Outcome equally across all observed touchpoints. It uses no path information, no transition probabilities, and no coalition logic. Its only job is to provide a floor that any non-trivial model must beat to justify its complexity.

If a sophisticated model cannot outperform an equal split on [Mean Absolute Error (MAE)](/en/reference/definitions#mae-mean-absolute-error) against ground truth, its added complexity has not earned a place in the pipeline.

Implementation: class `UniformCreditModel` in `modules/mta_attribution/src/uniform_attribution_model.py`.

## Current Implementation <span class="status-label status-verified" aria-label="Verified"></span>

The model is the shortest in this repository:

```python
class UniformCreditModel(MtaAttributionModel):
    model_id = "uniform_credit"
    model_version = "1.0.0"
    capabilities = ModelCapabilities(
        requires_fit=True,
        supports_persistence=False,
        deterministic=True,
    )

    def attribute(self, dataset):
        self._require_fitted(dataset)
        touchpoints = sorted(dataset.touchpoints)
        count = len(touchpoints)
        for outcome in SUPPORTED_OUTCOMES:
            total = float(dataset.outcome_totals[outcome])
            has_outcome = total != 0
            share = 1.0 / count if has_outcome else 0.0
            value = total / count
            for touchpoint in touchpoints:
                rows.append(StandardAttributionRow(
                    attribution_share=share,
                    attributed_value=value,
                    ...
                ))
        return rows
```

### Fit on dataset

- What it does: Records the outcome totals and touchpoint set
- Why: Ensures `attribute()` is called with a matching scope

### Sort touchpoints

- What it does: Deterministic order for reproducible output
- Why: Same touchpoints always produce the same row order

### Equal share

- What it does: `1.0 / count` for each touchpoint
- Why: Every touchpoint receives identical credit

### Zero-outcome handling

- What it does: `share = 0.0` when total is zero
- Why: Complies with the [standardized interface](./index.md#the-standard-output-row) zero-outcome rule

### Conservation

- What it does: `value = total / count` preserves the total
- Why: Sum of all attributed values equals the input total

## Why a Baseline Matters <span class="status-label status-verified" aria-label="Verified"></span>

The uniform model makes every other model's numbers meaningful in context:

### Markov beats uniform on MAE

The removal-effect method captures real path structure.

### Markov ties uniform on MAE

Historical paths carry no attribution signal beyond "these touchpoints exist".

### DNN matches Shapley but not uniform

Both learn from path structure; uniform confirms the structure exists.

### All models equal uniform

The data provides no differentiation between touchpoints — any allocation is arbitrary.

## Interpretation <span class="status-label status-inference" aria-label="Inference"></span>

Uniform credit is not a useful attribution method by itself. It is the **null hypothesis** of attribution: that all touchpoints are equally important. Rejecting it is the first threshold any model must clear.

Because every share is identical, Spearman's rho (rank correlation) is `None` — not `0.0`, which would falsely imply "measured absence of correlation" when the truth is "no ranking to correlate." This is a deliberate contract choice, not a bug.

## Comparison with Other Models

### Uses path order

- Uniform: No
- [Markov](./markov.md): Yes
- [Shapley](./shapley.md): No
- [DNN](./dnn.md): No

### Uses segment structure

- Uniform: No
- [Markov](./markov.md): No
- [Shapley](./shapley.md): No
- [DNN](./dnn.md): Yes

### Requires training

- Uniform: No
- [Markov](./markov.md): No
- [Shapley](./shapley.md): No
- [DNN](./dnn.md): Yes

### Persistable

- Uniform: No
- [Markov](./markov.md): Yes
- [Shapley](./shapley.md): Yes
- [DNN](./dnn.md): Yes

### Can predict new campaigns

- Uniform: No
- [Markov](./markov.md): No
- [Shapley](./shapley.md): No
- [DNN](./dnn.md): Yes

### Deterministic

- Uniform: Yes
- [Markov](./markov.md): Yes
- [Shapley](./shapley.md): Yes
- [DNN](./dnn.md): Yes

### Best use

- Uniform: Baseline floor
- [Markov](./markov.md): Official display
- [Shapley](./shapley.md): Sensitivity reference
- [DNN](./dnn.md): New-campaign ranking

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the Python files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `uniform_attribution_model.py`

Source: `modules/mta_attribution/src/uniform_attribution_model.py`

- Responsibility: Provide a deterministic equal-credit reference baseline.
- Inputs: A fitted `MtaSimDataset` scope.
- Outputs: Conservation-preserving native five-segment standard rows.
- Dependencies: Attribution interface and `mta_standard` output contract.
- Verification: `modules/mta_attribution/tests/test_uniform_attribution_model.py`.

## References

- [Standardized MTA interface](./index.md)
- [Model testing and comparison](../model-testing.md)
- [Model comparison governance](../model-governance.md)
