---
title: Assignment Type
description: How a budget was assigned, an optional Budget Observation field reserved for a future intervention study
compact: "AssignmentType StrEnum (RANDOMIZED, RULE_BASED, MANUAL, UNKNOWN) in modules/mta_common/src/enums.py — optional field on BudgetObservation.assignment_type. Reserved for a future intervention study; no current pipeline or legacy_adapters.py function populates it."
order: 50
lang: en-US
---

# Assignment Type

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`AssignmentType` names how a budget was assigned to a campaign: randomized for a controlled experiment, by a fixed rule, manually by a human, or unknown. It exists as an optional field on [Budget Observation](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-observation.md) so that class's shape does not need to change when a future intervention study is added, even though no current pipeline populates it.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/enums.py`, the vocabulary layer every other canonical class in `modules/mta_common/src/` depends on. `AssignmentType` has no dependency of its own beyond the Python standard library.

## Members <span class="status-label status-verified" aria-label="Verified"></span>

### RANDOMIZED

#### Meaning

The budget was assigned by a randomized mechanism, for example a controlled experiment arm.

### RULE_BASED

#### Meaning

The budget was assigned by a fixed, deterministic rule rather than randomization or manual judgment.

### MANUAL

#### Meaning

The budget was assigned directly by a human, outside of any randomized or rule-based mechanism.

### UNKNOWN

#### Meaning

It is not known which mechanism assigned the budget.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- Exactly four members exist: `RANDOMIZED`, `RULE_BASED`, `MANUAL`, `UNKNOWN`.
- As a `StrEnum`, each member's value is an exact string match of its name (`AssignmentType.RANDOMIZED == "RANDOMIZED"`).
- `BudgetObservation.assignment_type` is optional (`AssignmentType | None = None`); a `BudgetObservation` is fully constructible without ever setting it, and every current caller leaves it unset.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Budget Observation

[Budget Observation](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-observation.md)'s `assignment_type: AssignmentType | None = None` field is one of five fields — alongside `intervention_id`, `baseline_budget`, `budget_delta`, and `randomized` — its docstring marks "[r]eserved... for a future intervention study. Not populated by any current data source."

### Relationship to legacy_adapters.py

No function in `modules/mta_common/src/legacy_adapters.py` reads, produces, or accepts an `AssignmentType` value; the module does not import it.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None. No legacy shape this module bridges — not `strategy_request.json`, not `initial_budget_recommendation.json`, not any dashboard schema — records how a budget was assigned.

### Canonical Conversion

None. `legacy_adapters.py` does not import `AssignmentType`, and no adapter function sets `BudgetObservation.assignment_type`; every `BudgetObservation` it constructs leaves the field at its default of `None`.

### Information Loss

Not applicable. There is no legacy source and no adapter that populates this field, so there is no conversion in which information could be lost.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.budget import BudgetObservation
from modules.mta_common.src.enums import AssignmentType
from modules.mta_common.src.reporting_scope import ReportingScope

# No current adapter sets assignment_type; a future intervention study would.
observation = BudgetObservation(
    campaign_id="CAMPAIGN_1",
    reporting_scope=some_scope,
    configured_budget=100.0,
    actual_spend=80.0,
    assignment_type=AssignmentType.RANDOMIZED,
    randomized=True,
)
observation.assignment_type  # AssignmentType.RANDOMIZED, set explicitly by the caller
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future intervention study would populate `BudgetObservation.assignment_type` alongside `intervention_id`, `baseline_budget`, `budget_delta`, and `randomized` to record how each campaign's budget was assigned within the experiment, enabling causal comparison against a baseline. No such study exists in this repository today; this paragraph describes an intended future producer, not a guarantee enforced by `BudgetObservation` or any other class here.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/enums.py` and referenced as an optional field type by `BudgetObservation` in `modules/mta_common/src/budget.py`. `modules/mta_common/tests/test_enums_and_capabilities.py` and `modules/mta_common/tests/test_budget_and_delivery.py` exercise the surrounding classes; no test constructs a `BudgetObservation` with `assignment_type` set to a specific member.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No current pipeline component populates this field; it is a reserved slot on `BudgetObservation` for a future intervention study that does not exist yet.
- `AssignmentType` is an `enum.StrEnum`, one of seven vocabularies in `enums.py` that make up this repository's only use of the `Enum` family outside `modules/mta_common/`. Every other canonical class here is a plain `@dataclass(frozen=True)`; `StrEnum` was chosen for these seven vocabularies specifically so `AssignmentType` and the rest are not restated as ad-hoc string literals across the classes that reference them, at the cost of introducing a dependency the rest of this repository deliberately avoids.
