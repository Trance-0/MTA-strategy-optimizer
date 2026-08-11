---
title: synthetic_event_pipeline.py
source_file: modules/mta_attribution/src/synthetic_event_pipeline.py
---

# `synthetic_event_pipeline.py`

- Responsibility: Reproduce the legacy five-segment sample and its Ads/entity projections.
- Inputs: Report dates and the fixed simulated touchpoint catalogue.
- Outputs: Synthetic user events, path events, Ads rows, and entity aggregates.
- Dependencies: `simulated_touchpoints.py` and `touchpoint_key.py`.
- Verification: `modules/mta_attribution/tests/test_end_to_end_pipeline.py`.
