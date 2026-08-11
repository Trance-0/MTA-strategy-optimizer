---
title: attribution_contract.py
source_file: modules/mta_attribution/src/attribution_contract.py
---

# `attribution_contract.py`

- Responsibility: Own AMC path/Ads schemas, CSV boundaries, row validation, result dataclasses, spend aggregation, and conservation-preserving publication.
- Inputs: Aggregated path rows and Amazon Ads rows.
- Outputs: Validated rows, `AttributionResult`, `TouchpointSpend`, and published model-row dictionaries.
- Dependencies: `touchpoint_key.py`; Python standard library only.
- Verification: `modules/mta_attribution/tests/test_attribution_contract.py` and end-to-end pipeline tests.
