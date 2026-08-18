"""The canonical, provider-independent touchpoint and its field availability.

``Touchpoint`` replaces the ``AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:
INTERACTION_TYPE`` string key as the fundamental type: every field is a typed
attribute with an explicit provider and an explicit per-field availability,
instead of an opaque colon-joined string with an ``UNSPECIFIED`` fallback.
The five-segment string key is still produced and parsed for the existing
modules that require it, by ``legacy_adapters.py``, never by this file.

Data flow: a provider-specific loader builds a ``Touchpoint`` directly, or
``legacy_adapters.touchpoint_from_five_segment_key`` adapts an existing AMC
row. Both paths converge here before reaching ``AttributionEvidence``,
``DeliveryObservation``, or ``OutcomeObservation``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import FieldAvailability, Provider


@dataclass(frozen=True)
class TouchpointFieldAvailability:
    """Per-record availability of Touchpoint's three optional fields.

    Distinct from ``ProviderCapabilities``, which declares what a provider
    can support in general. This dataclass declares what one specific
    touchpoint instance actually carries, which may be more restrictive than
    the provider's ceiling but never claim availability the provider does
    not support.

    Attributes:
        placement: Availability of this touchpoint's ``placement`` value.
        creative: Availability of this touchpoint's ``creative`` value.
        interaction_type: Availability of this touchpoint's
            ``interaction_type`` value.
    """

    placement: FieldAvailability
    creative: FieldAvailability
    interaction_type: FieldAvailability

    @classmethod
    def all_available(cls) -> "TouchpointFieldAvailability":
        """Convenience constructor for a touchpoint with no missing fields."""
        return cls(
            placement=FieldAvailability.AVAILABLE,
            creative=FieldAvailability.AVAILABLE,
            interaction_type=FieldAvailability.AVAILABLE,
        )


@dataclass(frozen=True)
class Touchpoint:
    """One canonical, provider-independent advertising touchpoint.

    Attributes:
        provider: The advertising platform this touchpoint was delivered on.
        ad_product: The provider-specific advertising product, for example
            ``SPONSORED_PRODUCTS``. Validated against a
            ``ProviderCapabilities.supported_ad_products`` by callers that
            hold one; this class does not require a ``ProviderCapabilities``
            to construct a ``Touchpoint``.
        format: The ad format or inventory type. Required; unlike placement,
            creative, and interaction_type, no supported provider omits it.
        placement: Where the ad appeared, or ``None`` when unavailable.
        creative: The creative type, or ``None`` when unavailable.
        interaction_type: The billable interaction, typically ``CLICK`` or
            ``IMPRESSION``, or ``None`` when unavailable.
        field_availability: Why each optional field is or is not populated.
    """

    provider: Provider
    ad_product: str
    format: str
    placement: str | None
    creative: str | None
    interaction_type: str | None
    field_availability: TouchpointFieldAvailability

    def __post_init__(self) -> None:
        if not str(self.ad_product).strip():
            raise ValueError("ad_product is required")
        if not str(self.format).strip():
            raise ValueError("format is required")
        _require_consistent(
            self.placement, self.field_availability.placement, "placement"
        )
        _require_consistent(
            self.creative, self.field_availability.creative, "creative"
        )
        _require_consistent(
            self.interaction_type,
            self.field_availability.interaction_type,
            "interaction_type",
        )


def _require_consistent(
    value: str | None, availability: FieldAvailability, field: str
) -> None:
    """Enforce that a value is present if and only if it is marked AVAILABLE.

    Every non-``AVAILABLE`` state (``NOT_APPLICABLE``, ``NOT_PROVIDED``,
    ``UNKNOWN``, ``REDACTED``) requires ``value is None``. This keeps the
    five states distinguishable in the ``field_availability`` tag while
    still rejecting an inconsistent record, rather than inferring the tag
    from whether ``value`` happens to be ``None``.
    """
    if availability == FieldAvailability.AVAILABLE and value is None:
        raise ValueError(f"{field} is marked AVAILABLE but has no value")
    if availability != FieldAvailability.AVAILABLE and value is not None:
        raise ValueError(f"{field} is marked {availability.value} but carries a value")
