---
title: budget_recommender.py
source_file: modules/mta_strategy_recommendation/src/budget_recommender.py
---

# `budget_recommender.py`

- Responsibility: Convert governed attribution evidence and capacity into an explainable initial Ad Group budget seed.
- Inputs: Validated strategy request, candidate counts, attribution rows, and entity bridge rows.
- Outputs: Deterministic `INITIAL_SEED` budget recommendation.
- Dependencies: Python standard library only; consumes attribution artifacts, not attribution Python code.
- Verification: `modules/mta_strategy_recommendation/tests/test_hierarchy_validator.py`.
