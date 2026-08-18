---
title: Touchpoint
description: The canonical, typed, provider-independent replacement for the five-segment string key
compact: "Touchpoint replaces AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE with typed provider, ad_product, format, placement, creative, interaction_type fields plus TouchpointFieldAvailability. Bridges both the five-segment AMC key and four-segment MTA-SIM key via legacy_adapters.py, never inferring interaction_type."
lang: en-US
---

# Touchpoint

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`Touchpoint` is the canonical, provider-independent replacement for the [Touchpoint](/en/reference/definitions#touchpoint) key documented in [Terms and Abbreviations](/en/reference/definitions) and specified as the `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` string in [Attribution Model Overview](/en/attribution/index.md). Every component of that opaque colon-joined string becomes a typed attribute here, `provider` becomes an explicit field distinct from `ad_product` rather than an implicit assumption, and the string key's single `UNSPECIFIED` placeholder becomes one of five explicit [Field Availability](./field-availability.md) states carried in [Touchpoint Field Availability](./touchpoint-field-availability.md). The five-segment string key remains fully supported as a backward-compatible serialization, produced and parsed only by `legacy_adapters.py`.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/touchpoint.py`, alongside [Touchpoint Field Availability](./touchpoint-field-availability.md). Depends on the [Provider](./provider.md) and [Field Availability](./field-availability.md) vocabularies in `enums.py`. It is the type every observation record — [Delivery Observation](./delivery-observation.md), [Outcome Observation](./outcome-observation.md), [Attribution Evidence](./attribution-evidence.md) — attaches to identify what was observed.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### provider

#### Type

[Provider](./provider.md).

#### Requiredness

Required.

#### Meaning

The advertising platform this touchpoint was delivered on, independent of `ad_product`. Two touchpoints can share the same `ad_product` string while naming different providers; see [Provider](./provider.md)'s Examples.

#### Missingness

Not applicable; every `Touchpoint` names exactly one provider. No current data source carries an explicit provider field — every adapter defaults `provider=Provider.AMAZON_ADS` as a parameter default rather than reading it from a source field.

#### Validation

None beyond being a valid `Provider` member.

### ad_product

#### Type

`str`.

#### Requiredness

Required, non-blank.

#### Meaning

The provider-specific advertising product, for example `SPONSORED_PRODUCTS`. Validated against a [Provider Capabilities](./provider-capabilities.md)'s `supported_ad_products` by callers that hold one; `Touchpoint` itself does not require a `ProviderCapabilities` to construct.

#### Missingness

Not applicable; a blank `ad_product` is rejected outright rather than represented as missing.

#### Validation

`__post_init__` raises `ValueError` if `ad_product` is blank after stripping whitespace.

### format

#### Type

`str`.

#### Requiredness

Required, non-blank.

#### Meaning

The ad format or inventory type. Unlike `placement`, `creative`, and `interaction_type`, `format` has no `FieldAvailability` companion field: no provider this module models omits it.

#### Missingness

Not applicable; a blank `format` is rejected outright.

#### Validation

`__post_init__` raises `ValueError` if `format` is blank after stripping whitespace.

### placement

#### Type

`str | None`.

#### Requiredness

Optional.

#### Meaning

Where the ad appeared.

#### Missingness

`None` exactly when `field_availability.placement` is not `AVAILABLE`; which of the four non-`AVAILABLE` states applies is carried by that companion field, not inferred from `placement` being `None`.

#### Validation

`__post_init__` calls the module-level `_require_consistent` helper, which raises `ValueError` if `placement is None` while `field_availability.placement == AVAILABLE`, or if `placement is not None` while `field_availability.placement != AVAILABLE`.

### creative

#### Type

`str | None`.

#### Requiredness

Optional.

#### Meaning

The creative type.

#### Missingness

Same rule as `placement`, keyed to `field_availability.creative`.

#### Validation

Same `_require_consistent` check as `placement`, keyed to `field_availability.creative`.

### interaction_type

#### Type

`str | None`.

#### Requiredness

Optional.

#### Meaning

The billable interaction, typically `CLICK` or `IMPRESSION`.

#### Missingness

Same rule as `placement`, keyed to `field_availability.interaction_type`. A four-segment MTA-SIM key carries no `interaction_type` at all, so `touchpoint_from_four_segment_key` always leaves this `None` with `NOT_PROVIDED` unless a `SimulatorConfig` is used to expand to a five-segment key first — see Legacy Mapping.

#### Validation

Same `_require_consistent` check as `placement`, keyed to `field_availability.interaction_type`.

### field_availability

#### Type

[Touchpoint Field Availability](./touchpoint-field-availability.md).

#### Requiredness

Required.

#### Meaning

Why each of `placement`, `creative`, and `interaction_type` is or is not populated on this specific instance.

#### Missingness

Not applicable; every `Touchpoint` carries one.

#### Validation

Cross-validated field-by-field against `placement`/`creative`/`interaction_type` as described above; not separately validated as a standalone object beyond its own `__post_init__` (it has none — see [Touchpoint Field Availability](./touchpoint-field-availability.md)).

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `ad_product` and `format` are always non-blank.
- For each of `placement`, `creative`, `interaction_type`: the value is `None` if and only if the corresponding `field_availability` entry is not `AVAILABLE`. A value is never silently dropped or fabricated to satisfy this rule — an inconsistent combination raises `ValueError` at construction instead.
- `provider` and `ad_product` are independent: the same `ad_product` string may appear under two different `provider` values without conflict, and two `Touchpoint`s with the same `provider` may use entirely different `ad_product` vocabularies.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Provider and Field Availability

`Touchpoint.provider` is typed as [Provider](./provider.md). `Touchpoint.field_availability` is a [Touchpoint Field Availability](./touchpoint-field-availability.md), whose three fields are each typed as [Field Availability](./field-availability.md).

### Relationship to Provider Capabilities

A [Provider Capabilities](./provider-capabilities.md) instance is the static ceiling a caller may validate a `Touchpoint`'s `ad_product` and `field_availability` against; `Touchpoint` does not hold or require one directly.

### Relationship to Delivery Observation, Outcome Observation, and Attribution Evidence

[Delivery Observation](./delivery-observation.md), [Outcome Observation](./outcome-observation.md), and [Attribution Evidence](./attribution-evidence.md) each carry a `touchpoint: Touchpoint` field identifying what was observed or evaluated.

### Relationship to Attribution Documentation

[Attribution Model Overview](/en/attribution/index.md) specifies the five-segment string key this class replaces, canonicalized by `touchpoint_key.py`. `Touchpoint` references that existing contract through `legacy_adapters.py` rather than restating its validation rules.

### Relationship to Market Simulation Documentation

The four-segment MTA-SIM key this class also bridges is specified in [Market Simulation and Compatibility](/en/market-simulation/index.md), canonicalized by `modules/mta_standard/src/touchpoint_adapter.py`.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

Two distinct legacy formats, never conflated:

- The five-segment AMC key `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`, canonicalized by `modules.mta_attribution.src.touchpoint_key.canonicalize_touchpoint_key`, where a blank placement or creative component is rendered as the literal string `UNSPECIFIED` and `interaction_type` is always required and always one of `IMPRESSION`/`CLICK`.
- The four-segment MTA-SIM key `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE`, canonicalized by `modules.mta_standard.src.touchpoint_adapter.canonicalize_four_segment_key`, which carries no `interaction_type` segment at all.

### Canonical Conversion

`legacy_adapters.touchpoint_from_five_segment_key(key, *, provider=Provider.AMAZON_ADS)` splits the canonicalized five-segment key and maps each `UNSPECIFIED` placement or creative component to `(None, FieldAvailability.NOT_PROVIDED)`; a present component maps to `(value, FieldAvailability.AVAILABLE)`. `interaction_type` is always populated with `FieldAvailability.AVAILABLE`, since the five-segment key requires it.

`legacy_adapters.touchpoint_from_four_segment_key(key, *, provider=Provider.AMAZON_ADS)` performs the same `UNSPECIFIED`-collapsing for placement and creative, but always leaves `interaction_type=None` with `FieldAvailability.NOT_PROVIDED` — this function never guesses the interaction type from delivery metrics, matching `touchpoint_adapter.py`'s existing policy of rejecting rather than inferring a missing cost type. When a `SimulatorConfig` is available (see `modules.mta_standard.src.touchpoint_adapter.SimulatorConfig`), a caller should instead expand the four-segment key to five segments with `SimulatorConfig.to_five_segment(key)` and call `touchpoint_from_five_segment_key` on the result, so `interaction_type` is populated from the simulator's explicit billing configuration rather than left `None`. `legacy_adapters.attribution_evidence_from_standard_row` performs exactly this expansion when a `simulator_config` argument is given.

`legacy_adapters.touchpoint_to_five_segment_key(touchpoint)` projects a canonical `Touchpoint` back to the legacy key, for the existing attribution algorithms that still require the string form. It renders a missing `placement` or `creative` back to `UNSPECIFIED` regardless of which of the five `FieldAvailability` states caused the field to be missing, and raises `ValueError` if `touchpoint.interaction_type is None`, since the legacy format has no representation for an inapplicable or unknown interaction type.

`provider` has no legacy source field in either format: `touchpoint_from_five_segment_key` and `touchpoint_from_four_segment_key` both default `provider=Provider.AMAZON_ADS`, since every current record originates from Amazon Ads; no adapter reads a provider value from source data.

### Information Loss

- The five-segment key's `UNSPECIFIED` placeholder collapses whatever the source actually meant — not applicable, not provided, unknown, or redacted — into one legacy sentinel. Adapting a legacy `UNSPECIFIED` component can therefore only ever produce `FieldAvailability.NOT_PROVIDED`, never `NOT_APPLICABLE`, `UNKNOWN`, or `REDACTED`; those three states have no legacy representation to adapt from.
- Projecting back to a five-segment key loses the distinction between the five `FieldAvailability` states again: every non-`AVAILABLE` state for `placement`/`creative` renders as the same `UNSPECIFIED` string.
- A `Touchpoint` whose `interaction_type` is `None` — for example, one adapted from a bare four-segment key — cannot be projected to a five-segment key at all; `touchpoint_to_five_segment_key` raises rather than choosing a default interaction type.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.legacy_adapters import (
    touchpoint_from_five_segment_key,
    touchpoint_to_five_segment_key,
)

key = "SPONSORED_PRODUCTS:SP:UNSPECIFIED:UNSPECIFIED:CLICK"
touchpoint = touchpoint_from_five_segment_key(key)
touchpoint.placement  # None
touchpoint.field_availability.placement  # FieldAvailability.NOT_PROVIDED
touchpoint_to_five_segment_key(touchpoint) == key  # True
```

```python
from modules.mta_common.src.legacy_adapters import touchpoint_from_four_segment_key

touchpoint = touchpoint_from_four_segment_key("SPONSORED_PRODUCTS:SP:TOP_OF_SEARCH:VIDEO")
touchpoint.interaction_type  # None
touchpoint.field_availability.interaction_type  # FieldAvailability.NOT_PROVIDED
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future response-prediction model would read `Touchpoint` as part of `CampaignEpisode`'s observed-after-treatment records. A future incrementality model would key its estimates by `Touchpoint`. Neither exists yet.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented and tested in `modules/mta_common/tests/test_touchpoint.py` (provider/ad_product separation, `NOT_APPLICABLE`/`NOT_PROVIDED` distinguishability, value/availability consistency enforcement, required-field rejection) and `modules/mta_common/tests/test_legacy_adapters.py` (five-segment round-trip, four-segment key never guessing `interaction_type`). See [Canonical Data Model](./index.md) for the full test count and command.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- `ad_product` is an open string, not validated against any `ProviderCapabilities` vocabulary by `Touchpoint` itself; that check is left to a future caller.
- No adapter derives `provider` from source data; it is always a caller-supplied default.
- No real second-provider loader constructs a `Touchpoint` today; only `legacy_adapters.py`'s Amazon Ads-format adapters and this module's own tests do.
