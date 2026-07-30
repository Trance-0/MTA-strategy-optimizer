from __future__ import annotations

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
EXPECTED_FIXTURE = MODULE_ROOT / "tests" / "fixtures" / "expected_initial_recommendation.json"


class HierarchyValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        temporary_root = Path(self.temporary.name)
        self.data_dir = temporary_root / "simulated"
        self.recommendation_path = temporary_root / "expected_initial_recommendation.json"
        shutil.copytree(SAMPLE_DIR, self.data_dir)
        shutil.copyfile(EXPECTED_FIXTURE, self.recommendation_path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _read_input(self, name: str) -> dict:
        with (self.data_dir / name).open(encoding="utf-8") as handle:
            return json.load(handle)

    def _write_input(self, name: str, value: dict) -> None:
        with (self.data_dir / name).open("w", encoding="utf-8") as handle:
            json.dump(value, handle)

    def _read_recommendation(self) -> dict:
        with self.recommendation_path.open(encoding="utf-8") as handle:
            return json.load(handle)

    def _write_recommendation(self, value: dict) -> None:
        with self.recommendation_path.open("w", encoding="utf-8") as handle:
            json.dump(value, handle)

    def _validate(self) -> dict:
        return validate_simulated_hierarchy(self.data_dir, self.recommendation_path)

    def test_standard_sample_is_valid(self) -> None:
        summary = self._validate()
        self.assertEqual(summary["campaign_count"], 4)
        self.assertEqual(summary["recommended_ad_group_count"], 6)
        self.assertEqual(summary["keyword_count"], 6)
        self.assertEqual(summary["sku_count"], 4)
        self.assertEqual(summary["pair_count"], 9)
        self.assertTrue(summary["has_budget_baseline"])
        self.assertEqual(summary["recommendation_type"], "INITIAL_SEED")
        self.assertEqual(summary["warnings"], [])

    def test_input_directory_has_only_two_business_json_files_and_readme(self) -> None:
        self.assertEqual(
            {path.name for path in SAMPLE_DIR.iterdir() if path.is_file()},
            {"strategy_request.json", "candidate_pool.json", "README.md"},
        )
        self.assertTrue(EXPECTED_FIXTURE.is_file())
        self.assertFalse((SAMPLE_DIR / "initial_recommendation.json").exists())

        shutil.copyfile(EXPECTED_FIXTURE, self.data_dir / "initial_recommendation.json")
        with self.assertRaisesRegex(HierarchyValidationError, "must not be stored in the input directory"):
            self._validate()

        (self.data_dir / "initial_recommendation.json").unlink()
        (self.data_dir / "archive").mkdir()
        with self.assertRaisesRegex(HierarchyValidationError, "must not be stored in the input directory"):
            self._validate()

    def test_missing_required_input_is_rejected(self) -> None:
        (self.data_dir / "candidate_pool.json").unlink()
        with self.assertRaisesRegex(HierarchyValidationError, "missing required sample file"):
            self._validate()

        shutil.copyfile(SAMPLE_DIR / "candidate_pool.json", self.data_dir / "candidate_pool.json")
        self.recommendation_path.unlink()
        with self.assertRaisesRegex(HierarchyValidationError, "missing recommendation fixture"):
            self._validate()

    def test_campaign_count_must_be_four(self) -> None:
        request = self._read_input("strategy_request.json")
        request["campaigns"] = request["campaigns"][:3]
        self._write_input("strategy_request.json", request)
        with self.assertRaisesRegex(HierarchyValidationError, "exactly 4 campaigns"):
            self._validate()

    def test_campaign_ad_product_is_required_and_scalar(self) -> None:
        request = self._read_input("strategy_request.json")
        request["campaigns"][0]["ad_product"] = "SPONSORED_PRODUCTS|SPONSORED_BRANDS"
        self._write_input("strategy_request.json", request)
        with self.assertRaisesRegex(HierarchyValidationError, "one scalar value"):
            self._validate()

        shutil.copyfile(SAMPLE_DIR / "strategy_request.json", self.data_dir / "strategy_request.json")
        request = self._read_input("strategy_request.json")
        request["campaigns"][0]["ad_product"] = ["SPONSORED_PRODUCTS"]
        self._write_input("strategy_request.json", request)
        with self.assertRaisesRegex(HierarchyValidationError, "must be a non-empty string"):
            self._validate()

    def test_ad_group_must_belong_to_an_input_campaign(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["campaigns"][0]["campaign_id"] = "C_OUTSIDE"
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "every input campaign exactly once"):
            self._validate()

    def test_keyword_must_come_from_frozen_pool(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["campaigns"][0]["recommended_ad_groups"][0]["keywords"][0]["keyword_id"] = "K_OUTSIDE"
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "outside the eligible pool"):
            self._validate()

    def test_blocked_pair_is_rejected(self) -> None:
        recommendation = self._read_recommendation()
        ad_group = recommendation["campaigns"][3]["recommended_ad_groups"][0]
        ad_group["keywords"] = [{"keyword_id": "K_DISCOVERY", "match_type": "BROAD"}]
        ad_group["pairings"] = [
            {"keyword_id": "K_DISCOVERY", "sku_id": "SKU_VOMERO_RED", "match_type": "BROAD"}
        ]
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "missing or BLOCKED pair"):
            self._validate()

        shutil.copyfile(EXPECTED_FIXTURE, self.recommendation_path)
        recommendation = self._read_recommendation()
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][1]
        ad_group["strategy_role"] = "CORE_CONVERSION"
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "controlled EXPLORATION"):
            self._validate()

        shutil.copyfile(EXPECTED_FIXTURE, self.recommendation_path)
        recommendation = self._read_recommendation()
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group["reason_codes"].append("CONTROLLED_EXPLORATION_PAIR")
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "without an exploration pair"):
            self._validate()

    def test_budget_must_be_conserved(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["campaigns"][0]["campaign_budget_seed"] = 449.0
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "budget is not conserved"):
            self._validate()

        shutil.copyfile(EXPECTED_FIXTURE, self.recommendation_path)
        request = self._read_input("strategy_request.json")
        request["ad_group_constraints"]["max_ad_groups_per_campaign"] = 1
        self._write_input("strategy_request.json", request)
        with self.assertRaisesRegex(HierarchyValidationError, "exceeds max_ad_groups_per_campaign"):
            self._validate()

    def test_no_total_budget_allows_relative_shares_only(self) -> None:
        request = self._read_input("strategy_request.json")
        request["campaign_group"].pop("total_daily_budget")
        self._write_input("strategy_request.json", request)
        recommendation = self._read_recommendation()
        recommendation.pop("budget_seed_total")
        for campaign in recommendation["campaigns"]:
            campaign.pop("campaign_budget_seed")
            for ad_group in campaign["recommended_ad_groups"]:
                ad_group.pop("initial_daily_budget")
        self._write_recommendation(recommendation)

        summary = self._validate()
        self.assertFalse(summary["has_budget_baseline"])
        self.assertEqual(summary["warnings"], ["NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY"])

    def test_no_total_budget_rejects_absolute_budget(self) -> None:
        request = self._read_input("strategy_request.json")
        request["campaign_group"].pop("total_daily_budget")
        self._write_input("strategy_request.json", request)
        with self.assertRaisesRegex(HierarchyValidationError, "absolute Ad Group budget must be omitted"):
            self._validate()

    def test_ad_product_is_not_duplicated_on_ad_group(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["campaigns"][0]["recommended_ad_groups"][0]["ad_product"] = "SPONSORED_PRODUCTS"
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "inherit ad_product"):
            self._validate()

    def test_boolean_budget_is_not_numeric(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["campaigns"][0]["budget_seed_share"] = True
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "must be numeric"):
            self._validate()

    def test_candidate_pool_lineage_must_match(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["candidate_pool_id"] = "pool_stale"
        self._write_input("candidate_pool.json", pool)
        with self.assertRaisesRegex(HierarchyValidationError, "candidate_pool_id does not match"):
            self._validate()

        shutil.copyfile(SAMPLE_DIR / "candidate_pool.json", self.data_dir / "candidate_pool.json")
        pool = self._read_input("candidate_pool.json")
        pool["sample_version"] = "1.0"
        self._write_input("candidate_pool.json", pool)
        with self.assertRaisesRegex(HierarchyValidationError, "sample_version"):
            self._validate()

    def test_disabled_campaign_is_rejected(self) -> None:
        request = self._read_input("strategy_request.json")
        request["campaigns"][0]["status"] = "paused"
        self._write_input("strategy_request.json", request)
        with self.assertRaisesRegex(HierarchyValidationError, "must be enabled"):
            self._validate()

        shutil.copyfile(SAMPLE_DIR / "strategy_request.json", self.data_dir / "strategy_request.json")
        request = self._read_input("strategy_request.json")
        request["campaigns"][0]["targeting"] = ["MANUAL"]
        self._write_input("strategy_request.json", request)
        with self.assertRaisesRegex(HierarchyValidationError, "must be a non-empty string"):
            self._validate()

    def test_unavailable_sku_is_rejected(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["skus"][0]["inventory_available"] = False
        self._write_input("candidate_pool.json", pool)
        with self.assertRaisesRegex(HierarchyValidationError, "is not executable"):
            self._validate()

        shutil.copyfile(SAMPLE_DIR / "candidate_pool.json", self.data_dir / "candidate_pool.json")
        pool = self._read_input("candidate_pool.json")
        pool["keywords"][0]["allowed_match_types"] = ["FUZZY"]
        self._write_input("candidate_pool.json", pool)
        with self.assertRaisesRegex(HierarchyValidationError, "unsupported match type"):
            self._validate()

    def test_duplicate_sku_and_pairing_are_rejected(self) -> None:
        recommendation = self._read_recommendation()
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group["skus"].append(dict(ad_group["skus"][0]))
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "repeats SKU"):
            self._validate()

        shutil.copyfile(EXPECTED_FIXTURE, self.recommendation_path)
        recommendation = self._read_recommendation()
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group["pairings"].append(dict(ad_group["pairings"][0]))
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "repeats pairing"):
            self._validate()

    def test_strategy_traceability_is_required_and_compatible(self) -> None:
        recommendation = self._read_recommendation()
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group.pop("reason_codes")
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "must contain reason_codes"):
            self._validate()

        shutil.copyfile(EXPECTED_FIXTURE, self.recommendation_path)
        recommendation = self._read_recommendation()
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group["mta_evidence"][0]["touchpoint"] = "AMAZON_DSP:DISPLAY:UNSPECIFIED:IMAGE:IMPRESSION"
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "not a compatible five-part key"):
            self._validate()

        shutil.copyfile(EXPECTED_FIXTURE, self.recommendation_path)
        recommendation = self._read_recommendation()
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group["mta_evidence"][0]["touchpoint"] = (
            "SPONSORED_PRODUCTS: :TOP_OF_SEARCH:UNSPECIFIED:CLICK"
        )
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "not a compatible five-part key"):
            self._validate()

        shutil.copyfile(EXPECTED_FIXTURE, self.recommendation_path)
        recommendation = self._read_recommendation()
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group.pop("strategy_name")
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "strategy_name"):
            self._validate()

        shutil.copyfile(EXPECTED_FIXTURE, self.recommendation_path)
        recommendation = self._read_recommendation()
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group["mta_evidence"][0]["touchpoint"] = (
            "SPONSORED_PRODUCTS::TOP_OF_SEARCH:UNSPECIFIED:CLICK"
        )
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "not a compatible five-part key"):
            self._validate()

        shutil.copyfile(EXPECTED_FIXTURE, self.recommendation_path)
        recommendation = self._read_recommendation()
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group["mta_evidence"][0]["outcomes"] = [[]]
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "must be a non-empty string"):
            self._validate()

    def test_pairing_match_type_must_be_assigned(self) -> None:
        recommendation = self._read_recommendation()
        pairing = recommendation["campaigns"][0]["recommended_ad_groups"][0]["pairings"][0]
        pairing["match_type"] = "PHRASE"
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "unassigned match type"):
            self._validate()

        shutil.copyfile(EXPECTED_FIXTURE, self.recommendation_path)
        recommendation = self._read_recommendation()
        ad_group = recommendation["campaigns"][0]["recommended_ad_groups"][0]
        ad_group["keywords"].append({"keyword_id": "K_RUNNING_EXACT", "match_type": "PHRASE"})
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "unpaired Keyword or SKU"):
            self._validate()


if __name__ == "__main__":
    unittest.main()
