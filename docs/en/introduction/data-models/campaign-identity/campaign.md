---
title: Campaign
description: The canonical, provider-independent representation of one advertising campaign
compact: "Frozen dataclass `Campaign` in modules/mta_common/src/campaign.py: campaign_id, campaign_name, provider, ad_product, status, reporting_scope. Separates provider from ad_product; imposes no closed ad_product vocabulary. Adapted from strategy_request.json by legacy_adapters.campaign_from_strategy_request_row."
order: 10
lang: en-US
---

# Campaign

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`Campaign` is the canonical representation of one advertising campaign, independent of which [provider](/en/introduction/data-models/vocabularies/provider.md) runs it or how many products it advertises. It exists because today's only representation of a campaign is four required keys inside `strategy_request.json` (`campaign_id`, `campaign_name`, `ad_product`, `status`), and that shape is only ever valid inside a Campaign Group hardcoded to exactly four campaigns covering Amazon's four ad products (`budget_recommender.py`'s `SUPPORTED_AD_PRODUCTS` constant and its "exactly 4 campaigns" check). `Campaign` carries the same information without either constraint, so a future provider or a campaign group of a different shape can be represented without changing the type.

The field that matters most here is the split between `provider` and `ad_product`. The legacy five-segment touchpoint key conflates the two — `ad_product` is the key's first segment, and which platform issued the key is never recorded at all. `Campaign.provider` and `Campaign.ad_product` are two separate, orthogonal fields: `provider` says which advertising platform the campaign runs on (Amazon Ads today), and `ad_product` says which product on that platform (`SPONSORED_PRODUCTS`, and so on). A second provider with its own `ad_product` vocabulary does not need a new field, only a new `Provider` value.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/campaign.py`, alongside [Ad Group](/en/introduction/data-models/campaign-identity/ad-group.md). This is the Campaign Identity layer of the [Canonical Data Model](/en/introduction/data-models/index.md): it depends on [Provider](/en/introduction/data-models/vocabularies/provider.md) and [Reporting Scope](/en/introduction/data-models/touchpoint-and-provider-contract/reporting-scope.md), and is in turn depended on by [Campaign Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md), which composes a `Campaign` with its budget, delivery, and outcome observations.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### campaign_id

#### Type

`str`

#### Requiredness

Required.

#### Meaning

Stable campaign identifier, unique within the owning provider and account.

#### Missingness

Not applicable. `Campaign` carries no optional-field machinery — every field on this class must always carry a value. The five explicit [Field Availability](/en/introduction/data-models/vocabularies/field-availability.md) states describe why a `Touchpoint` component may be missing, not why a campaign identity field would be; a record that cannot supply a `campaign_id` is not a valid `Campaign`.

#### Validation

`__post_init__` rejects a blank or whitespace-only string.

### campaign_name

#### Type

`str`

#### Requiredness

Required.

#### Meaning

Human-readable campaign name, as reported by the provider.

#### Missingness

Not applicable, for the same reason as `campaign_id`.

#### Validation

`__post_init__` rejects a blank or whitespace-only string.

### provider

#### Type

[`Provider`](/en/introduction/data-models/vocabularies/provider.md)

#### Requiredness

Required.

#### Meaning

The advertising platform this campaign runs on, independent of `ad_product`.

#### Missingness

Not applicable. `Provider` is a closed enum with no null-equivalent member; a `Campaign` whose platform is genuinely unknown cannot be constructed by design.

#### Validation

None beyond Python's own type system — any `Provider` member is accepted.

### ad_product

#### Type

`str`

#### Requiredness

Required.

#### Meaning

Provider-specific advertising product, for example `SPONSORED_PRODUCTS`. `Campaign` itself imposes no closed vocabulary; a caller that needs to reject an unrecognized product validates the value against a [Provider Capabilities](/en/introduction/data-models/touchpoint-and-provider-contract/provider-capabilities.md) instance for `provider`, not against `Campaign`.

#### Missingness

Not applicable, for the same reason as `campaign_id`.

#### Validation

`__post_init__` rejects a blank or whitespace-only string. It does **not** check membership in any fixed set — `test_ad_product_is_not_restricted_to_a_fixed_vocabulary` in `modules/mta_common/tests/test_campaign.py` constructs a `Campaign` with `ad_product="SOME_FUTURE_PRODUCT"` and asserts it succeeds, specifically to lock in this design choice.

### status

#### Type

`str`

#### Requiredness

Required.

#### Meaning

Provider-reported campaign status string, for example `enabled`.

#### Missingness

Not applicable, for the same reason as `campaign_id`.

#### Validation

`__post_init__` rejects a blank or whitespace-only string.

### reporting_scope

#### Type

[`ReportingScope`](/en/introduction/data-models/touchpoint-and-provider-contract/reporting-scope.md)

#### Requiredness

Required.

#### Meaning

The account, market, currency, and date window this campaign's identity was read from.

#### Missingness

Not applicable. A `Campaign` without a scope has no way to say which account or market it belongs to.

#### Validation

None inside `Campaign.__post_init__` itself; `ReportingScope` validates its own fields at construction, so an invalid scope cannot reach this point.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `campaign_id`, `campaign_name`, `ad_product`, and `status` must all be non-blank strings; a `Campaign` cannot be constructed with any of them blank or whitespace-only.
- `provider` and `ad_product` are independent — no rule ties one to a fixed set of the other's values inside this class. Enforcing that a given `provider` only issues certain `ad_product` values is a caller responsibility, exercised through [Provider Capabilities](/en/introduction/data-models/touchpoint-and-provider-contract/provider-capabilities.md), not a `Campaign` invariant.
- `Campaign` is immutable (`@dataclass(frozen=True)`): once constructed, no field can be reassigned.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Ad Group

[`AdGroup`](/en/introduction/data-models/campaign-identity/ad-group.md) belongs to exactly one `Campaign` through `AdGroup.campaign_id`, a plain string reference rather than a database-enforced foreign key — `Campaign` does not hold a collection of its ad groups.

### Relationship to Reporting Scope

Every `Campaign` embeds one [`ReportingScope`](/en/introduction/data-models/touchpoint-and-provider-contract/reporting-scope.md) directly as a field, rather than referencing one by identifier.

### Relationship to Campaign Episode

[`CampaignEpisode`](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md) composes a `Campaign` with its [`BudgetConstraints`](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-constraints.md), [`BudgetObservation`](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-observation.md), [`DeliveryObservation`](/en/introduction/data-models/budget-delivery-and-outcome-observations/delivery-observation.md), [`OutcomeObservation`](/en/introduction/data-models/budget-delivery-and-outcome-observations/outcome-observation.md), and [`AttributionEvidence`](/en/introduction/data-models/historical-evidence-and-lineage/attribution-evidence.md) records into the shape a future response model would consume.

### Relationship to Campaign Product Link

A future [`CampaignProductLink`](/en/introduction/data-models/product-identity-and-economics/campaign-product-link.md) references a campaign by `campaign_id`, expressing the many-to-many relationship between campaigns and [`Product`](/en/introduction/data-models/product-identity-and-economics/product.md) that `Campaign` itself does not carry.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

`strategy_request.json`'s `campaigns[]` entries, each carrying `campaign_id`, `campaign_name`, `ad_product`, and `status`, nested inside a Campaign Group that is validated elsewhere to contain exactly four campaigns spanning Amazon's four ad products.

### Canonical Conversion

`legacy_adapters.campaign_from_strategy_request_row(campaign_row, *, reporting_scope, provider=Provider.AMAZON_ADS)` reads the four fields directly off the row and combines them with a caller-supplied `ReportingScope` (typically produced by `legacy_adapters.reporting_scope_from_campaign_group`). `provider` is **not** read from the row — `strategy_request.json` has no provider field, since every campaign in it is implicitly Amazon Ads — and is instead a keyword parameter defaulting to `Provider.AMAZON_ADS`.

### Information Loss

None for the four adapted fields themselves; they map one to one. What is lost is a constraint, not a value: the legacy schema's "exactly four campaigns, one per Amazon ad product" rule has no representation in `Campaign` and is not re-derived by the adapter, since that rule belongs to `hierarchy_validator.py`'s validation of the whole request, not to one campaign's identity.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

Constructing directly:

```python
from modules.mta_common.src.campaign import Campaign
from modules.mta_common.src.enums import Provider
from modules.mta_common.src.reporting_scope import ReportingScope

campaign = Campaign(
    campaign_id="CAMP-1",
    campaign_name="Campaign One",
    provider=Provider.AMAZON_ADS,
    ad_product="SPONSORED_PRODUCTS",
    status="enabled",
    reporting_scope=ReportingScope(
        marketplace="US",
        advertiser_id="ADV-1",
        currency="USD",
        report_start_date="2026-01-01",
        report_end_date="2026-01-31",
    ),
)
```

Adapting from today's schema:

```python
from modules.mta_common.src.legacy_adapters import campaign_from_strategy_request_row

campaign = campaign_from_strategy_request_row(
    {
        "campaign_id": "CAMP-1",
        "campaign_name": "Campaign One",
        "ad_product": "SPONSORED_PRODUCTS",
        "status": "enabled",
    },
    reporting_scope=scope,
)
```

A blank `campaign_id` raises `ValueError` before either construction path returns.

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future strategy optimizer would read a campaign's [`CampaignEpisode`](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md) — which embeds this `Campaign` — to decide a budget allocation, and a future response model would use `provider`/`ad_product` as categorical features. Neither consumer exists yet.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Fully implemented and validated by dedicated tests in `modules/mta_common/tests/test_campaign.py`, with the legacy strategy-request path covered by `test_legacy_adapters.py`. The MTA-SIM research adapter also constructs canonical Campaigns from generated run snapshots and verifies their shared semantic fields.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- `Campaign` does not itself enforce that `ad_product` belongs to `provider`'s real vocabulary; that check is deferred to a caller consulting [Provider Capabilities](/en/introduction/data-models/touchpoint-and-provider-contract/provider-capabilities.md), which this class does not reference.
- No adapter reads a `provider` field from any current source, since none exists; every adaptation path defaults to `Provider.AMAZON_ADS` as a parameter rather than deriving it from data.
- `Campaign` has no reference back to its `AdGroup`s or to any `CampaignProductLink`; both are separate records that name a `campaign_id`, not a collection this class owns.
