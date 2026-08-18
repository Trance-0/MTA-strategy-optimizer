---
title: Product
description: Business product identity, independent of any advertising platform or provider-specific advertising identifier
compact: "Product's canonical business identity (product_id) separated from provider-specific advertising identifiers (provider_ad_identifiers, immutable, Provider-keyed, e.g. Amazon ASIN). No Amazon-specific ID required. No legacy source or adapter exists yet; tested in test_product_and_economics.py."
lang: en-US
---

# Product

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`Product` represents a business product's identity independently of any advertising platform. It exists because no such concept exists anywhere in the currently implemented pipeline: the dashboard schema has no product-identity field at all, and `modules/mta_strategy_recommendation` explicitly forbids `sku_id`/`sku_ids` as output fields. `Product` separates a stable business identity (`product_id`) from zero or more provider-specific advertising identities (`provider_ad_identifiers`), since no current data ties the two together and a future advertising provider may use a different identifier scheme than the one Amazon Ads uses today.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/product.py`, in the Product Identity and Economics family of the [Canonical Data Model](./index.md). A `@dataclass(frozen=True)` value object with explicit `__post_init__` validation; it has no ORM mapping, no database coupling, and no reference back to any `Campaign`. [Product Economics](./product-economics.md) and [Campaign Product Link](./campaign-product-link.md) both reference a `Product` only by its `product_id` string, not by holding a `Product` instance.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### product_id

#### Type

`str`

#### Requiredness

Required; no default.

#### Meaning

A stable business identifier — for example a Global Trade Item Number or an internal product identifier. Deliberately not required to be, or derived from, any Amazon-specific identifier.

#### Missingness

Not applicable: `product_id` has no missing-but-valid state. A `Product` cannot exist without one.

#### Validation

`__post_init__` raises `ValueError` when `str(product_id).strip()` is empty.

### provider_ad_identifiers

#### Type

`Mapping[Provider, str]`, stored internally as an immutable `types.MappingProxyType` regardless of what mapping type the caller passes in.

#### Requiredness

Optional; defaults to an empty mapping via `default_factory`.

#### Meaning

Zero or more provider-specific advertising identifiers for this product, keyed by [Provider](./provider.md) — for example `{Provider.AMAZON_ADS: "B000000001"}` for an [Amazon Standard Identification Number (ASIN)](/en/reference/definitions#asin-amazon-standard-identification-number) under Amazon Ads. There is no requirement that any entry exist, and no requirement that an Amazon Ads entry specifically exist.

#### Missingness

An empty mapping means "this business product is known but has no advertising identity linked to any provider yet" — a valid, common state, not an error.

#### Validation

`__post_init__` rewraps whatever mapping the caller passed into `MappingProxyType(dict(...))` via `object.__setattr__` (required because the dataclass is frozen). This produces two effects, both directly tested: mutating the caller's original `dict` after construction does not change the stored value, because a defensive copy is made; and attempting item assignment on `product.provider_ad_identifiers` itself raises `TypeError`, because a `MappingProxyType` is read-only.

### name

#### Type

`str | None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

Optional display name.

#### Missingness

`None` means "not supplied." This field does not use the five-state [Field Availability](./field-availability.md) vocabulary — that vocabulary is reserved for `Touchpoint` fields whose absence has provider-level significance; a display name's absence does not.

#### Validation

None.

### category

#### Type

`str | None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

Optional product category.

#### Missingness

`None` means "not supplied."

#### Validation

None.

### brand

#### Type

`str | None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

Optional brand.

#### Missingness

`None` means "not supplied."

#### Validation

None.

### status

#### Type

`str | None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

Optional lifecycle status, for example `ACTIVE` or `DISCONTINUED`. No enum backs this field today; it is a free-form string.

#### Missingness

`None` means "not supplied."

#### Validation

None.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `product_id` is always non-blank.
- `provider_ad_identifiers` is always an immutable mapping, regardless of the mutability of whatever the caller passed at construction time.
- `Product` imposes no advertising-platform identity requirement at all: `provider_ad_identifiers` may be empty, and no field on `Product` is Amazon-specific.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Provider

`provider_ad_identifiers` keys are typed as [Provider](./provider.md), the enum that also names which platform a `Touchpoint` or `Campaign` came from — the same vocabulary is reused rather than restated.

### Relationship to Product Economics

[Product Economics](./product-economics.md) references a product by matching `ProductEconomics.product_id` to `Product.product_id`. This is a convention, not an enforced foreign key: `ProductEconomics` can be constructed without a corresponding `Product` instance existing anywhere.

### Relationship to Campaign Product Link

[Campaign Product Link](./campaign-product-link.md) references a product the same way, via `CampaignProductLink.product_id`, as one side of its many-to-many relationship to `Campaign`.

### Relationship to Campaign

`Product` has no direct field relating it to [Campaign](./campaign.md). The many-to-many relationship between the two is expressed entirely through `CampaignProductLink`, never through a field on either class.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None. `modules/mta_common/src/legacy_adapters.py` contains zero references to `Product` — no adapter function exists. No current pipeline component defines product identity at all: the dashboard schema has no price, cost-of-goods, margin, or inventory field naming a product; and `modules/mta_strategy_recommendation`'s `hierarchy_validator.FORBIDDEN_OUTPUT_FIELDS` explicitly forbids `sku_id`/`sku_ids` as output fields. The only identified-[Stock Keeping Unit (SKU)](/en/reference/definitions#sku-stock-keeping-unit)-adjacent field anywhere in the current pipeline is an anonymous integer count, `eligible_sku_count`, which counts eligible SKUs without identifying any of them.

### Canonical Conversion

Not implemented. A future product-data integration would construct `Product` instances directly from its own source; no adapter function derives one from any data this pipeline currently reads.

### Information Loss

Not applicable — there is no legacy representation of product identity to lose information from.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.enums import Provider
from modules.mta_common.src.product import Product

product = Product(
    product_id="SKU-001",
    provider_ad_identifiers={Provider.AMAZON_ADS: "B000000001"},
    name="Example Widget",
    category="Widgets",
    brand="Acme",
    status="ACTIVE",
)

# A product with no advertising identity linked yet is valid:
unlinked = Product(product_id="SKU-002")
assert dict(unlinked.provider_ad_identifiers) == {}
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future product-data integration would populate `Product` records, which a future join against [Product Economics](./product-economics.md) and [Campaign Product Link](./campaign-product-link.md) would then use, and which a future response model or strategy optimizer would eventually need to reason about a product's advertising identity across more than one provider. Nothing in the current pipeline constructs or consumes `Product` outside its own tests.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/product.py`. Validated by `modules/mta_common/tests/test_product_and_economics.py::ProductIdentityTests`: a product's identity is independent of its advertising identifiers, a product with no advertising identity is valid, `provider_ad_identifiers` is immutable against both external mutation and direct item assignment, and a blank `product_id` is rejected. No current pipeline component constructs a `Product` instance outside this test suite.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No current data source supplies `Product` identity; every instance today is hand-constructed in tests.
- `provider_ad_identifiers`'s `Provider`-keyed shape has only been exercised in tests with `Provider.AMAZON_ADS`; nothing here demonstrates a second provider populating it (that demonstration lives instead in [Provider Capabilities](./provider-capabilities.md)).
