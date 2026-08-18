"""Tests for Campaign and AdGroup.

Covers: blank required-field rejection on both classes, AdGroup's
budget_seed_share bound and non-negative initial_daily_budget checks, and
that a fully populated instance of each is constructible.
"""

from __future__ import annotations

import unittest

from modules.mta_common.src.campaign import AdGroup, Campaign
from modules.mta_common.src.enums import Provider
from modules.mta_common.src.reporting_scope import ReportingScope


def _scope(**overrides: object) -> ReportingScope:
    fields = {
        "marketplace": "US",
        "advertiser_id": "ADV-1",
        "currency": "USD",
        "report_start_date": "2026-01-01",
        "report_end_date": "2026-01-31",
    }
    fields.update(overrides)
    return ReportingScope(**fields)


def _campaign(**overrides: object) -> Campaign:
    fields = {
        "campaign_id": "CAMP-1",
        "campaign_name": "Campaign One",
        "provider": Provider.AMAZON_ADS,
        "ad_product": "SPONSORED_PRODUCTS",
        "status": "enabled",
        "reporting_scope": _scope(),
    }
    fields.update(overrides)
    return Campaign(**fields)


class CampaignTests(unittest.TestCase):
    def test_fully_populated_campaign_is_constructible(self) -> None:
        campaign = _campaign()
        self.assertEqual(campaign.campaign_id, "CAMP-1")
        self.assertEqual(campaign.provider, Provider.AMAZON_ADS)

    def test_blank_campaign_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _campaign(campaign_id="  ")

    def test_blank_campaign_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _campaign(campaign_name="")

    def test_blank_ad_product_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _campaign(ad_product="")

    def test_blank_status_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _campaign(status="")

    def test_ad_product_is_not_restricted_to_a_fixed_vocabulary(self) -> None:
        # Campaign itself imposes no closed ad_product vocabulary; enforcing
        # one against ProviderCapabilities is the caller's responsibility.
        campaign = _campaign(ad_product="SOME_FUTURE_PRODUCT")
        self.assertEqual(campaign.ad_product, "SOME_FUTURE_PRODUCT")


def _ad_group(**overrides: object) -> AdGroup:
    fields = {
        "ad_group_id": "AG-1",
        "campaign_id": "CAMP-1",
    }
    fields.update(overrides)
    return AdGroup(**fields)


class AdGroupTests(unittest.TestCase):
    def test_minimal_ad_group_is_constructible(self) -> None:
        ad_group = _ad_group()
        self.assertIsNone(ad_group.allocation_basis)
        self.assertIsNone(ad_group.budget_seed_share)
        self.assertIsNone(ad_group.initial_daily_budget)

    def test_fully_populated_ad_group_is_constructible(self) -> None:
        ad_group = _ad_group(
            allocation_basis="EQUAL_SPLIT",
            budget_seed_share=0.25,
            initial_daily_budget=50.0,
        )
        self.assertEqual(ad_group.budget_seed_share, 0.25)

    def test_blank_ad_group_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _ad_group(ad_group_id="")

    def test_blank_campaign_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _ad_group(campaign_id="   ")

    def test_budget_seed_share_above_one_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _ad_group(budget_seed_share=1.5)

    def test_budget_seed_share_below_zero_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _ad_group(budget_seed_share=-0.1)

    def test_negative_initial_daily_budget_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _ad_group(initial_daily_budget=-1.0)


if __name__ == "__main__":
    unittest.main()
