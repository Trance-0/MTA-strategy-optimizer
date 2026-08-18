"""Canonical Campaign and Ad Group, independent of platform or product count.

Today's only representation of a Campaign is four required keys in
``strategy_request.json`` (`campaign_id`, `campaign_name`, `ad_product`,
`status`), and it is only ever valid inside a Campaign Group hardcoded to
exactly four Campaigns covering Amazon's four ad products
(``budget_recommender.py``'s ``SUPPORTED_AD_PRODUCTS`` and its "exactly 4
Campaigns" check). Ad Group only appears as a bridge key
(``entity.get("ad_group_id")``); it is never an addressable object. This
module's ``Campaign`` and ``AdGroup`` carry the same information without
either constraint, so a future provider or a Campaign Group of a different
shape can be represented without changing the type.

Data flow: a provider adapter builds ``Campaign``/``AdGroup`` from its native
schema, or ``legacy_adapters.py`` builds them from ``strategy_request.json``
and the initial-budget-recommendation output. Downstream, ``CampaignEpisode``
composes a ``Campaign`` with its budget, delivery, and outcome observations.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import Provider
from .reporting_scope import ReportingScope


@dataclass(frozen=True)
class Campaign:
    """One advertising campaign, independent of provider or product count.

    Attributes:
        campaign_id: Stable campaign identifier.
        campaign_name: Human-readable campaign name.
        provider: The advertising platform this campaign runs on.
        ad_product: Provider-specific advertising product, for example
            ``SPONSORED_PRODUCTS``. Not restricted to a fixed four-value
            vocabulary; validate against a ``ProviderCapabilities`` when one
            is available.
        status: Provider-reported campaign status string.
        reporting_scope: Account, market, currency, and window this
            campaign's identity was read from.
    """

    campaign_id: str
    campaign_name: str
    provider: Provider
    ad_product: str
    status: str
    reporting_scope: ReportingScope

    def __post_init__(self) -> None:
        for field_name in ("campaign_id", "campaign_name", "ad_product", "status"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required")


@dataclass(frozen=True)
class AdGroup:
    """One ad group belonging to exactly one Campaign.

    Attributes:
        ad_group_id: Stable ad group identifier, or a recommender-assigned
            slot identifier before the ad group is actually created.
        campaign_id: The owning ``Campaign.campaign_id``.
        allocation_basis: Optional description of how this ad group's budget
            share was derived, mirroring
            ``budget_recommender.py``'s ``allocation_basis`` output field.
        budget_seed_share: Optional fraction of the campaign's budget seed
            assigned to this ad group.
        initial_daily_budget: Optional recommended starting daily budget.
    """

    ad_group_id: str
    campaign_id: str
    allocation_basis: str | None = None
    budget_seed_share: float | None = None
    initial_daily_budget: float | None = None

    def __post_init__(self) -> None:
        if not str(self.ad_group_id).strip():
            raise ValueError("ad_group_id is required")
        if not str(self.campaign_id).strip():
            raise ValueError("campaign_id is required")
        if self.budget_seed_share is not None and not (0.0 <= self.budget_seed_share <= 1.0):
            raise ValueError("budget_seed_share must be between 0 and 1")
        if self.initial_daily_budget is not None and self.initial_daily_budget < 0:
            raise ValueError("initial_daily_budget must not be negative")
