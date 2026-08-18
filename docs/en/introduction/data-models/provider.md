---
title: Provider
description: The advertising platform or data source a canonical record originates from, kept independent of ad_product
compact: "Provider StrEnum (AMAZON_ADS, GENERIC) in modules/mta_common/src/enums.py — identifies which advertising platform a Touchpoint, Campaign, or ProviderCapabilities instance came from, independent of ad_product. No legacy field carries it; every adapter defaults provider=AMAZON_ADS."
lang: en-US
---

# Provider

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`Provider` identifies which advertising platform or data source a canonical record came from. It exists as a field separate from `ad_product` because the current implementation conflates the two: the five-segment touchpoint key's first segment (`SPONSORED_PRODUCTS`, `SPONSORED_BRANDS`, `SPONSORED_DISPLAY`, `AMAZON_DSP`) names an Amazon Ads product, not a platform, and nothing in today's data distinguishes "which platform" from "which product on that platform." `Provider` gives every canonical class a place to state the platform explicitly, so a future second platform does not have to be smuggled into the `ad_product` vocabulary.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/enums.py`, the vocabulary layer every other canonical class in `modules/mta_common/src/` depends on. `Provider` has no dependency of its own beyond the Python standard library.

## Members <span class="status-label status-verified" aria-label="Verified"></span>

### AMAZON_ADS

#### Meaning

The only real platform this repository currently adapts data from. Every legacy source this module bridges — the five-segment touchpoint key, `strategy_request.json`, `initial_budget_recommendation.json`, `AttributionResult`, `TouchpointSpend`, `StandardAttributionRow` — is implicitly Amazon Ads data, even though none of those shapes carries an explicit provider field.

### GENERIC

#### Meaning

Not a real platform. It exists so [Provider Capabilities](./provider-capabilities.md) and the tests that use it (`GENERIC_CAPABILITIES` in `modules/mta_common/src/provider_capabilities.py`) can demonstrate a second, differently shaped provider profile — one with a distinct `supported_ad_products` vocabulary and `placement_availability`/`creative_availability` fixed to `FieldAvailability.NOT_PROVIDED` — without this module claiming to adapt a second real advertising platform. No adapter function in `legacy_adapters.py` ever produces a record with `provider=Provider.GENERIC`.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- Exactly two members exist today: `AMAZON_ADS` and `GENERIC`. Adding a real second-provider integration would add a third member here, plus a matching `ProviderCapabilities` constant and adapter functions in `legacy_adapters.py` — none of which exist yet.
- As a `StrEnum`, each member's value is an exact string match of its name (`Provider.AMAZON_ADS == "AMAZON_ADS"`), so it round-trips cleanly through JSON and CSV without a separate serialization mapping.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Touchpoint

[Touchpoint](./touchpoint.md)'s `provider` field is typed `Provider`, replacing the implicit "everything is Amazon Ads" assumption baked into the five-segment key.

### Relationship to Campaign

[Campaign](./campaign.md)'s `provider` field is typed `Provider`, independent of `ad_product`.

### Relationship to Provider Capabilities

[Provider Capabilities](./provider-capabilities.md) is keyed to exactly one `Provider` value per instance (`AMAZON_ADS_CAPABILITIES.provider == Provider.AMAZON_ADS`, `GENERIC_CAPABILITIES.provider == Provider.GENERIC`), declaring what that provider can supply at all.

### Relationship to Data Lineage

[Data Lineage](./data-lineage.md)'s `provider` field is an optional `Provider`, scoping a record's provenance to a platform when applicable.

### Relationship to legacy_adapters.py

Every adapter function in `modules/mta_common/src/legacy_adapters.py` that constructs a `Touchpoint`, `Campaign`, or `AttributionEvidence` accepts a `provider: Provider = Provider.AMAZON_ADS` keyword parameter. See Legacy Mapping below.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None. No field named `provider` (or an equivalent) exists anywhere in the legacy shapes this module bridges — not in the five-segment touchpoint key, not in `strategy_request.json`, not in `initial_budget_recommendation.json`, not on `AttributionResult`, `TouchpointSpend`, or `StandardAttributionRow`. Every record produced by the current pipeline is Amazon Ads data by convention, never by an explicit field asserting it.

### Canonical Conversion

Every `legacy_adapters.py` function that builds a `Touchpoint`, `Campaign`, or `AttributionEvidence` — `touchpoint_from_five_segment_key`, `touchpoint_from_four_segment_key`, `attribution_evidence_from_attribution_result`, `attribution_evidence_from_standard_row`, `delivery_observation_from_touchpoint_spend`, `outcome_observation_from_touchpoint_spend`, `campaign_from_strategy_request_row` — takes `provider: Provider = Provider.AMAZON_ADS` as a keyword-only parameter with that default. The value is never read out of a source field; it is either the default or an explicit override the caller supplies.

### Information Loss

None in the legacy-to-canonical direction, since there is no legacy field to lose information from. The risk runs the other way: a caller that passes an incorrect `provider` override would silently mislabel a record's platform, since no legacy source exists to cross-check the claim against.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.enums import Provider

Provider.AMAZON_ADS == "AMAZON_ADS"  # True — StrEnum value equals member name
Provider.GENERIC in set(Provider)     # True

# Every current adapter defaults to Amazon Ads without reading a source field:
from modules.mta_common.src.legacy_adapters import touchpoint_from_five_segment_key
touchpoint = touchpoint_from_five_segment_key(
    "SPONSORED_PRODUCTS:SP:TOP_OF_SEARCH:VIDEO:CLICK"
)
touchpoint.provider  # Provider.AMAZON_ADS, the parameter default
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future second-provider integration would add a new `Provider` member, a matching `ProviderCapabilities` constant declaring that provider's field ceiling, and new `legacy_adapters.py`-equivalent functions reading that provider's real source shape instead of defaulting to `AMAZON_ADS`. None of this exists yet; `GENERIC` only proves the type shape is not Amazon-specific.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/enums.py` and exercised by `modules/mta_common/tests/test_enums_and_capabilities.py`, plus indirectly by every test in `modules/mta_common/tests/test_legacy_adapters.py` that checks an adapted record's `provider` field.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- Only `AMAZON_ADS` represents a real platform; `GENERIC` is a synthetic placeholder proving the contract is not Amazon-specific, not a working second-provider integration.
- `Provider` is an `enum.StrEnum`, one of seven vocabularies in `enums.py` that make up this repository's only use of the `Enum` family outside `modules/mta_common/`. Every other canonical class here is a plain `@dataclass(frozen=True)`; `StrEnum` was chosen for these seven vocabularies specifically so `Provider` and the rest are not restated as ad-hoc string literals across the classes that reference them, at the cost of introducing a dependency the rest of this repository deliberately avoids.
