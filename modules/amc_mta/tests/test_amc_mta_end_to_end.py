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
import generate_simulated_amazon_ads_report as ads_generator  # noqa: E402
from generate_simulated_amazon_ads_report import FIELDS, generate_file, generate_rows  # noqa: E402
from generate_simulated_amc_touchpoint_events import generate_rows as generate_event_rows  # noqa: E402
from regenerate_simulated_dataset import regenerate  # noqa: E402
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
from simulated_touchpoints import TOUCHPOINT_CATALOG, TOUCHPOINT_KEYS  # noqa: E402


RELIABILITY_FIELDS = {
    "calculation_valid",
    "data_support_sufficient",
    "models_consistent",
    "reliability_status",
    "reliability_reason",
}


class EndToEndSampleTests(unittest.TestCase):
    def test_ads_subrange_and_cross_year_use_fixed_epoch(self) -> None:
        full = generate_rows(date(2026, 1, 1), date(2026, 12, 31))
        sliced = generate_rows(date(2026, 4, 3), date(2026, 4, 9))
        self.assertEqual(sliced, [row for row in full if "2026-04-03" <= row["reportDate"] <= "2026-04-09"])
        cross_year = generate_rows(date(2025, 12, 31), date(2026, 1, 1))
        self.assertEqual(cross_year[-17:], generate_rows(date(2026, 1, 1), date(2026, 1, 1)))
        self.assertEqual(len({(row["reportDate"], row["normalizedTouchpoint"]) for row in full}), 365 * 17)

    def test_annual_event_sample_is_complete_and_reproducible(self) -> None:
        rows = generate_event_rows()
        stored = read_csv(AMC_TOUCHPOINT_EVENTS_FILE)
        self.assertEqual([{key: str(row.get(key, "")) for key in stored[0]} for row in rows], stored)
        self.assertEqual(len(rows), 520)
        self.assertEqual(len({row["journey_id"] for row in rows}), 146)
        conversions = [row for row in rows if row["event_type"] == "CONVERSION"]
        self.assertEqual(len(conversions), 158)
        self.assertEqual({row["event_time"][:7] for row in conversions}, {f"2026-{month:02d}" for month in range(1, 13)})
        annual_conversions = [
            row for row in conversions if row["journey_id"].startswith("annual_")
        ]
        monthly = {
            f"2026-{month:02d}": sum(
                row["event_time"].startswith(f"2026-{month:02d}")
                for row in annual_conversions
            )
            for month in range(1, 13)
        }
        self.assertEqual(set(monthly.values()), {13})

    def test_annual_journeys_accept_once_and_boundary_fixtures_are_rejected(self) -> None:
        rows = generate_event_rows()
        journey_ids = {row["journey_id"] for row in rows}
        annual_ids = {value for value in journey_ids if value.startswith("annual_")}
        secondary_ids = {f"annual_{month:02d}_00" for month in range(1, 13)}
        self.assertEqual(len(annual_ids), 144)
        self.assertEqual(
            {value for value in annual_ids if sum(
                row["event_type"] == "CONVERSION" and row["journey_id"] == value
                for row in rows
            ) == 2},
            secondary_ids,
        )
        for journey_id in annual_ids:
            journey_rows = [row for row in rows if row["journey_id"] == journey_id]
            built = build_aggregated_path_rows(
                journey_rows, REPORT_START_DATE, REPORT_END_DATE, 14
            )
            self.assertEqual(len(built), 1, journey_id)
        for journey_id in ("reject_start", "reject_gap"):
            journey_rows = [row for row in rows if row["journey_id"] == journey_id]
            self.assertEqual(
                build_aggregated_path_rows(
                    journey_rows, REPORT_START_DATE, REPORT_END_DATE, 14
                ),
                [],
            )

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
        self.assertEqual(len(stored), 144)
        self.assertEqual(len({row["path"] for row in stored}), 144)
        self.assertTrue(all("reject_" not in row["path"] for row in stored))
        first_counts = {}
        for row in stored:
            first = row["path"].split(" > ")[0]
            first_counts[first] = first_counts.get(first, 0) + 1
        self.assertEqual(len(first_counts), 17)
        self.assertLessEqual(max(first_counts.values()) - min(first_counts.values()), 1)
        self.assertEqual(sum(int(row["converted_users"]) for row in stored), 3316)
        self.assertEqual(sum(int(row["purchase_count"]) for row in stored), 4185)
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
        self.assertEqual(len(stored), 365 * 17)
        expected_keys = set(TOUCHPOINT_KEYS)
        self.assertEqual(len(expected_keys), 17)
        self.assertEqual({row["reportDate"] for row in stored}, {
            date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + offset).isoformat()
            for offset in range(365)
        })
        for report_date in {row["reportDate"] for row in stored}:
            daily = [row for row in stored if row["reportDate"] == report_date]
            self.assertEqual(len(daily), 17)
            self.assertEqual({row["normalizedTouchpoint"] for row in daily}, expected_keys)
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

    def test_ads_billing_semantics_and_invalid_range_preserves_file(self) -> None:
        rows = generate_rows(date(2026, 1, 1), date(2026, 1, 1))
        for row in rows:
            if row["interaction_type"] == "CLICK":
                self.assertEqual(row["cost_type"], "CPC")
                self.assertGreater(row["clicks"], 0)
                self.assertGreaterEqual(row["purchases"], 0)
            else:
                self.assertEqual(row["cost_type"], "CPM")
                self.assertEqual(row["clicks"], 0)
                self.assertEqual(row["purchases"], 0)
                self.assertEqual(row["sales"], 0)
            spec = next(spec for spec in TOUCHPOINT_CATALOG if spec.key == row["normalizedTouchpoint"])
            if spec.interaction_type != spec.billed_interaction:
                self.assertEqual(row["cost"], 0)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ads.csv"
            output.write_bytes(b"old artifact\n")
            with self.assertRaisesRegex(ValueError, "on or before"):
                generate_file(output, date(2026, 2, 1), date(2026, 1, 1))
            self.assertEqual(output.read_bytes(), b"old artifact\n")

    def test_catalog_drift_fails_before_ads_generation(self) -> None:
        with patch.object(ads_generator, "TOUCHPOINT_CATALOG", TOUCHPOINT_CATALOG[:-1]):
            with self.assertRaisesRegex(ValueError, "exactly 17"):
                ads_generator.generate_rows(date(2026, 1, 1), date(2026, 1, 1))

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
            self.assertTrue(
                all(b"\r\n" not in path.read_bytes() for path in generated_paths)
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
                        3316.0,
                        places=4,
                    )
                    self.assertAlmostEqual(
                        sum(float(row["attributed_purchase_count"]) for row in generated),
                        4185.0,
                        places=4,
                    )
                    self.assertAlmostEqual(
                        sum(float(row["attributed_revenue"]) for row in generated),
                        343161.0,
                        places=2,
                    )
                    self.assertTrue(
                        all(len(row["touchpoint"].split(":")) == 5 for row in generated)
                    )
                    self.assertTrue(all("cost" in row for row in generated))
                    self.assertTrue(
                        all(row["interaction_type"] in {"IMPRESSION", "CLICK"} for row in generated)
                    )
                    self.assertTrue(RELIABILITY_FIELDS.isdisjoint(generated[0]))

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
            self.assertTrue(
                all(set(row) == set(TOUCHPOINT_COMPARISON_FIELDS) for row in comparison_rows)
            )
            self.assertTrue(all(set(row) == set(SUMMARY_FIELDS) for row in summary_rows))
            self.assertTrue(
                all(set(row) == set(RECOMMENDED_FIELDS) for row in recommended_rows)
            )
            self.assertEqual(len(RECOMMENDED_FIELDS), 15)
            self.assertTrue(
                all(row["calculation_valid"] == "true" for row in comparison_rows)
            )
            self.assertEqual(
                sum(row["data_support_sufficient"] == "true" for row in comparison_rows),
                51,
            )
            supported_rows = [
                row for row in comparison_rows if row["data_support_sufficient"] == "true"
            ]
            self.assertTrue(all(row["models_consistent"] == "true" for row in supported_rows))
            self.assertEqual(
                sum(row["reliability_status"] == "RELIABLE" for row in comparison_rows),
                51,
            )
            self.assertTrue(
                all(row["reliability_status"] == "RELIABLE" for row in comparison_rows)
            )
            self.assertTrue(
                all(
                    row["recommended_value"] == row["official_share"]
                    for row in recommended_rows
                )
            )
            comparison_reliability = {
                (row["touchpoint"], row["outcome"]): tuple(
                    row[field] for field in RELIABILITY_FIELDS
                )
                for row in comparison_rows
            }
            self.assertTrue(
                all(
                    comparison_reliability[(row["touchpoint"], row["outcome"])]
                    == tuple(row[field] for field in RELIABILITY_FIELDS)
                    for row in recommended_rows
                )
            )
            self.assertTrue(all(row["calculation_valid"] == "true" for row in summary_rows))
            self.assertTrue(
                all(row["data_support_sufficient"] == "true" for row in summary_rows)
            )
            self.assertTrue(all(row["models_consistent"] == "true" for row in summary_rows))
            self.assertTrue(
                all(row["reliability_status"] == "RELIABLE" for row in summary_rows)
            )
            self.assertTrue(
                all(
                    row["reliability_reason"]
                    == "ALL_CRITERIA_PASSED"
                    for row in summary_rows
                )
            )
            self.assertTrue(
                all(
                    canonicalize_amc_touchpoint_key(row["touchpoint"])
                    == row["touchpoint"]
                    for row in comparison_rows
                )
            )
            self.assertTrue(
                all(row["touchpoint"].rsplit(":", 1)[1] == row["interaction_type"] for row in recommended_rows)
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
            for row in comparison_rows + summary_rows + recommended_rows:
                self.assertTrue(forbidden_reason_codes.isdisjoint(row))
                self.assertNotIn("reason_code", row)
            expected_reasons = {
                "NO_OUTCOME": {"NO_OUTCOME"},
                "LONG_TAIL": {"LONG_TAIL", "LONG_TAIL_MODEL_SENSITIVE"},
                "SMALL": {"ALIGNED"},
                "MEDIUM": {"MODEL_REVIEW"},
                "LARGE": {"ABSOLUTE_GAP", "RELATIVE_AND_ABSOLUTE_GAP"},
            }
            self.assertTrue(all("difference_level" not in row for row in comparison_rows + summary_rows + recommended_rows))
            self.assertEqual(
                len({(row["touchpoint"], row["outcome"]) for row in comparison_rows}),
                51,
            )

            five_part = {row["outcome"]: row for row in summary_rows}
            expected = {
                "converted_users": (0.014066, 0.740650047, 0.4),
                "purchase_count": (0.013891, 0.776211059, 0.6),
                "revenue": (0.014266, 0.796568627, 0.4),
            }
            for outcome, (tvd, rho, overlap) in expected.items():
                with self.subTest(outcome=outcome):
                    self.assertAlmostEqual(float(five_part[outcome]["tvd"]), tvd, places=6)
                    self.assertAlmostEqual(float(five_part[outcome]["spearman_rho"]), rho, places=6)
                    self.assertAlmostEqual(float(five_part[outcome]["top_k_overlap_rate"]), overlap)

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

    def test_invalid_amc_report_date_fails_before_comparison_publication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            invalid_rows = read_csv(AMC_REPORT_FILE)
            invalid_rows[0]["report_start_date"] = "not-a-date"
            invalid_amc = Path(tmp) / "invalid-amc.csv"
            write_csv(invalid_amc, invalid_rows, PATH_REPORT_FIELDS)
            output_dir = Path(tmp) / "outputs"
            attribution_dir = ROOT / "outputs" / "attribution"

            with self.assertRaisesRegex(ValueError, "ISO dates"):
                compare_model_files(
                    attribution_dir / MARKOV_OUTPUT_FILE,
                    attribution_dir / SHAPLEY_OUTPUT_FILE,
                    invalid_amc,
                    AMAZON_ADS_REPORT_FILE,
                    output_dir,
                )

            self.assertFalse(output_dir.exists())

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

    def test_complete_dataset_is_byte_reproducible_and_rolls_back_all_eight(self) -> None:
        names = [
            Path(AMC_TOUCHPOINT_EVENTS_FILE).name,
            Path(AMAZON_ADS_REPORT_FILE).name,
            Path(AMC_REPORT_FILE).name,
            MARKOV_OUTPUT_FILE,
            SHAPLEY_OUTPUT_FILE,
            MODEL_COMPARISON_TOUCHPOINTS_FILE,
            MODEL_COMPARISON_SUMMARY_FILE,
            RECOMMENDED_ATTRIBUTION_FILE,
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destinations = [root / f"{index}_{name}" for index, name in enumerate(names)]
            # Output matching is filename-based, so preserve the five model filenames.
            destinations[3:] = [root / "outputs" / name for name in names[3:]]
            destinations[:3] = [root / name for name in names[:3]]
            regenerate(destinations)
            first = {path: path.read_bytes() for path in destinations}
            regenerate(destinations)
            self.assertEqual(first, {path: path.read_bytes() for path in destinations})

            old = {path: f"old-{index}\n".encode() for index, path in enumerate(destinations)}
            for path, content in old.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            real_replace = __import__("os").replace
            call_count = 0

            def fail_on_fifth_replace(source: Path, destination: Path) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 5:
                    raise OSError("simulated fifth publication failure")
                real_replace(source, destination)

            with patch("run_pipeline.os.replace", side_effect=fail_on_fifth_replace):
                with self.assertRaisesRegex(OSError, "fifth publication failure"):
                    regenerate(destinations)
            self.assertEqual(old, {path: path.read_bytes() for path in destinations})

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
