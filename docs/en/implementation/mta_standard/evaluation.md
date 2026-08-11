---
title: evaluation.py
source_file: modules/mta_standard/src/evaluation.py
---

# `evaluation.py`

- Responsibility: Load simulation ground truth separately and score standard model output.
- Inputs: Standard rows and evaluation-only ground truth.
- Outputs: Error, rank, overlap, conservation, and runtime metrics.
- Dependencies: Dataloader scope, output contract, and attribution Spearman calculation.
- Verification: `modules/mta_standard/tests/test_evaluation.py`.
