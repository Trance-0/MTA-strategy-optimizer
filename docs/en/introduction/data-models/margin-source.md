---
title: Margin Source
description: Whether a Product Economics contribution margin was given directly or derived from price and cost, with a validated agreement requirement
compact: "MarginSource StrEnum (EXPLICIT, DERIVED) in modules/mta_common/src/enums.py — optional field on ProductEconomics.margin_source, required together with unit_contribution_margin. DERIVED requires unit_price and unit_cogs; explicit margin plus both components must agree within 1e-6. No legacy_adapters.py function populates it."
lang: en-US
---

# Margin Source

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`MarginSource` states whether a product's [Contribution Margin](/en/reference/definitions#contribution-margin) was supplied directly by a source or derived by this repository from unit price and [Cost of Goods Sold (COGS)](/en/reference/definitions#cogs-cost-of-goods-sold). It is required whenever `ProductEconomics.unit_contribution_margin` is set, so a reader never has to guess whether a margin value is an external claim or a locally computed subtraction.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/enums.py`, the vocabulary layer every other canonical class in `modules/mta_common/src/` depends on. `MarginSource` has no dependency of its own beyond the Python standard library.

## Members <span class="status-label status-verified" aria-label="Verified"></span>

### EXPLICIT

#### Meaning

`unit_contribution_margin` was given directly by a source, not computed by this repository from `unit_price` and `unit_cogs`.

### DERIVED

#### Meaning

`unit_contribution_margin` was derived from `unit_price` minus `unit_cogs`. Requires both `unit_price` and `unit_cogs` to be present; see Invariants below.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- Exactly two members exist: `EXPLICIT` and `DERIVED`.
- As a `StrEnum`, each member's value is an exact string match of its name (`MarginSource.EXPLICIT == "EXPLICIT"`).
- `ProductEconomics.__post_init__` enforces: `unit_contribution_margin` and `margin_source` must be given together — one is `None` if and only if the other is (`ValueError: "unit_contribution_margin and margin_source must be given together"`).
- `margin_source == MarginSource.DERIVED` requires both `unit_price` and `unit_cogs` to be present (`ValueError: "margin_source=DERIVED requires both unit_price and unit_cogs"`).
- When `unit_contribution_margin`, `unit_price`, and `unit_cogs` are all present — regardless of `margin_source` — the implied margin (`unit_price - unit_cogs`) must agree with the given `unit_contribution_margin` within a tolerance of `1e-6`, or construction raises `ValueError: "unit_contribution_margin contradicts unit_price minus unit_cogs: given=..., implied=..."`. This check applies even when `margin_source=EXPLICIT`: an explicit margin is still cross-checked against price and cost whenever both are also present.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Product Economics

[Product Economics](./product-economics.md)'s `margin_source: MarginSource | None = None` field gates `unit_contribution_margin`. Its docstring: "`unit_contribution_margin` may be given directly (`margin_source=EXPLICIT`) or derived from `unit_price` and `unit_cogs` (`margin_source=DERIVED`). When both an explicit margin and its components are present, they must agree." `ProductEconomics` also keeps `unit_cogs` unset rather than zero-filled when unknown, since "zero and unknown are not the same claim" — the same missingness discipline [Field Availability](./field-availability.md) applies elsewhere in this module, expressed here as a plain optional field rather than a five-state enum.

### Relationship to legacy_adapters.py

No function in `modules/mta_common/src/legacy_adapters.py` reads, produces, or accepts a `MarginSource` value; the module does not import it, and no adapter function constructs a `ProductEconomics` today.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None. `product.py`'s module docstring states `ProductEconomics` "is entirely new: no field it defines has a populated source today." `dashboard/models.py` has no price, cost-of-goods, or margin field; `modules/mta_strategy_recommendation` treats `sku_id`/`sku_ids` as forbidden output fields; `docs/en/market-simulation/product-data-model.md` documents an external, unconnected `msproduct` schema with a `sku.specification_profit` field that is historical reference material, not data this pipeline reads.

### Canonical Conversion

None. `legacy_adapters.py` does not import `MarginSource` or `ProductEconomics`; no adapter function in this repository constructs a `ProductEconomics` from a legacy source today.

### Information Loss

Not applicable. There is no legacy source and no adapter, so there is no conversion in which information could be lost.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.product import ProductEconomics
from modules.mta_common.src.enums import MarginSource

# DERIVED requires both components; the derived value must agree with any
# separately given unit_contribution_margin within 1e-6.
economics = ProductEconomics(
    product_id="PRODUCT_1",
    currency="USD",
    unit_price=19.99,
    unit_cogs=8.50,
    unit_contribution_margin=11.49,
    margin_source=MarginSource.DERIVED,
)

# An EXPLICIT margin given without price or cost is valid on its own.
ProductEconomics(
    product_id="PRODUCT_2",
    currency="USD",
    unit_contribution_margin=5.00,
    margin_source=MarginSource.EXPLICIT,
)

# Raises ValueError: an EXPLICIT margin that contradicts price minus cost
# is rejected even though margin_source is not DERIVED.
ProductEconomics(
    product_id="PRODUCT_3",
    currency="USD",
    unit_price=20.00,
    unit_cogs=10.00,
    unit_contribution_margin=5.00,
    margin_source=MarginSource.EXPLICIT,
)
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future `MAXIMIZE_PROFIT` optimizer (see [Strategy Objective](./strategy-objective.md)) would read `ProductEconomics.unit_contribution_margin` to convert attributed units into profit, and could use `margin_source` to decide how much to trust that value — for example, preferring `EXPLICIT` margins from a source of record over `DERIVED` values computed from separately sourced price and cost fields that might not be contemporaneous. No optimizer exists in this repository today; this paragraph describes an intended future reader's semantics, not a guarantee enforced by `ProductEconomics` or any other class here.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/enums.py`, referenced as an optional field type by `ProductEconomics` in `modules/mta_common/src/product.py`, and exercised by `modules/mta_common/tests/test_product_and_economics.py`, including the together-required, `DERIVED`-requires-both-components, and agreement-tolerance validation rules.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No current pipeline component populates `ProductEconomics`, so no record in this repository carries a `MarginSource` value today outside of tests.
- The `1e-6` agreement tolerance is a fixed constant in `product.py`, not configurable per currency or per caller; a source reporting margins rounded to a coarser precision than that tolerance could be rejected even when its rounding is legitimate.
- `MarginSource` is an `enum.StrEnum`, one of seven vocabularies in `enums.py` that make up this repository's only use of the `Enum` family outside `modules/mta_common/`. Every other canonical class here is a plain `@dataclass(frozen=True)`; `StrEnum` was chosen for these seven vocabularies specifically so `MarginSource` and the rest are not restated as ad-hoc string literals across the classes that reference them, at the cost of introducing a dependency the rest of this repository deliberately avoids.
