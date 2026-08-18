---
title: Provider Capabilities
description: Per-provider static ceiling declaring which Touchpoint fields a provider can supply at all
compact: "ProviderCapabilities declares, per Provider, the closed ad_product vocabulary and default FieldAvailability for format/placement/creative/interaction_type. Hand-authored constants AMAZON_ADS_CAPABILITIES and GENERIC_CAPABILITIES; no adapter derives one from data."
order: 10
lang: en-US
---

# Provider Capabilities

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`ProviderCapabilities` states, for one [Provider](/en/introduction/data-models/vocabularies/provider.md), which fields of a [Touchpoint](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint.md) exist and are supplied at all, before any individual record is read. It answers two different questions that the current implementation conflates: "can this provider's ad products ever carry a `placement`" and "did this specific touchpoint carry one." `ProviderCapabilities` answers only the first, as a static ceiling; [Touchpoint Field Availability](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint-field-availability.md) answers the second, per record, and must never claim availability the provider-level ceiling does not support.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/provider_capabilities.py`. Depends only on the [Provider](/en/introduction/data-models/vocabularies/provider.md) and [Field Availability](/en/introduction/data-models/vocabularies/field-availability.md) vocabularies in `enums.py`. Has no dependents within `modules/mta_common/src/` itself; it is a reference constant a provider-specific loader or validator would read before constructing a [Touchpoint](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint.md).

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### provider

#### Type

[Provider](/en/introduction/data-models/vocabularies/provider.md).

#### Requiredness

Required.

#### Meaning

The provider this declaration describes.

#### Missingness

Not applicable; every instance names exactly one provider.

#### Validation

None beyond being a valid `Provider` member.

### supported_ad_products

#### Type

`tuple[str, ...]`.

#### Requiredness

Required, non-empty.

#### Meaning

The closed vocabulary of `ad_product` values this provider can report. Not every provider shares Amazon Ads' four-product vocabulary — this field exists precisely so a second provider's vocabulary does not have to be hardcoded alongside Amazon's.

#### Missingness

Not applicable; a `ProviderCapabilities` with no products is meaningless and is rejected.

#### Validation

`__post_init__` raises `ValueError` if `supported_ad_products` is empty or contains a repeated value.

### format_availability

#### Type

[Field Availability](/en/introduction/data-models/vocabularies/field-availability.md).

#### Requiredness

Required.

#### Meaning

Default availability of `Touchpoint.format` for this provider.

#### Missingness

Not applicable; the field itself states the default missingness reason, so it cannot be missing.

#### Validation

None beyond being a valid `FieldAvailability` member.

### placement_availability

#### Type

[Field Availability](/en/introduction/data-models/vocabularies/field-availability.md).

#### Requiredness

Required.

#### Meaning

Default availability of `Touchpoint.placement` for this provider. `GENERIC_CAPABILITIES` sets this to `NOT_PROVIDED`, demonstrating a provider whose delivery reporting omits placement entirely.

#### Missingness

Not applicable, for the same reason as `format_availability`.

#### Validation

None beyond being a valid `FieldAvailability` member.

### creative_availability

#### Type

[Field Availability](/en/introduction/data-models/vocabularies/field-availability.md).

#### Requiredness

Required.

#### Meaning

Default availability of `Touchpoint.creative` for this provider.

#### Missingness

Not applicable, for the same reason as `format_availability`.

#### Validation

None beyond being a valid `FieldAvailability` member.

### interaction_type_availability

#### Type

[Field Availability](/en/introduction/data-models/vocabularies/field-availability.md).

#### Requiredness

Required.

#### Meaning

Default availability of `Touchpoint.interaction_type` for this provider.

#### Missingness

Not applicable, for the same reason as `format_availability`.

#### Validation

None beyond being a valid `FieldAvailability` member.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `supported_ad_products` is non-empty and contains no duplicate.
- Each of the four `*_availability` fields is one member of [Field Availability](/en/introduction/data-models/vocabularies/field-availability.md); nothing enforces a relationship between them, since a provider's four fields are independently either applicable and reportable or not.
- Two constants exist today, `AMAZON_ADS_CAPABILITIES` and `GENERIC_CAPABILITIES`; nothing in the class itself limits the module to two, and a third `ProviderCapabilities` instance for a real second platform is a documented non-goal of this foundation, not a structural limitation.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Provider

Each `ProviderCapabilities` names exactly one [Provider](/en/introduction/data-models/vocabularies/provider.md) in its `provider` field; the two module-level constants cover `Provider.AMAZON_ADS` and `Provider.GENERIC`, the vocabulary's only two members.

### Relationship to Touchpoint and Touchpoint Field Availability

A caller that holds a `ProviderCapabilities` would validate a [Touchpoint](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint.md)'s `ad_product` against `supported_ad_products` and its [Touchpoint Field Availability](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint-field-availability.md) against the four `*_availability` ceilings — `Touchpoint` itself does not require a `ProviderCapabilities` to construct, so this validation is the caller's responsibility, not a structural constraint on `Touchpoint`.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None. No current adapter function derives a `ProviderCapabilities` from any report, schema, or configuration file.

### Canonical Conversion

There is no conversion function. `AMAZON_ADS_CAPABILITIES` is hand-authored in `provider_capabilities.py` to match the four-product vocabulary hardcoded today in `modules/mta_strategy_recommendation/src/budget_recommender.py`'s `SUPPORTED_AD_PRODUCTS` constant — `SPONSORED_PRODUCTS`, `SPONSORED_BRANDS`, `SPONSORED_DISPLAY`, `AMAZON_DSP`. `GENERIC_CAPABILITIES` has no legacy source at all; it exists only to demonstrate a differently shaped provider profile.

### Information Loss

Not applicable; there is no source data being converted.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.provider_capabilities import AMAZON_ADS_CAPABILITIES

"SPONSORED_PRODUCTS" in AMAZON_ADS_CAPABILITIES.supported_ad_products  # True
AMAZON_ADS_CAPABILITIES.placement_availability  # FieldAvailability.AVAILABLE
```

```python
from modules.mta_common.src.provider_capabilities import GENERIC_CAPABILITIES

GENERIC_CAPABILITIES.placement_availability  # FieldAvailability.NOT_PROVIDED
GENERIC_CAPABILITIES.creative_availability  # FieldAvailability.NOT_PROVIDED
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future provider-specific loader would select one `ProviderCapabilities` constant and use it to validate every `Touchpoint` it constructs, both for `ad_product` membership and for whether a `TouchpointFieldAvailability` it assigns is consistent with the provider's ceiling. No current loader performs this validation yet.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented and tested in `modules/mta_common/tests/test_enums_and_capabilities.py`: an empty or duplicate `supported_ad_products` is rejected, and `AMAZON_ADS_CAPABILITIES`/`GENERIC_CAPABILITIES` declare different, non-overlapping ad-product vocabularies with different placement/creative availability defaults. See [Canonical Data Model](/en/introduction/data-models/index.md) for the full test count and command.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No caller validates a `Touchpoint` against a `ProviderCapabilities` today; the class exists as a declared contract, not an enforced one.
- `AMAZON_ADS_CAPABILITIES`'s product vocabulary is a hand-copy of `budget_recommender.py`'s `SUPPORTED_AD_PRODUCTS`; the two are not derived from a single shared source, so they can drift out of sync if one is edited without the other.
- `GENERIC_CAPABILITIES` does not correspond to any real advertising platform; see [Canonical Data Model](/en/introduction/data-models/index.md)'s Scope and Non-Goals.
