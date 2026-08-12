---
title: attribution_contract.py
source_file: modules/mta_attribution/src/attribution_contract.py
compact: "Specifies AttributionResult, TouchpointSpend, read_csv, read_csv_normalized, write_csv_atomic, write_csv_set_atomic, validate_amc_aggregated_row, aggregate_spend_by_touchpoint, result_rows, and the START/CONVERSION/NULL states; result_rows emits the 18-column output with roas, roi, cpa. Read when changing path or Ads schemas."
---

# `attribution_contract.py`

- Responsibility: Own AMC path/Ads schemas, CSV boundaries, row validation, result dataclasses, spend aggregation, and conservation-preserving publication.
- Inputs: Aggregated path rows and Amazon Ads rows.
- Outputs: Validated rows, `AttributionResult`, `TouchpointSpend`, and published model-row dictionaries.
- Dependencies: `touchpoint_key.py`; Python standard library only.
- Verification: `modules/mta_attribution/tests/test_attribution_contract.py` and end-to-end pipeline tests.
