from __future__ import annotations

import csv
import sys
import tempfile
import unittest
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
    classify_difference,
    compare_attribution_models,
    read_amc_csv_strict,
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


class DifferenceRuleTests(unittest.TestCase):
    def test_thresholds_apply_in_documented_order(self) -> None:
        self.assertEqual(classify_difference(0.009, 0.008)[0], "LONG_TAIL")
        self.assertEqual(classify_difference(0.10, 0.09)[0], "SMALL")
        self.assertEqual(classify_difference(0.10, 0.07)[0], "LARGE")
        self.assertEqual(classify_difference(0.045, 0.025)[0], "LARGE")
        self.assertEqual(classify_difference(0.10, 0.085)[0], "MEDIUM")

    def test_critical_divergence_is_head_share_with_five_pp_gap(self) -> None:
        level, _, critical = classify_difference(0.13, 0.19)
        self.assertEqual(level, "LARGE")
        self.assertTrue(critical)

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

    def test_repeated_touchpoint_counts_once_per_path_support(self) -> None:
        support = calculate_raw_support(
            [amc_row(f"{A_IMPRESSION} > {A_IMPRESSION}")]
        )
        self.assertEqual(support[A_IMPRESSION]["raw_unique_paths"], 1)
        self.assertEqual(support[A_IMPRESSION]["raw_purchase_count"], 100)


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
        self.assertTrue(all(row["grain"] == "FIVE_PART" for row in artifacts.summary))
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
        self.assertTrue(all(row["decision_value"] == "" for row in artifacts.recommended))
        self.assertTrue(
            all(row["decision_status"] == "EVIDENCE_UNVERIFIED" for row in artifacts.recommended)
        )
        for field in (
            "markov_interval_low",
            "markov_interval_high",
            "shapley_interval_low",
            "shapley_interval_high",
            "gap_direction_rate",
            "top5_entry_rate",
        ):
            self.assertIn(field, TOUCHPOINT_COMPARISON_FIELDS)
            self.assertTrue(all(row[field] == "" for row in artifacts.touchpoints))
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
        self.assertEqual(
            {
                row["reason_code"]
                for row in artifacts.touchpoints
            },
            {"ABSOLUTE_GAP"},
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
        self.assertTrue(all(row["grain"] == "FIVE_PART" for row in artifacts.summary))
        reason_tokens = {
            token
            for row in artifacts.touchpoints
            for token in row["reason_code"].split("|")
        }
        self.assertTrue(
            forbidden_reason_codes.isdisjoint(reason_tokens)
        )

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
        self.assertTrue(all(row["gap_direction"] == "TIE" for row in artifacts.touchpoints))

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

        with self.assertRaisesRegex(ValueError, "positive integer"):
            compare_attribution_models(
                self.markov, self.shapley, self.amc_rows, reference_window_days=0
            )

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
        self.assertTrue(all(row["comparison_status"] == "NO_OUTCOME" for row in artifacts.summary))
        self.assertTrue(all(row["tvd"] == "" for row in artifacts.summary))
        self.assertTrue(
            all(row["difference_level"] == "NO_OUTCOME" for row in artifacts.touchpoints)
        )
        self.assertTrue(
            all(row["decision_status"] == "NO_OUTCOME" for row in artifacts.recommended)
        )


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
