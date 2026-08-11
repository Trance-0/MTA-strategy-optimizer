---
title: mta_sim_generator_adapter.py
source_file: modules/mta_standard/src/mta_sim_generator_adapter.py
---

# `mta_sim_generator_adapter.py`

- Responsibility: Invoke the pinned ZheyuanWu generator and prepare framework-compatible model/evaluation views.
- Inputs: Submodule path, configuration, output directory, and generator variant.
- Outputs: Generated manifest, model dataset, and evaluation-only ground truth path.
- Dependencies: External generator, dataloader, and touchpoint adapter.
- Verification: `modules/mta_standard/tests/test_mta_sim_generator_adapter.py`.
