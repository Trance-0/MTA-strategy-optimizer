---
title: Attribution Evidence
description: One touchpoint's historical attributed share of one outcome, for one model run, free of any optimization claim
compact: "AttributionEvidence: canonical, provider-independent record of one touchpoint's historical MTA attribution share and value for one outcome. Pure historical evidence — no marginal-return, causal-incrementality, optimal-budget, or contribution-profit field. Adapted from AttributionResult and StandardAttributionRow."
order: 10
lang: en-US
---

# Attribution Evidence

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`AttributionEvidence` is the canonical, provider-independent record of one [Multi-Touch Attribution (MTA)](/en/reference/definitions#mta-multi-touch-attribution) model's historical output: how much of one outcome one [touchpoint](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint.md) explains, for one reporting window. It exists to adapt today's two attribution-result shapes — `AttributionResult` in `modules/mta_attribution` and `StandardAttributionRow` in `modules/mta_standard` — into a single canonical type, without changing what either shape means.

This class is deliberately narrow. It carries an [Attribution Share](/en/reference/definitions#attribution-share) and an attributed absolute value, and nothing else that could be mistaken for a forward-looking claim. It has no field for marginal return, no field for causal incrementality, no field for an optimal budget, and no field for a product's contribution profit. It does not define `MTA_share * profit` or any other optimization target — that computation, if it is ever built, belongs to a future optimizer that reads `AttributionEvidence` as one input among several, not to this class. A dedicated test, `AttributionEvidenceScopeTests.test_no_field_carries_a_marginal_or_causal_optimization_claim` in `modules/mta_common/tests/test_outcome_and_attribution_evidence.py`, enforces this boundary by asserting no field name on the dataclass contains `marginal`, `incremental`, `causal`, `optimal_budget`, or `contribution_profit`.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/attribution_evidence.py`. Sits in the "historical evidence" layer of the [Canonical Data Model](/en/introduction/data-models/index.md): built from a [Touchpoint](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint.md) and a [Reporting Scope](/en/introduction/data-models/touchpoint-and-provider-contract/reporting-scope.md), and consumed, in the future, by [Campaign Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md) as one of the observed-after-treatment records a response model would read.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### model_id

#### Type

`str`

#### Requiredness

Required.

#### Meaning

Stable identifier of the producing attribution model, for example a Markov or Shapley model's name.

#### Missingness

Not applicable; `AttributionEvidence` has no missingness states of its own for this field, unlike [Touchpoint](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint.md)'s optional fields. A blank or whitespace-only value is rejected outright, not represented as a missing state.

#### Validation

`__post_init__` strips and rejects a blank value with `ValueError`.

### model_version

#### Type

`str`

#### Requiredness

Required.

#### Meaning

Version of `model_id`'s contract and behavior, so two runs of a changed model are distinguishable.

#### Missingness

Not applicable; rejected outright when blank.

#### Validation

`__post_init__` strips and rejects a blank value with `ValueError`.

### reporting_scope

#### Type

[`ReportingScope`](/en/introduction/data-models/touchpoint-and-provider-contract/reporting-scope.md)

#### Requiredness

Required.

#### Meaning

The account, market, currency, and date window the attribution ran over.

#### Missingness

Not applicable; `ReportingScope` is a required, non-optional field.

#### Validation

None beyond `ReportingScope`'s own `__post_init__`, which this class does not restate.

### touchpoint

#### Type

[`Touchpoint`](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint.md)

#### Requiredness

Required.

#### Meaning

The touchpoint this evidence describes.

#### Missingness

Not applicable; `Touchpoint` is a required, non-optional field.

#### Validation

None beyond `Touchpoint`'s own `__post_init__`, which this class does not restate.

### outcome

#### Type

`str`

#### Requiredness

Required.

#### Meaning

The outcome name this evidence's share and value are for, for example `converted_users`, `purchase_count`, or `revenue` — the [three Outcome types](/en/attribution/index.md#three-outcome-types) this project's attribution layer currently produces.

#### Missingness

Not applicable; rejected outright when blank.

#### Validation

`__post_init__` strips and rejects a blank value with `ValueError`.

### attribution_share

#### Type

`float`

#### Requiredness

Required.

#### Meaning

The proportion of `outcome` credited to `touchpoint` by `model_id`, in `[0, 1]`. See [Attribution Share](/en/reference/definitions#attribution-share).

#### Missingness

Not applicable; always populated when the record exists. This class does not carry an "attribution was not computed" state — a record simply would not exist for that touchpoint/outcome pair.

#### Validation

`__post_init__` rejects a value outside `[0, 1]` (with a `1e-9` floating-point tolerance above `1.0`) with `ValueError`.

### attributed_value

#### Type

`float`

#### Requiredness

Required.

#### Meaning

The absolute amount of `outcome` credited to `touchpoint` — for example, a dollar amount for `revenue`, or a count for `purchase_count`.

#### Missingness

Not applicable; always populated when the record exists.

#### Validation

`__post_init__` rejects a negative value with `ValueError`.

### valid

#### Type

`bool`

#### Requiredness

Optional, defaults to `True`.

#### Meaning

Whether the producing model considers this row usable, mirroring `StandardAttributionRow.valid` in `modules/mta_standard`.

#### Missingness

Not applicable; always `True` or `False`, never unset.

#### Validation

None; any boolean is accepted.

### warnings

#### Type

`tuple[str, ...]`

#### Requiredness

Optional, defaults to an empty tuple.

#### Meaning

Ordered, de-duplicated warning codes for the row, for example `ZERO_OUTCOME_TOTAL`, mirroring `StandardAttributionRow.warnings`.

#### Missingness

Not applicable; an empty tuple means no warnings, not an unknown state.

#### Validation

`__post_init__` rejects a `warnings` tuple containing a repeated code with `ValueError`.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `model_id`, `model_version`, and `outcome` are never blank.
- `attribution_share` is always within `[0, 1]` (with floating-point tolerance).
- `attributed_value` is never negative.
- `warnings` never contains a duplicate code.
- No field name contains `marginal`, `incremental`, `causal`, `optimal_budget`, or `contribution_profit` — enforced by a dedicated test, not just by convention, so a future edit that reintroduces one of these concepts on this class fails the test suite rather than silently passing review.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Touchpoint

Every `AttributionEvidence` describes exactly one [Touchpoint](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint.md), embedded by value rather than referenced by an identifier, so the evidence record is self-contained.

### Relationship to Reporting Scope

Every `AttributionEvidence` carries the [Reporting Scope](/en/introduction/data-models/touchpoint-and-provider-contract/reporting-scope.md) it was computed over, rather than inlining `marketplace`/`advertiser_id`/`currency`/window fields of its own.

### Relationship to Campaign Episode

A future [Campaign Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md) would compose one campaign's `AttributionEvidence` records among its observed-after-treatment fields, alongside [Budget Observation](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-observation.md), [Delivery Observation](/en/introduction/data-models/budget-delivery-and-outcome-observations/delivery-observation.md), and [Outcome Observation](/en/introduction/data-models/budget-delivery-and-outcome-observations/outcome-observation.md). This is not implemented for `AttributionEvidence` specifically yet — see Downstream Usage.

### Relationship to Attribution Model Documentation

The two shapes this class adapts, `AttributionResult` and `StandardAttributionRow`, are specified in [Attribution Model Overview](/en/attribution/index.md) and [Model Testing and Comparison](/en/attribution/model-testing.md). `AttributionEvidence` restates neither model's calculation; it only carries their already-computed output.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

Two existing shapes carry this information today, defined in `modules/mta_attribution/src/attribution_contract.py` and `modules/mta_standard/src/output_contract.py`:

- `AttributionResult`: one record per five-segment touchpoint, carrying all three outcomes at once — `converted_user_share`/`attributed_converted_users`, `purchase_count_share`/`attributed_purchase_count`, `revenue_share`/`attributed_revenue`.
- `StandardAttributionRow`: one record per touchpoint per outcome, carrying `model_id`, `model_version`, `report_start_date`, `report_end_date`, `marketplace`, `touchpoint` (a four-segment MTA-SIM key), `outcome`, `attribution_share`, `attributed_value`, `valid`, `warnings`.

### Canonical Conversion

`modules/mta_common/src/legacy_adapters.py` provides two adapters:

- `attribution_evidence_from_attribution_result(result, *, model_id, model_version, reporting_scope, provider=Provider.AMAZON_ADS)` fans out one `AttributionResult` into exactly three `AttributionEvidence` records — one for `converted_users`, one for `purchase_count`, one for `revenue`, in that order — since the canonical shape is one evidence row per outcome, matching `StandardAttributionRow`'s existing one-outcome-per-row shape. `model_id`, `model_version`, and `reporting_scope` are supplied by the caller because `AttributionResult` does not carry them. This exact three-record fan-out is verified by `AttributionResultFanOutTests.test_one_result_produces_exactly_three_evidence_records` in `modules/mta_common/tests/test_legacy_adapters.py`.
- `attribution_evidence_from_standard_row(row, *, reporting_scope, simulator_config=None, provider=Provider.AMAZON_ADS)` adapts one `StandardAttributionRow` directly. Because `StandardAttributionRow` carries no `advertiser_id` or `currency`, the caller-supplied `reporting_scope` cannot be derived from `row` alone; instead the adapter cross-validates `row.marketplace` and `row`'s report window against `reporting_scope` and raises `ValueError` on any mismatch, rather than fabricating or silently overwriting either side. `StandardRowCrossValidationTests.test_marketplace_mismatch_is_rejected` and `test_report_window_mismatch_is_rejected` in `modules/mta_common/tests/test_legacy_adapters.py` verify this rejection behavior directly.

Both adapters route `row.touchpoint`/`result.touchpoint` through `touchpoint_from_five_segment_key` or `touchpoint_from_four_segment_key` (see [Touchpoint](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint.md#legacy-mapping)) before constructing the `AttributionEvidence`.

### Information Loss

None identified for the fields this class carries: every field on `AttributionResult` and `StandardAttributionRow` relevant to attribution evidence has a corresponding canonical field. The loss, if any, is structural rather than field-level — `AttributionResult`'s single-record-per-touchpoint shape becomes three canonical records, which is a re-shaping, not a data loss, since every source value is preserved on one of the three.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

Constructing directly:

```python
from modules.mta_common.src.attribution_evidence import AttributionEvidence
from modules.mta_common.src.enums import Provider
from modules.mta_common.src.reporting_scope import ReportingScope
from modules.mta_common.src.touchpoint import Touchpoint, TouchpointFieldAvailability

evidence = AttributionEvidence(
    model_id="markov_official",
    model_version="1.0",
    reporting_scope=ReportingScope(
        marketplace="US",
        advertiser_id="ADV-1",
        currency="USD",
        report_start_date="2026-01-01",
        report_end_date="2026-01-31",
    ),
    touchpoint=Touchpoint(
        provider=Provider.AMAZON_ADS,
        ad_product="SPONSORED_PRODUCTS",
        format="SP",
        placement="TOP_OF_SEARCH",
        creative="VIDEO",
        interaction_type="CLICK",
        field_availability=TouchpointFieldAvailability.all_available(),
    ),
    outcome="revenue",
    attribution_share=0.3,
    attributed_value=100.0,
)
```

Adapting from an existing `AttributionResult`, fanning out to three records:

```python
from modules.mta_common.src.legacy_adapters import attribution_evidence_from_attribution_result

evidence_records = attribution_evidence_from_attribution_result(
    result,
    model_id="markov_official",
    model_version="1.0",
    reporting_scope=reporting_scope,
)
assert len(evidence_records) == 3
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future response-prediction model would read `AttributionEvidence` as one of several observed-after-treatment inputs composed into a [Campaign Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md). A future strategy optimizer would read `AttributionEvidence` alongside [Product Economics](/en/introduction/data-models/product-identity-and-economics/product-economics.md) and future incrementality evidence, but only through whatever composition a not-yet-built optimizer defines — `AttributionEvidence` itself never becomes an optimization target by growing a new field. Neither consumer is implemented yet.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented and tested. `AttributionEvidence`'s own validation is covered by `AttributionEvidenceScopeTests` in `modules/mta_common/tests/test_outcome_and_attribution_evidence.py`; both legacy adapters are covered by `AttributionResultFanOutTests` and `StandardRowCrossValidationTests` in `modules/mta_common/tests/test_legacy_adapters.py`. No current pipeline component calls either adapter outside these tests.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- Carries no confidence interval or reliability flag distinguishing a Markov `RELIABLE` share from an `UNRELIABLE` interval midpoint, the governance distinction described in [Attribution Model Overview](/en/attribution/index.md#dual-model-governance). A caller adapting a governed recommendation into `AttributionEvidence` would need to decide how to represent that distinction; this class does not decide it.
- `outcome` is a free-form `str`, not one of the enums this module otherwise uses, matching both source shapes' existing string-typed `outcome` fields rather than introducing a new closed vocabulary this session.
