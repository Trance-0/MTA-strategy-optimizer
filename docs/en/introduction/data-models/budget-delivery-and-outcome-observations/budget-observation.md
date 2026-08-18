---
title: Budget Observation
description: What was actually configured and spent for one campaign over a reporting window
compact: "BudgetObservation (modules/mta_common/src/budget.py): campaign_id, reporting_scope, configured_budget, actual_spend, plus five fields reserved for a future intervention study. actual_spend < configured_budget is valid under-spend. No adapter populates actual_spend."
order: 20
lang: en-US
---

# Budget Observation

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`BudgetObservation` records what was actually configured and spent for one campaign over a reporting window: the backward-looking counterpart to [Budget Constraints](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-constraints.md)'s forward-looking bounds. It deliberately keeps `configured_budget` (what was authorized) and `actual_spend` (what was consumed) as two independent fields rather than collapsing them, because under-spend — `actual_spend` less than `configured_budget` — is a normal, valid outcome, not an error condition to be flagged or corrected. Five additional fields are reserved, unpopulated by any current data source, for a future study of budget interventions (their causal effect when a budget is deliberately changed).

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/budget.py`, in the Budget, Delivery, and Outcome Observations layer of the [Canonical Data Model](/en/introduction/data-models/index.md). It depends on [Reporting Scope](/en/introduction/data-models/touchpoint-and-provider-contract/reporting-scope.md) to bound the observation window, and on [Assignment Type](/en/introduction/data-models/vocabularies/assignment-type.md) for its reserved intervention-study fields.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### campaign_id

#### Type

`str`

#### Requiredness

Required, no default.

#### Meaning

The observed [Campaign](/en/introduction/data-models/campaign-identity/campaign.md)'s `campaign_id`.

#### Missingness

Not applicable; the field has no `None` state.

#### Validation

Rejected when blank or all-whitespace.

### reporting_scope

#### Type

[`ReportingScope`](/en/introduction/data-models/touchpoint-and-provider-contract/reporting-scope.md)

#### Requiredness

Required, no default.

#### Meaning

The marketplace, advertiser, currency, and date range this observation covers, and optionally the campaign group it is scoped to.

#### Missingness

Not applicable; the field has no `None` state, since `ReportingScope` itself carries its own optionality for `campaign_group_id`.

#### Validation

Delegated to `ReportingScope`'s own validation (`marketplace`, `advertiser_id`, and `currency` non-blank; `report_end_date` not before `report_start_date`).

### configured_budget

#### Type

`float`

#### Requiredness

Required, no default.

#### Meaning

The budget that was actually authorized for this campaign over this reporting window — what was configured, independent of what was spent.

#### Missingness

Not applicable; the field has no `None` state.

#### Validation

Rejected when negative.

### actual_spend

#### Type

`float | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

What was actually spent against `configured_budget` over this reporting window. Deliberately independent of `configured_budget`: `actual_spend` less than `configured_budget` is valid and expected under-spend, not an inconsistency. No current adapter populates this field — see Legacy Mapping.

#### Missingness

`None` means actual spend is not known or not provided for this observation, not that zero was spent.

#### Validation

Rejected when negative. No constraint relates it to `configured_budget`: neither exceeding nor falling short of the configured amount is rejected.

### intervention_id

#### Type

`str | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

Reserved for a future budget-intervention study: an identifier for a deliberate, tracked budget change applied to this campaign.

#### Missingness

`None` means either no intervention applies to this observation, or the field is simply not yet populated by any current source. No current adapter populates it.

#### Validation

No constraint beyond field type.

### baseline_budget

#### Type

`float | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

Reserved for a future intervention study: the budget that would have applied absent the intervention, enabling a before/after or treatment/control comparison against `configured_budget`.

#### Missingness

`None` means no baseline is recorded for this observation. No current adapter populates it.

#### Validation

Rejected when negative, when present.

### budget_delta

#### Type

`float | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

Reserved for a future intervention study: the signed change applied to the budget, typically `configured_budget` minus `baseline_budget`.

#### Missingness

`None` means no delta is recorded. No current adapter populates it.

#### Validation

No constraint beyond field type; may be negative (a budget decrease) or positive (an increase).

### assignment_type

#### Type

[`AssignmentType | None`](/en/introduction/data-models/vocabularies/assignment-type.md)

#### Requiredness

Optional, defaults to `None`.

#### Meaning

Reserved for a future intervention study: how this campaign's intervention (if any) was assigned — `RANDOMIZED`, `RULE_BASED`, `MANUAL`, or `UNKNOWN`.

#### Missingness

`None` means no assignment mechanism is recorded. No current adapter populates it.

#### Validation

Must be an `AssignmentType` member, when present.

### randomized

#### Type

`bool | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

Reserved for a future intervention study: whether this specific observation's intervention was randomized, as a convenience flag alongside the more granular `assignment_type`.

#### Missingness

`None` means randomization status is not recorded, not that randomization is known to be false.

#### Validation

No constraint beyond field type.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `campaign_id` is never blank.
- `configured_budget` is never negative.
- `actual_spend` is never negative, when present.
- `actual_spend` below `configured_budget` is explicitly valid, covered by the dedicated test `test_actual_spend_below_configured_budget_is_valid`; `actual_spend` equal to `configured_budget` is likewise valid (`test_actual_spend_equal_to_configured_budget_is_valid`), both in `modules/mta_common/tests/test_budget_and_delivery.py`.
- `baseline_budget` is never negative, when present.
- The five intervention-study fields (`intervention_id`, `baseline_budget`, `budget_delta`, `assignment_type`, `randomized`) default to `None` and are unconstrained relative to one another; `BudgetObservation` does not require them to be populated together.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Campaign

