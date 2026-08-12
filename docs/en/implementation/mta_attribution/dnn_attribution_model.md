---
title: dnn_attribution_model.py
source_file: modules/mta_attribution/src/dnn_attribution_model.py
compact: "Specifies DeepNeuralAttributionModel (fit, attribute, predicted_shares, predict_new_campaign, save, load), build_touchpoint_features(), TouchpointFeatures, SEGMENT_NAMES and NUMERIC_FEATURE_NAMES; listwise softmax over the four segments trained on Shapley targets. Read when scoring unlaunched campaigns."
---

# `dnn_attribution_model.py`

- Responsibility: Learn segment-based attribution shares from path-level Shapley targets and score unseen campaign touchpoints.
- Inputs: Four-segment dataset features; simulation ground truth is excluded.
- Outputs: Standard attribution rows and optional persisted network state.
- Dependencies: Attribution interface, Shapley implementation, and `mta_standard` contracts, plus `NULL` and `safe_float` from `attribution_contract.py` and `OUTCOME_FIELDS` from `attribution_model_comparison.py`.
- Verification: `modules/mta_attribution/tests/test_dnn_attribution_model.py`.
