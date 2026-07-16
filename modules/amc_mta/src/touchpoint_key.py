from __future__ import annotations

import re
from typing import Mapping


UNSPECIFIED = "UNSPECIFIED"
INTERACTION_TYPES = frozenset({"IMPRESSION", "CLICK"})
_COMPONENT_PATTERN = re.compile(r"^[A-Z0-9_]+$")


def _component(value: object, field: str, *, allow_missing: bool = False) -> str:
    raw = "" if value is None else str(value).strip()
    if not raw:
        if allow_missing:
            return UNSPECIFIED
        raise ValueError(f"{field} is required")
    if not raw.isascii():
        raise ValueError(
            f"{field} must contain only ASCII letters, numbers, and underscores: {value!r}"
        )
    text = raw.upper()
    if not _COMPONENT_PATTERN.fullmatch(text):
        raise ValueError(
            f"{field} must contain only uppercase letters, numbers, and underscores: {value!r}"
        )
    return text


def canonical_touchpoint_key(
    ad_product: object,
    format_value: object,
    placement: object = None,
    creative: object = None,
    interaction_type: object = None,
) -> str:
    interaction = _component(interaction_type, "interaction_type")
    if interaction not in INTERACTION_TYPES:
        allowed = ", ".join(sorted(INTERACTION_TYPES))
        raise ValueError(f"interaction_type must be one of {allowed}: {interaction!r}")
    return ":".join(
        (
            _component(ad_product, "ad_product"),
            _component(format_value, "format"),
            _component(placement, "placement", allow_missing=True),
            _component(creative, "creative", allow_missing=True),
            interaction,
        )
    )


def canonicalize_touchpoint_key(value: object) -> str:
    if value is None or not str(value).strip():
        raise ValueError("touchpoint key is required")
    parts = str(value).strip().split(":")
    if len(parts) != 5:
        raise ValueError(
            f"touchpoint key must contain exactly five colon-separated components: {value!r}"
        )
    if any(not part.strip() for part in parts):
        raise ValueError(f"touchpoint key cannot contain empty components: {value!r}")
    return canonical_touchpoint_key(*parts)


def canonical_amc_touchpoint_key(
    ad_product: object,
    format_value: object,
    placement: object,
    creative: object,
    interaction_type: object,
) -> str:
    """Backward-compatible name for the canonical five-component key."""
    return canonical_touchpoint_key(
        ad_product, format_value, placement, creative, interaction_type
    )


def canonicalize_amc_touchpoint_key(value: object) -> str:
    """Backward-compatible validator name for the canonical five-part key."""
    return canonicalize_touchpoint_key(value)


def touchpoint_key_from_ads_row(
    row: Mapping[str, object],
    *,
    row_number: int | None = None,
    verify_stored: bool = True,
) -> str:
    prefix = f"Amazon Ads row {row_number}: " if row_number is not None else "Amazon Ads row: "
    try:
        ad_product = _component(row.get("adProduct"), "adProduct")
    except ValueError as exc:
        raise ValueError(f"{prefix}{exc}") from exc
    if ad_product == "AMAZON_DSP":
        format_value = row.get("inventoryType")
    elif ad_product.startswith("SPONSORED_"):
        format_value = row.get("adType")
    else:
        raise ValueError(f"{prefix}unsupported adProduct: {ad_product!r}")

    try:
        expected = canonical_amc_touchpoint_key(
            ad_product,
            format_value,
            row.get("placement"),
            row.get("creativeType"),
            row.get("interaction_type"),
        )
    except ValueError as exc:
        raise ValueError(f"{prefix}{exc}") from exc

    if verify_stored:
        actual_value = row.get("normalizedTouchpoint")
        if actual_value is None or not str(actual_value).strip():
            raise ValueError(f"{prefix}normalizedTouchpoint is required; expected {expected}")
        actual = str(actual_value).strip()
        if actual != expected:
            raise ValueError(
                f"{prefix}normalizedTouchpoint mismatch; expected {expected}, actual {actual}"
            )
    return expected
