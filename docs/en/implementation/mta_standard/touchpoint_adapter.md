---
title: touchpoint_adapter.py
source_file: modules/mta_standard/src/touchpoint_adapter.py
compact: "Specifies frozen `SimulatorConfig` (`from_mapping`, `cost_type_for`, `interaction_type_for`, `to_five_segment`, `adapt_path`, `assert_reversible`) plus `canonical_four_segment_key()`, `canonicalize_four_segment_key()`, `to_four_segment()`, `four_segment_key_from_ads_row()`. Read when the CPC to CLICK / CPM to IMPRESSION mapping changes."
---

# `touchpoint_adapter.py`

- Responsibility: Validate four-segment MTA-SIM keys and bridge them to native five-segment keys.
- Inputs: Four-segment keys and explicit CPC/CPM configuration.
- Outputs: Reversible key/path adaptations for the observed simulator dataset.
- Dependencies: Native attribution touchpoint-key contract.
- Verification: `modules/mta_standard/tests/test_touchpoint_adapter.py`.
