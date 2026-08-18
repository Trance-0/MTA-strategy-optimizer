---
title: Outcome Observation
description: Total, organic, and incremental outcomes for one Touchpoint, kept distinct
compact: "OutcomeObservation (modules/mta_common/src/outcome.py): touchpoint, reporting_scope, total_units, total_revenue, plus organic-baseline and incremental fields left None until a real incrementality-estimation source exists. Never fabricates incremental from total-observed data."
lang: en-US
---

# Outcome Observation

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`OutcomeObservation` keeps three distinct claims about a [Touchpoint](./touchpoint.md)'s outcomes apart, rather than collapsing them into one number: total-observed outcomes (`total_units`, `total_revenue`, encompassing both organic and ad-driven demand), organic-baseline outcomes (`expected_organic_units`, `expected_organic_revenue`, what would have happened without advertising), and incremental-attributable outcomes (`incremental_units`, `incremental_revenue`, what advertising actually caused, plus `incrementality_evidence_source` recording how that figure was produced). Today's pipeline reports only total-observed values — `converted_users`, `purchase_count`, `revenue` in the path report, `purchases`/`sales` in the Ads report — and nothing in it separates organic from incremental demand; `docs/en/market-simulation/index.md` explicitly isolates `simulation_ground_truth`, the only place such a split is known, as evaluation-only. `OutcomeObservation` therefore leaves every organic and incremental field `None` until a real incrementality-estimation source exists, and must never be used to fabricate an incremental figure from total-observed data.

This is the profit-relevant class in the canonical model: a future strategy optimizer's profit objective would need `incremental_units` — not `total_units` — multiplied by [Product Economics](./product-economics.md)'s `unit_contribution_margin` and compared against observed cost, since crediting advertising with organic demand it did not cause would overstate its profitability. No incrementality-estimation source or optimizer exists yet; this class only reserves the shape that objective would read.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/outcome.py`, in the Budget, Delivery, and Outcome Observations layer of the [Canonical Data Model](./index.md). It depends on [Touchpoint](./touchpoint.md) and [Reporting Scope](./reporting-scope.md).

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### touchpoint

#### Type

[`Touchpoint`](./touchpoint.md)

#### Requiredness

Required, no default.

#### Meaning

The observed touchpoint this outcome was recorded against.

#### Missingness

Not applicable; the field has no `None` state.

#### Validation

Delegated to `Touchpoint`'s own construction rules.

### reporting_scope

#### Type

[`ReportingScope`](./reporting-scope.md)

#### Requiredness

Required, no default.

#### Meaning

The marketplace, advertiser, currency, and date range this observation covers.

#### Missingness

Not applicable; the field has no `None` state.

#### Validation

Delegated to `ReportingScope`'s own validation.

### total_units

#### Type

`int | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

Total observed unit count for this touchpoint, encompassing both organic and ad-driven demand. Not itself a claim of ad-causation.

#### Missingness

`None` means total units are not known or not provided for this observation, not that zero units were observed.

#### Validation

Rejected when negative, when present.

### total_revenue

#### Type

`float | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

Total observed revenue for this touchpoint, on the same total-observed basis as `total_units`.

#### Missingness

`None` means total revenue is not known or not provided, not that zero revenue was observed.

#### Validation

Rejected when negative, when present.

### expected_organic_units

#### Type

`float | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

Estimated units that would have occurred without advertising. `None` until a real estimation source is wired in; never derived here from `total_units`.

#### Missingness

`None` means no organic-baseline estimate is available for this observation. No current adapter populates it.

#### Validation

No constraint beyond field type; `OutcomeObservation.__post_init__` does not reject a negative value on this field.

### expected_organic_revenue

#### Type

`float | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

Estimated revenue that would have occurred without advertising. Same rule as `expected_organic_units`: never derived from `total_revenue`.

#### Missingness

`None` means no organic-baseline estimate is available. No current adapter populates it.

#### Validation

No constraint beyond field type.

### incremental_units

#### Type

`float | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

`total_units` attributable to advertising. `None` until a real estimation source is wired in; never assumed equal to `total_units`.

#### Missingness

`None` means no incrementality estimate is available for this observation. No current adapter populates it.

#### Validation

No constraint beyond field type. If populated (together with or in place of `incremental_revenue`), `incrementality_evidence_source` becomes required — see Invariants.

### incremental_revenue

#### Type

