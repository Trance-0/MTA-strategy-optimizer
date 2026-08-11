---
title: touchpoint_adapter.py
source_file: modules/mta_standard/src/touchpoint_adapter.py
---

# `touchpoint_adapter.py`

- Responsibility: Validate four-segment MTA-SIM keys and bridge them to native five-segment keys.
- Inputs: Four-segment keys and explicit CPC/CPM configuration.
- Outputs: Reversible key/path adaptations for the observed simulator dataset.
- Dependencies: Native attribution touchpoint-key contract.
- Verification: `modules/mta_standard/tests/test_touchpoint_adapter.py`.
