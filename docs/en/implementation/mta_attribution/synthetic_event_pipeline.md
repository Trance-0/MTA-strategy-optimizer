---
title: synthetic_event_pipeline.py
source_file: modules/mta_attribution/src/synthetic_event_pipeline.py
compact: "Specifies generate_synthetic_user_events(), validate_synthetic_user_events(), derive_amc_touchpoint_events(), derive_amazon_ads_rows(), derive_touchpoint_entity_aggregate(), validate_derivations(), validate_no_user_identifiers(), the SYNTHETIC_EVENT_FIELDS, AMC_EVENT_FIELDS, ADS_FIELDS, ENTITY_AGGREGATE_FIELDS schemas, and STANDARD_COHORT_COUNT 136. Read when regenerating the committed sample CSVs under data/."
---

# `synthetic_event_pipeline.py`

- Responsibility: Reproduce the legacy five-segment sample and its Ads/entity projections.
- Inputs: Report dates and the fixed simulated touchpoint catalogue.
- Outputs: Synthetic user events, path events, Ads rows, and entity aggregates.
- Dependencies: `simulated_touchpoints.py` and `touchpoint_key.py`.
- Verification: `modules/mta_attribution/tests/test_end_to_end_pipeline.py`.