`float | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

`total_revenue` attributable to advertising. Same rule as `incremental_units`.

#### Missingness

`None` means no incrementality estimate is available. No current adapter populates it.

#### Validation

Same evidence-source requirement as `incremental_units` — see Invariants.

### incrementality_evidence_source

#### Type

`str | None`

#### Requiredness

Optional, defaults to `None`; required whenever either incremental field is populated.

#### Meaning

Free-text description of what produced the incremental figures, so a reader can judge the evidence behind an incremental claim rather than trusting an unexplained number.

#### Missingness

`None` means no incremental figures have been claimed for this observation, and is only valid in that case.

#### Validation

Rejected as missing (raises `ValueError`) when either `incremental_units` or `incremental_revenue` is not `None` and this field is falsy.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `total_units` is never negative, when present.
- `total_revenue` is never negative, when present.
- `incrementality_evidence_source` is required whenever `incremental_units` or `incremental_revenue` is populated — covered by the dedicated tests `test_incremental_units_without_evidence_source_is_rejected` and `test_incremental_units_with_evidence_source_is_valid` in `modules/mta_common/tests/test_outcome_and_attribution_evidence.py`.
- A total-only observation (only `total_units`/`total_revenue` populated, every organic and incremental field `None`) is explicitly valid — covered by `test_total_only_observation_is_valid_and_leaves_incremental_none`.
- `expected_organic_units`, `expected_organic_revenue`, `incremental_units`, and `incremental_revenue` are not constrained relative to `total_units`/`total_revenue` or to each other by `__post_init__`; nothing in this class enforces, for example, that `incremental_units` does not exceed `total_units`.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Touchpoint

Every `OutcomeObservation` carries exactly one [Touchpoint](./touchpoint.md).

### Relationship to Reporting Scope

Every `OutcomeObservation` is bounded by exactly one [Reporting Scope](./reporting-scope.md).

### Relationship to Delivery Observation

`OutcomeObservation` and [Delivery Observation](./delivery-observation.md) both adapt from the same legacy `TouchpointSpend` row and share its `Touchpoint`/`ReportingScope` pair, so the two can be joined. When both are adapted from the same row, `OutcomeObservation.total_units`/`total_revenue` and `DeliveryObservation.reported_purchases`/`reported_sales` are sourced from the same underlying values, but `OutcomeObservation` additionally reserves the organic-baseline and incremental fields that `DeliveryObservation` does not have.

### Relationship to Attribution Evidence

`AttributionEvidence` references the same `Touchpoint`/`ReportingScope` pair as `OutcomeObservation`, so a touchpoint's attributed share and its outcome can be joined. `AttributionEvidence` itself carries no marginal-return, causal-incrementality, optimal-budget, or product-contribution-profit field; a future incrementality source populating `OutcomeObservation.incremental_units`/`incremental_revenue` is the intended path to that figure, not `AttributionEvidence`.

### Relationship to Product Economics

A future profit objective would multiply `incremental_units` by [Product Economics](./product-economics.md)'s `unit_contribution_margin` (itself governed by [Margin Source](./margin-source.md)) and net out observed advertising cost, for example [Delivery Observation](./delivery-observation.md)'s `cost` or [Budget Observation](./budget-observation.md)'s `actual_spend`, to estimate profit rather than revenue. This class supplies only the `incremental_units`/`incremental_revenue` half of that calculation, and only once a real incrementality-estimation source populates it.

### Relationship to Evaluation Ground Truth

The organic/incremental split this class reserves is the same kind of information `docs/en/market-simulation/index.md`'s `simulation_ground_truth` already isolates as evaluation-only. A future [Evaluation Ground Truth](./evaluation-ground-truth.md) record, not `OutcomeObservation` itself, is where a simulator's true organic/incremental split would live for evaluation purposes, kept structurally separate from any model-facing record.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

`TouchpointSpend` (`modules/mta_attribution/src/attribution_contract.py`): `touchpoint` (a five-segment string key), `reported_purchases`, `reported_sales`, as produced by `aggregate_spend_by_touchpoint`. No field on `TouchpointSpend`, or anywhere else in the current pipeline, separates organic from ad-driven demand.

### Canonical Conversion

`legacy_adapters.outcome_observation_from_touchpoint_spend(spend, *, reporting_scope, provider=Provider.AMAZON_ADS)` parses `spend.touchpoint`'s five-segment key into a canonical `Touchpoint` via `touchpoint_from_five_segment_key`, then builds an `OutcomeObservation` with `total_units` set from `spend.reported_purchases` and `total_revenue` set from `spend.reported_sales`. Every organic-baseline and incremental field is left at its `None` default; the function accepts no parameters for them.

### Information Loss

`total_units`/`total_revenue` carry through exactly from `reported_purchases`/`reported_sales`, verified by the dedicated test `test_total_units_and_revenue_come_from_reported_purchases_and_sales` in `OutcomeObservationFromSpendTests`, `modules/mta_common/tests/test_legacy_adapters.py`. The organic-baseline and incremental fields are not lost so much as never available from this source — `TouchpointSpend` carries no field to adapt them from — verified by the companion test `test_organic_and_incremental_fields_are_left_none`.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

Adapting an existing spend row, leaving every organic/incremental field `None`:

```python
from modules.mta_attribution.src.attribution_contract import TouchpointSpend
from modules.mta_common.src.legacy_adapters import outcome_observation_from_touchpoint_spend
from modules.mta_common.src.reporting_scope import ReportingScope

