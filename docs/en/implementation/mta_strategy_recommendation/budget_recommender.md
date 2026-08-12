---
title: budget_recommender.py
source_file: modules/mta_strategy_recommendation/src/budget_recommender.py
compact: "Specifies `generate_budget_recommendation()`, `recommend_ad_group_count()`, `BudgetRecommendationError`, and constants `SUPPORTED_SAMPLE_VERSION` 4.0, `NORMALIZATION_UNIVERSE`, `FORMULA_VERSION`: emits `budget_seed_share`, `campaign_budget_seed`, `recommended_ad_groups`, `budget_derivation`. Read when changing capacity or split rules."
---

# `budget_recommender.py`

- Responsibility: Convert governed attribution evidence and capacity into an explainable initial Ad Group budget seed.
- Inputs: `generate_budget_recommendation(request, pool, attribution_rows, entity_rows)` takes the whole validated candidate-pool object, not bare counts; the per-Campaign counts are the nested `campaign_candidate_counts` key. Only the internal helper `recommend_ad_group_count()` takes raw counts.
- Outputs: Deterministic `INITIAL_SEED` budget recommendation.
- Dependencies: Python standard library only; consumes attribution artifacts, not attribution Python code.
- Verification: `modules/mta_strategy_recommendation/tests/test_hierarchy_validator.py`. This module has no dedicated suite; its coverage lives in the hierarchy validator tests.