`campaign_id` references [Campaign](/en/introduction/data-models/campaign-identity/campaign.md).`campaign_id` by value, matching the pattern used by [Budget Constraints](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-constraints.md).

### Relationship to Reporting Scope

Every `BudgetObservation` is bounded by exactly one [Reporting Scope](/en/introduction/data-models/touchpoint-and-provider-contract/reporting-scope.md), which supplies the date range the `configured_budget`/`actual_spend` pair applies to.

### Relationship to Budget Constraints

[Budget Constraints](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-constraints.md) declares what is allowed going forward; `BudgetObservation` records what actually happened. A future optimizer would compare a campaign's `BudgetObservation` history against its `BudgetConstraints` to evaluate past decisions before making a new one.

### Relationship to Assignment Type

`assignment_type` reuses [Assignment Type](/en/introduction/data-models/vocabularies/assignment-type.md), the same enum used to describe how a treatment was assigned in a controlled study; here it is scoped specifically to budget interventions.

### Relationship to Campaign Episode

A future [Campaign Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md) would carry a campaign's `BudgetObservation` history as part of its trajectory, alongside its [Delivery Observation](/en/introduction/data-models/budget-delivery-and-outcome-observations/delivery-observation.md) and [Outcome Observation](/en/introduction/data-models/budget-delivery-and-outcome-observations/outcome-observation.md) history.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

`modules/mta_strategy_recommendation`'s campaign output, specifically `campaign_id` and `initial_daily_budget`, plus a caller-supplied `reporting_scope` (the legacy schema carries no reporting window of its own for a campaign output entry).

### Canonical Conversion

`legacy_adapters.budget_observation_from_campaign_output(campaign_output, *, reporting_scope)` reads `campaign_id` from the campaign output and `initial_daily_budget` into `configured_budget`. `reporting_scope` is a required keyword argument, since no legacy field supplies it. `actual_spend` and all five intervention-study fields are left at their `None` defaults; the function does not accept parameters for them.

### Information Loss

`configured_budget` and `campaign_id` carry through exactly, sourced from `initial_daily_budget`. `actual_spend` is not lost so much as never available from this source in the first place — `initial_budget_recommendation.json` is a pre-spend planning artifact, not a post-spend report, so it has no field representing actual spend to adapt from. This is verified by the dedicated test `test_actual_spend_is_always_none` in `modules/mta_common/tests/test_legacy_adapters.py`. The five intervention-study fields have no legacy representation at all in any current schema.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

Adapting an existing campaign output, with `actual_spend` necessarily absent:

```python
from modules.mta_common.src.legacy_adapters import budget_observation_from_campaign_output
from modules.mta_common.src.reporting_scope import ReportingScope

campaign_output = {"campaign_id": "CAMP-1", "initial_daily_budget": 50.0}
observation = budget_observation_from_campaign_output(
    campaign_output,
    reporting_scope=ReportingScope(
        marketplace="US",
        advertiser_id="ADV-1",
        currency="USD",
        report_start_date="2026-01-01",
        report_end_date="2026-01-31",
    ),
)
# observation.actual_spend is None: no current source reports actual spend
```

Constructing one directly, illustrating valid under-spend:

```python
from modules.mta_common.src.budget import BudgetObservation
from modules.mta_common.src.reporting_scope import ReportingScope

BudgetObservation(
    campaign_id="CAMP-1",
    reporting_scope=ReportingScope(
        marketplace="US",
        advertiser_id="ADV-1",
        currency="USD",
        report_start_date="2026-01-01",
        report_end_date="2026-01-31",
    ),
    configured_budget=50.0,
    actual_spend=32.5,  # under-spend, not an error
)
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future strategy optimizer would compare `actual_spend` against `configured_budget` across a campaign's `BudgetObservation` history to judge whether past allocations were well-used before recommending a new one. A future intervention study would populate and read the five reserved fields (`intervention_id`, `baseline_budget`, `budget_delta`, `assignment_type`, `randomized`) to estimate the causal effect of deliberate budget changes. Neither the optimizer nor the intervention-study analysis exists yet.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented and tested. Direct validation and the under-spend/equal-spend cases are covered by `BudgetObservationSpendVsConfiguredTests` in `modules/mta_common/tests/test_budget_and_delivery.py`, including `test_reserved_intervention_fields_default_unpopulated`. The adapter path is covered by `test_actual_spend_is_always_none` in `BudgetOutputAdapterTests`, `modules/mta_common/tests/test_legacy_adapters.py`. Nothing outside `modules/mta_common`'s own test suite currently constructs a `BudgetObservation`.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- `actual_spend` has no current data source; every adapted instance leaves it `None`. Populating it would require a post-spend reporting feed that `modules/mta_strategy_recommendation`'s pre-spend planning artifacts do not provide.
- The five intervention-study fields (`intervention_id`, `baseline_budget`, `budget_delta`, `assignment_type`, `randomized`) have no current data source at all; they exist to reserve the shape for a future study, not to represent data available today.
- `CampaignEpisode` (see [Campaign Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md)) does not currently carry a `BudgetObservation` history field, so a future trajectory-level consumer would need that composition extended first.
