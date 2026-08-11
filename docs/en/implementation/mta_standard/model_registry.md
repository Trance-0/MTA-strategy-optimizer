---
title: model_registry.py
source_file: modules/mta_standard/src/model_registry.py
---

# `model_registry.py`

- Responsibility: Map stable model identifiers to independently owned model classes.
- Inputs: A model identifier.
- Outputs: A new unfitted model implementing the shared interface.
- Dependencies: Concrete classes from `mta_attribution`; contains no model mathematics.
- Verification: Registry assertions across attribution and framework test suites.
