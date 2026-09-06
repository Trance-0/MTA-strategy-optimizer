---
title: "Adding a Model to the Comparison"
compact: "Registering a model in shared conformance, governance and ground-truth evaluation loops."
---

# Adding a Model to the Comparison

A new model joins all three layers by satisfying one interface and being registered.

1. Implement `MtaAttributionModel` — `fit`, `attribute`, and a `ModelCapabilities` declaration.
2. Add it to `MODEL_REGISTRY` in `model_registry.py`.
3. Nothing else. The interface, output-contract, and evaluation suites iterate the registry, so the new model is immediately covered by every registry-driven test.

```python
for model_id in MODEL_REGISTRY:
    rows = build_model(model_id).fit(dataset).attribute(dataset)
    validate_standard_output(
        rows,
        outcome_totals=dataset.outcome_totals,
        expected_touchpoints=dataset.touchpoints,
    )
```

> [!TIP]
> Registry-driven tests are why `dnn_credit` required no new conformance tests when it was added. Write tests for what is unique about a model; the shared contract is already enforced for everything registered.
