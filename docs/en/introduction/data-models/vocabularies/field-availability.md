---
title: Field Availability
description: The five explicit, distinguishable reasons a canonical field may not carry a value
compact: "FieldAvailability StrEnum (AVAILABLE, NOT_APPLICABLE, NOT_PROVIDED, UNKNOWN, REDACTED) in modules/mta_common/src/enums.py, backing TouchpointFieldAvailability and ProviderCapabilities. Replaces the five-segment key's single UNSPECIFIED sentinel, which legacy_adapters.py can only ever map to NOT_PROVIDED."
order: 20
lang: en-US
---

# Field Availability

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`FieldAvailability` replaces silent none-means-missing collapsing with five explicit, distinguishable states. The current five-segment touchpoint key represents every unavailable `placement` or `creative` component with one sentinel, `UNSPECIFIED`, which conflates at least four different real-world facts: the concept does not apply to this ad product, the source system simply did not report it, it is genuinely unknown, or it was withheld. `FieldAvailability` gives each of those facts its own name, so a canonical record can state which one actually happened rather than losing the distinction the moment a field is missing.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/enums.py`, the vocabulary layer. Depended on by [Touchpoint Field Availability](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint-field-availability.md) and [Provider Capabilities](/en/introduction/data-models/touchpoint-and-provider-contract/provider-capabilities.md); has no dependency of its own beyond the Python standard library.

## Members <span class="status-label status-verified" aria-label="Verified"></span>

### AVAILABLE

#### Meaning

The field carries a real observed or provided value. On a `Touchpoint`, this is the only state under which the corresponding value field (`placement`, `creative`, or `interaction_type`) is non-`None`; every other state requires that value field to be `None`.

### NOT_APPLICABLE

#### Meaning

The concept the field represents does not exist for this record — for example, `interaction_type` on a provider whose ad products are not billed per impression or click at all, so there is no interaction type to report, missing or otherwise.

### NOT_PROVIDED

#### Meaning

The source system could in principle supply the field, but this specific extract, report, or provider integration does not include it. This is the state the legacy `UNSPECIFIED` sentinel collapses to when adapted into the canonical model — see Legacy Mapping.

### UNKNOWN

#### Meaning

It is not known whether the field applies or what its value would be. Distinct from `NOT_PROVIDED`: `NOT_PROVIDED` means the source chose not to include a field it could supply, `UNKNOWN` means the answer itself is not known to anyone in the pipeline.

### REDACTED

#### Meaning

The field was deliberately withheld, for example for privacy or contractual reasons. Distinct from `NOT_PROVIDED`: `REDACTED` asserts the value exists and was intentionally removed, rather than simply never having been included.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- Exactly five members exist: `AVAILABLE`, `NOT_APPLICABLE`, `NOT_PROVIDED`, `UNKNOWN`, `REDACTED`. `modules/mta_common/tests/test_enums_and_capabilities.py::FieldAvailabilityTests.test_five_states_are_distinct_values` asserts the member set has exactly five distinct values.
- No member is named `UNSPECIFIED`; `test_no_state_is_named_unspecified` asserts this directly, so the legacy sentinel's ambiguity cannot silently re-enter the canonical vocabulary under a new name.
- On [Touchpoint](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint.md), a `FieldAvailability` value and its corresponding value field are structurally linked: the value field is non-`None` if and only if availability is `AVAILABLE`. This is enforced by the module-level `_require_consistent()` helper in `touchpoint.py`, not by `FieldAvailability` itself, which carries no logic of its own beyond being a `StrEnum`.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Touchpoint Field Availability

[Touchpoint Field Availability](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint-field-availability.md) is a per-record triple of `FieldAvailability` values (`placement`, `creative`, `interaction_type`), one per optional `Touchpoint` field.

### Relationship to Provider Capabilities

[Provider Capabilities](/en/introduction/data-models/touchpoint-and-provider-contract/provider-capabilities.md)'s `format_availability`, `placement_availability`, `creative_availability`, and `interaction_type_availability` fields are each a `FieldAvailability`, declaring a provider-level ceiling that a given `Touchpoint`'s own `TouchpointFieldAvailability` should not exceed.

### Relationship to legacy_adapters.py

`touchpoint_from_five_segment_key` and `touchpoint_from_four_segment_key` are the only functions that produce a `FieldAvailability` value from legacy data — see Legacy Mapping.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

The five-segment touchpoint key's `UNSPECIFIED` placeholder, used for a missing `PLACEMENT` or `CREATIVE` segment, and the four-segment MTA-SIM key's complete absence of an `INTERACTION_TYPE` segment.

### Canonical Conversion

`legacy_adapters._optional_component()` maps a legacy component equal to the `UNSPECIFIED` sentinel to `(None, FieldAvailability.NOT_PROVIDED)`, and any other value to `(value, FieldAvailability.AVAILABLE)`. `touchpoint_from_four_segment_key` always produces `interaction_type=None` with `FieldAvailability.NOT_PROVIDED`, since a four-segment key carries no interaction type at all and this module never guesses one from delivery metrics.

### Information Loss

Adapting a legacy `UNSPECIFIED` component can only ever produce `FieldAvailability.NOT_PROVIDED` — never `NOT_APPLICABLE`, `UNKNOWN`, or `REDACTED`. Those three states have no legacy representation to adapt from, since the legacy key format collapsed all four possibilities into one sentinel before this module ever sees the data. A `Touchpoint` legitimately constructed with `NOT_APPLICABLE`, `UNKNOWN`, or `REDACTED` availability (for example, by a provider-specific loader that knows more than the five-segment key can express) cannot be round-tripped through `touchpoint_to_five_segment_key` and back without collapsing to `NOT_PROVIDED` — the five-segment key format itself is the lossy boundary, not this enum.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.legacy_adapters import touchpoint_from_five_segment_key

touchpoint = touchpoint_from_five_segment_key(
    "SPONSORED_PRODUCTS:SP:UNSPECIFIED:UNSPECIFIED:CLICK"
)
touchpoint.placement  # None
touchpoint.field_availability.placement  # FieldAvailability.NOT_PROVIDED — never
                                          # NOT_APPLICABLE/UNKNOWN/REDACTED from
                                          # this legacy path
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future provider-specific loader for a platform that can positively state "this field does not apply" (rather than merely "this field was not given") would be the first real producer of `FieldAvailability.NOT_APPLICABLE`, `UNKNOWN`, or `REDACTED` — none of the current adapters in `legacy_adapters.py` produce anything but `AVAILABLE` or `NOT_PROVIDED`.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/enums.py`; the five-state distinctness and non-`UNSPECIFIED` naming are directly tested in `modules/mta_common/tests/test_enums_and_capabilities.py`. Its use as a per-field consistency constraint is tested in `modules/mta_common/tests/test_touchpoint.py`, and its legacy round-trip behavior is tested in `modules/mta_common/tests/test_legacy_adapters.py::FiveSegmentKeyRoundTripTests`.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No current adapter ever produces `NOT_APPLICABLE`, `UNKNOWN`, or `REDACTED` — only `AVAILABLE` and `NOT_PROVIDED` are reachable from today's data, since every legacy source this module bridges collapses the other three into the single `UNSPECIFIED` sentinel before adaptation.
- `FieldAvailability` is an `enum.StrEnum`, one of seven vocabularies in `enums.py` that make up this repository's only use of the `Enum` family outside `modules/mta_common/`. Every other canonical class here is a plain `@dataclass(frozen=True)`; `StrEnum` was chosen for these seven vocabularies specifically so `FieldAvailability` and the rest are not restated as ad-hoc string literals across the classes that reference them, at the cost of introducing a dependency the rest of this repository deliberately avoids.
