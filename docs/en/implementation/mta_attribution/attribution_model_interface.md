---
title: attribution_model_interface.py
source_file: modules/mta_attribution/src/attribution_model_interface.py
compact: "Specifies the abstract MtaAttributionModel (fit, attribute, save, load, fitted_scope, _require_fitted), ModelCapabilities, _JsonPersistedModel, and standard_rows_from_attribution_results(), which folds five-segment AttributionResult into four-segment StandardAttributionRow. Read when adding a model or changing the fitted-scope guard."
---

# `attribution_model_interface.py`

- Responsibility: Define the common `fit`, `attribute`, `save`, and `load` contract implemented by every concrete attribution model.
- Inputs: Framework `MtaSimDataset` objects.
- Outputs: Lists of standard attribution rows and persisted model state where supported.
- Dependencies: `mta_standard` dataset, output contract, and touchpoint adapter, plus `AttributionResult` from `attribution_contract.py` and `OUTCOME_FIELDS` from `attribution_model_comparison.py`. Also exposes the public helper `standard_rows_from_attribution_results`, which both standard adapters call.
- Verification: `modules/mta_attribution/tests/test_attribution_model_interface.py`.
