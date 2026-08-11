---
title: touchpoint_key.py
source_file: modules/mta_attribution/src/touchpoint_key.py
---

# `touchpoint_key.py`

- Responsibility: Define and canonicalize the native five-segment touchpoint key.
- Inputs: Touchpoint components or Amazon Ads rows.
- Outputs: Canonical `PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` keys.
- Dependencies: Python standard library only.
- Verification: `modules/mta_attribution/tests/test_touchpoint_key.py`.
