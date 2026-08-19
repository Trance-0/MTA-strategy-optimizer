---
title: Product
description: Business product identity, independent of any advertising platform or provider-specific advertising identifier
compact: "Product's canonical business identity, optional sku_id, inventory/salable state, and immutable Provider-keyed advertising identifiers. MTA-SIM research snapshots populate this class through the market-simulation adapter; no Amazon-specific identifier is required."
order: 10
lang: en-US
---

# Product

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`Product` represents a business product independently of any advertising platform. It separates a stable business identity (`product_id`) from an optional Stock Keeping Unit (SKU) identifier (`sku_id`), provider-specific advertising identities, and optional inventory availability. MTA-SIM research snapshots are the first implemented source; their adapter constructs this canonical class without creating an optimizer-local product container.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/product.py`, in the Product Identity and Economics family of the [Canonical Data Model](/en/introduction/data-models/index.md). A `@dataclass(frozen=True)` value object with explicit `__post_init__` validation; it has no ORM mapping, no database coupling, and no reference back to any `Campaign`. [Product Economics](/en/introduction/data-models/product-identity-and-economics/product-economics.md) and [Campaign Product Link](/en/introduction/data-models/product-identity-and-economics/campaign-product-link.md) both reference a `Product` only by its `product_id` string, not by holding a `Product` instance.

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

Zero or more provider-specific advertising identifiers for this product, keyed by [Provider](/en/introduction/data-models/vocabularies/provider.md) — for example `{Provider.AMAZON_ADS: "B000000001"}` for an [Amazon Standard Identification Number (ASIN)](/en/reference/definitions#asin-amazon-standard-identification-number) under Amazon Ads. There is no requirement that any entry exist, and no requirement that an Amazon Ads entry specifically exist.

#### Missingness

An empty mapping means "this business product is known but has no advertising identity linked to any provider yet" — a valid, common state, not an error.

#### Validation

Every supplied identifier value must be non-blank. `__post_init__` rewraps whatever mapping the caller passed into `MappingProxyType(dict(...))` via `object.__setattr__` (required because the dataclass is frozen). This produces two effects, both directly tested: mutating the caller's original `dict` after construction does not change the stored value, because a defensive copy is made; and attempting item assignment on `product.provider_ad_identifiers` itself raises `TypeError`, because a `MappingProxyType` is read-only.

### sku_id

#### Type

`str | None`

#### Meaning

An optional Stock Keeping Unit identifier used by the business. It is not the canonical identity and need not equal any provider advertising identifier.

### name

#### Type

`str | None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

Optional display name.

#### Missingness

`None` means "not supplied." This field does not use the five-state [Field Availability](/en/introduction/data-models/vocabularies/field-availability.md) vocabulary — that vocabulary is reserved for `Touchpoint` fields whose absence has provider-level significance; a display name's absence does not.

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

### inventory_units

#### Type

`int | None`

#### Meaning

Optional current inventory quantity. `None` means not supplied; zero means supplied and out of stock.

#### Validation

When present, it must not be negative.

### salable

#### Type

`bool | None`

#### Meaning

Optional explicit eligibility to sell the product. `None` means the source did not make that assertion and is distinct from `False`.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `product_id` is always non-blank.
- `provider_ad_identifiers` is always an immutable mapping, regardless of the mutability of whatever the caller passed at construction time.
- A present provider advertising identifier is never blank.
- `Product` imposes no advertising-platform identity requirement at all: `provider_ad_identifiers` may be empty, and no field on `Product` is Amazon-specific.
- `inventory_units`, when supplied, is non-negative; `salable` preserves three states: true, false, and not supplied.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Provider

`provider_ad_identifiers` keys are typed as [Provider](/en/introduction/data-models/vocabularies/provider.md), the enum that also names which platform a `Touchpoint` or `Campaign` came from — the same vocabulary is reused rather than restated.

### Relationship to Product Economics

[Product Economics](/en/introduction/data-models/product-identity-and-economics/product-economics.md) references a product by matching `ProductEconomics.product_id` to `Product.product_id`. This is a convention, not an enforced foreign key: `ProductEconomics` can be constructed without a corresponding `Product` instance existing anywhere.

### Relationship to Campaign Product Link

[Campaign Product Link](/en/introduction/data-models/product-identity-and-economics/campaign-product-link.md) references a product the same way, via `CampaignProductLink.product_id`, as one side of its many-to-many relationship to `Campaign`.

### Relationship to Campaign

`Product` has no direct field relating it to [Campaign](/en/introduction/data-models/campaign-identity/campaign.md). The many-to-many relationship between the two is expressed entirely through `CampaignProductLink`, never through a field on either class.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

MTA-SIM research snapshots provide `product_id`, optional `sku_id`, provider advertising identifiers, display attributes, inventory units, and salable state. The market-simulation adapter maps those fields directly. The older strategy-request compatibility adapter still does not invent a product from anonymous `eligible_sku_count` values.

### Canonical Conversion

Implemented for MTA-SIM research snapshots by `load_mta_sim_research_snapshot`. Legacy strategy-request input has no identified product source and therefore has no conversion.

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

A future product-data integration would populate `Product` records, which a future join against [Product Economics](/en/introduction/data-models/product-identity-and-economics/product-economics.md) and [Campaign Product Link](/en/introduction/data-models/product-identity-and-economics/campaign-product-link.md) would then use, and which a future response model or strategy optimizer would eventually need to reason about a product's advertising identity across more than one provider. Nothing in the current pipeline constructs or consumes `Product` outside its own tests.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/product.py`. Validated by `modules/mta_common/tests/test_product_and_economics.py::ProductIdentityTests`, including identity independence, immutable provider identifiers, inventory validation, and preserved salable missingness. MTA-SIM snapshot conversion is verified by the market-simulation adapter tests.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- CSV-only MTA-SIM imports cannot reconstruct product identity because the unchanged legacy CSV schemas do not contain product master data; the research sidecar or database tables are required.
- Inventory is a snapshot value and carries no warehouse, reservation, or replenishment model.
