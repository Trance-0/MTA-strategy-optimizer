from __future__ import annotations

import csv
import math
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SCRIPTS))

from compare_attribution_models import read_model_csv_strict  # noqa: E402
from amc_mta_attribution import write_csv_set_atomic  # noqa: E402
from model_comparison import (  # noqa: E402
    MODEL_OUTPUT_FIELDS,
    RECOMMENDED_FIELDS,
    SUMMARY_FIELDS,
    TOUCHPOINT_COMPARISON_FIELDS,
    calculate_raw_support,
    compare_attribution_models,
    data_support_is_sufficient,
    models_are_consistent,
    read_amc_csv_strict,
    reliability_fields,
    spearman_rho,
)


A_IMPRESSION = "PRODUCT_A:FORMAT:PLACEMENT:CREATIVE:IMPRESSION"
A_CLICK = "PRODUCT_A:FORMAT:PLACEMENT:CREATIVE:CLICK"


def amc_row(path: str, **overrides: object) -> dict:
    row = {
        "report_start_date": "2026-05-01",
        "report_end_date": "2026-06-30",
        "marketplace": "US",
        "advertiser_id": "A1",
        "path": path,
        "users": "100",
        "converted_users": "50",
        "purchase_count": "100",
        "revenue": "1000",
    }
    row.update(overrides)
    return row


def model_row(model: str, touchpoint: str, share: float, **overrides: object) -> dict:
    row = {
        "attribution_model": model,
        "touchpoint": touchpoint,
        "interaction_type": touchpoint.rsplit(":", 1)[1],
        "converted_user_share": share,
        "purchase_count_share": share,
        "revenue_share": share,
        "attributed_converted_users": share * 50,
        "attributed_purchase_count": share * 100,
        "attributed_revenue": share * 1000,
        "impressions": 100,
        "clicks": 0,
        "cost": 10,
        "reported_purchases": 1,
        "reported_sales": 20,
        "roas": share * 100,
        "roi": share * 100 - 1,
        "cpa": "" if share == 0 else 10 / (share * 100),
        "cost_per_converted_user": "" if share == 0 else 10 / (share * 50),
    }
    row.update(overrides)
    return row


def high_support_amc_rows() -> list[dict]:
    return [
        amc_row(path)
        for path in (
            f"{A_IMPRESSION} > {A_CLICK}",
            f"{A_CLICK} > {A_IMPRESSION}",
            f"{A_IMPRESSION} > {A_IMPRESSION} > {A_CLICK}",
            f"{A_IMPRESSION} > {A_CLICK} > {A_IMPRESSION}",
            f"{A_CLICK} > {A_IMPRESSION} > {A_CLICK}",
        )
    ]


def high_support_model_row(model: str, touchpoint: str, share: float) -> dict:
    return model_row(
        model,
        touchpoint,
        share,
        attributed_converted_users=share * 250,
        attributed_purchase_count=share * 500,
        attributed_revenue=share * 5000,
        roas=share * 500,
        roi=share * 500 - 1,
        cpa=10 / (share * 500),
        cost_per_converted_user=10 / (share * 250),
    )


class DifferenceRuleTests(unittest.TestCase):
    def test_spearman_handles_ties_and_undefined_rankings(self) -> None:
        self.assertAlmostEqual(
            spearman_rho({"a": 0.5, "b": 0.5, "c": 0.0}, {"a": 0.4, "b": 0.4, "c": 0.2}),
            1.0,
        )
        self.assertIsNone(spearman_rho({"a": 1.0}, {"a": 1.0}))
        self.assertIsNone(spearman_rho({"a": 0.5, "b": 0.5}, {"a": 0.4, "b": 0.6}))


class SupportTests(unittest.TestCase):
    def test_impression_and_click_support_remain_separate(self) -> None:
        rows = [amc_row(f"{A_IMPRESSION} > {A_CLICK}")]
        support = calculate_raw_support(rows)

        self.assertEqual(set(support), {A_IMPRESSION, A_CLICK})
        self.assertEqual(support[A_IMPRESSION]["raw_unique_paths"], 1)
        self.assertEqual(support[A_CLICK]["raw_unique_paths"], 1)
        self.assertEqual(support[A_IMPRESSION]["raw_purchase_count"], 100)
        self.assertEqual(support[A_CLICK]["raw_purchase_count"], 100)

    def test_sufficient_support_requires_all_inclusive_minimums(self) -> None:
        minimum = {
            "raw_purchase_count": 30,
            "raw_converted_users": 20,
            "raw_unique_paths": 5,
        }
        self.assertTrue(data_support_is_sufficient(minimum))
        for field in minimum:
            with self.subTest(field=field):
                below = dict(minimum)
                below[field] -= 1
                self.assertFalse(data_support_is_sufficient(below))

    def test_repeated_touchpoint_counts_once_per_path_support(self) -> None:
        support = calculate_raw_support(
            [amc_row(f"{A_IMPRESSION} > {A_IMPRESSION}")]
        )
        self.assertEqual(support[A_IMPRESSION]["raw_unique_paths"], 1)
        self.assertEqual(support[A_IMPRESSION]["raw_purchase_count"], 100)


