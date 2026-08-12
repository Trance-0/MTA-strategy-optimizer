---
title: output_contract.py
source_file: modules/mta_standard/src/output_contract.py
compact: "Specifies frozen `StandardAttributionRow`, `validate_standard_output()`, `standard_rows_to_dicts()`, `STANDARD_OUTPUT_FIELDS`, `SUPPORTED_OUTCOMES`, and `ZERO_OUTCOME_TOTAL` in `output_contract.py`: enforces non-negativity, row uniqueness, share and outcome conservation. Read when altering the emitted row shape or tolerances."
---

# `output_contract.py`

- Responsibility: Define standard attribution rows and enforce four invariants: non-negativity, row uniqueness, share conservation, and outcome conservation. Share and outcome conservation are checked separately, at 1e-6 absolute tolerance and a 1e-9 relative allowance respectively.
- Inputs: Model-produced standard rows and observed outcome totals.
- Outputs: Validated output summaries or precise contract errors.
- Dependencies: Four-segment touchpoint adapter and governed outcome vocabulary.
- Verification: `modules/mta_standard/tests/test_output_contract.py`.
