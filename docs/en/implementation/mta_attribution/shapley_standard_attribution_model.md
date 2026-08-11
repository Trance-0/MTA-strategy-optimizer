---
title: shapley_standard_attribution_model.py
source_file: modules/mta_attribution/src/shapley_standard_attribution_model.py
---

# `shapley_standard_attribution_model.py`

- Responsibility: Adapt the native path-level Shapley model to the common interface.
- Inputs: `MtaSimDataset` with model-facing path rows.
- Outputs: Four-segment `StandardAttributionRow` records.
- Dependencies: Native Shapley model plus `mta_standard` framework contracts.
- Verification: `modules/mta_attribution/tests/test_shapley_standard_attribution_model.py`.
