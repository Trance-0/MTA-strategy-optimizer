"""Canonical product identity, economics, and Campaign relationship values.

The market-simulation adapter constructs these provider-independent records
from MTA-SIM research snapshots. Legacy strategy input has no identified
product source and therefore does not fabricate them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .enums import MarginSource, Provider


@dataclass(frozen=True)
class Product:
    """A business product, identified independently of any ad platform.

    Attributes:
        product_id: Stable business identifier, for example a Global Trade
            Item Number or an internal product identifier. Not an
            Amazon-specific identifier requirement.
        provider_ad_identifiers: Provider-specific advertising identifiers
            for this product, for example ``{Provider.AMAZON_ADS: "ASIN..."}``.
            May be empty when the product is known but not yet linked to any
            advertising identity. Stored as an immutable mapping regardless
            of what mapping type the caller passes in.
        name: Optional display name.
        category: Optional product category.
        brand: Optional brand.
        status: Optional lifecycle status, for example ``ACTIVE`` or
            ``DISCONTINUED``.
    """

    product_id: str
    provider_ad_identifiers: Mapping[Provider, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    sku_id: str | None = None
    name: str | None = None
    category: str | None = None
    brand: str | None = None
    status: str | None = None
    inventory_units: int | None = None
    salable: bool | None = None

    def __post_init__(self) -> None:
        if not str(self.product_id).strip():
            raise ValueError("product_id is required")
        identifiers = dict(self.provider_ad_identifiers)
        if any(not str(value).strip() for value in identifiers.values()):
            raise ValueError("provider_ad_identifiers must not contain blank values")
        object.__setattr__(
            self,
            "provider_ad_identifiers",
            MappingProxyType(identifiers),
        )
        if self.inventory_units is not None and self.inventory_units < 0:
            raise ValueError("inventory_units must not be negative")


@dataclass(frozen=True)
class ProductEconomics:
    """A product's price and cost structure for one reporting scope.

    Missing cost-of-goods-sold stays missing (``unit_cogs is None``); it must
    never be zero-filled, since zero and unknown are not the same claim.
    ``unit_contribution_margin`` may be given directly
    (``margin_source=EXPLICIT``) or derived from ``unit_price`` and
    ``unit_cogs`` (``margin_source=DERIVED``). When both an explicit margin
    and its components are present, they must agree.

    Attributes:
        product_id: The ``Product.product_id`` this economics record
            describes.
        currency: Currency all monetary fields are denominated in.
        unit_price: Optional per-unit selling price.
        unit_cogs: Optional per-unit cost of goods sold. ``None`` means
            unknown, not zero.
        unit_contribution_margin: Optional per-unit contribution margin
            (price minus cost of goods sold, before any allocation of fixed
            or corporate overhead).
        margin_source: Whether ``unit_contribution_margin`` was given
            directly or derived from price and cost. Required whenever
            ``unit_contribution_margin`` is not ``None``.
    """

    product_id: str
    currency: str
    unit_price: float | None = None
    unit_cogs: float | None = None
    variable_cost_per_unit: float | None = None
    variable_fulfillment_cost_per_unit: float | None = None
    variable_platform_fee_per_unit: float | None = None
    other_variable_cost_per_unit: float | None = None
    unit_contribution_margin: float | None = None
    margin_source: MarginSource | None = None

    def __post_init__(self) -> None:
        if not str(self.product_id).strip():
            raise ValueError("product_id is required")
        if not str(self.currency).strip():
            raise ValueError("currency is required")
        if self.unit_price is not None and self.unit_price < 0:
            raise ValueError("unit_price must not be negative")
        if self.unit_cogs is not None and self.unit_cogs < 0:
            raise ValueError("unit_cogs must not be negative")
        for field_name in (
            "variable_cost_per_unit",
            "variable_fulfillment_cost_per_unit",
            "variable_platform_fee_per_unit",
            "other_variable_cost_per_unit",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} must not be negative")
        components = tuple(
            value
            for value in (
                self.variable_fulfillment_cost_per_unit,
                self.variable_platform_fee_per_unit,
                self.other_variable_cost_per_unit,
            )
            if value is not None
        )
        if (
            self.variable_cost_per_unit is not None
            and components
            and abs(self.variable_cost_per_unit - sum(components)) > 1e-6
        ):
            raise ValueError(
                "variable_cost_per_unit contradicts granular variable costs"
            )
        if (self.unit_contribution_margin is None) != (self.margin_source is None):
            raise ValueError(
                "unit_contribution_margin and margin_source must be given together"
            )
        if (
            self.margin_source == MarginSource.DERIVED
            and (self.unit_price is None or self.unit_cogs is None)
        ):
            raise ValueError(
                "margin_source=DERIVED requires both unit_price and unit_cogs"
            )
        if (
            self.unit_contribution_margin is not None
            and self.unit_price is not None
            and self.unit_cogs is not None
        ):
            implied = (
                self.unit_price
                - self.unit_cogs
                - self.represented_variable_cost_per_unit
            )
            if abs(implied - self.unit_contribution_margin) > 1e-6:
                raise ValueError(
                    "unit_contribution_margin contradicts unit_price minus "
                    "unit costs: "
                    f"given={self.unit_contribution_margin}, "
                    f"implied={implied}"
                )

    @property
    def represented_variable_cost_per_unit(self) -> float:
        """Return the aggregate cost, or the sum of supplied components."""

        if self.variable_cost_per_unit is not None:
            return self.variable_cost_per_unit
        return sum(
            value or 0.0
            for value in (
                self.variable_fulfillment_cost_per_unit,
                self.variable_platform_fee_per_unit,
                self.other_variable_cost_per_unit,
            )
        )


@dataclass(frozen=True)
class CampaignProductLink:
    """One edge of the many-to-many relationship between Campaign and Product.

    A Campaign may advertise several Products and a Product may be advertised
    by several Campaigns, so this is a first-class link object rather than a
    single product field on ``Campaign``.

    Attributes:
        campaign_id: The linked ``Campaign.campaign_id``.
        product_id: The linked ``Product.product_id``.
        eligibility_status: Reserved for a future targeting-eligibility
            state, for example ``ELIGIBLE`` or ``INELIGIBLE``. Not populated
            by any current data source.
        link_status: Reserved for a future link lifecycle state, for example
            ``ACTIVE`` or ``PAUSED``. Not populated by any current data
            source.
    """

    campaign_id: str
    product_id: str
    eligibility_status: str | None = None
    link_status: str | None = None

    def __post_init__(self) -> None:
        if not str(self.campaign_id).strip():
            raise ValueError("campaign_id is required")
        if not str(self.product_id).strip():
            raise ValueError("product_id is required")
