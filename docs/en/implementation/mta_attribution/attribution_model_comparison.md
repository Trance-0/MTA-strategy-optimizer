---
title: attribution_model_comparison.py
source_file: modules/mta_attribution/src/attribution_model_comparison.py
---

# `attribution_model_comparison.py`

- Responsibility: Compare Markov and Shapley outputs, calculate reliability, and build recommendation artifacts.
- Inputs: Two model result sets and the governed path report.
- Outputs: Touchpoint comparison, summary, and recommended-attribution rows.
- Dependencies: `attribution_contract.py` and `touchpoint_key.py`.
- Verification: `modules/mta_attribution/tests/test_attribution_model_comparison.py`.
