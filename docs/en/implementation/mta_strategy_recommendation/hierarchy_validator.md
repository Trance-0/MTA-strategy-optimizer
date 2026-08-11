---
title: hierarchy_validator.py
source_file: modules/mta_strategy_recommendation/src/hierarchy_validator.py
---

# `hierarchy_validator.py`

- Responsibility: Validate Campaign Group scope and pin attribution/entity evidence by SHA-256.
- Inputs: Strategy request, candidate pool, attribution CSV, and entity bridge CSV.
- Outputs: Validated input objects or a precise hierarchy error.
- Dependencies: `budget_recommender.py` contracts and Python standard library.
- Verification: `modules/mta_strategy_recommendation/tests/test_hierarchy_validator.py`.
