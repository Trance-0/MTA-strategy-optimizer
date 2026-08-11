---
title: shapley_attribution_model.py
source_file: modules/mta_attribution/src/shapley_attribution_model.py
---

# `shapley_attribution_model.py`

- Responsibility: Implement exact path-level Shapley attribution as a sum of unanimity games.
- Inputs: Validated five-segment aggregated paths.
- Outputs: Native `AttributionResult` records.
- Dependencies: `attribution_contract.py`.
- Verification: `modules/mta_attribution/tests/test_attribution_contract.py`.
