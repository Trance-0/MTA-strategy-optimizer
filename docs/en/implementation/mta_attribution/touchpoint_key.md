---
title: touchpoint_key.py
source_file: modules/mta_attribution/src/touchpoint_key.py
compact: "Specifies canonical_touchpoint_key(), canonicalize_touchpoint_key(), touchpoint_key_from_ads_row(), the canonical_amc_touchpoint_key/canonicalize_amc_touchpoint_key aliases, UNSPECIFIED and INTERACTION_TYPES; builds AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE, reading inventoryType for AMAZON_DSP and adType for SPONSORED_*. Read when keys fail to join."
---

# `touchpoint_key.py`

- Responsibility: Define and canonicalize the native five-segment touchpoint key.
- Inputs: Touchpoint components or Amazon Ads rows.
- Outputs: Canonical `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` keys.
- Dependencies: Python standard library only.
- Verification: `modules/mta_attribution/tests/test_touchpoint_key.py`.
