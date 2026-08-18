---
title: Delivery Observation
description: Impressions, clicks, cost, and reported purchases/sales observed for one Touchpoint
compact: "DeliveryObservation (modules/mta_common/src/delivery.py): touchpoint, reporting_scope, cost, reported_purchases, reported_sales, plus optional impressions/clicks left None (not zero) when not applicable to the touchpoint's billing interaction type."
lang: en-US
---

# Delivery Observation

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`DeliveryObservation` records the impressions, clicks, cost, and platform-reported purchases/sales observed for one [Touchpoint](./touchpoint.md) over one [Reporting Scope](./reporting-scope.md). It corresponds to today's `TouchpointSpend` (`modules/mta_attribution/src/attribution_contract.py`), keeping the same underlying fields but attaching a canonical `Touchpoint` and `ReportingScope` instead of a bare five-segment touchpoint-key string, and — its one behavioral departure from the legacy shape — leaving whichever of `impressions`/`clicks` does not apply to the touchpoint's billing interaction type as `None` rather than the implicit `0` the legacy contract stores for it.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/delivery.py`, in the Budget, Delivery, and Outcome Observations layer of the [Canonical Data Model](./index.md). It depends on [Touchpoint](./touchpoint.md) and [Reporting Scope](./reporting-scope.md).

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### touchpoint

#### Type

[`Touchpoint`](./touchpoint.md)

#### Requiredness

Required, no default.

#### Meaning

The observed touchpoint this delivery was recorded against.

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

### cost

#### Type

`float`

#### Requiredness

Required, no default.

#### Meaning

Observed spend attributed to this touchpoint.

#### Missingness

Not applicable; the field has no `None` state.

#### Validation

Rejected when negative.

### reported_purchases

#### Type

`int`

#### Requiredness

Required, no default.

#### Meaning

Platform-reported purchase count, mirroring `TouchpointSpend.reported_purchases`.

#### Missingness

Not applicable; the field has no `None` state. A touchpoint with no reported purchases carries `0`, not `None`, matching the legacy shape's own representation of this field.

#### Validation

Rejected when negative.

### reported_sales

#### Type

`float`

#### Requiredness

Required, no default.

#### Meaning

Platform-reported sales value, mirroring `TouchpointSpend.reported_sales`.

#### Missingness

Not applicable; the field has no `None` state, following the same zero-versus-absent convention as `reported_purchases`.

#### Validation

Rejected when negative.

### impressions

#### Type

`int | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

Observed impression count, populated only when `touchpoint.interaction_type` is `"IMPRESSION"`.

#### Missingness

`None` means impressions do not apply to this touchpoint's billing interaction type — for example a `CLICK`-billed touchpoint — not that zero impressions were observed. This is a deliberate departure from the legacy `TouchpointSpend.impressions`, a non-optional `int` that defaults to `0` for a non-matching interaction type; `DeliveryObservation` does not carry that legacy `0` through, since "zero observed" and "not applicable" are different claims.

#### Validation

Rejected when negative, when present.

### clicks

#### Type

