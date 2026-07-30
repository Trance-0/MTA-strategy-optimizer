from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_ROOT.parents[1]
sys.path.insert(0, str(MODULE_ROOT / "src"))

from hierarchy_validator import HierarchyValidationError, validate_simulated_hierarchy  # noqa: E402


SAMPLE_DIR = MODULE_ROOT / "data" / "simulated"
EXPECTED_FIXTURE = MODULE_ROOT / "tests" / "fixtures" / "expected_initial_recommendation.json"
AMC_ATTRIBUTION = PROJECT_ROOT / "modules" / "amc_mta" / "outputs" / "attribution" / "amc_mta_recommended_attribution.csv"
AMC_ENTITY = PROJECT_ROOT / "modules" / "amc_mta" / "data" / "simulated" / "amc_touchpoint_entity_aggregate_sample.csv"
ATTRIBUTION_SHA = "df47aac7e0cff152d77b375900a16ac6057289f376e63339e66712fb34fc9066"
ENTITY_SHA = "208f038314b9e9a3549cfd1e992adb8b1940ad5b03cbee48ae535611e70fad3e"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HierarchyValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        temporary_root = Path(self.temporary.name)
        self.data_dir = temporary_root / "simulated"
        self.recommendation_path = temporary_root / "expected_initial_recommendation.json"
        self.attribution_path = temporary_root / AMC_ATTRIBUTION.name
        self.entity_path = temporary_root / AMC_ENTITY.name
        shutil.copytree(SAMPLE_DIR, self.data_dir)
        shutil.copyfile(EXPECTED_FIXTURE, self.recommendation_path)
        shutil.copyfile(AMC_ATTRIBUTION, self.attribution_path)
        shutil.copyfile(AMC_ENTITY, self.entity_path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _read_input(self, name: str) -> dict:
        return json.loads((self.data_dir / name).read_text(encoding="utf-8"))

    def _write_input(self, name: str, value: dict) -> None:
        (self.data_dir / name).write_text(json.dumps(value), encoding="utf-8")

    def _read_recommendation(self) -> dict:
        return json.loads(self.recommendation_path.read_text(encoding="utf-8"))

    def _write_recommendation(self, value: dict) -> None:
        self.recommendation_path.write_text(json.dumps(value), encoding="utf-8")

    def _validate(self) -> dict:
        return validate_simulated_hierarchy(
            self.data_dir,
            self.recommendation_path,
            self.attribution_path,
            self.entity_path,
        )

    def test_standard_sample_is_fully_amc_aligned(self) -> None:
        summary = self._validate()
        self.assertEqual(summary["campaign_count"], 4)
        self.assertEqual(summary["recommended_ad_group_count"], 6)
        self.assertEqual(summary["attribution_touchpoint_count"], 17)
        self.assertEqual(summary["entity_row_count"], 34)
        self.assertEqual(summary["selected_touchpoint_count"], 6)
        self.assertEqual(summary["historical_pair_count"], 8)
        self.assertEqual(summary["normalization_universe"], "SELECTED_RECOMMENDED_TOUCHPOINTS")
        self.assertTrue(summary["has_budget_baseline"])
        self.assertEqual(summary["warnings"], [])

    def test_amc_sources_remain_byte_identical_to_approved_baseline(self) -> None:
        self.assertEqual(_sha256(AMC_ATTRIBUTION), ATTRIBUTION_SHA)
        self.assertEqual(_sha256(AMC_ENTITY), ENTITY_SHA)

    def test_input_directory_contains_only_two_json_inputs_and_readme(self) -> None:
        self.assertEqual(
            {path.name for path in SAMPLE_DIR.iterdir()},
            {"strategy_request.json", "candidate_pool.json", "README.md"},
        )
        shutil.copyfile(EXPECTED_FIXTURE, self.data_dir / "extra.json")
        with self.assertRaisesRegex(HierarchyValidationError, "unrelated content"):
            self._validate()

    def test_amc_attribution_sha_drift_is_rejected(self) -> None:
        self.attribution_path.write_text(
            self.attribution_path.read_text(encoding="utf-8") + "\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(HierarchyValidationError, "attribution SHA-256"):
            self._validate()

    def test_amc_entity_sha_drift_is_rejected(self) -> None:
        self.entity_path.write_text(
            self.entity_path.read_text(encoding="utf-8") + "\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(HierarchyValidationError, "entity SHA-256"):
            self._validate()

    def test_mta_source_scope_must_match_group(self) -> None:
        request = self._read_input("strategy_request.json")
        request["mta_source"]["advertiser_id"] = "adv_stale"
        self._write_input("strategy_request.json", request)
        with self.assertRaisesRegex(HierarchyValidationError, "scope does not match Campaign Group"):
            self._validate()

    def test_recommendation_source_snapshot_drift_is_rejected(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["mta_source_snapshot"]["report_end_date"] = "2026-03-30"
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "source snapshot mismatch"):
            self._validate()

    def test_mta_outcome_value_drift_is_rejected(self) -> None:
        recommendation = self._read_recommendation()
        evidence = recommendation["campaigns"][0]["recommended_ad_groups"][0]["mta_evidence"][0]
        evidence["outcomes"]["revenue"]["recommended_value"] += 0.001
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "MTA value drift"):
            self._validate()

    def test_mta_reliability_drift_is_rejected(self) -> None:
        recommendation = self._read_recommendation()
        evidence = recommendation["campaigns"][0]["recommended_ad_groups"][0]["mta_evidence"][0]
        evidence["outcomes"]["revenue"]["reliability_status"] = "UNRELIABLE"
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "reliability drift"):
            self._validate()

    def test_composite_score_is_recomputed(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["campaigns"][0]["recommended_ad_groups"][0]["mta_evidence"][0]["composite_score"] += 0.01
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "composite score"):
            self._validate()

    def test_budget_share_is_recomputed_from_six_selected_scores(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["campaigns"][0]["recommended_ad_groups"][0]["budget_seed_share"] += 0.01
        recommendation["campaigns"][0]["budget_seed_share"] += 0.01
        recommendation["campaigns"][0]["recommended_ad_groups"][0]["initial_daily_budget"] += 10
        recommendation["campaigns"][0]["campaign_budget_seed"] += 10
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "budget share is not normalized"):
            self._validate()

    def test_selected_score_total_is_recomputed(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["budget_derivation"]["selected_composite_score_total"] += 0.1
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "score total"):
            self._validate()

    def test_seventeen_to_six_scope_is_required(self) -> None:
        request = self._read_input("strategy_request.json")
        request["touchpoint_selection"]["excluded_touchpoint_count"] = 10
        self._write_input("strategy_request.json", request)
        with self.assertRaisesRegex(HierarchyValidationError, "17 to 6"):
            self._validate()

    def test_all_six_selected_touchpoints_are_used_once(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["touchpoint_selection"]["selected_touchpoints"].pop()
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "count does not match"):
            self._validate()

    def test_historical_keyword_must_exist_in_amc_entities(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["keywords"][4]["evidence_type"] = "HISTORICAL"
        self._write_input("candidate_pool.json", pool)
        with self.assertRaisesRegex(HierarchyValidationError, "HISTORICAL keyword"):
            self._validate()

    def test_historical_keyword_metadata_must_match_amc_entities(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["keywords"][0]["keyword_text"] = "stale running keyword"
        self._write_input("candidate_pool.json", pool)
        with self.assertRaisesRegex(HierarchyValidationError, "metadata does not match AMC"):
            self._validate()

    def test_ineligible_keyword_is_rejected_before_native_or_signal_use(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["keywords"][1]["eligible"] = False
        self._write_input("candidate_pool.json", pool)
        with self.assertRaisesRegex(HierarchyValidationError, "keyword K_NIKE_EXACT is not executable"):
            self._validate()

    def test_historical_pair_must_exist_at_declared_touchpoint(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["pair_rules"][0]["historical_touchpoints"] = [
            "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED:CLICK"
        ]
        self._write_input("candidate_pool.json", pool)
        with self.assertRaisesRegex(HierarchyValidationError, "not supported by AMC"):
            self._validate()

    def test_validated_pair_cannot_claim_historical_touchpoint(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["pair_rules"][8]["historical_touchpoints"] = [
            "SPONSORED_DISPLAY:DISPLAY:PRODUCT_PAGE:IMAGE:CLICK"
        ]
        self._write_input("candidate_pool.json", pool)
        with self.assertRaisesRegex(HierarchyValidationError, "must not claim"):
            self._validate()

    def test_blocked_historical_pair_cannot_be_used_as_native(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["pair_rules"][4]["policy_status"] = "BLOCKED"
        self._write_input("candidate_pool.json", pool)
        with self.assertRaisesRegex(HierarchyValidationError, "allowed HISTORICAL pair"):
            self._validate()

    def test_deterministic_selection_skips_a_blocked_higher_revenue_row(self) -> None:
        pool = self._read_input("candidate_pool.json")
        next(
            pair
            for pair in pool["pair_rules"]
            if (pair["keyword_id"], pair["sku_id"], pair["match_type"])
            == ("K_LIGHTWEIGHT", "SKU_TRAIL_BLUE", "PHRASE")
        )["policy_status"] = "BLOCKED"
        self._write_input("candidate_pool.json", pool)

        recommendation = self._read_recommendation()
        first, second = recommendation["campaigns"][0]["recommended_ad_groups"]
        first["targeting_assignment"]["native_targets"]["keywords"] = [
            {
                "keyword_id": "K_NIKE_EXACT",
                "match_type": "PHRASE",
                "target_id": "TGT_SP_K_NIKE_EXACT_PHRASE",
            }
        ]
        first["targeting_assignment"]["native_targets"]["skus"] = [
            {"sku_id": "SKU_PEG_WHITE", "advertised_asin": "B0DEMOPEG41W"}
        ]
        first["targeting_assignment"]["pairings"] = [
            {"keyword_id": "K_NIKE_EXACT", "sku_id": "SKU_PEG_WHITE", "match_type": "PHRASE"}
        ]
        first["entity_evidence"].update(
            {"source_ad_group_id": "C_DEMO_SP_AG02", "selection_rank": 2, "assisted_revenue": 8687.03}
        )
        second["targeting_assignment"]["native_targets"]["keywords"] = [
            {
                "keyword_id": "K_RUNNING_EXACT",
                "match_type": "EXACT",
                "target_id": "TGT_SP_K_RUNNING_EXACT_EXACT",
            }
        ]
        second["targeting_assignment"]["native_targets"]["skus"] = [
            {"sku_id": "SKU_PEG_BLACK", "advertised_asin": "B0DEMOPEG41B"}
        ]
        second["targeting_assignment"]["pairings"] = [
            {"keyword_id": "K_RUNNING_EXACT", "sku_id": "SKU_PEG_BLACK", "match_type": "EXACT"}
        ]
        second["entity_evidence"].update(
            {"source_ad_group_id": "C_DEMO_SP_AG01", "selection_rank": 2, "assisted_revenue": 6384.08}
        )
        self._write_recommendation(recommendation)
        self.assertEqual(self._validate()["recommended_ad_group_count"], 6)

    def test_search_sample_rejects_appended_unverified_native_items(self) -> None:
        baseline = self._read_recommendation()
        mutations = (
            ("Keyword", lambda native, assignment, signals: native["keywords"].append({})),
            ("SKU", lambda native, assignment, signals: native["skus"].append({})),
            ("pairing", lambda native, assignment, signals: assignment["pairings"].append({})),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                recommendation = json.loads(json.dumps(baseline))
                assignment = recommendation["campaigns"][0]["recommended_ad_groups"][0]["targeting_assignment"]
                mutate(assignment["native_targets"], assignment, assignment["strategy_signals"])
                self._write_recommendation(recommendation)
                with self.assertRaisesRegex(HierarchyValidationError, "exactly one Keyword/SKU/pairing"):
                    self._validate()

    def test_display_sample_rejects_appended_unverified_targeting(self) -> None:
        baseline = self._read_recommendation()
        mutations = (
            ("SKU", lambda native, signals: native["skus"].append({})),
            ("Target", lambda native, signals: native["target_ids"].append("TGT_STALE_EXTRA")),
            ("Audience", lambda native, signals: native["audience_ids"].append("AUD_STALE_EXTRA")),
            ("SKU signal", lambda native, signals: signals["sku_ids"].append({"sku_id": "SKU_STALE"})),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                recommendation = json.loads(json.dumps(baseline))
                assignment = recommendation["campaigns"][2]["recommended_ad_groups"][0]["targeting_assignment"]
                mutate(assignment["native_targets"], assignment["strategy_signals"])
                self._write_recommendation(recommendation)
                with self.assertRaisesRegex(HierarchyValidationError, "exactly one SKU/Target/Audience"):
                    self._validate()

    def test_unknown_signal_evidence_type_is_rejected(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["signal_rules"][0]["evidence_type"] = "ARBITRARY_ENUM"
        self._write_input("candidate_pool.json", pool)
        with self.assertRaisesRegex(HierarchyValidationError, "unsupported evidence_type"):
            self._validate()

    def test_search_native_target_must_follow_highest_revenue_selection(self) -> None:
        recommendation = self._read_recommendation()
        group = recommendation["campaigns"][0]["recommended_ad_groups"][1]
        native = group["targeting_assignment"]["native_targets"]
        native["keywords"] = [{"keyword_id": "K_RUNNING_EXACT", "match_type": "EXACT", "target_id": "TGT_SP_K_RUNNING_EXACT_EXACT"}]
        native["skus"] = [{"sku_id": "SKU_PEG_BLACK", "advertised_asin": "B0DEMOPEG41B"}]
        group["targeting_assignment"]["pairings"] = [{"keyword_id": "K_RUNNING_EXACT", "sku_id": "SKU_PEG_BLACK", "match_type": "EXACT"}]
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "deterministic AMC entity selection"):
            self._validate()

    def test_same_campaign_duplicate_keyword_match_is_skipped_deterministically(self) -> None:
        recommendation = self._read_recommendation()
        group = recommendation["campaigns"][1]["recommended_ad_groups"][1]
        native = group["targeting_assignment"]["native_targets"]
        native["keywords"] = [{"keyword_id": "K_RUNNING_EXACT", "match_type": "EXACT", "target_id": "TGT_SB_K_RUNNING_EXACT_EXACT"}]
        native["skus"] = [{"sku_id": "SKU_TRAIL_BLUE", "advertised_asin": "B0DEMOTRAILB"}]
        group["targeting_assignment"]["pairings"] = [{"keyword_id": "K_RUNNING_EXACT", "sku_id": "SKU_TRAIL_BLUE", "match_type": "EXACT"}]
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "deterministic AMC entity selection"):
            self._validate()

    def test_sd_keyword_cannot_be_native_target(self) -> None:
        recommendation = self._read_recommendation()
        native = recommendation["campaigns"][2]["recommended_ad_groups"][0]["targeting_assignment"]["native_targets"]
        native["keywords"] = [{"keyword_id": "K_NIKE_EXACT", "match_type": "PHRASE"}]
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "exactly one SKU/Target/Audience"):
            self._validate()

    def test_dsp_keyword_signal_cannot_claim_direct_mta_entity_evidence(self) -> None:
        recommendation = self._read_recommendation()
        signal = recommendation["campaigns"][3]["recommended_ad_groups"][0]["targeting_assignment"]["strategy_signals"]["keyword_ids"][0]
        signal["direct_mta_entity_evidence"] = True
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "cannot claim direct"):
            self._validate()

    def test_sd_target_or_audience_drift_is_rejected(self) -> None:
        recommendation = self._read_recommendation()
        native = recommendation["campaigns"][2]["recommended_ad_groups"][0]["targeting_assignment"]["native_targets"]
        native["target_ids"] = ["TGT_STALE"]
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "deterministic AMC entity selection"):
            self._validate()

    def test_entity_evidence_ad_group_is_readability_only_but_must_match_source(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["campaigns"][3]["recommended_ad_groups"][0]["entity_evidence"]["source_ad_group_id"] = "STALE"
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "entity evidence does not match AMC"):
            self._validate()

    def test_campaign_ad_group_counts_are_fixed_at_two_two_one_one(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["campaigns"][0]["recommended_ad_group_count"] = 1
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "must recommend 2"):
            self._validate()

    def test_recommendation_ad_group_ids_are_globally_unique(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["campaigns"][1]["recommended_ad_groups"][0]["ad_group_id"] = "C_DEMO_SP_AG_01"
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "duplicate recommendation ad_group_id"):
            self._validate()

    def test_output_must_not_duplicate_ad_product(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["campaigns"][0]["ad_product"] = "AMAZON_DSP"
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "inherit ad_product"):
            self._validate()

    def test_amazon_amc_source_rejects_another_platform(self) -> None:
        request = self._read_input("strategy_request.json")
        request["campaign_group"]["platform"] = "META"
        self._write_input("strategy_request.json", request)
        with self.assertRaisesRegex(HierarchyValidationError, "platform must be AMAZON"):
            self._validate()

    def test_exploration_pair_cannot_be_labeled_as_core_strategy(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pair = next(
            pair
            for pair in pool["pair_rules"]
            if (pair["keyword_id"], pair["sku_id"], pair["match_type"])
            == ("K_LIGHTWEIGHT", "SKU_TRAIL_BLUE", "PHRASE")
        )
        pair["allocation_role"] = "EXPLORATION"
        self._write_input("candidate_pool.json", pool)
        with self.assertRaisesRegex(HierarchyValidationError, "strategy role does not match"):
            self._validate()

    def test_absolute_budget_is_conserved(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["campaigns"][0]["campaign_budget_seed"] += 1
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "budget is not conserved"):
            self._validate()

    def test_no_total_budget_allows_relative_mta_shares_only(self) -> None:
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

    def test_no_total_budget_rejects_absolute_amounts(self) -> None:
        request = self._read_input("strategy_request.json")
        request["campaign_group"].pop("total_daily_budget")
        self._write_input("strategy_request.json", request)
        with self.assertRaisesRegex(HierarchyValidationError, "absolute Ad Group budget"):
            self._validate()

    def test_attribution_based_actions_cannot_claim_causality(self) -> None:
        recommendation = self._read_recommendation()
        recommendation["campaigns"][0]["recommended_ad_groups"][0]["recommended_actions"][0]["causal_claim"] = True
        self._write_recommendation(recommendation)
        with self.assertRaisesRegex(HierarchyValidationError, "causal claim"):
            self._validate()


if __name__ == "__main__":
    unittest.main()
