"""Tests for the canonical Touchpoint and its per-field availability.

Covers: provider is separate from ad_product, NOT_APPLICABLE and
NOT_PROVIDED remain distinguishable (not collapsed), and value/availability
consistency is enforced structurally rather than left to convention.
"""

from __future__ import annotations

import unittest

from modules.mta_common.src.enums import FieldAvailability, Provider
from modules.mta_common.src.touchpoint import Touchpoint, TouchpointFieldAvailability


def _touchpoint(**overrides: object) -> Touchpoint:
    fields = {
        "provider": Provider.AMAZON_ADS,
        "ad_product": "SPONSORED_PRODUCTS",
        "format": "SP",
        "placement": "TOP_OF_SEARCH",
        "creative": "VIDEO",
        "interaction_type": "CLICK",
        "field_availability": TouchpointFieldAvailability.all_available(),
    }
    fields.update(overrides)
    return Touchpoint(**fields)


class ProviderAdProductSeparationTests(unittest.TestCase):
    def test_provider_and_ad_product_are_independent_fields(self) -> None:
        amazon = _touchpoint(provider=Provider.AMAZON_ADS, ad_product="SPONSORED_PRODUCTS")
        generic = _touchpoint(provider=Provider.GENERIC, ad_product="DISPLAY")
        self.assertNotEqual(amazon.provider, generic.provider)
        self.assertNotEqual(amazon.ad_product, generic.ad_product)

    def test_same_ad_product_string_can_differ_by_provider(self) -> None:
        one = _touchpoint(provider=Provider.AMAZON_ADS, ad_product="DISPLAY")
        two = _touchpoint(provider=Provider.GENERIC, ad_product="DISPLAY")
        self.assertEqual(one.ad_product, two.ad_product)
        self.assertNotEqual(one.provider, two.provider)


class FieldAvailabilityConsistencyTests(unittest.TestCase):
    def test_not_applicable_and_not_provided_are_distinguishable(self) -> None:
        not_applicable = _touchpoint(
            placement=None,
            field_availability=TouchpointFieldAvailability(
                placement=FieldAvailability.NOT_APPLICABLE,
                creative=FieldAvailability.AVAILABLE,
                interaction_type=FieldAvailability.AVAILABLE,
            ),
        )
        not_provided = _touchpoint(
            placement=None,
            field_availability=TouchpointFieldAvailability(
                placement=FieldAvailability.NOT_PROVIDED,
                creative=FieldAvailability.AVAILABLE,
                interaction_type=FieldAvailability.AVAILABLE,
            ),
        )
        self.assertIsNone(not_applicable.placement)
        self.assertIsNone(not_provided.placement)
        self.assertNotEqual(
            not_applicable.field_availability.placement,
            not_provided.field_availability.placement,
        )

    def test_available_field_without_a_value_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _touchpoint(
                placement=None,
                field_availability=TouchpointFieldAvailability(
                    placement=FieldAvailability.AVAILABLE,
                    creative=FieldAvailability.AVAILABLE,
                    interaction_type=FieldAvailability.AVAILABLE,
                ),
            )

    def test_non_available_field_carrying_a_value_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _touchpoint(
                placement="TOP_OF_SEARCH",
                field_availability=TouchpointFieldAvailability(
                    placement=FieldAvailability.UNKNOWN,
                    creative=FieldAvailability.AVAILABLE,
                    interaction_type=FieldAvailability.AVAILABLE,
                ),
            )

    def test_redacted_field_must_still_have_no_value(self) -> None:
        with self.assertRaises(ValueError):
            _touchpoint(
                creative="VIDEO",
                field_availability=TouchpointFieldAvailability(
                    placement=FieldAvailability.AVAILABLE,
                    creative=FieldAvailability.REDACTED,
                    interaction_type=FieldAvailability.AVAILABLE,
                ),
            )


class RequiredFieldTests(unittest.TestCase):
    def test_blank_ad_product_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _touchpoint(ad_product="  ")

    def test_blank_format_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _touchpoint(format="")


if __name__ == "__main__":
    unittest.main()
