---
title: Strategy Objective
description: What a future budget optimizer would maximize, declared independently of how the budget must be used
compact: "StrategyObjective StrEnum (MAXIMIZE_REVENUE, MAXIMIZE_PROFIT) in modules/mta_common/src/enums.py — a future optimizer's objective, orthogonal to BudgetUsagePolicy. Not referenced by any dataclass field anywhere in modules/mta_common/src/; no optimizer reads it yet. Pure declaration."
lang: en-US
---

# Strategy Objective

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`StrategyObjective` names what a future budget optimizer would maximize: total attributed revenue, or profit after advertising cost. It exists as a standalone vocabulary, not a field on any class defined today, because no optimizer exists in this repository yet to read it. Declaring the vocabulary now lets [Canonical Data Model](./index.md)'s foundation state the intended objective space without pretending an optimizer already consumes it.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/enums.py`, the vocabulary layer every other canonical class in `modules/mta_common/src/` depends on. `StrategyObjective` has no dependency of its own beyond the Python standard library.

## Members <span class="status-label status-verified" aria-label="Verified"></span>

### MAXIMIZE_REVENUE

#### Meaning

A future optimizer configured with this objective would maximize total attributed revenue, without subtracting advertising Spend or product cost.

### MAXIMIZE_PROFIT

#### Meaning

A future optimizer configured with this objective would maximize profit: attributed revenue net of advertising cost and, where available, product cost via [Contribution Margin](/en/reference/definitions#contribution-margin). Distinct from [ROAS](/en/reference/definitions#roas-return-on-ad-spend), which is a ratio rather than a total the optimizer could maximize directly.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- Exactly two members exist: `MAXIMIZE_REVENUE` and `MAXIMIZE_PROFIT`. `modules/mta_common/tests/test_enums_and_capabilities.py::StrategyObjectiveAndBudgetPolicyTests` asserts `StrategyObjective` and [Budget Usage Policy](./budget-usage-policy.md) have disjoint member sets and, via `itertools.product`, that all four combinations of one `StrategyObjective` with one `BudgetUsagePolicy` are constructible and distinct — the two vocabularies are orthogonal, not two branches of one choice.
- As a `StrEnum`, each member's value is an exact string match of its name (`StrategyObjective.MAXIMIZE_REVENUE == "MAXIMIZE_REVENUE"`).
- `StrategyObjective` is not stored as a field on any `@dataclass(frozen=True)` in `modules/mta_common/src/` today. This is unlike [Budget Usage Policy](./budget-usage-policy.md), which is a required field on `BudgetConstraints`.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Budget Constraints

[Budget Constraints](./budget-constraints.md) does not carry a `StrategyObjective` field today. `budget.py`'s module docstring names `StrategyObjective` alongside `BudgetConstraints` and `BudgetUsagePolicy` as inputs "a future strategy optimizer would read... to decide an allocation," but that reading path is prose describing an intended future consumer, not a field reference in code.

### Relationship to Budget Usage Policy

[Budget Usage Policy](./budget-usage-policy.md) is the orthogonal vocabulary a future optimizer would read alongside `StrategyObjective`: one names what to maximize, the other names whether the authorized budget must be exhausted while doing so. Neither enum's docstring frames the other as a precondition or a special case.

### Relationship to Canonical Data Model

[Canonical Data Model](./index.md)'s Scope and Non-Goals section names "a budget optimizer that reads `StrategyObjective` and `BudgetUsagePolicy` and produces an allocation" as something this module deliberately does not implement.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None. No field in `strategy_request.json`, `initial_budget_recommendation.json`, or any other legacy shape this module bridges names a revenue-versus-profit objective.

### Canonical Conversion

None. No function in `modules/mta_common/src/legacy_adapters.py` reads, produces, or accepts a `StrategyObjective` value; the module does not import it.

### Information Loss

Not applicable. There is no legacy source and no adapter, so there is no conversion in which information could be lost.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.enums import BudgetUsagePolicy, StrategyObjective
import itertools

# The two vocabularies are orthogonal: all four combinations are valid.
for objective, policy in itertools.product(StrategyObjective, BudgetUsagePolicy):
    (objective, policy)  # e.g. (MAXIMIZE_PROFIT, SPEND_UP_TO_BUDGET)

StrategyObjective.MAXIMIZE_REVENUE == "MAXIMIZE_REVENUE"  # True — StrEnum
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future optimizer would read a campaign's configured `StrategyObjective` to choose what quantity to maximize subject to `BudgetConstraints`. A `MAXIMIZE_PROFIT` optimizer would need to combine attributed revenue with `ProductEconomics.unit_contribution_margin` (via [Margin Source](./margin-source.md)) and actual ad spend; unused authorized budget under [Budget Usage Policy](./budget-usage-policy.md)'s `SPEND_UP_TO_BUDGET` would not be counted as a positive profit or revenue term, since it was never spent and produced no attributed outcome. No code in this repository implements this logic today — this paragraph describes an intended future reader's semantics, not a guarantee enforced by any class here.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/enums.py` and exercised by `modules/mta_common/tests/test_enums_and_capabilities.py::StrategyObjectiveAndBudgetPolicyTests`. Not referenced by any other file under `modules/mta_common/src/`.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- Unlike every other vocabulary in `enums.py`, `StrategyObjective` is not a field on any dataclass defined in this module. It exists purely as a declaration for a future optimizer, with no current caller and no current adapter.
- `StrategyObjective` is an `enum.StrEnum`, one of seven vocabularies in `enums.py` that make up this repository's only use of the `Enum` family outside `modules/mta_common/`. Every other canonical class here is a plain `@dataclass(frozen=True)`; `StrEnum` was chosen for these seven vocabularies specifically so `StrategyObjective` and the rest are not restated as ad-hoc string literals across the classes that would reference them, at the cost of introducing a dependency the rest of this repository deliberately avoids.
