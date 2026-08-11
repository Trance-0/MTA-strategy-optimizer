---
title: Uniform Credit Baseline
description: Equal-split reference model for baseline comparison
lang: en-US
order: 200
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

| Step | What it does | Why |
| --- | --- | --- |
| Fit on dataset | Records the outcome totals and touchpoint set | Ensures `attribute()` is called with a matching scope |
| Sort touchpoints | Deterministic order for reproducible output | Same touchpoints always produce the same row order |
| Equal share | `1.0 / count` for each touchpoint | Every touchpoint receives identical credit |
| Zero-outcome handling | `share = 0.0` when total is zero | Complies with the [standardized interface](./index.md#the-standard-output-row) zero-outcome rule |
| Conservation | `value = total / count` preserves the total | Sum of all attributed values equals the input total |

## Why a Baseline Matters <span class="status-label status-verified" aria-label="Verified"></span>

The uniform model makes every other model's numbers meaningful in context:

| Scenario | What uniform tells you |
| --- | --- |
| Markov beats uniform on MAE | The removal-effect method captures real path structure |
| Markov ties uniform on MAE | Historical paths carry no attribution signal beyond "these touchpoints exist" |
| DNN matches Shapley but not uniform | Both learn from path structure; uniform confirms the structure exists |
| All models equal uniform | The data provides no differentiation between touchpoints — any allocation is arbitrary |

## Interpretation <span class="status-label status-inference" aria-label="Inference"></span>

Uniform credit is not a useful attribution method by itself. It is the **null hypothesis** of attribution: that all touchpoints are equally important. Rejecting it is the first threshold any model must clear.

Because every share is identical, Spearman's rho (rank correlation) is `None` — not `0.0`, which would falsely imply "measured absence of correlation" when the truth is "no ranking to correlate." This is a deliberate contract choice, not a bug.

## Comparison with Other Models

| Property | Uniform | [Markov](./markov.md) | [Shapley](./shapley.md) | [DNN](./dnn.md) |
| --- | --- | --- | --- | --- |
| Uses path order | No | Yes | No | No |
| Uses segment structure | No | No | No | Yes |
| Requires training | No | No | No | Yes |
| Persistable | No | Yes | Yes | Yes |
| Can predict new campaigns | No | No | No | Yes |
| Deterministic | Yes | Yes | Yes | Yes |
| Best use | Baseline floor | Official display | Sensitivity reference | New-campaign ranking |

## References

- [Standardized MTA interface](./index.md)
- [Model testing and comparison](../model-testing.md)
- [Model comparison governance](../model-governance.md)
