---
title: dataloader.py
source_file: modules/mta_standard/src/dataloader.py
compact: "Specifies `load_mta_sim_dataset()`, `load_amc_path_report()`, `load_amazon_ads_daily_touchpoint_performance()`, `four_segment_touchpoints_from_path_rows()` and the frozen `MtaSimDataset` / `ReportScope` in `dataloader.py`: builds `path_rows`, `ads_rows`, `outcome_totals`. Read when changing CSV headers or ground-truth exclusion."
---

# `dataloader.py`

- Responsibility: Load MTA-SIM path and performance tables into a model-facing dataset.
- Inputs: External CSV paths and an explicit simulator configuration.
- Outputs: `MtaSimDataset` with ground truth structurally excluded.
- Dependencies: Attribution path contract, `touchpoint_adapter.py`, and `read_amc_csv_strict` from `attribution_model_comparison.py`.
- Verification: `modules/mta_standard/tests/test_dataloader.py`.
