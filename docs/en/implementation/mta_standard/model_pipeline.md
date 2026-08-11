---
title: model_pipeline.py
source_file: modules/mta_standard/src/model_pipeline.py
---

# `model_pipeline.py`

- Responsibility: Build, fit, execute, and validate selected registered models.
- Inputs: `MtaSimDataset` and distinct model identifiers.
- Outputs: Immutable `ModelRun` mappings.
- Dependencies: Dataloader, model registry, and output contract only.
- Verification: `modules/mta_standard/tests/test_model_pipeline.py`.
