"""Tests for controlled vocabularies and provider capability declarations.

Covers: the five FieldAvailability states stay distinguishable rather than
collapsing to one UNSPECIFIED sentinel, StrategyObjective and
BudgetUsagePolicy are independent axes (all four combinations representable),
and ProviderCapabilities rejects an empty or duplicate ad-product vocabulary.
"""

from __future__ import annotations

import itertools
import unittest

from modules.mta_common.src.enums import (
    BudgetUsagePolicy,
    FieldAvailability,
    Provider,
    StrategyObjective,
)
from modules.mta_common.src.provider_capabilities import (
    AMAZON_ADS_CAPABILITIES,
    GENERIC_CAPABILITIES,
    ProviderCapabilities,
)


class FieldAvailabilityTests(unittest.TestCase):
    def test_five_states_are_distinct_values(self) -> None:
        values = {
            FieldAvailability.AVAILABLE,
            FieldAvailability.NOT_APPLICABLE,
            FieldAvailability.NOT_PROVIDED,
            FieldAvailability.UNKNOWN,
            FieldAvailability.REDACTED,
        }
        self.assertEqual(len(values), 5)

    def test_no_state_is_named_unspecified(self) -> None:
        names = {member.name for member in FieldAvailability}
        self.assertNotIn("UNSPECIFIED", names)


class StrategyObjectiveAndBudgetPolicyTests(unittest.TestCase):
    def test_two_independent_axes_are_all_representable(self) -> None:
        combinations = set(
            itertools.product(StrategyObjective, BudgetUsagePolicy)
        )
        self.assertEqual(len(combinations), 4)

    def test_enums_do_not_share_members(self) -> None:
        self.assertTrue(
            set(StrategyObjective).isdisjoint(set(BudgetUsagePolicy))
        )


class ProviderCapabilitiesTests(unittest.TestCase):
    def test_amazon_ads_and_generic_declare_different_ad_products(self) -> None:
        self.assertNotEqual(
            set(AMAZON_ADS_CAPABILITIES.supported_ad_products),
            set(GENERIC_CAPABILITIES.supported_ad_products),
        )

    def test_generic_capabilities_is_not_amazon_specific(self) -> None:
        self.assertEqual(GENERIC_CAPABILITIES.provider, Provider.GENERIC)
        self.assertNotIn(
            "SPONSORED_PRODUCTS", GENERIC_CAPABILITIES.supported_ad_products
        )
        self.assertEqual(
            GENERIC_CAPABILITIES.placement_availability,
            FieldAvailability.NOT_PROVIDED,
        )

    def test_empty_ad_product_vocabulary_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProviderCapabilities(
                provider=Provider.GENERIC,
                supported_ad_products=(),
                format_availability=FieldAvailability.AVAILABLE,
                placement_availability=FieldAvailability.AVAILABLE,
                creative_availability=FieldAvailability.AVAILABLE,
                interaction_type_availability=FieldAvailability.AVAILABLE,
            )

    def test_duplicate_ad_product_vocabulary_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProviderCapabilities(
                provider=Provider.GENERIC,
                supported_ad_products=("DISPLAY", "DISPLAY"),
                format_availability=FieldAvailability.AVAILABLE,
                placement_availability=FieldAvailability.AVAILABLE,
                creative_availability=FieldAvailability.AVAILABLE,
                interaction_type_availability=FieldAvailability.AVAILABLE,
            )


if __name__ == "__main__":
    unittest.main()
