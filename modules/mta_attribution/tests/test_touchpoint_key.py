"""Tests for the canonical touchpoint key and data alignment.

Covers component rules, the product-specific format column, `UNSPECIFIED`
fallbacks, and the alignment validator's checks on scope, report window, daily
coverage, and billing consistency.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from attribution_contract import (  # noqa: E402
    aggregate_spend_by_touchpoint  # noqa: E402,
)
from touchpoint_key import (  # noqa: E402
    canonical_touchpoint_key,
    canonicalize_touchpoint_key,
    touchpoint_key_from_ads_row,
)
from validate_data_alignment import (  # noqa: E402
    touchpoints_from_amc_path,
    validate_data_alignment_rows,
)


BASE = "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED"
IMPRESSION = f"{BASE}:IMPRESSION"
CLICK = f"{BASE}:CLICK"


def ads_row(day: str, interaction: str, cost_type: str, cost: str = "0") -> dict:
    click = interaction == "CLICK"
    return {
        "reportDate": day,
        "marketplace": "US",
        "accountId": "adv_test",
        "currencyCode": "USD",
        "adProduct": "SPONSORED_PRODUCTS",
        "adType": "PRODUCT_AD",
        "inventoryType": "",
        "placement": "TOP_OF_SEARCH",
        "creativeType": "",
        "interaction_type": interaction,
        "cost_type": cost_type,
        "normalizedTouchpoint": f"{BASE}:{interaction}",
        "impressions": "0" if click else "100",
        "clicks": "5" if click else "0",
        "cost": cost,
        "purchases": "1" if click else "0",
        "sales": "30" if click else "0",
    }


class TouchpointKeyTests(unittest.TestCase):
    def test_key_is_strictly_five_part(self) -> None:
        self.assertEqual(
            canonical_touchpoint_key(
                " sponsored_products ", " product_ad ", "top_of_search", None, "click"
            ),
            CLICK,
        )
        for value in (BASE, f"{BASE}:VIEW", "PRODUCT:FORMAT::CREATIVE:CLICK"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonicalize_touchpoint_key(value)

    def test_ads_key_uses_interaction_type_and_verifies_stored_key(self) -> None:
        self.assertEqual(touchpoint_key_from_ads_row(ads_row("2026-05-01", "CLICK", "CPC")), CLICK)
        bad = ads_row("2026-05-01", "CLICK", "CPC")
        bad["normalizedTouchpoint"] = IMPRESSION
        with self.assertRaisesRegex(ValueError, "normalizedTouchpoint mismatch"):
            touchpoint_key_from_ads_row(bad, row_number=2)

    def test_spend_keeps_interactions_separate_and_cost_unique(self) -> None:
        spend = aggregate_spend_by_touchpoint(
            [ads_row("2026-05-01", "IMPRESSION", "CPM"), ads_row("2026-05-01", "CLICK", "CPC", "10")]
        )
        self.assertEqual(set(spend), {IMPRESSION, CLICK})
        self.assertEqual(spend[IMPRESSION].cost, 0)
        self.assertEqual(spend[CLICK].cost, 10)
        self.assertEqual(spend[IMPRESSION].impressions, 100)
        self.assertEqual(spend[CLICK].clicks, 5)

    def test_rejects_billing_conflict_and_non_click_platform_outcomes(self) -> None:
        with self.assertRaisesRegex(ValueError, "conflicts"):
            aggregate_spend_by_touchpoint([ads_row("2026-05-01", "IMPRESSION", "CPC", "1")])
        with self.assertRaisesRegex(ValueError, "conflicts"):
            aggregate_spend_by_touchpoint([ads_row("2026-05-01", "IMPRESSION", "CPC")])
        row = ads_row("2026-05-01", "IMPRESSION", "CPM", "1")
        row["purchases"] = "1"
        with self.assertRaisesRegex(ValueError, "only for CLICK"):
            aggregate_spend_by_touchpoint([row])
        row = ads_row("2026-05-01", "CLICK", "CPC")
        row["impressions"] = "1"
        with self.assertRaisesRegex(ValueError, "only for IMPRESSION"):
            aggregate_spend_by_touchpoint([row])

    def test_alignment_compares_complete_five_part_keys_and_daily_coverage(self) -> None:
        amc = {
            "report_start_date": "2026-05-01",
            "report_end_date": "2026-05-02",
            "marketplace": "US",
            "advertiser_id": "adv_test",
            "path": f"{IMPRESSION} > {CLICK}",
            "users": "2",
            "converted_users": "1",
            "purchase_count": "1",
            "revenue": "10",
        }
        ads = [
            ads_row(day, interaction, "CPM" if interaction == "IMPRESSION" else "CPC")
            for day in ("2026-05-01", "2026-05-02")
            for interaction in ("IMPRESSION", "CLICK")
        ]
        summary = validate_data_alignment_rows([amc], ads)
        self.assertEqual(summary["amc_touchpoints"], 2)
        with self.assertRaisesRegex(ValueError, "incomplete daily touchpoint coverage"):
            validate_data_alignment_rows([amc], ads[:-1])

        with self.assertRaisesRegex(ValueError, "duplicate touchpoint/reportDate"):
            validate_data_alignment_rows([amc], [*ads, dict(ads[0])])

        conflict = [dict(row) for row in ads]
        conflict[0]["cost"] = "1"
        conflict[0]["cost_type"] = "CPC"
        with self.assertRaisesRegex(ValueError, "conflicts"):
            validate_data_alignment_rows([amc], conflict)

    def test_path_parser_preserves_interaction_identity(self) -> None:
        self.assertEqual(touchpoints_from_amc_path(f"{IMPRESSION} > {CLICK}"), {IMPRESSION, CLICK})


if __name__ == "__main__":
    unittest.main()
