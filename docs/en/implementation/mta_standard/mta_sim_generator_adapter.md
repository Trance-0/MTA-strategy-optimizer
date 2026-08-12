---
title: mta_sim_generator_adapter.py
source_file: modules/mta_standard/src/mta_sim_generator_adapter.py
compact: "Specifies `generate_and_load_mta_sim_dataset()` and frozen `GeneratedMtaSimRun` in `mta_sim_generator_adapter.py`: runs the pinned ZheyuanWu `run_pipeline` for variant baseline or regional, writing `model_input_amc_path_report.csv` and `model_evaluation_ground_truth.csv`. Read when the submodule pin or CPC/CPM derivation changes."
---

# `mta_sim_generator_adapter.py`

- Responsibility: Invoke the pinned ZheyuanWu generator and prepare framework-compatible model/evaluation views.
- Inputs: Submodule path, configuration, output directory, and generator variant.
- Outputs: Generated manifest, model dataset, and evaluation-only ground truth path.
- Dependencies: External generator, dataloader, and touchpoint adapter.
- Verification: `modules/mta_standard/tests/test_mta_sim_generator_adapter.py`.
