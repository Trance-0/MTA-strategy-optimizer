---
title: simulated_touchpoints.py
source_file: modules/mta_attribution/src/simulated_touchpoints.py
compact: "Specifies TouchpointSpec, TOUCHPOINT_CATALOG, TOUCHPOINT_KEYS, EXPECTED_TOUCHPOINT_KEYS (17 frozen five-segment keys), validate_touchpoint_catalog(), historical_entity_for_touchpoint(), CAMPAIGN_BY_AD_PRODUCT, and constants MARKETPLACE US, ADVERTISER_ID adv_demo_001, CAMPAIGN_GROUP_ID CG_DEMO_001. Read when changing the fixed sample touchpoint set."
---

# `simulated_touchpoints.py`

- Responsibility: Define the fixed legacy touchpoint catalogue used by committed sample generation.
- Inputs: Declarative touchpoint specifications.
- Outputs: Validated touchpoint and entity specifications.
- Dependencies: `touchpoint_key.py`.
- Verification: `modules/mta_attribution/tests/test_end_to_end_pipeline.py`.
