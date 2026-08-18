---
title: Product Economics
description: A product's price and cost structure, with missing cost-of-goods-sold kept missing rather than zero-filled
compact: "ProductEconomics: unit_price, unit_cogs (missing stays None, never zero-filled), unit_contribution_margin, margin_source (EXPLICIT or DERIVED, cross-validated within 1e-6 tolerance of price minus COGS). No current price/COGS/margin source; tested in test_product_and_economics.py."
lang: en-US
---

# ProductEconomics

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`ProductEconomics` carries a product's price and cost structure. It exists because no price, [Cost of Goods Sold (COGS)](/en/reference/definitions#cogs-cost-of-goods-sold), or margin field exists anywhere in the currently implemented pipeline, and because a profit-relevant field like COGS must never be allowed to silently default to zero — a missing cost and a zero cost are different facts with different downstream consequences, so this class enforces the distinction by construction rather than leaving it to caller discipline.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/product.py`, alongside [Product](./product.md), in the Product Identity and Economics family of the [Canonical Data Model](./index.md). A `@dataclass(frozen=True)` value object with explicit `__post_init__` validation. It is deliberately not composed inside `Product` itself — the two are linked only by matching `product_id` values — so a product can exist with no economics record, and this module never enforces that a matching `Product` instance exists.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### product_id

#### Type

`str`

#### Requiredness

Required; no default.

#### Meaning

The [Product](./product.md)`.product_id` this economics record describes.

#### Missingness

Not applicable: required.

#### Validation

`__post_init__` raises `ValueError` when `str(product_id).strip()` is empty.

### currency

#### Type

`str`

#### Requiredness

Required; no default.

#### Meaning

The currency all monetary fields on this record (`unit_price`, `unit_cogs`, `unit_contribution_margin`) are denominated in.

#### Missingness

Not applicable: required.

#### Validation

`__post_init__` raises `ValueError` when `str(currency).strip()` is empty.

### unit_price

#### Type

`float | None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

Per-unit selling price.

#### Missingness

`None` means the price is unknown or not supplied.

#### Validation

When not `None`, must not be negative, or `__post_init__` raises `ValueError`.

### unit_cogs

#### Type

`float | None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

