---
title: uniform_attribution_model.py
source_file: modules/mta_attribution/src/uniform_attribution_model.py
compact: "Specifies UniformCreditModel, model_id uniform_credit, whose attribute() splits each dataset.outcome_totals equally across sorted touchpoints and emits StandardAttributionRow with the residual absorbed by the last row and ZERO_OUTCOME_WARNING on empty outcomes. Read when checking conservation baselines."
---

# `uniform_attribution_model.py`

- Responsibility: Provide a deterministic equal-credit reference baseline.
- Inputs: A fitted `MtaSimDataset` scope.
- Outputs: Conservation-preserving four-segment standard rows.
- Dependencies: Attribution interface and `mta_standard` output contract.
- Verification: `modules/mta_attribution/tests/test_uniform_attribution_model.py`.
