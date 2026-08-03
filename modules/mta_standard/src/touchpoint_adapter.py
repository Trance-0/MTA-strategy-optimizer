from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping

from legacy_paths import ensure_amc_mta_src_on_path

ensure_amc_mta_src_on_path()

from amc_mta_attribution import NULL  # noqa: E402
from touchpoint_key import (  # noqa: E402
    canonical_touchpoint_key,
    canonicalize_touchpoint_key,
    touchpoint_key_from_ads_row,
)


FOUR_SEGMENT_COUNT = 4
FIVE_SEGMENT_COUNT = 5

# MTA-SIM bills a touchpoint by cost type; this repository encodes the same
# distinction as the fifth key segment. The mapping is the only sanctioned
# bridge between the two contracts and is never inferred from delivery metrics.
COST_TYPE_TO_INTERACTION: Mapping[str, str] = MappingProxyType(
    {
        "CPC": "CLICK",
        "CPM": "IMPRESSION",
    }
)

# Component-level rules (ASCII, uppercase, underscore, UNSPECIFIED defaults)
# live in touchpoint_key. A four-segment key is validated by appending this
# placeholder, reusing that validator, and dropping the placeholder again, so
# the rules are never restated here.
_PLACEHOLDER_INTERACTION = "CLICK"


def canonical_four_segment_key(
    ad_product: object,
    format_value: object,
    placement: object = None,
    creative: object = None,
) -> str:
    """Build MTA-SIM's canonical ``AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE`` key.

    Args:
        ad_product: Advertising product; required.
        format_value: Ad format (``adType`` or ``inventoryType``); required.
        placement: Placement; blank becomes ``UNSPECIFIED``.
        creative: Creative type; blank becomes ``UNSPECIFIED``.

    Returns:
        str: The canonical four-segment touchpoint key.

    Raises:
        ValueError: if any component violates the shared component rules.
    """
    five = canonical_touchpoint_key(
        ad_product, format_value, placement, creative, _PLACEHOLDER_INTERACTION
    )
    return five.rsplit(":", 1)[0]


def canonicalize_four_segment_key(value: object) -> str:
    """Validate and canonicalize an existing four-segment key string.

    Unlike :func:`canonical_four_segment_key`, every component must already be
    present; a blank component is a contract violation rather than an implicit
    ``UNSPECIFIED``.

    Args:
        value: The four-segment key as written in MTA-SIM data.

    Returns:
        str: The canonical four-segment touchpoint key.

    Raises:
        ValueError: if the key is blank, has a segment count other than four,
            or contains an empty or non-conforming component.
    """
    if value is None or not str(value).strip():
        raise ValueError("four-segment touchpoint key is required")
    text = str(value).strip()
    if len(text.split(":")) != FOUR_SEGMENT_COUNT:
        raise ValueError(
            "four-segment touchpoint key must contain exactly four "
            f"colon-separated components: {value!r}"
        )
    five = canonicalize_touchpoint_key(f"{text}:{_PLACEHOLDER_INTERACTION}")
    return five.rsplit(":", 1)[0]


def to_four_segment(five_segment_key: object) -> str:
    """Reduce a five-segment repository key to MTA-SIM's four-segment grain.

    Args:
        five_segment_key: A canonical five-segment touchpoint key.

    Returns:
        str: The key with its ``INTERACTION_TYPE`` segment removed.

    Raises:
        ValueError: if the input is not a canonical five-segment key.
    """
    return canonicalize_touchpoint_key(five_segment_key).rsplit(":", 1)[0]


def four_segment_key_from_ads_row(
    row: Mapping[str, object], *, row_number: int | None = None
) -> str:
    """Derive the four-segment key from an MTA-SIM daily performance row.

    The choice of format column is product-specific (``inventoryType`` for
    ``AMAZON_DSP``, ``adType`` for ``SPONSORED_*``). That rule already exists in
    ``touchpoint_key.touchpoint_key_from_ads_row``, so it is reused here with a
    placeholder interaction segment that is dropped again, rather than restated.

    Args:
        row: One ``amazon_ads_daily_touchpoint_performance`` row.
        row_number: One-based CSV row number used in error messages.

    Returns:
        str: The canonical four-segment touchpoint key for the row.

    Raises:
        ValueError: if the product is unsupported or a component is invalid.

    Invariants:
        The stored ``normalizedTouchpoint`` is not consulted; callers compare it
        against this derived value themselves.
    """
    probe = {**dict(row), "interaction_type": _PLACEHOLDER_INTERACTION}
    five = touchpoint_key_from_ads_row(
        probe, row_number=row_number, verify_stored=False
    )
    return five.rsplit(":", 1)[0]


