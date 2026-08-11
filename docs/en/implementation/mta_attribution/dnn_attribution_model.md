---
title: dnn_attribution_model.py
source_file: modules/mta_attribution/src/dnn_attribution_model.py
---

# `dnn_attribution_model.py`

- Responsibility: Learn segment-based attribution shares from path-level Shapley targets and score unseen campaign touchpoints.
- Inputs: Four-segment dataset features; simulation ground truth is excluded.
- Outputs: Standard attribution rows and optional persisted network state.
- Dependencies: Attribution interface, Shapley implementation, and `mta_standard` contracts.
- Verification: `modules/mta_attribution/tests/test_dnn_attribution_model.py`.
