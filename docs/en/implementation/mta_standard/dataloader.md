---
title: dataloader.py
source_file: modules/mta_standard/src/dataloader.py
---

# `dataloader.py`

- Responsibility: Load MTA-SIM path and performance tables into a model-facing dataset.
- Inputs: External CSV paths and an explicit simulator configuration.
- Outputs: `MtaSimDataset` with ground truth structurally excluded.
- Dependencies: Attribution path contract and `touchpoint_adapter.py`.
- Verification: `modules/mta_standard/tests/test_dataloader.py`.
