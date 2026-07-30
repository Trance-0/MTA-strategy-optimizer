from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from modules.mta_strategy_recommender.src.budget_recommender import (  # noqa: E402
    BudgetRecommendationError,
    generate_budget_recommendation,
)
from modules.mta_strategy_recommender.src.hierarchy_validator import (  # noqa: E402
    FORBIDDEN_OUTPUT_FIELDS,
    HierarchyValidationError,
    validate_simulated_hierarchy,
)


SAMPLE_DIR = MODULE_ROOT / "data" / "simulated"
EXPECTED_OUTPUT = MODULE_ROOT / "outputs" / "initial_budget_recommendation.json"
AMC_ATTRIBUTION = (
    PROJECT_ROOT
    / "modules"
    / "amc_mta"
    / "outputs"
    / "attribution"
    / "amc_mta_recommended_attribution.csv"
)
AMC_ENTITY = (
    PROJECT_ROOT
    / "modules"
    / "amc_mta"
    / "data"
    / "simulated"
    / "amc_touchpoint_entity_aggregate_sample.csv"
)
ATTRIBUTION_SHA = "df47aac7e0cff152d77b375900a16ac6057289f376e63339e66712fb34fc9066"
ENTITY_SHA = "208f038314b9e9a3549cfd1e992adb8b1940ad5b03cbee48ae535611e70fad3e"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _all_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            keys.update(_all_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_all_keys(child))
    return keys


class BudgetOnlyStrategyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        temporary_root = Path(self.temporary.name)
        self.data_dir = temporary_root / "simulated"
        self.recommendation_path = temporary_root / "initial_budget_recommendation.json"
        self.attribution_path = temporary_root / AMC_ATTRIBUTION.name
        self.entity_path = temporary_root / AMC_ENTITY.name
        shutil.copytree(SAMPLE_DIR, self.data_dir)
        shutil.copyfile(EXPECTED_OUTPUT, self.recommendation_path)
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

    def _generate(
        self,
        request: dict | None = None,
        pool: dict | None = None,
        attribution_rows: list[dict[str, str]] | None = None,
        entity_rows: list[dict[str, str]] | None = None,
    ) -> dict:
        return generate_budget_recommendation(
            request if request is not None else self._read_input("strategy_request.json"),
            pool if pool is not None else self._read_input("candidate_pool.json"),
            attribution_rows if attribution_rows is not None else _read_csv(self.attribution_path),
            entity_rows if entity_rows is not None else _read_csv(self.entity_path),
        )

    def _regenerate_recommendation(self) -> dict:
        result = self._generate()
        self._write_recommendation(result)
        return result

    def _validate(self) -> dict:
        return validate_simulated_hierarchy(
            self.data_dir,
            self.recommendation_path,
            self.attribution_path,
            self.entity_path,
        )

    def test_standard_sample_generates_four_one_group_campaigns(self) -> None:
        summary = self._validate()
        self.assertEqual(summary["campaign_count"], 4)
        self.assertEqual(summary["recommended_ad_group_count"], 4)
        self.assertEqual(set(summary["recommended_ad_group_counts"].values()), {1})
        self.assertEqual(summary["attribution_touchpoint_count"], 17)
        self.assertEqual(summary["entity_row_count"], 34)
        self.assertEqual(summary["normalization_universe"], "ALL_AVAILABLE_MTA_TOUCHPOINTS")
        self.assertEqual(summary["warnings"], [])

    def test_committed_output_is_exact_deterministic_generator_output(self) -> None:
        generated_once = self._generate()
        generated_twice = self._generate()
        self.assertEqual(generated_once, generated_twice)
        self.assertEqual(generated_once, self._read_recommendation())
        command = [
            sys.executable,
            "-B",
            str(MODULE_ROOT / "scripts" / "generate_initial_budget.py"),
        ]
        for option in ("--check-output", "--check-fixture"):
            with self.subTest(option=option):
                completed = subprocess.run(
                    [*command, option],
                    cwd=PROJECT_ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn('"output_matches": true', completed.stdout)
                self.assertIn('"fixture_matches": true', completed.stdout)

    def test_output_contains_no_detailed_candidate_or_targeting_fields(self) -> None:
        output = self._generate()
        self.assertTrue(FORBIDDEN_OUTPUT_FIELDS.isdisjoint(_all_keys(output)))
        for campaign in output["campaigns"]:
            for group in campaign["recommended_ad_groups"]:
                self.assertEqual(
                    set(group),
                    {
                        "ad_group_slot_id",
                        "allocation_basis",
                        "budget_seed_share",
                        "initial_daily_budget",
                    },
                )

    def test_amc_sources_remain_byte_identical_to_approved_baseline(self) -> None:
        self.assertEqual(_sha256(AMC_ATTRIBUTION), ATTRIBUTION_SHA)
        self.assertEqual(_sha256(AMC_ENTITY), ENTITY_SHA)

    def test_input_directory_contains_only_two_json_inputs_and_readme(self) -> None:
        self.assertEqual(
            {path.name for path in SAMPLE_DIR.iterdir()},
            {"strategy_request.json", "candidate_pool.json", "README.md"},
        )
        shutil.copyfile(EXPECTED_OUTPUT, self.data_dir / "extra.json")
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

    def test_search_keyword_count_crossing_capacity_adds_a_group(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["campaign_candidate_counts"][0]["eligible_keyword_unit_count"] = 51
        self._write_input("candidate_pool.json", pool)
        output = self._regenerate_recommendation()
        campaign = output["campaigns"][0]
        self.assertEqual(campaign["recommended_ad_group_count"], 2)
        self.assertEqual(campaign["count_rationale"]["keyword_capacity_count"], 2)
        first, second = campaign["recommended_ad_groups"]
        self.assertEqual(first["allocation_basis"], "CAMPAIGN_MTA_EQUAL_SPLIT")
        self.assertTrue(math.isclose(first["budget_seed_share"], second["budget_seed_share"]))
        self.assertEqual(self._validate()["recommended_ad_group_count"], 5)

    def test_display_target_count_crossing_capacity_adds_a_group(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["campaign_candidate_counts"][2]["eligible_target_count"] = 51
        self._write_input("candidate_pool.json", pool)
        output = self._regenerate_recommendation()
        self.assertEqual(output["campaigns"][2]["recommended_ad_group_count"], 2)
        self.assertEqual(
            output["campaigns"][2]["count_rationale"]["target_capacity_count"], 2
        )

    def test_every_product_capacity_dimension_can_add_a_group(self) -> None:
        cases = (
            (0, "eligible_keyword_unit_count", 51),
            (0, "eligible_sku_count", 21),
            (0, "eligible_legal_pair_count", 101),
            (1, "eligible_keyword_unit_count", 51),
            (1, "eligible_sku_count", 21),
            (1, "eligible_legal_pair_count", 101),
            (2, "eligible_sku_count", 21),
            (2, "eligible_target_count", 51),
            (2, "eligible_audience_count", 51),
            (3, "eligible_sku_count", 21),
            (3, "eligible_target_count", 51),
            (3, "eligible_audience_count", 51),
        )
        baseline = self._read_input("candidate_pool.json")
        for campaign_position, field, value in cases:
            with self.subTest(campaign_position=campaign_position, field=field):
                pool = json.loads(json.dumps(baseline))
                row = pool["campaign_candidate_counts"][campaign_position]
                row[field] = value
                if field == "eligible_legal_pair_count":
                    row["eligible_keyword_unit_count"] = 11
                    row["eligible_sku_count"] = 10
                output = self._generate(pool=pool)
                self.assertEqual(
                    output["campaigns"][campaign_position]["recommended_ad_group_count"],
                    2,
                )

    def test_count_exceeding_campaign_max_is_rejected(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["campaign_candidate_counts"][0]["eligible_keyword_unit_count"] = 501
        with self.assertRaisesRegex(BudgetRecommendationError, "exceeding max_ad_groups"):
            self._generate(pool=pool)

    def test_search_rejects_target_counts_and_display_rejects_keyword_counts(self) -> None:
        baseline = self._read_input("candidate_pool.json")
        mutations = ((0, "eligible_target_count"), (2, "eligible_keyword_unit_count"))
        for position, field in mutations:
            with self.subTest(position=position, field=field):
                pool = json.loads(json.dumps(baseline))
                pool["campaign_candidate_counts"][position][field] = 1
                with self.assertRaisesRegex(BudgetRecommendationError, "must not include"):
                    self._generate(pool=pool)

    def test_campaign_shares_are_the_weighted_all_touchpoint_mta_results(self) -> None:
        output = self._generate()
        expected = {
            "C_DEMO_SP": 0.2398318,
            "C_DEMO_SB": 0.2973985,
            "C_DEMO_SD": 0.2341669,
            "C_DEMO_DSP": 0.2286028,
        }
        for campaign in output["campaigns"]:
            self.assertTrue(
                math.isclose(
                    campaign["budget_seed_share"], expected[campaign["campaign_id"]], abs_tol=1e-12
                )
            )
            self.assertFalse(campaign["bridge_summary"]["fallback_used"])
            self.assertEqual(campaign["bridge_summary"]["historical_ad_group_count"], 2)

    def test_candidate_counts_are_filtered_per_ad_product(self) -> None:
        output = self._generate()
        rationale = {
            campaign["campaign_id"]: campaign["count_rationale"]
            for campaign in output["campaigns"]
        }
        self.assertEqual(
            (
                rationale["C_DEMO_SP"]["eligible_keyword_unit_count"],
                rationale["C_DEMO_SP"]["eligible_sku_count"],
                rationale["C_DEMO_SP"]["eligible_legal_pair_count"],
            ),
            (3, 3, 3),
        )
        self.assertEqual(
            (
                rationale["C_DEMO_SB"]["eligible_keyword_unit_count"],
                rationale["C_DEMO_SB"]["eligible_sku_count"],
                rationale["C_DEMO_SB"]["eligible_legal_pair_count"],
            ),
            (4, 4, 4),
        )
        self.assertEqual(rationale["C_DEMO_SD"]["eligible_target_count"], 4)
        self.assertEqual(rationale["C_DEMO_DSP"]["eligible_target_count"], 8)

    def test_bridge_requires_historical_ad_group_identity(self) -> None:
        entity_rows = _read_csv(self.entity_path)
        entity_rows[0]["ad_group_id"] = ""
        with self.assertRaisesRegex(BudgetRecommendationError, "ad_group_id"):
            self._generate(entity_rows=entity_rows)

    def test_each_mta_outcome_must_remain_a_complete_share_distribution(self) -> None:
        attribution_rows = _read_csv(self.attribution_path)
        attribution_rows[0]["recommended_value"] = str(
            float(attribution_rows[0]["recommended_value"]) + 0.01
        )
        with self.assertRaisesRegex(BudgetRecommendationError, "must sum to 1"):
            self._generate(attribution_rows=attribution_rows)

    def test_unreliable_mta_ranges_use_disclosed_midpoints(self) -> None:
        attribution_rows = _read_csv(self.attribution_path)
        for row in attribution_rows:
            if row["outcome"] == "converted_users":
                point = float(row["recommended_value"])
                row["recommended_value"] = f"[{point - 0.001},{point + 0.001}]"
                row["reliability_status"] = "UNRELIABLE"
        output = self._generate(attribution_rows=attribution_rows)
        self.assertIn("UNRELIABLE_MTA_RANGE_MIDPOINT_USED", output["warnings"])
        self.assertEqual(
            output["budget_derivation"]["reliability_status_counts"],
            {"RELIABLE": 34, "UNRELIABLE": 17},
        )
        self.assertEqual(
            output["budget_derivation"]["mta_value_policy"],
            "RELIABLE_POINT_OR_UNRELIABLE_RANGE_MIDPOINT",
        )

    def test_unreliable_mta_value_requires_an_ordered_range(self) -> None:
        attribution_rows = _read_csv(self.attribution_path)
        attribution_rows[0]["reliability_status"] = "UNRELIABLE"
        attribution_rows[0]["recommended_value"] = "not-a-range"
        with self.assertRaisesRegex(BudgetRecommendationError, r"must be \[low,high\]"):
            self._generate(attribution_rows=attribution_rows)

    def test_unreliable_mta_range_cannot_exceed_share_bounds(self) -> None:
        attribution_rows = _read_csv(self.attribution_path)
        attribution_rows[0]["reliability_status"] = "UNRELIABLE"
        attribution_rows[0]["recommended_value"] = "[0.1,1.1]"
        with self.assertRaisesRegex(BudgetRecommendationError, "endpoints must be <= 1"):
            self._generate(attribution_rows=attribution_rows)

    def test_assisted_outcome_zero_falls_back_to_clicks(self) -> None:
        attribution_rows = _read_csv(self.attribution_path)
        entity_rows = _read_csv(self.entity_path)
        touchpoint = next(
            row["touchpoint"]
            for row in entity_rows
            if float(row["clicks"]) > 0
            and any(
                candidate["touchpoint"] == row["touchpoint"]
                and candidate["outcome"] == "converted_users"
                for candidate in attribution_rows
            )
        )
        for row in entity_rows:
            if row["touchpoint"] == touchpoint:
                row["assisted_converted_users"] = "0"
        output = self._generate(attribution_rows=attribution_rows, entity_rows=entity_rows)
        product_to_campaign = {
            campaign["ad_product"]: campaign["campaign_id"]
            for campaign in self._read_input("strategy_request.json")["campaigns"]
        }
        campaign_id = product_to_campaign[touchpoint.split(":", 1)[0]]
        campaign = next(
            item for item in output["campaigns"] if item["campaign_id"] == campaign_id
        )
        self.assertGreater(campaign["bridge_summary"]["method_counts"].get("CLICKS", 0), 0)
        self.assertTrue(campaign["bridge_summary"]["fallback_used"])

    def test_bridge_fallback_reaches_impressions_users_and_equal(self) -> None:
        attribution_rows = _read_csv(self.attribution_path)
        baseline_entities = _read_csv(self.entity_path)
        touchpoint = baseline_entities[0]["touchpoint"]
        cases = (
            ({"assisted_revenue": "0", "clicks": "0"}, "IMPRESSIONS"),
            (
                {
                    "assisted_revenue": "0",
                    "clicks": "0",
                    "impressions": "0",
                },
                "UNIQUE_USERS",
            ),
            (
                {
                    "assisted_revenue": "0",
                    "clicks": "0",
                    "impressions": "0",
                    "unique_users": "0",
                },
                "EQUAL",
            ),
        )
        for mutation, expected_method in cases:
            with self.subTest(expected_method=expected_method):
                entity_rows = json.loads(json.dumps(baseline_entities))
                for row in entity_rows:
                    if row["touchpoint"] == touchpoint:
                        row.update(mutation)
                output = self._generate(
                    attribution_rows=attribution_rows, entity_rows=entity_rows
                )
                dsp = next(
                    campaign
                    for campaign in output["campaigns"]
                    if campaign["campaign_id"] == "C_DEMO_DSP"
                )
                self.assertGreater(
                    dsp["bridge_summary"]["method_counts"].get(expected_method, 0), 0
                )

    def test_touchpoint_without_entity_bridge_is_rejected(self) -> None:
        attribution_rows = _read_csv(self.attribution_path)
        entity_rows = _read_csv(self.entity_path)
        missing_touchpoint = attribution_rows[0]["touchpoint"]
        entity_rows = [row for row in entity_rows if row["touchpoint"] != missing_touchpoint]
        with self.assertRaisesRegex(BudgetRecommendationError, "has no entity bridge"):
            self._generate(attribution_rows=attribution_rows, entity_rows=entity_rows)

    def test_malformed_touchpoint_and_invalid_entity_coverage_are_rejected(self) -> None:
        attribution_rows = _read_csv(self.attribution_path)
        attribution_rows[0]["touchpoint"] = "AMAZON_DSP:TOO_SHORT"
        with self.assertRaisesRegex(BudgetRecommendationError, "five-segment"):
            self._generate(attribution_rows=attribution_rows)

        baseline_entities = _read_csv(self.entity_path)
        duplicate_entities = baseline_entities + [dict(baseline_entities[0])]
        with self.assertRaisesRegex(BudgetRecommendationError, "duplicate AMC entity row"):
            self._generate(entity_rows=duplicate_entities)

        orphan_entities = baseline_entities + [dict(baseline_entities[0])]
        orphan_entities[-1]["touchpoint"] = (
            "AMAZON_DSP:ORPHAN:UNSPECIFIED:UNSPECIFIED:IMPRESSION"
        )
        with self.assertRaisesRegex(BudgetRecommendationError, "absent from attribution"):
            self._generate(entity_rows=orphan_entities)

    def test_budget_and_shares_are_conserved_at_every_level(self) -> None:
        output = self._generate()
        self.assertTrue(
            math.isclose(sum(c["budget_seed_share"] for c in output["campaigns"]), 1.0)
        )
        self.assertTrue(
            math.isclose(
                sum(c["campaign_budget_seed"] for c in output["campaigns"]),
                output["budget_seed_total"],
            )
        )
        for campaign in output["campaigns"]:
            groups = campaign["recommended_ad_groups"]
            self.assertTrue(
                math.isclose(
                    sum(group["budget_seed_share"] for group in groups),
                    campaign["budget_seed_share"],
                )
            )
            self.assertTrue(
                math.isclose(
                    sum(group["initial_daily_budget"] for group in groups),
                    campaign["campaign_budget_seed"],
                )
            )

    def test_no_budget_baseline_outputs_relative_shares_only(self) -> None:
        request = self._read_input("strategy_request.json")
        request["campaign_group"].pop("total_daily_budget")
        self._write_input("strategy_request.json", request)
        output = self._regenerate_recommendation()
        absolute_amount_fields = {
            "budget_seed_total",
            "campaign_budget_seed",
            "minimum_required_daily_budget",
            "initial_daily_budget",
        }
        self.assertFalse(_all_keys(output) & absolute_amount_fields)
        self.assertEqual(output["warnings"], ["NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY"])
        for campaign in output["campaigns"]:
            self.assertNotIn("campaign_budget_seed", campaign)
            self.assertEqual(campaign["execution_status"], "BUDGET_BASELINE_NOT_PROVIDED")
            for group in campaign["recommended_ad_groups"]:
                self.assertNotIn("initial_daily_budget", group)
        self.assertFalse(self._validate()["has_budget_baseline"])

    def test_insufficient_budget_keeps_count_and_marks_campaigns(self) -> None:
        request = self._read_input("strategy_request.json")
        request["campaign_group"]["total_daily_budget"] = 10
        self._write_input("strategy_request.json", request)
        output = self._regenerate_recommendation()
        self.assertEqual(sum(c["recommended_ad_group_count"] for c in output["campaigns"]), 4)
        for campaign in output["campaigns"]:
            self.assertEqual(campaign["execution_status"], "INSUFFICIENT_BUDGET_FOR_MINIMUMS")
        self.assertEqual(
            len([warning for warning in output["warnings"] if warning.startswith("INSUFFICIENT")]),
            4,
        )
        self.assertEqual(self._validate()["recommended_ad_group_count"], 4)

    def test_budget_share_drift_is_rejected(self) -> None:
        output = self._read_recommendation()
        output["campaigns"][0]["recommended_ad_groups"][0]["budget_seed_share"] += 0.01
        self._write_recommendation(output)
        with self.assertRaisesRegex(HierarchyValidationError, "does not match generated budget seed"):
            self._validate()

    def test_old_strategy_fields_are_rejected(self) -> None:
        output = self._read_recommendation()
        output["campaigns"][0]["recommended_ad_groups"][0]["recommended_actions"] = []
        self._write_recommendation(output)
        with self.assertRaisesRegex(HierarchyValidationError, "forbidden strategy field"):
            self._validate()

    def test_historical_ad_group_id_cannot_masquerade_as_new_slot(self) -> None:
        output = self._read_recommendation()
        group = output["campaigns"][0]["recommended_ad_groups"][0]
        group["historical_ad_group_id"] = "C_DEMO_SP_AG01"
        self._write_recommendation(output)
        with self.assertRaisesRegex(HierarchyValidationError, "forbidden strategy field"):
            self._validate()

    def test_new_slot_id_cannot_reuse_historical_ad_group_id(self) -> None:
        entity_rows = _read_csv(self.entity_path)
        for row in entity_rows:
            if row["campaign_id"] == "C_DEMO_SP":
                row["ad_group_id"] = "C_DEMO_SP_NEW_AG_01"
                break
        with self.assertRaisesRegex(BudgetRecommendationError, "collides with historical"):
            self._generate(entity_rows=entity_rows)

    def test_invalid_candidate_usage_policy_is_rejected(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["candidate_usage_policy"] = "SELECT_SUBSET"
        with self.assertRaisesRegex(BudgetRecommendationError, "USE_ALL_ELIGIBLE"):
            self._generate(pool=pool)

    def test_v4_schema_and_numeric_types_are_strict(self) -> None:
        request = self._read_input("strategy_request.json")
        request["campaigns"][0]["targeting"] = {}
        with self.assertRaisesRegex(BudgetRecommendationError, "exactly match v4 schema"):
            self._generate(request=request)

        pool = self._read_input("candidate_pool.json")
        pool["campaign_candidate_counts"][0]["eligible_sku_count"] = "3"
        with self.assertRaisesRegex(BudgetRecommendationError, "must be an integer"):
            self._generate(pool=pool)

    def test_impossible_pair_counts_and_invalid_budget_values_are_rejected(self) -> None:
        pool = self._read_input("candidate_pool.json")
        pool["campaign_candidate_counts"][0]["eligible_legal_pair_count"] = 10
        with self.assertRaisesRegex(BudgetRecommendationError, "Keyword × SKU upper bound"):
            self._generate(pool=pool)

        request = self._read_input("strategy_request.json")
        request["capacity_rules"]["SPONSORED_PRODUCTS"][
            "minimum_daily_budget_per_ad_group"
        ] = 0
        with self.assertRaisesRegex(BudgetRecommendationError, "must be > 0"):
            self._generate(request=request)

        request = self._read_input("strategy_request.json")
        request["campaign_group"]["total_daily_budget"] = ""
        with self.assertRaisesRegex(BudgetRecommendationError, "must be a JSON number"):
            self._generate(request=request)


if __name__ == "__main__":
    unittest.main()
