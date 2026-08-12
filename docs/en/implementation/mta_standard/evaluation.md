---
title: evaluation.py
source_file: modules/mta_standard/src/evaluation.py
compact: "Specifies `load_simulation_ground_truth()`, `evaluate_standard_output()`, `evaluate_model()`, `compare_models()` and the `GroundTruth` / `EvaluationMetrics` / `EvaluationReport` dataclasses in `evaluation.py`: emits credit_share_mae, rmse, total_variation_distance, spearman_rho, top_k_overlap, conservation_error. Read when adding a metric."
---

# `evaluation.py`

- Responsibility: Load simulation ground truth separately and score standard model output.
- Inputs: Standard rows and evaluation-only ground truth.
- Outputs: Error, rank, overlap, conservation, and runtime metrics.
- Dependencies: Dataloader scope, output contract, and attribution Spearman calculation. Also `read_csv_normalized` from `attribution_contract.py`, `MtaAttributionModel` from `attribution_model_interface.py`, which `evaluate_model()` and `compare_models()` are typed against, and `canonicalize_four_segment_key` from `touchpoint_adapter.py`.
- Verification: `modules/mta_standard/tests/test_evaluation.py`.
