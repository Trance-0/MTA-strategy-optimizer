---
title: markov_standard_attribution_model.py
source_file: modules/mta_attribution/src/markov_standard_attribution_model.py
compact: "Specifies MarkovRemovalEffectModel, model_id markov_removal_effect, a _JsonPersistedModel subclass whose attribute() calls run_markov_attribution() on dataset.path_rows then standard_rows_from_attribution_results() to emit StandardAttributionRow. Read when registering the Markov model or debugging four-segment adaptation."
---

# `markov_standard_attribution_model.py`

- Responsibility: Adapt the native Markov implementation to the common model interface without changing its mathematics.
- Inputs: `MtaSimDataset` with model-facing path rows.
- Outputs: Four-segment `StandardAttributionRow` records.
- Dependencies: Native Markov model plus `mta_standard` framework contracts.
- Verification: `modules/mta_attribution/tests/test_markov_standard_attribution_model.py`.
