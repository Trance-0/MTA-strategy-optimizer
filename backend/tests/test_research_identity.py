"""Verify research identity projection for strict dashboard history comparisons."""
import unittest
from backend.repository.research import _flatten_observation

class ResearchIdentityTests(unittest.TestCase):
    def test_scope_identity_and_measured_zero_are_preserved(self):
        result = _flatten_observation({"budget_level": 0, "advertiser_id": "top",
            "reporting_scope": {"marketplace": "UK", "campaign_id": "c", "product_id": "p", "advertiser_id": "scope", "budget_level": 2}})
        self.assertEqual(result["advertiser_id"], "scope")
        self.assertEqual(result["budget_level"], 0)
        self.assertEqual((result["marketplace"], result["campaign_id"], result["product_id"]), ("UK", "c", "p"))

    def test_touchpoint_fallback_and_missing_identifiers(self):
        self.assertEqual(_flatten_observation({"touchpoint": {"advertiser_id": "a"}})["advertiser_id"], "a")
        result = _flatten_observation({})
        for field in ("advertiser_id", "campaign_id", "product_id", "marketplace", "budget_level"):
            self.assertIsNone(result[field])
