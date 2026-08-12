---
title: model_registry.py
source_file: modules/mta_standard/src/model_registry.py
compact: "Specifies `MODEL_REGISTRY` and `build_model(model_id)` in `model_registry.py`: keys `model_id` onto `MarkovRemovalEffectModel`, `PathLevelShapleyModel`, `UniformCreditModel`, `DeepNeuralAttributionModel`, raising KeyError otherwise. Read when registering a new model or breaking an import cycle."
---

# `model_registry.py`

- Responsibility: Map stable model identifiers to independently owned model classes.
- Inputs: A model identifier.
- Outputs: A new unfitted model implementing the shared interface.
- Dependencies: Concrete classes from `mta_attribution`; contains no model mathematics.
- Verification: no dedicated suite. Registry assertions live in `modules/mta_standard/tests/test_evaluation.py`, `modules/mta_standard/tests/test_output_contract.py`, `modules/mta_attribution/tests/test_attribution_model_interface.py`, and `modules/mta_attribution/tests/test_dnn_attribution_model.py`.
