---
title: uniform_attribution_model.py
source_file: modules/mta_attribution/src/uniform_attribution_model.py
---

# `uniform_attribution_model.py`

- Responsibility: Provide a deterministic equal-credit reference baseline.
- Inputs: A fitted `MtaSimDataset` scope.
- Outputs: Conservation-preserving four-segment standard rows.
- Dependencies: Attribution interface and `mta_standard` output contract.
- Verification: `modules/mta_attribution/tests/test_uniform_attribution_model.py`.
