---
title: Analysis Workbench Release
compact: "Approved incremental Dashboard delivery: persistent datasets, standard imports, dataset-scoped resources and runs, readable charts, revisioned budget plans, strategy evaluation, provenance, recovery, and BMad story execution."
---

# Analysis Workbench Release

This release connects the existing Dashboard capabilities into a reproducible
offline analysis session. The operator chooses data, reads observed performance,
executes a budget plan, inspects evaluation, and can recover the exact inputs
behind a result. Separate datasets and runs prevent an earlier demonstration
from supplying numbers missing from a newly imported dataset.

The [requirements](./prd.md) define the accepted product behavior. The
[decision record](./decision-log.md) preserves the user's choices and the
workflow overrides used for this existing project. Design, architecture,
stories, and verification records are added here as their respective BMad
steps finish. Runtime contracts remain on their owning Dashboard pages.

[Architecture](./architecture.md), [visual design](./DESIGN.md) and
[interaction behavior](./EXPERIENCE.md) supply the implementation constraints.

[Verification](./verification.md) records implemented behavior, review fixes,
commands and completed integrated acceptance. The sprint record closes
implementation only after the native browser and large-data checks passed.
