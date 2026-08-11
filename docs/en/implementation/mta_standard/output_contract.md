---
title: output_contract.py
source_file: modules/mta_standard/src/output_contract.py
---

# `output_contract.py`

- Responsibility: Define standard attribution rows and enforce conservation, uniqueness, and non-negativity.
- Inputs: Model-produced standard rows and observed outcome totals.
- Outputs: Validated output summaries or precise contract errors.
- Dependencies: Four-segment touchpoint adapter and governed outcome vocabulary.
- Verification: `modules/mta_standard/tests/test_output_contract.py`.
