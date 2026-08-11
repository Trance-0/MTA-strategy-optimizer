"""Tests for four-to-five segment key adaptation.

Covers component rules at the four-segment grain, round-trip reversibility, and
the three configuration failures that must be rejected rather than guessed:
missing, ambiguous, and colliding cost-type mappings.
"""

from __future__ import annotations

import unittest

from modules.mta_standard.src.touchpoint_adapter import (
    COST_TYPE_TO_INTERACTION,
    SimulatorConfig,
    canonical_four_segment_key,
    canonicalize_four_segment_key,
    four_segment_key_from_ads_row,
    to_four_segment,
)
from modules.mta_standard.tests import mta_sim_fixtures as fixtures


class CanonicalFourSegmentKeyTest(unittest.TestCase):
    def test_builds_key_from_components(self) -> None:
        self.assertEqual(
            canonical_four_segment_key(
                "sponsored_products", "product_ad", "top_of_search", "image"
            ),
            "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:IMAGE",
        )

    def test_blank_placement_and_creative_become_unspecified(self) -> None:
        self.assertEqual(
            canonical_four_segment_key("AMAZON_DSP", "OTT", "", None),
            "AMAZON_DSP:OTT:UNSPECIFIED:UNSPECIFIED",
        )

    def test_required_components_are_enforced(self) -> None:
        with self.assertRaises(ValueError):
            canonical_four_segment_key("", "OTT", "UNSPECIFIED", "VIDEO")

    def test_component_character_rules_are_inherited(self) -> None:
        with self.assertRaises(ValueError):
            canonical_four_segment_key("SPONSORED PRODUCTS", "PRODUCT_AD", "X", "Y")


class CanonicalizeFourSegmentKeyTest(unittest.TestCase):
    def test_uppercases_and_strips(self) -> None:
        self.assertEqual(
            canonicalize_four_segment_key("  amazon_dsp:ott:unspecified:video "),
            fixtures.DISPLAY,
        )

    def test_rejects_five_segment_key(self) -> None:
        with self.assertRaises(ValueError):
            canonicalize_four_segment_key(f"{fixtures.DISPLAY}:IMPRESSION")

    def test_rejects_three_segment_key(self) -> None:
        with self.assertRaises(ValueError):
            canonicalize_four_segment_key("AMAZON_DSP:OTT:UNSPECIFIED")

    def test_rejects_empty_component(self) -> None:
        with self.assertRaises(ValueError):
            canonicalize_four_segment_key("AMAZON_DSP::UNSPECIFIED:VIDEO")

    def test_rejects_blank(self) -> None:
        with self.assertRaises(ValueError):
            canonicalize_four_segment_key("   ")


class SimulatorConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = SimulatorConfig.from_mapping(fixtures.SIMULATOR_COST_TYPES)

    def test_cost_type_maps_to_interaction_type(self) -> None:
        self.assertEqual(COST_TYPE_TO_INTERACTION["CPC"], "CLICK")
        self.assertEqual(COST_TYPE_TO_INTERACTION["CPM"], "IMPRESSION")
        self.assertEqual(self.config.interaction_type_for(fixtures.SEARCH), "CLICK")
        self.assertEqual(self.config.interaction_type_for(fixtures.DISPLAY), "IMPRESSION")

    def test_rejects_missing_mapping(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing simulator cost_type"):
            self.config.to_five_segment("AMAZON_DSP:DISPLAY:UNSPECIFIED:IMAGE")

    def test_rejects_ambiguous_cost_type(self) -> None:
        for cost_type in ("CPX", "", None, "CLICK"):
            with self.subTest(cost_type=cost_type):
                with self.assertRaisesRegex(ValueError, "must be one of"):
                    SimulatorConfig.from_mapping({fixtures.SEARCH: cost_type})

    def test_rejects_colliding_mapping(self) -> None:
        with self.assertRaisesRegex(ValueError, "colliding simulator cost_type"):
            SimulatorConfig.from_mapping(
                {
                    fixtures.SEARCH: "CPC",
                    fixtures.SEARCH.lower(): "CPM",
                }
            )

    def test_rejects_empty_configuration(self) -> None:
        with self.assertRaises(ValueError):
            SimulatorConfig.from_mapping({})


class KeyAdaptationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = SimulatorConfig.from_mapping(fixtures.SIMULATOR_COST_TYPES)

    def test_round_trip_is_identity_for_every_configured_key(self) -> None:
        for four in fixtures.SIMULATOR_COST_TYPES:
            with self.subTest(touchpoint=four):
                five = self.config.to_five_segment(four)
                self.assertEqual(len(five.split(":")), 5)
                self.assertEqual(to_four_segment(five), four)

    def test_assert_reversible_accepts_the_fixture_touchpoints(self) -> None:
        self.config.assert_reversible(fixtures.SIMULATOR_COST_TYPES)

    def test_assert_reversible_rejects_unmapped_key(self) -> None:
        with self.assertRaises(ValueError):
            self.config.assert_reversible(["AMAZON_DSP:DISPLAY:UNSPECIFIED:IMAGE"])

    def test_adapt_path_preserves_order_and_repetition(self) -> None:
        path = f"{fixtures.SEARCH} > {fixtures.DISPLAY} > {fixtures.SEARCH}"
        self.assertEqual(
            self.config.adapt_path(path),
            " > ".join(
                (
                    f"{fixtures.SEARCH}:CLICK",
                    f"{fixtures.DISPLAY}:IMPRESSION",
                    f"{fixtures.SEARCH}:CLICK",
                )
            ),
        )

    def test_adapt_path_passes_null_through(self) -> None:
        self.assertEqual(
            self.config.adapt_path(f"{fixtures.SEARCH} > Null"),
            f"{fixtures.SEARCH}:CLICK > Null",
        )

    def test_adapt_path_rejects_empty_touchpoint(self) -> None:
        with self.assertRaises(ValueError):
            self.config.adapt_path(f"{fixtures.SEARCH} >  > {fixtures.DISPLAY}")


class AdsRowKeyTest(unittest.TestCase):
    def test_dsp_uses_inventory_type_as_format(self) -> None:
        row = {
            "adProduct": "AMAZON_DSP",
            "adType": "",
            "creativeType": "VIDEO",
            "inventoryType": "OTT",
            "placement": "",
        }
        self.assertEqual(four_segment_key_from_ads_row(row, row_number=2), fixtures.DISPLAY)

    def test_sponsored_products_uses_ad_type_as_format(self) -> None:
        row = {
            "adProduct": "SPONSORED_PRODUCTS",
            "adType": "PRODUCT_AD",
            "creativeType": "",
            "inventoryType": "",
            "placement": "TOP_OF_SEARCH",
        }
        self.assertEqual(four_segment_key_from_ads_row(row, row_number=2), fixtures.SEARCH)

    def test_rejects_unsupported_ad_product(self) -> None:
        row = {
            "adProduct": "UNKNOWN_PRODUCT",
            "adType": "PRODUCT_AD",
            "creativeType": "",
            "inventoryType": "",
            "placement": "TOP_OF_SEARCH",
        }
        with self.assertRaisesRegex(ValueError, "unsupported adProduct"):
            four_segment_key_from_ads_row(row, row_number=2)


if __name__ == "__main__":
    unittest.main()
