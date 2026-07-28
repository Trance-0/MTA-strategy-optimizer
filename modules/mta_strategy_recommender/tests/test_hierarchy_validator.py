from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT / "src"))

from hierarchy_validator import HierarchyValidationError, validate_simulated_hierarchy  # noqa: E402


SAMPLE_DIR = MODULE_ROOT / "data" / "simulated"


class HierarchyValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary.name) / "simulated"
        shutil.copytree(SAMPLE_DIR, self.data_dir)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _read_json(self, name: str) -> dict:
        with (self.data_dir / name).open(encoding="utf-8") as handle:
            return json.load(handle)

    def _write_json(self, name: str, value: dict) -> None:
        with (self.data_dir / name).open("w", encoding="utf-8") as handle:
            json.dump(value, handle)

    def _read_csv(self, name: str) -> tuple[list[str], list[dict[str, str]]]:
        with (self.data_dir / name).open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return list(reader.fieldnames or []), list(reader)

    def _write_csv(self, name: str, fields: list[str], rows: list[dict[str, str]]) -> None:
        with (self.data_dir / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_standard_sample_is_valid(self) -> None:
        summary = validate_simulated_hierarchy(self.data_dir)
        self.assertEqual(summary["campaign_count"], 4)
        self.assertEqual(summary["recommended_ad_group_count"], 6)
        self.assertTrue(summary["has_budget_baseline"])
        self.assertEqual(summary["recommendation_type"], "INITIAL_SEED")
        self.assertEqual(summary["warnings"], [])

    def test_campaign_count_must_be_four(self) -> None:
        fields, rows = self._read_csv("campaigns.csv")
        self._write_csv("campaigns.csv", fields, rows[:3])
        relationship_fields, relationship_rows = self._read_csv("campaign_group_relationships.csv")
        self._write_csv("campaign_group_relationships.csv", relationship_fields, relationship_rows[:3])
        with self.assertRaisesRegex(HierarchyValidationError, "exactly 4 campaigns"):
            validate_simulated_hierarchy(self.data_dir)

    def test_campaign_ad_product_is_required_and_scalar(self) -> None:
        fields, rows = self._read_csv("campaigns.csv")
        rows[0]["ad_product"] = "SPONSORED_PRODUCTS|SPONSORED_BRANDS"
        self._write_csv("campaigns.csv", fields, rows)
        with self.assertRaisesRegex(HierarchyValidationError, "one scalar value"):
            validate_simulated_hierarchy(self.data_dir)

    def test_ad_group_must_belong_to_an_input_campaign(self) -> None:
        recommendation = self._read_json("initial_recommendation.json")
        recommendation["campaigns"][0]["campaign_id"] = "C_OUTSIDE"
        self._write_json("initial_recommendation.json", recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "every input campaign exactly once"):
            validate_simulated_hierarchy(self.data_dir)

    def test_keyword_must_come_from_frozen_pool(self) -> None:
        recommendation = self._read_json("initial_recommendation.json")
        recommendation["campaigns"][0]["recommended_ad_groups"][0]["keywords"][0]["keyword_id"] = "K_OUTSIDE"
        self._write_json("initial_recommendation.json", recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "outside the eligible pool"):
            validate_simulated_hierarchy(self.data_dir)

    def test_blocked_pair_is_rejected(self) -> None:
        recommendation = self._read_json("initial_recommendation.json")
        ad_group = recommendation["campaigns"][3]["recommended_ad_groups"][0]
        ad_group["keywords"] = [{"keyword_id": "K_DISCOVERY", "match_type": "BROAD"}]
        ad_group["pairings"] = [{"keyword_id": "K_DISCOVERY", "sku_id": "SKU_VOMERO_RED", "match_type": "BROAD"}]
        self._write_json("initial_recommendation.json", recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "missing or BLOCKED pair"):
            validate_simulated_hierarchy(self.data_dir)

    def test_budget_must_be_conserved(self) -> None:
        recommendation = self._read_json("initial_recommendation.json")
        recommendation["campaigns"][0]["campaign_budget_seed"] = 449.0
        self._write_json("initial_recommendation.json", recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "budget is not conserved"):
            validate_simulated_hierarchy(self.data_dir)

    def test_no_baseline_allows_relative_shares_only(self) -> None:
        envelope = self._read_json("campaign_group.json")
        envelope["campaign_group"].pop("budget_baseline")
        self._write_json("campaign_group.json", envelope)
        (self.data_dir / "historical_budgets.csv").unlink()
        recommendation = self._read_json("initial_recommendation.json")
        recommendation.pop("budget_seed_total")
        for campaign in recommendation["campaigns"]:
            campaign.pop("campaign_budget_seed")
            for ad_group in campaign["recommended_ad_groups"]:
                ad_group.pop("initial_daily_budget")
        self._write_json("initial_recommendation.json", recommendation)

        summary = validate_simulated_hierarchy(self.data_dir)
        self.assertFalse(summary["has_budget_baseline"])
        self.assertEqual(summary["warnings"], ["NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY"])

    def test_no_baseline_rejects_absolute_budget(self) -> None:
        envelope = self._read_json("campaign_group.json")
        envelope["campaign_group"].pop("budget_baseline")
        self._write_json("campaign_group.json", envelope)
        (self.data_dir / "historical_budgets.csv").unlink()
        with self.assertRaisesRegex(HierarchyValidationError, "absolute Ad Group budget must be omitted"):
            validate_simulated_hierarchy(self.data_dir)

    def test_ad_product_is_not_duplicated_on_ad_group(self) -> None:
        recommendation = self._read_json("initial_recommendation.json")
        recommendation["campaigns"][0]["recommended_ad_groups"][0]["ad_product"] = "SPONSORED_PRODUCTS"
        self._write_json("initial_recommendation.json", recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "inherit ad_product"):
            validate_simulated_hierarchy(self.data_dir)

    def test_boolean_budget_is_not_numeric(self) -> None:
        recommendation = self._read_json("initial_recommendation.json")
        recommendation["campaigns"][0]["budget_seed_share"] = True
        self._write_json("initial_recommendation.json", recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "must be numeric"):
            validate_simulated_hierarchy(self.data_dir)

    def test_candidate_pool_lineage_must_match(self) -> None:
        fields, rows = self._read_csv("candidate_keywords.csv")
        rows[0]["candidate_pool_id"] = "pool_stale"
        self._write_csv("candidate_keywords.csv", fields, rows)
        with self.assertRaisesRegex(HierarchyValidationError, "different candidate_pool_id"):
            validate_simulated_hierarchy(self.data_dir)

    def test_disabled_campaign_is_rejected(self) -> None:
        fields, rows = self._read_csv("campaigns.csv")
        rows[0]["status"] = "paused"
        self._write_csv("campaigns.csv", fields, rows)
        with self.assertRaisesRegex(HierarchyValidationError, "must be enabled"):
            validate_simulated_hierarchy(self.data_dir)

    def test_unavailable_sku_is_rejected(self) -> None:
        fields, rows = self._read_csv("candidate_skus.csv")
        rows[0]["inventory_available"] = "false"
        self._write_csv("candidate_skus.csv", fields, rows)
        with self.assertRaisesRegex(HierarchyValidationError, "is not executable"):
            validate_simulated_hierarchy(self.data_dir)

    def test_historical_budget_group_must_match(self) -> None:
        fields, rows = self._read_csv("historical_budgets.csv")
        rows[0]["campaign_group_id"] = "CG_OTHER"
        self._write_csv("historical_budgets.csv", fields, rows)
        with self.assertRaisesRegex(HierarchyValidationError, "different campaign_group_id"):
            validate_simulated_hierarchy(self.data_dir)

    def test_duplicate_sku_and_pairing_are_rejected(self) -> None:
        recommendation = self._read_json("initial_recommendation.json")
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group["skus"].append(dict(ad_group["skus"][0]))
        self._write_json("initial_recommendation.json", recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "repeats SKU"):
            validate_simulated_hierarchy(self.data_dir)

        recommendation = self._read_json("initial_recommendation.json")
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group["skus"] = ad_group["skus"][:-1]
        ad_group["pairings"].append(dict(ad_group["pairings"][0]))
        self._write_json("initial_recommendation.json", recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "repeats pairing"):
            validate_simulated_hierarchy(self.data_dir)

    def test_campaign_group_relationship_is_required(self) -> None:
        fields, rows = self._read_csv("campaign_group_relationships.csv")
        rows[0]["campaign_group_id"] = "CG_OTHER"
        self._write_csv("campaign_group_relationships.csv", fields, rows)
        with self.assertRaisesRegex(HierarchyValidationError, "exactly 4 campaigns"):
            validate_simulated_hierarchy(self.data_dir)

    def test_strategy_traceability_is_required_and_compatible(self) -> None:
        recommendation = self._read_json("initial_recommendation.json")
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group.pop("reason_codes")
        self._write_json("initial_recommendation.json", recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "must contain reason_codes"):
            validate_simulated_hierarchy(self.data_dir)

        recommendation = self._read_json("initial_recommendation.json")
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group["reason_codes"] = ["RELIABLE_MTA_TOUCHPOINT"]
        ad_group["mta_evidence"][0]["touchpoint"] = "AMAZON_DSP:DISPLAY:UNSPECIFIED:IMAGE:IMPRESSION"
        self._write_json("initial_recommendation.json", recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "not a compatible five-part key"):
            validate_simulated_hierarchy(self.data_dir)

    def test_pairing_match_type_must_be_assigned(self) -> None:
        recommendation = self._read_json("initial_recommendation.json")
        pairing = recommendation["campaigns"][0]["recommended_ad_groups"][0]["pairings"][0]
        pairing["match_type"] = "PHRASE"
        self._write_json("initial_recommendation.json", recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "unassigned match type"):
            validate_simulated_hierarchy(self.data_dir)


if __name__ == "__main__":
    unittest.main()
