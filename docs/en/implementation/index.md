---
title: Implementation Reference
description: One-to-one documentation index for maintained Python implementation files
---

# Implementation Reference

This section maps each maintained `modules/*/src/*.py` implementation to one page with the same filename stem. Introductory, environment, and research material remains in its existing sections.

| Module | Responsibility | File-level reference |
| --- | --- | --- |
| `mta_attribution` | Paths, contracts, concrete models, and comparison | [Attribution implementation](./mta_attribution/) |
| `mta_standard` | Loading, adapters, registry, execution, output validation, and evaluation | [Standard framework](./mta_standard/) |
| `mta_strategy_recommendation` | Hierarchy validation and budget initialization | [Strategy implementation](./mta_strategy_recommendation/) |

<DrawioDiagram base="./module-ownership" alt="Module ownership and execution flow" />
