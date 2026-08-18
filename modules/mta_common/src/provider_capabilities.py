"""Per-provider declaration of which Touchpoint fields exist and are supplied.

``ProviderCapabilities`` is a static, provider-level ceiling: it states
whether a field is meaningful for a provider's ad products at all
(``NOT_APPLICABLE``) or meaningful but sometimes withheld (``AVAILABLE`` as
the default expectation, ``NOT_PROVIDED`` when the provider's reporting
never includes it). ``TouchpointFieldAvailability`` in ``touchpoint.py`` is
the per-record realization; it may be more restrictive than the provider
ceiling but must never claim availability the provider does not support.

Data flow: a provider adapter selects one ``ProviderCapabilities`` constant,
then tags every ``Touchpoint`` it builds with a ``TouchpointFieldAvailability``
consistent with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import FieldAvailability, Provider


@dataclass(frozen=True)
class ProviderCapabilities:
    """Declares, for one Provider, which Touchpoint fields it can supply.

    Attributes:
        provider: The provider this declaration describes.
        supported_ad_products: The closed vocabulary of ``ad_product``
            values this provider can report. Not every provider shares
            Amazon Ads' four-product vocabulary.
        format_availability: Default availability of the ``format`` field.
        placement_availability: Default availability of the ``placement``
            field.
        creative_availability: Default availability of the ``creative``
            field.
        interaction_type_availability: Default availability of the
            ``interaction_type`` field.
    """

    provider: Provider
    supported_ad_products: tuple[str, ...]
    format_availability: FieldAvailability
    placement_availability: FieldAvailability
    creative_availability: FieldAvailability
    interaction_type_availability: FieldAvailability

    def __post_init__(self) -> None:
        if not self.supported_ad_products:
            raise ValueError("supported_ad_products must not be empty")
        if len(set(self.supported_ad_products)) != len(self.supported_ad_products):
            raise ValueError("supported_ad_products must not repeat")


# Matches the four-product vocabulary hardcoded today in
# modules/mta_strategy_recommendation/src/budget_recommender.py's
# SUPPORTED_AD_PRODUCTS. Declaring it here does not yet make the strategy
# module read it; see docs/en/introduction/data-models/provider-capabilities.md
# for the migration note.
AMAZON_ADS_CAPABILITIES = ProviderCapabilities(
    provider=Provider.AMAZON_ADS,
    supported_ad_products=(
        "SPONSORED_PRODUCTS",
        "SPONSORED_BRANDS",
        "SPONSORED_DISPLAY",
        "AMAZON_DSP",
    ),
    format_availability=FieldAvailability.AVAILABLE,
    placement_availability=FieldAvailability.AVAILABLE,
    creative_availability=FieldAvailability.AVAILABLE,
    interaction_type_availability=FieldAvailability.AVAILABLE,
)

# Demonstrates that the contract is generic, not Amazon-specific. No adapter
# exists for a real platform matching this profile; it exists only so tests
# and documentation can show a provider whose delivery reporting omits
# placement and creative detail entirely, unlike Amazon Ads.
GENERIC_CAPABILITIES = ProviderCapabilities(
    provider=Provider.GENERIC,
    supported_ad_products=("DISPLAY", "SEARCH"),
    format_availability=FieldAvailability.AVAILABLE,
    placement_availability=FieldAvailability.NOT_PROVIDED,
    creative_availability=FieldAvailability.NOT_PROVIDED,
    interaction_type_availability=FieldAvailability.AVAILABLE,
)