spend = TouchpointSpend(
    touchpoint="SPONSORED_PRODUCTS:SP:TOP_OF_SEARCH:VIDEO:CLICK",
    impressions=0,
    clicks=120,
    cost=45.5,
    reported_purchases=3,
    reported_sales=90.0,
)
observation = outcome_observation_from_touchpoint_spend(
    spend,
    reporting_scope=ReportingScope(
        marketplace="US",
        advertiser_id="ADV-1",
        currency="USD",
        report_start_date="2026-01-01",
        report_end_date="2026-01-31",
    ),
)
# observation.total_units == 3, observation.total_revenue == 90.0
# observation.incremental_units is None: no current source estimates it
```

Constructing one directly with an incremental claim, illustrating the evidence-source requirement — this construction is valid and tested today; only a real incrementality-estimation source to produce these numbers from observed data does not exist yet:

```python
from modules.mta_common.src.outcome import OutcomeObservation

OutcomeObservation(
    touchpoint=touchpoint,
    reporting_scope=reporting_scope,
    total_units=3,
    total_revenue=90.0,
    incremental_units=1.8,
    incremental_revenue=54.0,
    incrementality_evidence_source="holdout-test-2026-01",  # required once incremental_* is given
)
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future incrementality-estimation source (for example a geo holdout test or a causal model) would populate `expected_organic_units`/`expected_organic_revenue` and `incremental_units`/`incremental_revenue`, recording its method in `incrementality_evidence_source`. A future strategy optimizer's profit objective — conceptually `sum(incremental_units * unit_contribution_margin) - observed advertising cost` — would then read `incremental_units` rather than `total_units`, so that advertising is credited only with the demand it caused, not with organic demand it happened to precede. Neither the incrementality source nor the optimizer exists yet.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented and tested. Direct validation, including the evidence-source requirement and the total-only-is-valid case, is covered by `OutcomeObservationTests` in `modules/mta_common/tests/test_outcome_and_attribution_evidence.py` (`test_total_only_observation_is_valid_and_leaves_incremental_none`, `test_incremental_units_without_evidence_source_is_rejected`, `test_incremental_units_with_evidence_source_is_valid`, `test_negative_total_units_is_rejected`). The adapter path is covered by `OutcomeObservationFromSpendTests` in `modules/mta_common/tests/test_legacy_adapters.py`. Nothing outside `modules/mta_common`'s own test suite currently constructs an `OutcomeObservation`.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No incrementality-estimation source exists; every adapted instance leaves `expected_organic_units`, `expected_organic_revenue`, `incremental_units`, `incremental_revenue`, and `incrementality_evidence_source` at their `None` defaults.
- `expected_organic_units`, `expected_organic_revenue`, `incremental_units`, and `incremental_revenue` have no negativity or cross-field consistency check in `__post_init__`, unlike `total_units`/`total_revenue`; a future incrementality source populating these fields is responsible for their internal consistency (for example, that incremental does not exceed total) since this class does not enforce it.
- `total_units`/`total_revenue` on this class and `reported_purchases`/`reported_sales` on [Delivery Observation](./delivery-observation.md) currently duplicate the same underlying legacy values when both are adapted from the same `TouchpointSpend` row; there is no cross-class check enforcing that duplication stays consistent if the two are constructed independently.
