---
title: Budget Constraints
description: Forward-looking budget bounds and usage policy for one campaign
compact: "BudgetConstraints (modules/mta_common/src/budget.py): campaign_id, budget_usage_policy, optional minimum/maximum_daily_budget read by the Campaign budget optimizer as hard bounds. No adapter populates maximum_daily_budget or infers budget_usage_policy — the caller must supply it explicitly."
order: 10
lang: en-US
---

# Budget Constraints

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`BudgetConstraints` declares the forward-looking budget bounds and usage policy a future strategy optimizer would read before deciding an allocation for one campaign. `modules/mta_strategy_recommendation` is entirely pre-spend today: every budget-shaped field it produces (`total_daily_budget`, `campaign_budget_seed`, `initial_daily_budget`, `minimum_required_daily_budget`) is a forward-looking allocation amount, never an observed spend. `BudgetConstraints` models that forward-looking half of the budget picture; its counterpart, [Budget Observation](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-observation.md), models what was actually configured and spent.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/budget.py`, in the Budget, Delivery, and Outcome Observations layer of the [Canonical Data Model](/en/introduction/data-models/index.md). It depends only on `enums.py` for [Budget Usage Policy](/en/introduction/data-models/vocabularies/budget-usage-policy.md) and [Assignment Type](/en/introduction/data-models/vocabularies/assignment-type.md) (the latter is declared as a dependency of the module but not used by this class; see `BudgetObservation`). It does not depend on [Reporting Scope](/en/introduction/data-models/touchpoint-and-provider-contract/reporting-scope.md), since a budget constraint is a forward-looking bound on a campaign rather than an observation over a reporting window.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### campaign_id

#### Type

`str`

#### Requiredness

Required, no default.

#### Meaning

The constrained [Campaign](/en/introduction/data-models/campaign-identity/campaign.md)'s `campaign_id`.

#### Missingness

Not applicable; the field has no `None` state.

#### Validation

Rejected when blank or all-whitespace.

### budget_usage_policy

#### Type

[`BudgetUsagePolicy`](/en/introduction/data-models/vocabularies/budget-usage-policy.md)

#### Requiredness

Required, no default.

#### Meaning

Whether a future optimizer must exhaust this campaign's authorized budget (`SPEND_FULL_BUDGET`) or may leave part of it unused when no further spend is justified (`SPEND_UP_TO_BUDGET`). Declared here for a future optimizer to read; `BudgetConstraints` itself does not enforce the policy against any observed spend.

#### Missingness

Not applicable; the field has no `None` state. No legacy source represents this policy, so every current construction path requires the caller to supply one explicitly — see Legacy Mapping.

#### Validation

Must be a `BudgetUsagePolicy` member; no further constraint.

### minimum_daily_budget

#### Type

`float | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

A feasibility floor, mirroring `budget_recommender.py`'s existing `minimum_required_daily_budget`.

#### Missingness

`None` means no floor is known or applicable for this campaign, not a floor of zero.

#### Validation

Rejected when negative. Rejected when it exceeds `maximum_daily_budget`, when both are given.

### maximum_daily_budget

#### Type

