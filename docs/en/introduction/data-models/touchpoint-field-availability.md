---
title: Touchpoint Field Availability
description: Per-record realization of why placement, creative, and interaction_type are or are not populated on a Touchpoint
compact: "TouchpointFieldAvailability carries three FieldAvailability values, placement, creative, interaction_type, cross-validated against the matching Touchpoint fields. all_available() builds the common all-AVAILABLE case. No legacy source field; always constructed inline by legacy_adapters.py alongside the Touchpoint it describes."
lang: en-US
---

# Touchpoint Field Availability

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`TouchpointFieldAvailability` is the per-record companion to [Touchpoint](./touchpoint.md) that states, field by field, why `placement`, `creative`, and `interaction_type` are or are not populated. Where [Provider Capabilities](./provider-capabilities.md) states what a provider can ever report — a static ceiling — `TouchpointFieldAvailability` states what this specific touchpoint record actually reports, which must never exceed that ceiling. Splitting this out from `Touchpoint` itself keeps the three-way distinction between "not applicable to this ad format," "not provided by this data source," and "unknown" explicit and machine-readable, rather than folding all three into one legacy `UNSPECIFIED` sentinel.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/touchpoint.py`, in the same file as [Touchpoint](./touchpoint.md). Depends only on the [Field Availability](./field-availability.md) enum in `enums.py`. Every `Touchpoint` embeds exactly one `TouchpointFieldAvailability` in its `field_availability` field.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### placement

#### Type

[Field Availability](./field-availability.md).

#### Requiredness

Required.

#### Meaning

Why `Touchpoint.placement` is or is not populated on this record.

#### Missingness

Not applicable; every `TouchpointFieldAvailability` states a value for `placement`, even when that value is itself `NOT_PROVIDED`, `NOT_APPLICABLE`, `UNKNOWN`, or `REDACTED`.

#### Validation

Cross-validated against `Touchpoint.placement` by `Touchpoint.__post_init__`, not by `TouchpointFieldAvailability` itself: `Touchpoint.placement` must be `None` if and only if this field is not `AVAILABLE`. See [Touchpoint](./touchpoint.md)'s Invariants.

### creative

#### Type

[Field Availability](./field-availability.md).

#### Requiredness

Required.

#### Meaning

Why `Touchpoint.creative` is or is not populated on this record.

#### Missingness

Not applicable, same as `placement`.

#### Validation

Cross-validated against `Touchpoint.creative`, same mechanism as `placement`.

### interaction_type

#### Type

[Field Availability](./field-availability.md).

#### Requiredness

Required.

#### Meaning

Why `Touchpoint.interaction_type` is or is not populated on this record.

#### Missingness

Not applicable, same as `placement`.

#### Validation

Cross-validated against `Touchpoint.interaction_type`, same mechanism as `placement`.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- All three fields are always present; `TouchpointFieldAvailability` has no optional fields and no `__post_init__` of its own — it performs no validation independent of the `Touchpoint` that embeds it.
- The enforced relationship to the sibling `Touchpoint`'s optional string fields lives on `Touchpoint`, not here: see [Touchpoint](./touchpoint.md)'s Invariants for the exact consistency rule.
- `all_available()` is the only constructor helper defined on this class; it returns a `TouchpointFieldAvailability` with `placement=AVAILABLE`, `creative=AVAILABLE`, `interaction_type=AVAILABLE`, for the common case of a fully-populated touchpoint.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Field Availability

Each of the three fields is typed as [Field Availability](./field-availability.md), the shared five-state enum also used elsewhere in the canonical model.

### Relationship to Touchpoint

Embedded as `Touchpoint.field_availability`; every `Touchpoint` holds exactly one. See [Touchpoint](./touchpoint.md) for the field-by-field consistency rule this class's values are checked against.

### Relationship to Provider Capabilities

A [Provider Capabilities](./provider-capabilities.md) instance states the ceiling that a `TouchpointFieldAvailability` on a given provider's touchpoint should never exceed — for example, a provider whose `placement_availability` is `NOT_PROVIDED` should never produce a `Touchpoint` whose `field_availability.placement` is `AVAILABLE`. This ceiling is not currently enforced by any validation code; see Known Limitations.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None. No legacy data source has a field named or shaped like `TouchpointFieldAvailability`; it does not exist in either the five-segment AMC key or the four-segment MTA-SIM key formats.

### Canonical Conversion

`TouchpointFieldAvailability` has no standalone adapter function. It is always constructed inline, as a side effect, by the same `legacy_adapters.py` functions that construct the [Touchpoint](./touchpoint.md) it belongs to:

- `touchpoint_from_five_segment_key` builds it from the module-level `_optional_component(value)` helper applied to the key's placement and creative segments (`UNSPECIFIED` maps to `FieldAvailability.NOT_PROVIDED`, any other value maps to `FieldAvailability.AVAILABLE`), and always sets `interaction_type=FieldAvailability.AVAILABLE`, since the five-segment key requires that segment.
- `touchpoint_from_four_segment_key` applies the same `_optional_component` logic to placement and creative, and always sets `interaction_type=FieldAvailability.NOT_PROVIDED`, since the four-segment key carries no interaction-type segment at all.

### Information Loss

Because `_optional_component` only ever distinguishes `UNSPECIFIED` from present, every legacy-derived `TouchpointFieldAvailability` can only ever contain `AVAILABLE` or `NOT_PROVIDED` values. The other three states this enum supports — `NOT_APPLICABLE`, `UNKNOWN`, `REDACTED` — have no path to being produced from legacy data today; they are reachable only by constructing a `Touchpoint` directly in code that is not one of the two legacy adapter functions.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.touchpoint import TouchpointFieldAvailability
from modules.mta_common.src.enums import FieldAvailability

full = TouchpointFieldAvailability.all_available()
full.placement  # FieldAvailability.AVAILABLE

partial = TouchpointFieldAvailability(
    placement=FieldAvailability.NOT_PROVIDED,
    creative=FieldAvailability.NOT_APPLICABLE,
    interaction_type=FieldAvailability.AVAILABLE,
)
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future data-quality or coverage report would aggregate `TouchpointFieldAvailability` across a dataset to quantify how often each field is missing and why, informing whether a response model can rely on `placement` or `creative` as a feature for a given provider. No such report exists yet.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented and tested in `modules/mta_common/tests/test_touchpoint.py` (`FieldAvailabilityConsistencyTests`, covering `NOT_APPLICABLE` vs. `NOT_PROVIDED` distinguishability and value/availability consistency enforcement) and exercised indirectly by `modules/mta_common/tests/test_legacy_adapters.py`'s five- and four-segment key adaptation tests. See [Canonical Data Model](./index.md) for the full test count and command.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No code currently checks a `TouchpointFieldAvailability` against its provider's [Provider Capabilities](./provider-capabilities.md) ceiling; a caller could construct an inconsistent combination (for example, `AVAILABLE` for a field the provider's capabilities mark `NOT_PROVIDED`) without error.
- No legacy adapter path produces `NOT_APPLICABLE`, `UNKNOWN`, or `REDACTED`; those three states are only reachable through direct, non-adapter construction.
