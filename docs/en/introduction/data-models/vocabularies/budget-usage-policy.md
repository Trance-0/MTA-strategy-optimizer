---
title: Budget Usage Policy
description: Whether a future budget optimizer must exhaust an authorized budget, a required field on Budget Constraints with no legacy representation
compact: "BudgetUsagePolicy StrEnum (SPEND_UP_TO_BUDGET, SPEND_FULL_BUDGET) in modules/mta_common/src/enums.py — required field on BudgetConstraints.budget_usage_policy. No legacy source represents it; budget_constraints_from_campaign_output requires the caller to supply it explicitly. Orthogonal to StrategyObjective."
order: 40
lang: en-US
---

# Budget Usage Policy

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`BudgetUsagePolicy` states whether a future budget optimizer must allocate the full authorized budget or may leave some unused when no further spend is justified. It is a required field on [Budget Constraints](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-constraints.md) today, even though no optimizer exists yet to read it, because `BudgetConstraints` is meant to fully describe the bounds and rules an allocation must satisfy, and "must the budget be exhausted" is one of those rules.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/enums.py`, the vocabulary layer every other canonical class in `modules/mta_common/src/` depends on. `BudgetUsagePolicy` has no dependency of its own beyond the Python standard library.

## Members <span class="status-label status-verified" aria-label="Verified"></span>

### SPEND_UP_TO_BUDGET

#### Meaning

Allows a future optimizer to leave budget unused when no further spend is justified. The authorized amount is a ceiling, not a target.

### SPEND_FULL_BUDGET

#### Meaning

Requires a future optimizer to allocate the full authorized amount. The authorized amount is both a ceiling and a target.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- Exactly two members exist: `SPEND_UP_TO_BUDGET` and `SPEND_FULL_BUDGET`. `modules/mta_common/tests/test_enums_and_capabilities.py::StrategyObjectiveAndBudgetPolicyTests` asserts these are disjoint from [Strategy Objective](/en/introduction/data-models/vocabularies/strategy-objective.md)'s member set and, via `itertools.product`, that all four combinations of one `StrategyObjective` with one `BudgetUsagePolicy` are constructible and distinct.
- As a `StrEnum`, each member's value is an exact string match of its name (`BudgetUsagePolicy.SPEND_UP_TO_BUDGET == "SPEND_UP_TO_BUDGET"`).
- `BudgetConstraints.budget_usage_policy` is a required field with no default; a `BudgetConstraints` cannot be constructed without choosing one of the two members.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Budget Constraints

[Budget Constraints](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-constraints.md)'s `budget_usage_policy: BudgetUsagePolicy` field is required, unlike `minimum_daily_budget` and `maximum_daily_budget`, which are optional. `BudgetConstraints` itself does not enforce the policy against any observed spend; its docstring states this is "[d]eclared here for a future optimizer to read."

### Relationship to Strategy Objective

[Strategy Objective](/en/introduction/data-models/vocabularies/strategy-objective.md) is the orthogonal vocabulary a future optimizer would read alongside `BudgetUsagePolicy`: one names what to maximize, the other names whether the authorized budget must be exhausted while doing so.

### Relationship to legacy_adapters.py

`legacy_adapters.py`'s `budget_constraints_from_campaign_output` cannot default or infer a `BudgetUsagePolicy`; see Legacy Mapping below.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None. `legacy_adapters.py`'s module docstring states plainly: "`BudgetUsagePolicy` is not represented in that schema either" — referring to `strategy_request.json` and `initial_budget_recommendation.json`, neither of which has a field distinguishing "must exhaust the budget" from "may leave budget unused."

### Canonical Conversion

`budget_constraints_from_campaign_output(campaign_output, *, budget_usage_policy: BudgetUsagePolicy)` takes `budget_usage_policy` as a required keyword-only parameter with no default. Its docstring: "Not represented anywhere in `strategy_request.json` or its output today; the caller must supply it explicitly rather than have it defaulted or inferred." Every other field this function adapts (`campaign_id`, `minimum_daily_budget`) is read from `campaign_output`; `budget_usage_policy` is the one field the caller must decide.

### Information Loss

Not applicable in the legacy-to-canonical direction, since there is no legacy field to lose information from. The risk runs the other way: since `budget_constraints_from_campaign_output` has no source field to validate the caller's choice against, a caller that supplies the wrong policy would silently mislabel a campaign's allocation rule with no way for the adapter to detect the mismatch.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.enums import BudgetUsagePolicy
from modules.mta_common.src.legacy_adapters import budget_constraints_from_campaign_output

# budget_usage_policy has no legacy source; the caller must decide.
constraints = budget_constraints_from_campaign_output(
    {"campaign_id": "CAMPAIGN_1", "minimum_required_daily_budget": 50.0},
    budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
)
constraints.budget_usage_policy  # BudgetUsagePolicy.SPEND_UP_TO_BUDGET, as supplied
constraints.maximum_daily_budget  # None — no ceiling field in this legacy shape either
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future optimizer would read a campaign's `BudgetUsagePolicy` to decide whether an allocation leaving budget unused is acceptable (`SPEND_UP_TO_BUDGET`) or must be rejected in favor of one that allocates the full amount (`SPEND_FULL_BUDGET`). No optimizer exists in this repository today; this paragraph describes an intended future reader's semantics, not a guarantee enforced by `BudgetConstraints` or any other class here.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/enums.py`, required by `BudgetConstraints` in `modules/mta_common/src/budget.py`, and exercised by `modules/mta_common/tests/test_enums_and_capabilities.py::StrategyObjectiveAndBudgetPolicyTests`, `modules/mta_common/tests/test_budget_and_delivery.py`, and the adapter-path coverage in `modules/mta_common/tests/test_legacy_adapters.py` for `budget_constraints_from_campaign_output`.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No legacy source represents this policy; every `BudgetConstraints` built by `legacy_adapters.py` carries whatever value the caller supplied, with no source field to cross-check it against.
- `BudgetUsagePolicy` is an `enum.StrEnum`, one of seven vocabularies in `enums.py` that make up this repository's only use of the `Enum` family outside `modules/mta_common/`. Every other canonical class here is a plain `@dataclass(frozen=True)`; `StrEnum` was chosen for these seven vocabularies specifically so `BudgetUsagePolicy` and the rest are not restated as ad-hoc string literals across the classes that reference them, at the cost of introducing a dependency the rest of this repository deliberately avoids.
