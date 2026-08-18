"""Delivery metrics for one Touchpoint within one reporting scope.

Corresponds to today's ``TouchpointSpend`` in
``modules/mta_attribution/src/attribution_contract.py``: impressions, clicks,
and cost keyed by touchpoint. That existing type is campaign-agnostic (it is
never joined to a campaign's budget) and untyped for provider; this class
keeps the same fields but attaches a canonical ``Touchpoint`` and a
``ReportingScope`` instead of a bare touchpoint-key string, and makes
non-billable metrics ``None`` instead of implicitly zero.

Data flow: ``legacy_adapters.delivery_observation_from_touchpoint_spend``
adapts today's ``TouchpointSpend`` rows into this shape.
``AttributionEvidence`` and ``OutcomeObservation`` reference the same
``Touchpoint``/``ReportingScope`` pair so the three can be joined.
"""

from __future__ import annotations

from dataclasses import dataclass

from .reporting_scope import ReportingScope
from .touchpoint import Touchpoint


@dataclass(frozen=True)
class DeliveryObservation:
    """Impressions, clicks, and cost observed for one Touchpoint.

    ``impressions`` and ``clicks`` are mutually exclusive per the existing
    Amazon Ads contract: a ``CLICK`` touchpoint's cost is billed per click
    and never carries an impression count, and an ``IMPRESSION`` touchpoint's
    cost is billed per impression and never carries a click count. Rather
    than encoding the non-billed metric as zero, this class leaves it
    ``None``, since zero clicks observed and clicks not applicable to this
    interaction type are different claims.

    Attributes:
        touchpoint: The observed ``Touchpoint``.
        reporting_scope: Account, market, currency, and window this
            observation covers.
        impressions: Observed impression count, or ``None`` when not
            applicable to this touchpoint's ``interaction_type``.
        clicks: Observed click count, or ``None`` when not applicable to
            this touchpoint's ``interaction_type``.
        cost: Observed spend attributed to this touchpoint.
        reported_purchases: Platform-reported purchase count, mirroring
            ``TouchpointSpend.reported_purchases``.
        reported_sales: Platform-reported sales value, mirroring
            ``TouchpointSpend.reported_sales``.
    """

    touchpoint: Touchpoint
    reporting_scope: ReportingScope
    cost: float
    reported_purchases: int
    reported_sales: float
    impressions: int | None = None
    clicks: int | None = None

    def __post_init__(self) -> None:
        if self.cost < 0:
            raise ValueError("cost must not be negative")
        if self.reported_purchases < 0:
            raise ValueError("reported_purchases must not be negative")
        if self.reported_sales < 0:
            raise ValueError("reported_sales must not be negative")
        if self.impressions is not None and self.impressions < 0:
            raise ValueError("impressions must not be negative")
        if self.clicks is not None and self.clicks < 0:
            raise ValueError("clicks must not be negative")