class ReliabilityRuleTests(unittest.TestCase):
    def test_model_consistency_uses_both_inclusive_thresholds(self) -> None:
        self.assertTrue(models_are_consistent(1.0, 0.20, has_outcome=True))
        self.assertFalse(
            models_are_consistent(
                math.nextafter(1.0, math.inf), 0.20, has_outcome=True
            )
        )
        self.assertFalse(
            models_are_consistent(
                1.0, math.nextafter(0.20, math.inf), has_outcome=True
            )
        )
        self.assertFalse(models_are_consistent(1.000001, 0.20, has_outcome=True))
        self.assertFalse(models_are_consistent(1.0, 0.200001, has_outcome=True))
        for gap_pp, relative_gap in (
            (math.nan, 0.0),
            (0.0, math.nan),
            (math.inf, 0.0),
            (0.0, math.inf),
            (-math.inf, 0.0),
            (0.0, -math.inf),
            (-0.000001, 0.0),
            (0.0, -0.000001),
        ):
            with self.subTest(gap_pp=gap_pp, relative_gap=relative_gap):
                self.assertFalse(
                    models_are_consistent(
                        gap_pp, relative_gap, has_outcome=True
                    )
                )
        self.assertFalse(models_are_consistent(0.0, 0.0, has_outcome=False))

    def test_reliability_is_and_with_fixed_reason_order(self) -> None:
        self.assertEqual(
            reliability_fields(True, True, True),
            {
                "calculation_valid": "true",
                "data_support_sufficient": "true",
                "models_consistent": "true",
                "reliability_status": "RELIABLE",
                "reliability_reason": "ALL_CRITERIA_PASSED",
            },
        )
        self.assertEqual(
            reliability_fields(False, False, False)["reliability_reason"],
            "CALCULATION_INVALID|INSUFFICIENT_DATA_SUPPORT|MODELS_INCONSISTENT",
        )


class CompleteComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.amc_rows = [amc_row(f"{A_IMPRESSION} > {A_CLICK}")]
        self.markov = [
            model_row("markov", A_IMPRESSION, 0.4),
            model_row("markov", A_CLICK, 0.6),
        ]
        self.shapley = [
            model_row("shapley", A_IMPRESSION, 0.5),
            model_row("shapley", A_CLICK, 0.5),
        ]

    def test_all_touchpoints_and_outcomes_are_preserved_with_blocked_decisions(self) -> None:
        artifacts = compare_attribution_models(self.markov, self.shapley, self.amc_rows)

        self.assertEqual(len(artifacts.touchpoints), 6)
        self.assertEqual(len(artifacts.summary), 3)
        self.assertEqual(len(artifacts.recommended), 6)
        self.assertEqual(
            {row["outcome"] for row in artifacts.summary},
            {"converted_users", "purchase_count", "revenue"},
        )
        self.assertEqual(
            {(row["touchpoint"], row["outcome"]) for row in artifacts.touchpoints},
            {
                (touchpoint, outcome)
                for touchpoint in (A_IMPRESSION, A_CLICK)
                for outcome in ("converted_users", "purchase_count", "revenue")
            },
        )
        for field in (
            "markov_interval_low",
            "markov_interval_high",
            "shapley_interval_low",
            "shapley_interval_high",
            "gap_direction_rate",
            "top5_entry_rate",
        ):
            self.assertNotIn(field, TOUCHPOINT_COMPARISON_FIELDS)
        forbidden_fields = {
            "parent_touchpoint",
            "parent_support_level",
            "parent_difference_level",
        }
        self.assertTrue(forbidden_fields.isdisjoint(TOUCHPOINT_COMPARISON_FIELDS))
        self.assertTrue(
            all(forbidden_fields.isdisjoint(row) for row in artifacts.touchpoints)
        )
        self.assertTrue(
            all(forbidden_fields.isdisjoint(row) for row in artifacts.recommended)
        )
        self.assertTrue(
            all(row["calculation_valid"] == "true" for row in artifacts.touchpoints)
        )
        self.assertTrue(
            all(row["data_support_sufficient"] == "false" for row in artifacts.touchpoints)
        )
        self.assertTrue(
            all(row["models_consistent"] == "false" for row in artifacts.touchpoints)
        )
        self.assertTrue(
            all(row["reliability_status"] == "UNRELIABLE" for row in artifacts.touchpoints)
        )
        self.assertTrue(
            all(
                row["reliability_reason"]
                == "INSUFFICIENT_DATA_SUPPORT|MODELS_INCONSISTENT"
                for row in artifacts.touchpoints
            )
        )
        touchpoint_reliability = {
            (row["touchpoint"], row["outcome"]): (
                row["calculation_valid"],
                row["data_support_sufficient"],
                row["models_consistent"],
                row["reliability_status"],
                row["reliability_reason"],
            )
            for row in artifacts.touchpoints
        }
        self.assertTrue(
            all(
                touchpoint_reliability[(row["touchpoint"], row["outcome"])]
                == (
                    row["calculation_valid"],
                    row["data_support_sufficient"],
                    row["models_consistent"],
                    row["reliability_status"],
                    row["reliability_reason"],
                )
                for row in artifacts.recommended
            )
        )

    def test_nonzero_equal_long_tail_is_model_consistent(self) -> None:
        markov = [
            model_row("markov", A_IMPRESSION, 0.005),
            model_row("markov", A_CLICK, 0.995),
        ]
        shapley = [
            model_row("shapley", A_IMPRESSION, 0.005),
            model_row("shapley", A_CLICK, 0.995),
        ]
        artifacts = compare_attribution_models(markov, shapley, self.amc_rows)
        rows = [
            row for row in artifacts.touchpoints if row["touchpoint"] == A_IMPRESSION
        ]
        self.assertTrue(all(row["models_consistent"] == "true" for row in rows))
        self.assertTrue(all(row["reliability_status"] == "UNRELIABLE" for row in rows))
        self.assertTrue(
            all(row["reliability_reason"] == "INSUFFICIENT_DATA_SUPPORT" for row in rows)
        )

    def test_all_three_criteria_produce_reliable_outputs(self) -> None:
        markov = [
            high_support_model_row("markov", A_IMPRESSION, 0.4),
            high_support_model_row("markov", A_CLICK, 0.6),
        ]
        shapley = [
            high_support_model_row("shapley", A_IMPRESSION, 0.4),
            high_support_model_row("shapley", A_CLICK, 0.6),
        ]
        artifacts = compare_attribution_models(
            markov, shapley, high_support_amc_rows()
        )

        for rows in (artifacts.touchpoints, artifacts.summary, artifacts.recommended):
            self.assertTrue(all(row["calculation_valid"] == "true" for row in rows))
            self.assertTrue(
                all(row["data_support_sufficient"] == "true" for row in rows)
            )
            self.assertTrue(all(row["models_consistent"] == "true" for row in rows))
            self.assertTrue(all(row["reliability_status"] == "RELIABLE" for row in rows))
            self.assertTrue(
                all(row["reliability_reason"] == "ALL_CRITERIA_PASSED" for row in rows)
            )

    def test_summary_ands_touchpoint_booleans_not_overall_diagnostics(self) -> None:
        markov = [
            high_support_model_row("markov", A_IMPRESSION, 0.4),
            high_support_model_row("markov", A_CLICK, 0.6),
        ]
        shapley = [
            high_support_model_row("shapley", A_IMPRESSION, 0.42),
            high_support_model_row("shapley", A_CLICK, 0.58),
        ]

        artifacts = compare_attribution_models(
            markov, shapley, high_support_amc_rows()
        )

        self.assertTrue(
            all(row["models_consistent"] == "false" for row in artifacts.touchpoints)
        )
        self.assertTrue(
            all(row["models_consistent"] == "false" for row in artifacts.summary)
        )
        self.assertTrue(
            all(row["reliability_status"] == "UNRELIABLE" for row in artifacts.summary)
        )
        self.assertTrue(
            all(
                row["reliability_reason"] == "MODELS_INCONSISTENT"
                for row in artifacts.summary
            )
        )

    def test_uniform_identical_models_remain_reliable_when_spearman_is_undefined(self) -> None:
        markov = [
            high_support_model_row("markov", A_IMPRESSION, 0.5),
            high_support_model_row("markov", A_CLICK, 0.5),
        ]
        shapley = [
            high_support_model_row("shapley", A_IMPRESSION, 0.5),
            high_support_model_row("shapley", A_CLICK, 0.5),
        ]

        artifacts = compare_attribution_models(
            markov, shapley, high_support_amc_rows()
        )

        self.assertTrue(all(row["spearman_rho"] == "" for row in artifacts.summary))
        self.assertTrue(
            all(row["models_consistent"] == "true" for row in artifacts.summary)
        )
        self.assertTrue(
            all(row["reliability_status"] == "RELIABLE" for row in artifacts.summary)
        )

    def test_share_derived_exact_boundary_is_not_misclassified_by_binary_float(self) -> None:
        markov = [
            high_support_model_row("markov", A_IMPRESSION, 0.055),
            high_support_model_row("markov", A_CLICK, 0.945),
        ]
        shapley = [
            high_support_model_row("shapley", A_IMPRESSION, 0.045),
            high_support_model_row("shapley", A_CLICK, 0.955),
        ]

        artifacts = compare_attribution_models(
            markov, shapley, high_support_amc_rows()
        )
        boundary_rows = [
            row
            for row in artifacts.touchpoints
            if row["touchpoint"] == A_IMPRESSION
        ]

        self.assertTrue(all(row["gap_pp"] == 1.0 for row in boundary_rows))
        self.assertTrue(all(row["relative_gap"] == 0.2 for row in boundary_rows))
        self.assertTrue(
            all(row["models_consistent"] == "true" for row in boundary_rows)
        )

    def test_unrounded_text_shares_above_boundary_remain_unreliable_everywhere(self) -> None:
        share_fields = (
            "converted_user_share",
            "purchase_count_share",
            "revenue_share",
        )

        def with_raw_share(row: dict, raw_share: str) -> dict:
            result = dict(row)
            for field in share_fields:
                result[field] = raw_share
            return result

        markov = [
            with_raw_share(
                high_support_model_row("markov", A_IMPRESSION, 0.055),
                "0.055000000000000001",
            ),
            with_raw_share(
                high_support_model_row("markov", A_CLICK, 0.945),
                "0.944999999999999999",
            ),
        ]
        shapley = [
            with_raw_share(
                high_support_model_row("shapley", A_IMPRESSION, 0.045),
                "0.045",
            ),
            with_raw_share(
                high_support_model_row("shapley", A_CLICK, 0.955),
                "0.955",
            ),
        ]
        for left, right in (
            ("0.055000000000000001", "0.045"),
            ("0.944999999999999999", "0.955"),
        ):
            self.assertGreater(
                abs(Decimal(left) - Decimal(right)) * Decimal("100"),
                Decimal("1.0"),
            )

        artifacts = compare_attribution_models(
            markov, shapley, high_support_amc_rows()
        )

        for rows, schema in (
            (artifacts.touchpoints, TOUCHPOINT_COMPARISON_FIELDS),
            (artifacts.summary, SUMMARY_FIELDS),
            (artifacts.recommended, RECOMMENDED_FIELDS),
        ):
            self.assertTrue(all(set(row) == set(schema) for row in rows))
            self.assertTrue(
                all(
                    not any(field.startswith("__decimal_") for field in row)
                    for row in rows
                )
            )
            self.assertTrue(
                all(row["models_consistent"] == "false" for row in rows)
            )
            self.assertTrue(
                all(row["reliability_status"] == "UNRELIABLE" for row in rows)
            )
            self.assertTrue(
                all(row["reliability_reason"] == "MODELS_INCONSISTENT" for row in rows)
            )

    def test_five_part_governance_contract_is_exact(self) -> None:
        artifacts = compare_attribution_models(self.markov, self.shapley, self.amc_rows)
        forbidden_reason_codes = {
            "INTERACTION_ALLOCATION_DIVERGENCE",
            "INTERACTION_ALLOCATION_REVIEW",
            "PARENT_TOUCHPOINT_REVIEW",
            "PARENT_AGGREGATE_DIVERGENCE",
            "TOUCHPOINT_DIVERGENCE",
        }

        self.assertEqual(set(artifacts.touchpoints[0]), set(TOUCHPOINT_COMPARISON_FIELDS))
        self.assertEqual(set(artifacts.summary[0]), set(SUMMARY_FIELDS))
        self.assertEqual(set(artifacts.recommended[0]), set(RECOMMENDED_FIELDS))
        for row in artifacts.touchpoints + artifacts.summary + artifacts.recommended:
            self.assertTrue(forbidden_reason_codes.isdisjoint(row))
            self.assertNotIn("reason_code", row)
            self.assertNotIn("difference_level", row)

    def test_gap_direction_tolerance_is_measured_in_percentage_points(self) -> None:
        markov = [
            model_row("markov", A_IMPRESSION, 0.500000004),
            model_row("markov", A_CLICK, 0.499999996),
        ]
        shapley = [
            model_row("shapley", A_IMPRESSION, 0.499999996),
            model_row("shapley", A_CLICK, 0.500000004),
        ]
        artifacts = compare_attribution_models(markov, shapley, self.amc_rows)
        self.assertTrue(all(row["gap_pp"] <= 0.000001 for row in artifacts.touchpoints))

    def test_rejects_touchpoint_mismatch_duplicate_and_nonfinite_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "sets differ"):
            compare_attribution_models(self.markov, self.shapley[:1], self.amc_rows)
        with self.assertRaisesRegex(ValueError, "duplicate touchpoint"):
            compare_attribution_models(self.markov + [self.markov[0]], self.shapley, self.amc_rows)
        invalid = [dict(row) for row in self.markov]
        invalid[0]["purchase_count_share"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite and non-negative"):
            compare_attribution_models(invalid, self.shapley, self.amc_rows)

    def test_rejects_model_amc_set_mismatch_and_per_row_nonconservation(self) -> None:
        extra_amc = self.amc_rows + [
            amc_row("PRODUCT_B:FORMAT:PLACEMENT:CREATIVE:IMPRESSION")
        ]
        with self.assertRaisesRegex(ValueError, "model/AMC touchpoint sets differ"):
            compare_attribution_models(self.markov, self.shapley, extra_amc)

        invalid = [dict(row) for row in self.markov]
        invalid[0]["attributed_purchase_count"] += 2
        invalid[1]["attributed_purchase_count"] -= 2
        invalid[0]["cpa"] = 10 / invalid[0]["attributed_purchase_count"]
        invalid[1]["cpa"] = 10 / invalid[1]["attributed_purchase_count"]
        with self.assertRaisesRegex(ValueError, "share × AMC total"):
            compare_attribution_models(invalid, self.shapley, self.amc_rows)

    def test_rejects_invalid_efficiency_integer_metrics_scope_and_window_parameters(self) -> None:
        zero_cost = [dict(row) for row in self.markov]
        zero_cost_shapley = [dict(row) for row in self.shapley]
        zero_cost[0]["cost"] = 0
        zero_cost_shapley[0]["cost"] = 0
        with self.assertRaisesRegex(ValueError, "zero cost requires blank"):
            compare_attribution_models(zero_cost, zero_cost_shapley, self.amc_rows)

        fractional = [dict(row) for row in self.markov]
        fractional[0]["clicks"] = 0.5
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            compare_attribution_models(fractional, self.shapley, self.amc_rows)

        second_scope = [dict(self.amc_rows[0]), dict(self.amc_rows[0])]
        second_scope[1]["advertiser_id"] = "A2"
        with self.assertRaisesRegex(ValueError, "one report window"):
            compare_attribution_models(self.markov, self.shapley, second_scope)


    def test_rejects_invalid_or_inverted_amc_report_dates(self) -> None:
        invalid_cases = (
            ({"report_start_date": "not-a-date"}, "ISO dates"),
            ({"report_end_date": "2026-02-30"}, "ISO dates"),
            (
                {
                    "report_start_date": "2026-07-01",
                    "report_end_date": "2026-06-30",
                },
                "inverted",
            ),
        )
        for overrides, expected_message in invalid_cases:
            with self.subTest(overrides=overrides):
                invalid_amc = [dict(self.amc_rows[0], **overrides)]
                with self.assertRaisesRegex(ValueError, expected_message):
                    compare_attribution_models(self.markov, self.shapley, invalid_amc)

    def test_zero_outcome_is_reported_without_distribution_metrics(self) -> None:
        amc_rows = [
            amc_row(
                f"{A_IMPRESSION} > {A_CLICK}",
                converted_users="0",
                purchase_count="0",
                revenue="0",
            )
        ]
        markov = [model_row("markov", A_IMPRESSION, 0), model_row("markov", A_CLICK, 0)]
        shapley = [model_row("shapley", A_IMPRESSION, 0), model_row("shapley", A_CLICK, 0)]
        for rows in (markov, shapley):
            for row in rows:
                for field in (
                    "attributed_converted_users",
                    "attributed_purchase_count",
                    "attributed_revenue",
                ):
                    row[field] = 0
                row["cpa"] = ""
                row["cost_per_converted_user"] = ""
        artifacts = compare_attribution_models(markov, shapley, amc_rows)
        self.assertTrue(all(row["tvd"] == "" for row in artifacts.summary))
        self.assertTrue(all(row["official_share"] == "" for row in artifacts.recommended))
        for rows in (artifacts.touchpoints, artifacts.summary, artifacts.recommended):
            self.assertTrue(all(row["calculation_valid"] == "true" for row in rows))
            self.assertTrue(
                all(row["data_support_sufficient"] == "false" for row in rows)
            )
            self.assertTrue(all(row["models_consistent"] == "false" for row in rows))
            self.assertTrue(all(row["reliability_status"] == "UNRELIABLE" for row in rows))
            self.assertTrue(
                all(
                    row["reliability_reason"]
                    == "INSUFFICIENT_DATA_SUPPORT|MODELS_INCONSISTENT"
                    for row in rows
                )
            )

    def test_nonzero_outcome_zero_share_touchpoint_keeps_official_zero(self) -> None:
        markov = [model_row("markov", A_IMPRESSION, 0), model_row("markov", A_CLICK, 1)]
        shapley = [model_row("shapley", A_IMPRESSION, 0), model_row("shapley", A_CLICK, 1)]
        artifacts = compare_attribution_models(markov, shapley, self.amc_rows)
        zero_share_rows = [
            row for row in artifacts.recommended if row["touchpoint"] == A_IMPRESSION
        ]
        self.assertTrue(zero_share_rows)
        self.assertTrue(all(row["official_share"] == 0.0 for row in zero_share_rows))


class StrictCsvTests(unittest.TestCase):
    def test_strict_reader_rejects_header_and_value_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.csv"
            with path.open("w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow([f" {MODEL_OUTPUT_FIELDS[0]}", *MODEL_OUTPUT_FIELDS[1:]])
            with self.assertRaisesRegex(ValueError, "physical header"):
                read_model_csv_strict(path)

            row = model_row("markov", A_IMPRESSION, 1.0)
            row["touchpoint"] = f" {A_IMPRESSION}"
            with path.open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=MODEL_OUTPUT_FIELDS)
                writer.writeheader()
                writer.writerow(row)
            with self.assertRaisesRegex(ValueError, "surrounding whitespace"):
                read_model_csv_strict(path)

    def test_strict_model_reader_reports_extra_data_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.csv"
            path.write_text(
                ",".join(MODEL_OUTPUT_FIELDS) + "\n" + ",".join([""] * 18) + ",extra\n"
            )
            with self.assertRaisesRegex(ValueError, "extra column"):
                read_model_csv_strict(path)

    def test_strict_amc_reader_skips_one_description_and_rejects_extra_columns(self) -> None:
        from amc_mta_attribution import PATH_FIELD_DESCRIPTIONS

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "amc.csv"
            fieldnames = list(PATH_FIELD_DESCRIPTIONS)
            with path.open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(PATH_FIELD_DESCRIPTIONS)
                writer.writerow(amc_row(A_IMPRESSION))
            self.assertEqual(len(read_amc_csv_strict(path)), 1)

            with path.open("a", newline="") as file:
                file.write(",".join([""] * len(fieldnames)) + ",extra\n")
            with self.assertRaisesRegex(ValueError, "extra column"):
                read_amc_csv_strict(path)


class AtomicCsvSetTests(unittest.TestCase):
    def test_publication_failure_restores_the_whole_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.csv"
            second = root / "second.csv"
            first.write_text("old-first\n")
            second.write_text("old-second\n")
            real_replace = __import__("os").replace
            calls = 0

            def fail_second(source: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("publish failed")
                real_replace(source, destination)

            with patch("amc_mta_attribution.os.replace", side_effect=fail_second):
                with self.assertRaisesRegex(OSError, "publish failed"):
                    write_csv_set_atomic(
                        [
                            (first, [{"value": "new-first"}], ["value"]),
                            (second, [{"value": "new-second"}], ["value"]),
                        ]
                    )
            self.assertEqual(first.read_text(), "old-first\n")
            self.assertEqual(second.read_text(), "old-second\n")


if __name__ == "__main__":
    unittest.main()
