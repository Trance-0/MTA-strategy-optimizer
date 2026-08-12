---
title: model_pipeline.py
source_file: modules/mta_standard/src/model_pipeline.py
compact: "Specifies `run_registered_models(dataset, model_ids)` and the frozen `ModelRun` (`model_id`, `rows`) in `model_pipeline.py`: calls `build_model`, then fit/attribute, then `validate_standard_output`, returning an immutable mapping. Read when changing execution order or duplicate-identifier rejection."
---

# `model_pipeline.py`

- Responsibility: Build, fit, execute, and validate selected registered models.
- Inputs: `MtaSimDataset` and distinct model identifiers.
- Outputs: Immutable `ModelRun` mappings.
- Dependencies: Dataloader, model registry, and output contract only.
- Verification: `modules/mta_standard/tests/test_model_pipeline.py`.
