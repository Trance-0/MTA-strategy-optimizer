---
title: Campaign Product Link
description: The explicit many-to-many relationship between Campaign and Product
compact: "CampaignProductLink: explicit many-to-many Campaign-Product relationship (campaign_id, product_id), not a single field on either side. eligibility_status and link_status reserved, unpopulated. No legacy source beyond an anonymous eligible_sku_count; tested in test_product_and_economics.py."
order: 30
lang: en-US
---

# CampaignProductLink

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`CampaignProductLink` is the explicit many-to-many relationship object connecting [Campaign](/en/introduction/data-models/campaign-identity/campaign.md) and [Product](/en/introduction/data-models/product-identity-and-economics/product.md). It exists because a Campaign may advertise several Products and a Product may be advertised by several Campaigns, so the relationship is a first-class link object rather than a single product field bolted onto `Campaign`, or a single campaign field bolted onto `Product`.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/product.py`, alongside [Product](/en/introduction/data-models/product-identity-and-economics/product.md) and [Product Economics](/en/introduction/data-models/product-identity-and-economics/product-economics.md), in the Product Identity and Economics family of the [Canonical Data Model](/en/introduction/data-models/index.md). A `@dataclass(frozen=True)` value object. The relationship it expresses is purely by matching `campaign_id`/`product_id` string values across instances — it holds no object references to an actual `Campaign` or `Product` instance, and no cross-object existence check is performed at construction time.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### campaign_id

#### Type

`str`

#### Requiredness

Required; no default.

#### Meaning

The linked [Campaign](/en/introduction/data-models/campaign-identity/campaign.md)`.campaign_id`.

#### Missingness

Not applicable: required.

#### Validation

`__post_init__` raises `ValueError` when `str(campaign_id).strip()` is empty.

### product_id

#### Type

`str`

#### Requiredness

Required; no default.

#### Meaning

The linked [Product](/en/introduction/data-models/product-identity-and-economics/product.md)`.product_id`.

#### Missingness

Not applicable: required.

#### Validation

`__post_init__` raises `ValueError` when `str(product_id).strip()` is empty.

### eligibility_status

#### Type

`str | None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

Reserved for a future targeting-eligibility state, for example `ELIGIBLE` or `INELIGIBLE`. No enum backs this field today; it is a free-form string.

#### Missingness

`None` means "not yet populated by any current data source" — the default and only state produced today. It is not evidence that the campaign/product pair is ineligible.

#### Validation

None.

### link_status

#### Type

`str | None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

Reserved for a future link lifecycle state, for example `ACTIVE` or `PAUSED`. No enum backs this field today.

#### Missingness

`None` means "not yet populated," the same as `eligibility_status` — not evidence the link is paused.

#### Validation

None.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `campaign_id` and `product_id` are always non-blank.
- The relationship is genuinely many-to-many: many `CampaignProductLink` instances may share the same `campaign_id` with different `product_id` values, and vice versa. Demonstrated directly by `test_one_campaign_can_link_to_several_products` and `test_one_product_can_link_to_several_campaigns`.
- The class itself imposes no uniqueness constraint: constructing two identical `CampaignProductLink` instances is not rejected. Deduplication, if a caller needs it, is the caller's responsibility.
- `eligibility_status` and `link_status` are reserved fields — present in the dataclass shape today so that a future population of either does not require changing the shape — but no current code path sets either to anything other than the default `None`.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Campaign

`campaign_id` references [Campaign](/en/introduction/data-models/campaign-identity/campaign.md)`.campaign_id` by matching value, not by object reference.

### Relationship to Product

`product_id` references [Product](/en/introduction/data-models/product-identity-and-economics/product.md)`.product_id` by matching value, not by object reference.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None as an explicit, per-product relationship. The closest current analog is an anonymous integer count, `eligible_sku_count`, which records how many [Stock Keeping Unit (SKU)](/en/reference/definitions#sku-stock-keeping-unit)s are eligible for a campaign without identifying any of them individually.

### Canonical Conversion

Not implemented. `modules/mta_common/src/legacy_adapters.py` contains no function that constructs a `CampaignProductLink`; `eligible_sku_count` cannot be decomposed into individual links, since it carries no per-SKU identity to decompose.

### Information Loss

Not applicable in the adapter sense — there is no per-link legacy source to adapt from. Conceptually, the identity of which specific products `eligible_sku_count` counts was already lost before this canonical model existed; that loss predates `CampaignProductLink` and is not something this class's adapter path could recover even if one were written.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.product import CampaignProductLink

links = [
    CampaignProductLink(campaign_id="CAMP-1", product_id="SKU-001"),
    CampaignProductLink(campaign_id="CAMP-1", product_id="SKU-002"),
    CampaignProductLink(campaign_id="CAMP-2", product_id="SKU-001"),
]
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future targeting integration would populate `CampaignProductLink` from what is today only `eligible_sku_count`, and a future response model or strategy optimizer would use these links to know which products a campaign's Spend and Outcomes should be distributed across. Nothing in the current pipeline consumes `CampaignProductLink` yet.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/product.py`. Validated by `modules/mta_common/tests/test_product_and_economics.py::CampaignProductLinkTests`: one Campaign can link to several Products, one Product can link to several Campaigns, and blank `campaign_id`/`product_id` are both rejected. No current pipeline component constructs a `CampaignProductLink` instance outside this test suite.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No current data source supplies per-product campaign links; every instance today is hand-constructed in tests.
- `eligibility_status` and `link_status` have no defined vocabulary yet — no enum backs either field, pending a future targeting-eligibility design.
