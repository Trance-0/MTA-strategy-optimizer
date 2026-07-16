from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SCRIPTS))

from amc_path_builder import PATH_REPORT_FIELDS, build_aggregated_path_rows  # noqa: E402
from amc_mta_attribution import PATH_FIELD_DESCRIPTIONS, read_csv, write_csv  # noqa: E402
from build_amc_path_report import build_amc_path_report  # noqa: E402
from config import (  # noqa: E402
    AMAZON_ADS_REPORT_FILE,
    AMC_REPORT_FILE,
    AMC_TOUCHPOINT_EVENTS_FILE,
    MARKOV_OUTPUT_FILE,
    MODEL_COMPARISON_SUMMARY_FILE,
    MODEL_COMPARISON_TOUCHPOINTS_FILE,
    RECOMMENDED_ATTRIBUTION_FILE,
    REPORT_END_DATE,
    REPORT_START_DATE,
    SHAPLEY_OUTPUT_FILE,
)
from generate_simulated_amazon_ads_report import FIELDS, generate_rows  # noqa: E402
from run_amc_attribution import run_amc_attribution  # noqa: E402
from compare_attribution_models import compare_model_files  # noqa: E402
from run_pipeline import match_outputs_by_name, publish_with_rollback  # noqa: E402
from validate_data_alignment import validate_data_alignment_rows  # noqa: E402
from model_comparison import (  # noqa: E402
    RECOMMENDED_FIELDS,
    SUMMARY_FIELDS,
    TOUCHPOINT_COMPARISON_FIELDS,
)
from touchpoint_key import canonicalize_amc_touchpoint_key  # noqa: E402


