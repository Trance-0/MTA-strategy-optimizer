---
title: shapley_attribution_model.py
source_file: modules/mta_attribution/src/shapley_attribution_model.py
compact: "Specifies run_shapley_attribution(), AggregatedShapleyAttribution, and amc_rows_to_shapley_rows(); each path's unique touchpoint set is a unanimity game split equally, returning AttributionResult that conserves converted_users, purchase_count, and revenue exactly. Read when changing Shapley math or DNN targets."
---

# `shapley_attribution_model.py`

- Responsibility: Implement exact path-level Shapley attribution as a sum of unanimity games.
- Inputs: Validated five-segment aggregated paths.
- Outputs: Native `AttributionResult` records.
- Dependencies: `attribution_contract.py`.
- Verification: `modules/mta_attribution/tests/test_attribution_contract.py`. There is no model-specific suite; the shared contract tests exercise `run_shapley_attribution` and `AggregatedShapleyAttribution` directly.
