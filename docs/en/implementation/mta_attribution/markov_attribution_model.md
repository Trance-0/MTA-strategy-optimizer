---
title: markov_attribution_model.py
source_file: modules/mta_attribution/src/markov_attribution_model.py
---

# `markov_attribution_model.py`

- Responsibility: Implement weighted first-order Markov removal-effect attribution.
- Inputs: Validated five-segment aggregated paths.
- Outputs: Native `AttributionResult` records for converted users, purchases, and revenue.
- Dependencies: `attribution_contract.py` and `touchpoint_key.py`.
- Verification: `modules/mta_attribution/tests/test_attribution_contract.py`.