@dataclass(frozen=True)
class SimulatorConfig:
    """Explicit simulator billing configuration for key adaptation.

    MTA-SIM's ``amazon_ads_daily_touchpoint_performance`` table carries neither
    ``interaction_type`` nor ``cost_type``, so the fifth segment cannot be
    recovered from the data alone. This configuration supplies it explicitly and
    is rejected outright when it is missing, ambiguous, or colliding.

    Attributes:
        cost_type_by_touchpoint: Canonical four-segment key -> ``CPC``/``CPM``.
    """

    cost_type_by_touchpoint: Mapping[str, str]

    @classmethod
    def from_mapping(cls, raw: Mapping[object, object]) -> "SimulatorConfig":
        """Validate and canonicalize a raw cost-type mapping.

        Args:
            raw: Mapping of four-segment touchpoint keys to cost types. Keys may
                use any casing accepted by the shared component rules.

        Returns:
            SimulatorConfig: An immutable, canonicalized configuration.

        Raises:
            ValueError: if the mapping is empty, a key is not a valid
                four-segment key, a cost type is not exactly ``CPC`` or ``CPM``
                (ambiguous), or two raw keys canonicalize to the same key
                (colliding).
        """
        if not raw:
            raise ValueError("simulator configuration must define at least one cost type")

        resolved: dict[str, str] = {}
        sources: dict[str, object] = {}
        for key, cost_type in raw.items():
            canonical = canonicalize_four_segment_key(key)
            text = "" if cost_type is None else str(cost_type).strip().upper()
            if text not in COST_TYPE_TO_INTERACTION:
                allowed = ", ".join(sorted(COST_TYPE_TO_INTERACTION))
                raise ValueError(
                    f"simulator cost_type for {canonical} must be one of {allowed}; "
                    f"got {cost_type!r}"
                )
            if canonical in resolved:
                raise ValueError(
                    "colliding simulator cost_type mapping; "
                    f"{sources[canonical]!r} and {key!r} both canonicalize to "
                    f"{canonical} (existing={resolved[canonical]}, new={text})"
                )
            resolved[canonical] = text
            sources[canonical] = key
        return cls(cost_type_by_touchpoint=MappingProxyType(dict(resolved)))

    def cost_type_for(self, four_segment_key: object) -> str:
        """Return the configured cost type for a four-segment key.

        Args:
            four_segment_key: A four-segment touchpoint key.

        Returns:
            str: ``CPC`` or ``CPM``.

        Raises:
            ValueError: if the key is invalid or has no configured mapping.
        """
        canonical = canonicalize_four_segment_key(four_segment_key)
        try:
            return self.cost_type_by_touchpoint[canonical]
        except KeyError as exc:
            raise ValueError(
                f"missing simulator cost_type mapping for touchpoint {canonical}"
            ) from exc

    def interaction_type_for(self, four_segment_key: object) -> str:
        """Return the fifth key segment implied by the configured cost type.

        Args:
            four_segment_key: A four-segment touchpoint key.

        Returns:
            str: ``CLICK`` or ``IMPRESSION``.

        Raises:
            ValueError: if the key is invalid or has no configured mapping.
        """
        return COST_TYPE_TO_INTERACTION[self.cost_type_for(four_segment_key)]

    def to_five_segment(self, four_segment_key: object) -> str:
        """Expand a four-segment key to this repository's five-segment key.

        Args:
            four_segment_key: A four-segment touchpoint key.

        Returns:
            str: The canonical five-segment key.

        Raises:
            ValueError: if the key is invalid or has no configured mapping.
        """
        canonical = canonicalize_four_segment_key(four_segment_key)
        return f"{canonical}:{self.interaction_type_for(canonical)}"

    def adapt_path(self, path: object) -> str:
        """Expand every touchpoint in an MTA-SIM path to five segments.

        Args:
            path: A ``' > '``-separated four-segment path.

        Returns:
            str: The same ordered path expressed with five-segment keys.

        Raises:
            ValueError: if the path is blank, contains an empty touchpoint, or
                contains a touchpoint without a configured mapping.

        Invariants:
            Touchpoint order and repetition are preserved exactly; only the key
            grain changes. The reserved ``Null`` terminal state is passed
            through unchanged so that downstream contract validation, not the
            adapter, decides whether its position is legal.
        """
        if path is None or not str(path).strip():
            raise ValueError("path is required")
        parts = str(path).split(">")
        if any(not part.strip() for part in parts):
            raise ValueError(f"path contains an empty touchpoint: {path!r}")
        return " > ".join(
            NULL if part.strip() == NULL else self.to_five_segment(part)
            for part in parts
        )

    def assert_reversible(self, four_segment_keys: Iterable[object]) -> None:
        """Verify that key adaptation is a bijection over the given keys.

        Args:
            four_segment_keys: The four-segment keys observed in a dataset.

        Raises:
            ValueError: if a key has no mapping, if the four-to-five expansion
                is not round-trip identical, or if two distinct four-segment
                keys expand to the same five-segment key.

        Invariants:
            A dataset that passes may be converted to five segments for the
            existing models and back to four segments for standard output
            without any loss of information.
        """
        seen: dict[str, str] = {}
        for key in four_segment_keys:
            canonical = canonicalize_four_segment_key(key)
            five = self.to_five_segment(canonical)
            restored = to_four_segment(five)
            if restored != canonical:
                raise ValueError(
                    f"key adaptation is not reversible for {canonical}: got {restored}"
                )
            if five in seen and seen[five] != canonical:
                raise ValueError(
                    "colliding key adaptation; "
                    f"{seen[five]} and {canonical} both expand to {five}"
                )
            seen[five] = canonical
