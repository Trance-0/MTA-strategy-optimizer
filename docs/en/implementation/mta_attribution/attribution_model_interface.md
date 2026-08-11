---
title: attribution_model_interface.py
source_file: modules/mta_attribution/src/attribution_model_interface.py
---

# `attribution_model_interface.py`

- Responsibility: Define the common `fit`, `attribute`, `save`, and `load` contract implemented by every concrete attribution model.
- Inputs: Framework `MtaSimDataset` objects.
- Outputs: Lists of standard attribution rows and persisted model state where supported.
- Dependencies: `mta_standard` dataset, output contract, and touchpoint adapter.
- Verification: `modules/mta_attribution/tests/test_attribution_model_interface.py`.
