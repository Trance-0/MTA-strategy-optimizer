---
title: attribution_model_comparison.py
source_file: modules/mta_attribution/src/attribution_model_comparison.py
compact: "Specifies compare_attribution_models() returning ComparisonArtifacts (touchpoints, summary, recommended) plus read_amc_csv_strict, calculate_raw_support, data_support_is_sufficient, models_are_consistent, reliability_fields, spearman_rho, and the MODEL_OUTPUT_FIELDS/SUMMARY_FIELDS/RECOMMENDED_FIELDS schemas. Read when changing gap_pp or reliability thresholds."
---

# `attribution_model_comparison.py`

- Responsibility: Compare Markov and Shapley outputs, calculate reliability, and build recommendation artifacts.
- Inputs: Two model result sets and the governed path report.
- Outputs: Touchpoint comparison, summary, and recommended-attribution rows.
- Dependencies: `attribution_contract.py` and `touchpoint_key.py`.
- Verification: `modules/mta_attribution/tests/test_attribution_model_comparison.py`.