`float | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

An authorized spending ceiling for this campaign.

#### Missingness

`None` means no ceiling is known or applicable, not an unlimited-by-design ceiling recorded as such. No current adapter ever populates this field with a real value — see Legacy Mapping.

#### Validation

Rejected when negative. Rejected when it is smaller than `minimum_daily_budget`, when both are given.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `campaign_id` is never blank.
- `minimum_daily_budget` and `maximum_daily_budget` are each non-negative when present.
- `minimum_daily_budget` never exceeds `maximum_daily_budget` when both are present.
- `budget_usage_policy` is always one of the two [Budget Usage Policy](/en/introduction/data-models/vocabularies/budget-usage-policy.md) members; there is no third "unspecified" state, because the caller is required to choose one explicitly at construction time rather than defaulting to either.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Campaign

`campaign_id` references [Campaign](/en/introduction/data-models/campaign-identity/campaign.md).`campaign_id` by value; `BudgetConstraints` does not hold a `Campaign` object directly, matching the pattern used by [Budget Observation](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-observation.md).

### Relationship to Budget Observation

`BudgetConstraints` is forward-looking (what is allowed); [Budget Observation](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-observation.md) is backward-looking (what was configured and spent). A future optimizer reads both: `BudgetConstraints` to bound a decision, `BudgetObservation` to evaluate a past one.

### Relationship to Strategy Objective and Budget Usage Policy

`budget_usage_policy` is one of the two orthogonal axes — alongside [Strategy Objective](/en/introduction/data-models/vocabularies/strategy-objective.md) — that an optimizer reads together. Neither this class nor either enum implements the optimizer itself; the [Campaign budget optimizer](/en/strategy-recommendation/campaign-budget-optimizer.md) in `modules/mta_strategy_recommendation` is the implemented reader of both, and it honors `SPEND_FULL_BUDGET` and `SPEND_UP_TO_BUDGET` as distinct allocation constraints.

### Relationship to Campaign Episode

A [Campaign Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md) composed for a response model or optimizer would carry a campaign's `BudgetConstraints` alongside its `BudgetObservation` history, though `episode.py` does not yet include a `BudgetConstraints` field — see Known Limitations. The implemented optimizer works around this by taking constraints on its own request object rather than reading them from the episode.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

`modules/mta_strategy_recommendation`'s `initial_budget_recommendation.json` output, specifically one campaign output entry's `campaign_id` and, when a budget baseline was given, `minimum_required_daily_budget`. No field in that schema represents an authorized maximum distinct from the total Campaign Group budget, and no field represents a usage policy at all.

### Canonical Conversion

`legacy_adapters.budget_constraints_from_campaign_output(campaign_output, *, budget_usage_policy)` reads `campaign_id` and `minimum_required_daily_budget` from one campaign output entry into `campaign_id` and `minimum_daily_budget`. `budget_usage_policy` is a required keyword argument the caller must supply; the function never defaults or infers it, since `strategy_request.json` and its output carry no representation of that policy to adapt from.

### Information Loss

None on the fields that are adapted: `campaign_id` and `minimum_daily_budget` carry through exactly. `maximum_daily_budget` is not loss so much as absence — the adapted record always leaves it `None`, verified by the dedicated test `test_maximum_daily_budget_is_always_none` in `modules/mta_common/tests/test_legacy_adapters.py`.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

Adapting an existing campaign output, with the usage policy supplied explicitly since no source field carries it:

```python
from modules.mta_common.src.enums import BudgetUsagePolicy
from modules.mta_common.src.legacy_adapters import budget_constraints_from_campaign_output

campaign_output = {
    "campaign_id": "CAMP-1",
    "minimum_required_daily_budget": 10.0,
}
constraints = budget_constraints_from_campaign_output(
    campaign_output,
    budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
)
# constraints.maximum_daily_budget is None: no current source supplies it
```

Constructing one directly, with both bounds known:

```python
from modules.mta_common.src.budget import BudgetConstraints
from modules.mta_common.src.enums import BudgetUsagePolicy

BudgetConstraints(
    campaign_id="CAMP-1",
    budget_usage_policy=BudgetUsagePolicy.SPEND_FULL_BUDGET,
    minimum_daily_budget=10.0,
    maximum_daily_budget=100.0,
)
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A strategy optimizer reads `BudgetConstraints` together with [Strategy Objective](/en/introduction/data-models/vocabularies/strategy-objective.md) to decide how much to allocate to a campaign, respecting `minimum_daily_budget`/`maximum_daily_budget` as hard bounds and `budget_usage_policy` as a spend-exhaustion rule. The [Campaign budget optimizer](/en/strategy-recommendation/campaign-budget-optimizer.md) in `modules/mta_strategy_recommendation` is that reader: it treats an absent minimum as zero and an absent maximum as unbounded, refuses a request whose minimum exceeds its maximum, and re-checks every returned allocation against both bounds before reporting it. This class declares the shape; it does not itself enforce it.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented and tested. Direct validation is covered by `BudgetConstraintsTests` in `modules/mta_common/tests/test_budget_and_delivery.py` (minimum-above-maximum rejection, negative-bound rejection, both usage policies constructible). The adapter path is covered by `test_maximum_daily_budget_is_always_none` in `BudgetOutputAdapterTests`, `modules/mta_common/tests/test_legacy_adapters.py`. Nothing in `script/`, `modules/mta_attribution`, `modules/mta_standard`, `modules/mta_strategy_recommendation`, or the dashboard currently constructs a `BudgetConstraints`; it is exercised only by its own test suite.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- `maximum_daily_budget` has no current data source; every adapted instance leaves it `None`.
- `budget_usage_policy` has no current data source either; every adapted instance requires the caller to choose one, which today means the choice is made by the caller of the adapter function rather than read from any campaign data.
- `CampaignEpisode` (see [Campaign Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md)) does not currently carry a `BudgetConstraints` field, so a future response model or optimizer consuming an episode would need that composition extended first.
