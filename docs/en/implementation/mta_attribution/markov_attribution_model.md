---
title: markov_attribution_model.py
source_file: modules/mta_attribution/src/markov_attribution_model.py
compact: "Specifies run_markov_attribution(), WeightedMarkovAttribution, amc_path_to_markov_path(), amc_rows_to_markov_rows(), amc_rows_to_outcome_markov_rows(); one removal-effect model per outcome over Start/Conversion/Null states, returning AttributionResult rescaled onto converted_users, purchase_count, revenue. Read when changing removal-effect math."
---

# `markov_attribution_model.py`

- Responsibility: Implement weighted first-order Markov removal-effect attribution.
- Inputs: Validated five-segment aggregated paths.
- Outputs: Native `AttributionResult` records for converted users, purchases, and revenue.
- Dependencies: `attribution_contract.py` and `touchpoint_key.py`.
- Verification: `modules/mta_attribution/tests/test_attribution_contract.py`. There is no model-specific suite; the shared contract tests exercise `run_markov_attribution` and `WeightedMarkovAttribution` directly.