Per-unit [Cost of Goods Sold (COGS)](/en/reference/definitions#cogs-cost-of-goods-sold).

#### Missingness

`None` means unknown — explicitly and deliberately not the same claim as a zero cost. No code path in this class or anywhere in `modules/mta_common/` zero-fills a missing `unit_cogs`.

#### Validation

When not `None`, must not be negative, or `__post_init__` raises `ValueError`.

### unit_contribution_margin

#### Type

`float | None`

#### Requiredness

Optional; defaults to `None`. Required to be given together with `margin_source` — see Validation.

#### Meaning

Per-unit [Contribution Margin](/en/reference/definitions#contribution-margin): `unit_price` minus `unit_cogs`, before any allocation of fixed or corporate overhead. No fixed corporate overhead allocation is computed or required anywhere in this class.

#### Missingness

`None` means no margin figure was given at all.

#### Validation

Must be `None` exactly when `margin_source` is also `None` (`__post_init__` raises `ValueError` if only one of the two is set). When both `unit_contribution_margin`, `unit_price`, and `unit_cogs` are present, the implied margin `unit_price - unit_cogs` must equal `unit_contribution_margin` within an absolute tolerance of `1e-6`; a contradiction raises `ValueError` naming both the given and implied values.

### margin_source

#### Type

[`MarginSource | None`](./margin-source.md)

#### Requiredness

Optional; defaults to `None`. Required to be given together with `unit_contribution_margin` — see Validation.

#### Meaning

Whether `unit_contribution_margin` was given directly by a source (`MarginSource.EXPLICIT`) or derived from `unit_price` and `unit_cogs` (`MarginSource.DERIVED`).

#### Missingness

`None` is only valid when `unit_contribution_margin` is also `None`.

#### Validation

Must be given together with `unit_contribution_margin` (see above). When `margin_source == MarginSource.DERIVED`, both `unit_price` and `unit_cogs` must be non-`None`, or `__post_init__` raises `ValueError`. `MarginSource.EXPLICIT` carries no such requirement — an explicit margin may be given with no price or cost components at all.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `product_id` and `currency` are always non-blank.
- `unit_price` and `unit_cogs`, when present, are never negative.
- A missing `unit_cogs` always stays `None`; it is never zero-filled by this class or by any current adapter.
- `unit_contribution_margin` and `margin_source` are always both `None` or both set — never one without the other.
- `MarginSource.DERIVED` always requires both `unit_price` and `unit_cogs` to be present.
- Whenever `unit_contribution_margin`, `unit_price`, and `unit_cogs` are all present together, they must agree within `1e-6`, regardless of whether `margin_source` is `EXPLICIT` or `DERIVED` — a contradictory record cannot be constructed at all, rather than being caught later by a downstream consumer.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Product

References [Product](./product.md) by matching `product_id`; not an enforced foreign key or object reference.

### Relationship to Margin Source

`margin_source` is typed as [Margin Source](./margin-source.md).

### Relationship to a future profit objective

Conceptually, a future strategy optimizer's profit objective — `sum_s(incremental_units_s * unit_contribution_margin_s) - actual_ad_spend` — would read `unit_contribution_margin` from this class per product `s`, paired with a future incrementality source's `incremental_units` (see [Outcome Observation](./outcome-observation.md)). No optimizer is implemented, and [Campaign Episode](./campaign-episode.md) does not currently carry a `ProductEconomics` field.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None. No price, cost-of-goods, or margin field exists anywhere in the currently implemented pipeline: the dashboard schema has none of these fields, and neither `modules/mta_strategy_recommendation` nor `modules/mta_attribution` carries any product-economics data. `docs/en/market-simulation/product-data-model.md` documents an external, unconnected `msproduct` schema — including a `sku.specification_profit` field — as historical reference material only, not a data source this pipeline reads.

### Canonical Conversion

Not implemented. `modules/mta_common/src/legacy_adapters.py` contains no function that constructs a `ProductEconomics`.

### Information Loss

Not applicable — there is no legacy representation to lose information from.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.enums import MarginSource
from modules.mta_common.src.product import ProductEconomics

# Missing COGS stays None, not zero:
partial = ProductEconomics(product_id="SKU-001", currency="USD", unit_price=19.99)
assert partial.unit_cogs is None

# Consistent derived margin:
economics = ProductEconomics(
    product_id="SKU-001",
    currency="USD",
    unit_price=10.0,
    unit_cogs=6.0,
    unit_contribution_margin=4.0,
    margin_source=MarginSource.DERIVED,
)

# An explicit margin with no price or cost components at all is also valid:
explicit_only = ProductEconomics(
    product_id="SKU-002",
    currency="USD",
    unit_contribution_margin=5.0,
    margin_source=MarginSource.EXPLICIT,
)
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future strategy optimizer running under `StrategyObjective.MAXIMIZE_PROFIT` (see [Strategy Objective](./strategy-objective.md)) would read `unit_contribution_margin` to compute per-product profit contribution, combined with a future incrementality source's incremental units. Nothing in the current pipeline reads `ProductEconomics`.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/product.py`. Validated by `modules/mta_common/tests/test_product_and_economics.py::ProductEconomicsMissingCogsTests` and `::ProductEconomicsMarginTests`: a missing `unit_cogs` stays `None` and is explicitly asserted not equal to zero, negative `unit_cogs` is rejected, an explicit margin with no components is valid, a margin without its source (and a source without its margin) is rejected, a derived margin requires both components, a consistent derived margin is accepted, and a contradictory explicit margin is rejected. No current pipeline component constructs a `ProductEconomics` instance outside this test suite.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No current data source supplies price, COGS, or margin; every instance today is hand-constructed in tests.
- The class docstring describes it as covering "one reporting scope," but `ProductEconomics` carries no `reporting_scope` field itself — associating an instance with a specific window is left entirely to the caller's construction-time convention and is not validated by this class.
- `unit_contribution_margin` is a single flat per-unit figure; tiered or promotional pricing that varies within a window is not representable without constructing multiple instances, which this class does not itself distinguish or prevent from overlapping.
