---
title: hierarchy_validator.py
source_file: modules/mta_strategy_recommendation/src/hierarchy_validator.py
compact: "Specifies `load_aligned_strategy_inputs()`, `validate_simulated_hierarchy()`, `HierarchyValidationError`, `REQUIRED_INPUT_FILES` (`strategy_request.json`, `candidate_pool.json`) and `FORBIDDEN_OUTPUT_FIELDS`: re-derives the recommendation and diffs it. Read when changing SHA-256 pinning or budget-only field bans."
---

# `hierarchy_validator.py`

- Responsibility: Validate Campaign Group scope and pin attribution/entity evidence by SHA-256.
- Inputs: `load_aligned_strategy_inputs(data_dir, attribution_path, entity_path)` takes a directory and reads `strategy_request.json` and `candidate_pool.json` from it itself, together with the attribution and entity bridge CSV paths. `validate_simulated_hierarchy()` additionally accepts `recommendation_path`.
- Outputs: `load_aligned_strategy_inputs` returns the validated request, pool, attribution rows, and entity rows, or raises `HierarchyValidationError`. `validate_simulated_hierarchy` returns a summary mapping containing `campaign_group_id`, `campaign_count`, `recommended_ad_group_count`, `normalization_universe`, `has_budget_baseline`, `recommendation_type`, and `warnings`.
- Dependencies: `budget_recommender.py` contracts and Python standard library.
- Verification: `modules/mta_strategy_recommendation/tests/test_hierarchy_validator.py`.
