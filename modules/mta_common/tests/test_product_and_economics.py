"""Tests for Product, ProductEconomics, and CampaignProductLink.

Covers: missing cost-of-goods stays missing rather than zero-filled, an
explicit margin that contradicts price minus cost is rejected, margin_source
requirements, and Campaign/Product as an explicit many-to-many relationship.
"""

from __future__ import annotations

import unittest

from modules.mta_common.src.enums import MarginSource, Provider
from modules.mta_common.src.product import (
    CampaignProductLink,
    Product,
    ProductEconomics,
)


class ProductIdentityTests(unittest.TestCase):
    def test_product_id_is_independent_of_provider_ad_identifiers(self) -> None:
        product = Product(
            product_id="SKU-001",
            provider_ad_identifiers={Provider.AMAZON_ADS: "B000000001"},
        )
        self.assertEqual(product.product_id, "SKU-001")
        self.assertEqual(product.provider_ad_identifiers[Provider.AMAZON_ADS], "B000000001")

    def test_product_with_no_advertising_identity_is_valid(self) -> None:
        product = Product(product_id="SKU-002")
        self.assertEqual(dict(product.provider_ad_identifiers), {})

    def test_provider_ad_identifiers_is_immutable(self) -> None:
        source = {Provider.AMAZON_ADS: "B000000001"}
        product = Product(product_id="SKU-003", provider_ad_identifiers=source)
        source[Provider.AMAZON_ADS] = "MUTATED"
        self.assertEqual(product.provider_ad_identifiers[Provider.AMAZON_ADS], "B000000001")
        with self.assertRaises(TypeError):
            product.provider_ad_identifiers["X"] = "Y"  # type: ignore[index]

    def test_blank_product_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Product(product_id="  ")


class ProductEconomicsMissingCogsTests(unittest.TestCase):
    def test_missing_cogs_stays_none_not_zero(self) -> None:
        economics = ProductEconomics(
            product_id="SKU-001", currency="USD", unit_price=19.99
        )
        self.assertIsNone(economics.unit_cogs)
        self.assertNotEqual(economics.unit_cogs, 0)

    def test_negative_cogs_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProductEconomics(product_id="SKU-001", currency="USD", unit_cogs=-1.0)


class ProductEconomicsMarginTests(unittest.TestCase):
    def test_explicit_margin_without_price_or_cogs_is_valid(self) -> None:
        economics = ProductEconomics(
            product_id="SKU-001",
            currency="USD",
            unit_contribution_margin=5.0,
            margin_source=MarginSource.EXPLICIT,
        )
        self.assertEqual(economics.unit_contribution_margin, 5.0)

    def test_margin_without_margin_source_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProductEconomics(
                product_id="SKU-001", currency="USD", unit_contribution_margin=5.0
            )

    def test_margin_source_without_margin_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProductEconomics(
                product_id="SKU-001",
                currency="USD",
                margin_source=MarginSource.EXPLICIT,
            )

    def test_derived_margin_requires_price_and_cogs(self) -> None:
        with self.assertRaises(ValueError):
            ProductEconomics(
                product_id="SKU-001",
                currency="USD",
                unit_price=10.0,
                unit_contribution_margin=4.0,
                margin_source=MarginSource.DERIVED,
            )

    def test_consistent_derived_margin_is_accepted(self) -> None:
        economics = ProductEconomics(
            product_id="SKU-001",
            currency="USD",
            unit_price=10.0,
            unit_cogs=6.0,
            unit_contribution_margin=4.0,
            margin_source=MarginSource.DERIVED,
        )
        self.assertAlmostEqual(economics.unit_contribution_margin, 4.0)

    def test_contradictory_margin_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProductEconomics(
                product_id="SKU-001",
                currency="USD",
                unit_price=10.0,
                unit_cogs=6.0,
                unit_contribution_margin=999.0,
                margin_source=MarginSource.EXPLICIT,
            )


class CampaignProductLinkTests(unittest.TestCase):
    def test_one_campaign_can_link_to_several_products(self) -> None:
        links = [
            CampaignProductLink(campaign_id="CAMP-1", product_id="SKU-001"),
            CampaignProductLink(campaign_id="CAMP-1", product_id="SKU-002"),
        ]
        self.assertEqual({link.product_id for link in links}, {"SKU-001", "SKU-002"})

    def test_one_product_can_link_to_several_campaigns(self) -> None:
        links = [
            CampaignProductLink(campaign_id="CAMP-1", product_id="SKU-001"),
            CampaignProductLink(campaign_id="CAMP-2", product_id="SKU-001"),
        ]
        self.assertEqual({link.campaign_id for link in links}, {"CAMP-1", "CAMP-2"})

    def test_blank_ids_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CampaignProductLink(campaign_id="", product_id="SKU-001")
        with self.assertRaises(ValueError):
            CampaignProductLink(campaign_id="CAMP-1", product_id="")


if __name__ == "__main__":
    unittest.main()