`int | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

Observed click count, populated only when `touchpoint.interaction_type` is `"CLICK"`.

#### Missingness

`None` means clicks do not apply to this touchpoint's billing interaction type — for example an `IMPRESSION`-billed touchpoint — not that zero clicks were observed. Same legacy-`0`-versus-canonical-`None` departure as `impressions`.

#### Validation

Rejected when negative, when present.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `cost`, `reported_purchases`, and `reported_sales` are never negative.
- `impressions` and `clicks` are never negative, when present.
- `impressions` and `clicks` are mutually exclusive by construction whenever `DeliveryObservation` is built through `legacy_adapters.delivery_observation_from_touchpoint_spend`: exactly one is populated, matching the touchpoint's `interaction_type`, and the other is `None`. `DeliveryObservation.__post_init__` itself does not forbid both being populated on a directly constructed instance; the mutual exclusivity is a property of the adapter, not a dataclass-level constraint, since a future non-Amazon-Ads provider might bill on both metrics at once.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Touchpoint

Every `DeliveryObservation` carries exactly one [Touchpoint](./touchpoint.md), whose `interaction_type` determines which of `impressions`/`clicks` is applicable.

### Relationship to Reporting Scope

Every `DeliveryObservation` is bounded by exactly one [Reporting Scope](./reporting-scope.md).

### Relationship to Outcome Observation

`DeliveryObservation` and [Outcome Observation](./outcome-observation.md) both adapt from the same legacy `TouchpointSpend` row and both share its `Touchpoint`/`ReportingScope` pair, so the two can be joined on that pair. `DeliveryObservation.reported_purchases`/`reported_sales` and `OutcomeObservation.total_units`/`total_revenue` are sourced from the same underlying `TouchpointSpend.reported_purchases`/`reported_sales` values when both are adapted from the same row, but the two classes exist for different purposes: `DeliveryObservation` mirrors the legacy delivery report shape field-for-field, while `OutcomeObservation` additionally reserves the organic-baseline and incremental fields that `DeliveryObservation` does not have.

### Relationship to Attribution Evidence

`AttributionEvidence` references the same `Touchpoint`/`ReportingScope` pair as `DeliveryObservation`, so a touchpoint's delivery, its outcome, and its attribution share can all be joined together.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

`TouchpointSpend` (`modules/mta_attribution/src/attribution_contract.py`): `touchpoint` (a five-segment string key), `impressions`, `clicks`, `cost`, `reported_purchases`, `reported_sales`, as produced by `aggregate_spend_by_touchpoint`. That function already enforces impressions/clicks mutual exclusivity by `interaction_type` at aggregation time, raising `ValueError` on a conflicting row, so the non-matching metric on a `TouchpointSpend` row is always `0`, never a real value.

### Canonical Conversion

`legacy_adapters.delivery_observation_from_touchpoint_spend(spend, *, reporting_scope, provider=Provider.AMAZON_ADS)` parses `spend.touchpoint`'s five-segment key into a canonical `Touchpoint` via `touchpoint_from_five_segment_key`, then builds a `DeliveryObservation` with `cost`, `reported_purchases`, and `reported_sales` carried through unchanged, and `impressions`/`clicks` each set to the corresponding `spend` value only when `touchpoint.interaction_type` matches (`"IMPRESSION"` or `"CLICK"` respectively) — otherwise `None`.

### Information Loss

`cost`, `reported_purchases`, and `reported_sales` carry through exactly. `impressions`/`clicks` are not lost so much as reclassified: the legacy `0` placeholder for the non-applicable metric becomes canonical `None`, verified by the dedicated tests `test_click_touchpoint_leaves_impressions_none` and `test_impression_touchpoint_leaves_clicks_none` in `DeliveryObservationFromSpendTests`, `modules/mta_common/tests/test_legacy_adapters.py`.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

Adapting a click-billed touchpoint, where `impressions` becomes `None` rather than the legacy `0`:

```python
from modules.mta_attribution.src.attribution_contract import TouchpointSpend
from modules.mta_common.src.legacy_adapters import delivery_observation_from_touchpoint_spend
from modules.mta_common.src.reporting_scope import ReportingScope

spend = TouchpointSpend(
    touchpoint="SPONSORED_PRODUCTS:SP:TOP_OF_SEARCH:VIDEO:CLICK",
    impressions=0,
    clicks=120,
    cost=45.5,
    reported_purchases=3,
    reported_sales=90.0,
)
observation = delivery_observation_from_touchpoint_spend(
    spend,
    reporting_scope=ReportingScope(
        marketplace="US",
        advertiser_id="ADV-1",
        currency="USD",
        report_start_date="2026-01-01",
        report_end_date="2026-01-31",
    ),
)
# observation.impressions is None; observation.clicks == 120
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future [Cost Per Click (CPC)](/en/reference/definitions#cpc-cost-per-click) or [Cost Per Mille (CPM)](/en/reference/definitions#cpm-cost-per-mille--cost-per-thousand-impressions) efficiency calculation would divide `cost` by whichever of `clicks`/`impressions` is populated, reading `None` as "not this touchpoint's billing metric" rather than treating it as zero and producing a misleadingly infinite or undefined rate. No such downstream calculation is implemented against this class yet.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented and tested. Direct construction and validation are exercised by the dataclass's own `__post_init__` (no dedicated direct-construction test class beyond the adapter tests). The adapter path is covered by `DeliveryObservationFromSpendTests` in `modules/mta_common/tests/test_legacy_adapters.py`. Nothing outside `modules/mta_common`'s own test suite currently constructs a `DeliveryObservation`.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- The mutual exclusivity of `impressions`/`clicks` is enforced only by the adapter's logic and, upstream of that, by `aggregate_spend_by_touchpoint`'s own `ValueError` on conflicting rows — not by `DeliveryObservation.__post_init__` itself. A directly constructed instance with both fields populated is not rejected by this class.
- `reported_purchases`/`reported_sales` on this class and `total_units`/`total_revenue` on [Outcome Observation](./outcome-observation.md) currently duplicate the same underlying legacy values when both are adapted from the same `TouchpointSpend` row; there is no cross-class check enforcing that duplication stays consistent if the two are constructed independently.