class EndToEndSampleTests(unittest.TestCase):
    def test_removed_sales_quantity_is_absent_from_public_csv_schemas(self) -> None:
        paths = [
            AMC_TOUCHPOINT_EVENTS_FILE,
            AMC_REPORT_FILE,
            AMAZON_ADS_REPORT_FILE,
            ROOT / "outputs" / "attribution" / MARKOV_OUTPUT_FILE,
            ROOT / "outputs" / "attribution" / SHAPLEY_OUTPUT_FILE,
            ROOT / "outputs" / "attribution" / MODEL_COMPARISON_TOUCHPOINTS_FILE,
            ROOT / "outputs" / "attribution" / MODEL_COMPARISON_SUMMARY_FILE,
            ROOT / "outputs" / "attribution" / RECOMMENDED_ATTRIBUTION_FILE,
        ]
        for path in paths:
            with self.subTest(path=path), Path(path).open(newline="") as file:
                header = next(csv.reader(file))
                self.assertNotIn("units" + "Sold", header)
                self.assertNotIn("units" + "_sold", header)

    def test_stored_path_report_is_exactly_reproducible(self) -> None:
        generated = build_aggregated_path_rows(
            read_csv(AMC_TOUCHPOINT_EVENTS_FILE),
            REPORT_START_DATE,
            REPORT_END_DATE,
            14,
        )
        stored = read_csv(AMC_REPORT_FILE)
        normalized_generated = [
            {field: str(row[field]) for field in PATH_REPORT_FIELDS} for row in generated
        ]

        self.assertEqual(normalized_generated, stored)
        with Path(AMC_REPORT_FILE).open(newline="") as file:
            physical_rows = csv.reader(file)
            self.assertEqual(next(physical_rows), PATH_REPORT_FIELDS)
            description_row = next(physical_rows)
        self.assertEqual(
            description_row,
            [PATH_FIELD_DESCRIPTIONS[field] for field in PATH_REPORT_FIELDS],
        )
        self.assertEqual(len(description_row), 9)
        self.assertTrue(all(value.strip() for value in description_row))
        self.assertEqual(sum(int(row["converted_users"]) for row in stored), 1826)
        self.assertEqual(sum(int(row["purchase_count"]) for row in stored), 2044)
        self.assertIn(
            "SPONSORED_DISPLAY:DISPLAY:PRODUCT_PAGE:VIDEO:IMPRESSION",
            {part.strip() for row in stored for part in row["path"].split(">")},
        )
        self.assertTrue(
            all(
                part.strip().rsplit(":", 1)[-1] in {"IMPRESSION", "CLICK"}
                for row in stored
                for part in row["path"].split(">")
                if part.strip() != "Null"
            )
        )

    def test_generated_path_report_preserves_description_and_reader_skips_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "path.csv"
            build_amc_path_report(AMC_TOUCHPOINT_EVENTS_FILE, output)

            with output.open(newline="") as file:
                physical_rows = list(csv.reader(file))
            self.assertEqual(physical_rows[0], PATH_REPORT_FIELDS)
            self.assertEqual(
                physical_rows[1],
                [PATH_FIELD_DESCRIPTIONS[field] for field in PATH_REPORT_FIELDS],
            )
            self.assertEqual(len(read_csv(output)), len(physical_rows) - 2)

    def test_reader_does_not_guess_that_arbitrary_chinese_data_is_a_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chinese-data.csv"
            path.write_text("name,market\n广告系列,中国\n", encoding="utf-8")
            self.assertEqual(read_csv(path), [{"name": "广告系列", "market": "中国"}])

    def test_ads_sample_is_reproducible_complete_and_not_month_repeated(self) -> None:
        generated = generate_rows(
            date.fromisoformat(REPORT_START_DATE), date.fromisoformat(REPORT_END_DATE)
        )
        stored = read_csv(AMAZON_ADS_REPORT_FILE)
        normalized_generated = [
            {field: str(row[field]) for field in FIELDS} for row in generated
        ]

        self.assertEqual(normalized_generated, stored)
        self.assertEqual(len(stored), 61 * 17)
        with Path(AMAZON_ADS_REPORT_FILE).open(newline="") as file:
            physical_rows = csv.reader(file)
            next(physical_rows)
            description_row = next(physical_rows)
        self.assertEqual(description_row[0].strip(), "报告日期")
        self.assertTrue(all(value.strip() for value in description_row))
        may_first = [row for row in stored if row["reportDate"] == "2026-05-01"]
        june_first = [row for row in stored if row["reportDate"] == "2026-06-01"]
        self.assertNotEqual(
            [(row["impressions"], row["clicks"], row["cost"]) for row in may_first],
            [(row["impressions"], row["clicks"], row["cost"]) for row in june_first],
        )
        validate_data_alignment_rows(read_csv(AMC_REPORT_FILE), stored)

    def test_attribution_outputs_are_exactly_reproducible_and_conserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            generated_paths = run_amc_attribution(
                AMC_REPORT_FILE, output_dir, AMAZON_ADS_REPORT_FILE
            )
            stored_paths = {
                name: ROOT / "outputs" / "attribution" / name
                for name in (
                    MARKOV_OUTPUT_FILE,
                    SHAPLEY_OUTPUT_FILE,
                    MODEL_COMPARISON_TOUCHPOINTS_FILE,
                    MODEL_COMPARISON_SUMMARY_FILE,
                    RECOMMENDED_ATTRIBUTION_FILE,
                )
            }
            self.assertEqual(
                {path.name for path in generated_paths}, set(stored_paths)
            )
            for generated_path in generated_paths[:2]:
                with self.subTest(model=generated_path.name):
                    generated = read_csv(generated_path)
                    stored = read_csv(stored_paths[generated_path.name])
                    self.assertEqual(generated, stored)
                    self.assertAlmostEqual(
                        sum(float(row["converted_user_share"]) for row in generated),
                        1.0,
                        places=6,
                    )
                    self.assertAlmostEqual(
                        sum(float(row["purchase_count_share"]) for row in generated),
                        1.0,
                        places=6,
                    )
                    self.assertAlmostEqual(
                        sum(float(row["revenue_share"]) for row in generated),
                        1.0,
                        places=6,
                    )
                    self.assertAlmostEqual(
                        sum(float(row["attributed_converted_users"]) for row in generated),
                        1826.0,
                        places=4,
                    )
                    self.assertAlmostEqual(
                        sum(float(row["attributed_purchase_count"]) for row in generated),
                        2044.0,
                        places=4,
                    )
                    self.assertAlmostEqual(
                        sum(float(row["attributed_revenue"]) for row in generated),
                        226628.0,
                        places=2,
                    )
                    self.assertTrue(
                        all(len(row["touchpoint"].split(":")) == 5 for row in generated)
                    )
                    self.assertTrue(all("cost" in row for row in generated))
                    self.assertTrue(
                        all(row["interaction_type"] in {"IMPRESSION", "CLICK"} for row in generated)
                    )

            for generated_path in generated_paths[2:]:
                with self.subTest(comparison=generated_path.name):
                    self.assertEqual(
                        read_csv(generated_path),
                        read_csv(stored_paths[generated_path.name]),
                    )

            comparison_rows = read_csv(output_dir / MODEL_COMPARISON_TOUCHPOINTS_FILE)
            summary_rows = read_csv(output_dir / MODEL_COMPARISON_SUMMARY_FILE)
            recommended_rows = read_csv(output_dir / RECOMMENDED_ATTRIBUTION_FILE)
            self.assertEqual(len(comparison_rows), 51)
            self.assertEqual(len(summary_rows), 3)
            self.assertEqual(len(recommended_rows), 51)
            self.assertTrue(all(row["grain"] == "FIVE_PART" for row in summary_rows))
            self.assertTrue(
                all(set(row) == set(TOUCHPOINT_COMPARISON_FIELDS) for row in comparison_rows)
            )
            self.assertTrue(all(set(row) == set(SUMMARY_FIELDS) for row in summary_rows))
            self.assertTrue(
                all(set(row) == set(RECOMMENDED_FIELDS) for row in recommended_rows)
            )
            self.assertTrue(
                all(
                    canonicalize_amc_touchpoint_key(row["touchpoint"])
                    == row["touchpoint"]
                    and row["touchpoint"].rsplit(":", 1)[1] == row["interaction_type"]
                    for row in comparison_rows + recommended_rows
                )
            )
            forbidden_fields = {
                "parent_touchpoint",
                "parent_support_level",
                "parent_difference_level",
            }
            self.assertTrue(forbidden_fields.isdisjoint(comparison_rows[0]))
            self.assertTrue(forbidden_fields.isdisjoint(recommended_rows[0]))
            self.assertTrue(
                all(
                    not field.startswith("parent_")
                    for row in comparison_rows + summary_rows + recommended_rows
                    for field in row
                )
            )
            for filename in (
                MODEL_COMPARISON_TOUCHPOINTS_FILE,
                MODEL_COMPARISON_SUMMARY_FILE,
                RECOMMENDED_ATTRIBUTION_FILE,
            ):
                self.assertNotIn("FOUR_PART", (output_dir / filename).read_text())
            forbidden_reason_codes = {
                "INTERACTION_ALLOCATION_DIVERGENCE",
                "INTERACTION_ALLOCATION_REVIEW",
                "PARENT_TOUCHPOINT_REVIEW",
                "PARENT_AGGREGATE_DIVERGENCE",
                "TOUCHPOINT_DIVERGENCE",
            }
            allowed_reason_codes = {
                "NO_OUTCOME",
                "LONG_TAIL",
                "LONG_TAIL_MODEL_SENSITIVE",
                "ALIGNED",
                "MODEL_REVIEW",
                "ABSOLUTE_GAP",
                "RELATIVE_AND_ABSOLUTE_GAP",
            }
            reason_tokens = {
                token
                for row in comparison_rows + recommended_rows
                for token in row["reason_code"].split("|")
            }
            self.assertTrue(
                forbidden_reason_codes.isdisjoint(reason_tokens)
            )
            self.assertTrue(reason_tokens <= allowed_reason_codes)
            expected_reasons = {
                "NO_OUTCOME": {"NO_OUTCOME"},
                "LONG_TAIL": {"LONG_TAIL", "LONG_TAIL_MODEL_SENSITIVE"},
                "SMALL": {"ALIGNED"},
                "MEDIUM": {"MODEL_REVIEW"},
                "LARGE": {"ABSOLUTE_GAP", "RELATIVE_AND_ABSOLUTE_GAP"},
            }
            self.assertTrue(
                all(
                    "|" not in row["reason_code"]
                    and row["reason_code"] in expected_reasons[row["difference_level"]]
                    for row in comparison_rows + recommended_rows
                )
            )
            self.assertEqual(
                len({(row["touchpoint"], row["outcome"]) for row in comparison_rows}),
                51,
            )
            self.assertTrue(all(row["decision_value"] == "" for row in recommended_rows))
            self.assertTrue(
                all(row["decision_status"] == "EVIDENCE_UNVERIFIED" for row in recommended_rows)
            )

            five_part = {row["outcome"]: row for row in summary_rows}
            expected = {
                "converted_users": (0.091599, 0.987699877, "5"),
                "purchase_count": (0.092277, 0.989551508, "5"),
                "revenue": (0.098206, 0.982779828, "4"),
            }
            for outcome, (tvd, rho, overlap) in expected.items():
                with self.subTest(outcome=outcome):
                    self.assertAlmostEqual(float(five_part[outcome]["tvd"]), tvd, places=6)
                    self.assertAlmostEqual(float(five_part[outcome]["spearman_rho"]), rho, places=6)
                    self.assertEqual(five_part[outcome]["top_k_overlap"], overlap)

            expected_headers = {
                MODEL_COMPARISON_TOUCHPOINTS_FILE: TOUCHPOINT_COMPARISON_FIELDS,
                MODEL_COMPARISON_SUMMARY_FILE: SUMMARY_FIELDS,
                RECOMMENDED_ATTRIBUTION_FILE: RECOMMENDED_FIELDS,
            }
            for filename, header in expected_headers.items():
                with (output_dir / filename).open(newline="") as file:
                    self.assertEqual(next(csv.reader(file)), header)

    def test_standalone_comparison_runs_ads_scope_and_currency_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ads_rows = read_csv(AMAZON_ADS_REPORT_FILE)
            ads_rows[0]["currencyCode"] = "EUR"
            invalid_ads = Path(tmp) / "ads.csv"
            write_csv(invalid_ads, ads_rows, FIELDS)
            output_dir = ROOT / "outputs" / "attribution"
            with self.assertRaisesRegex(ValueError, "one marketplace/account/currency"):
                compare_model_files(
                    output_dir / MARKOV_OUTPUT_FILE,
                    output_dir / SHAPLEY_OUTPUT_FILE,
                    AMC_REPORT_FILE,
                    invalid_ads,
                    Path(tmp) / "outputs",
                )

    def test_publication_failure_restores_previous_artifact_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_one = root / "source_one"
            source_two = root / "source_two"
            destination_one = root / "destination_one"
            destination_two = root / "destination_two"
            source_one.write_text("new one")
            source_two.write_text("new two")
            destination_one.write_text("old one")
            destination_two.write_text("old two")
            real_replace = __import__("os").replace
            call_count = 0

            def fail_on_second_replace(source: Path, destination: Path) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise OSError("simulated publication failure")
                real_replace(source, destination)

            with patch("run_pipeline.os.replace", side_effect=fail_on_second_replace):
                with self.assertRaisesRegex(OSError, "simulated publication failure"):
                    publish_with_rollback(
                        [
                            (source_one, destination_one),
                            (source_two, destination_two),
                        ],
                        root / "backups",
                    )

            self.assertEqual(destination_one.read_text(), "old one")
            self.assertEqual(destination_two.read_text(), "old two")

    def test_output_publication_matches_files_by_name_not_return_order(self) -> None:
        generated = [Path("tmp/shapley.csv"), Path("tmp/markov.csv")]
        expected = [Path("final/markov.csv"), Path("final/shapley.csv")]

        self.assertEqual(
            match_outputs_by_name(generated, expected),
            [
                (Path("tmp/markov.csv"), Path("final/markov.csv")),
                (Path("tmp/shapley.csv"), Path("final/shapley.csv")),
            ],
        )

    def test_output_publication_rejects_missing_extra_or_duplicate_names(self) -> None:
        expected = [Path("final/markov.csv"), Path("final/shapley.csv")]
        invalid_sets = [
            [Path("tmp/markov.csv")],
            [Path("tmp/markov.csv"), Path("tmp/extra.csv")],
            [Path("one/markov.csv"), Path("two/markov.csv")],
        ]
        for generated in invalid_sets:
            with self.subTest(generated=generated):
                with self.assertRaisesRegex(ValueError, "expected artifact set"):
                    match_outputs_by_name(generated, expected)

    def test_publication_rejects_duplicate_destinations_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "same.csv"
            with self.assertRaisesRegex(ValueError, "duplicate destinations"):
                publish_with_rollback(
                    [
                        (root / "one.csv", destination),
                        (root / "two.csv", destination),
                    ],
                    root / "backups",
                )
            self.assertFalse((root / "backups").exists())


if __name__ == "__main__":
    unittest.main()
