"""Tests for MTA-SIM dataset loading.

Covers loading from a directory outside the repository, header and scope
validation, the optional performance table, and the structural guarantees that
keep ground truth out of the model-facing dataset.
"""

from __future__ import annotations

import csv
import dataclasses
import inspect
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

import mta_sim_fixtures as fixtures  # noqa: E402
from dataloader import (  # noqa: E402
    GROUND_TRUTH_ONLY_FIELDS,
    MTA_SIM_ADS_FIELDS,
    MtaSimDataset,
    four_segment_touchpoints_from_path_rows,
    load_amazon_ads_daily_touchpoint_performance,
    load_amc_path_report,
    load_mta_sim_dataset,
)
from touchpoint_adapter import SimulatorConfig  # noqa: E402


class DataloaderTestCase(unittest.TestCase):
    """Base case that writes fixtures into a directory outside the repository."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="mta_sim_")
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)
        self.paths = fixtures.write_dataset(self.directory)
        self.config = SimulatorConfig.from_mapping(fixtures.SIMULATOR_COST_TYPES)

    def load(self) -> MtaSimDataset:
        return load_mta_sim_dataset(
            self.paths["path_report"], self.paths["ads_performance"], config=self.config
        )

    def rewrite_csv(self, path: Path, rows: list[dict], fieldnames: tuple[str, ...]) -> Path:
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=list(fieldnames), lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        return path

    def read_csv(self, path: Path) -> list[dict]:
        with path.open(newline="") as handle:
            return list(csv.DictReader(handle))


class ExternalPathLoadingTest(DataloaderTestCase):
    def test_loads_from_a_directory_outside_the_repository(self) -> None:
        repository_root = ROOT.parents[1]
        self.assertNotIn(repository_root, self.paths["path_report"].parents)

        dataset = self.load()
        self.assertEqual(dataset.scope.report_start_date, fixtures.REPORT_START)
        self.assertEqual(dataset.scope.report_end_date, fixtures.REPORT_END)
        self.assertEqual(dataset.scope.marketplace, fixtures.MARKETPLACE)
        self.assertEqual(dataset.scope.advertiser_id, fixtures.ADVERTISER_ID)

    def test_missing_file_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_amc_path_report(self.directory / "absent.csv", config=self.config)
        with self.assertRaises(FileNotFoundError):
            load_amazon_ads_daily_touchpoint_performance(
                self.directory / "absent.csv", config=self.config
            )

    def test_touchpoints_are_four_segment_and_paths_are_five_segment(self) -> None:
        dataset = self.load()
        self.assertEqual(
            dataset.touchpoints,
            tuple(sorted(fixtures.SIMULATOR_COST_TYPES)),
        )
        for row in dataset.path_rows:
            for part in str(row["path"]).split(">"):
                self.assertEqual(len(part.strip().split(":")), 5)
        self.assertEqual(
            four_segment_touchpoints_from_path_rows(dataset.path_rows),
            dataset.touchpoints,
        )

    def test_five_segment_touchpoints_follow_the_configured_cost_types(self) -> None:
        dataset = self.load()
        self.assertEqual(
            dataset.five_segment_touchpoints(),
            tuple(
                sorted(
                    (
                        f"{fixtures.DISPLAY}:IMPRESSION",
                        f"{fixtures.SEARCH}:CLICK",
                        f"{fixtures.BRAND}:CLICK",
                    )
                )
            ),
        )

    def test_outcome_totals_match_the_path_report(self) -> None:
        dataset = self.load()
        self.assertEqual(
            dict(dataset.outcome_totals),
            {"converted_users": 85.0, "purchase_count": 105.0, "revenue": 10500.0},
        )

    def test_performance_table_is_optional(self) -> None:
        dataset = load_mta_sim_dataset(self.paths["path_report"], config=self.config)
        self.assertEqual(dataset.ads_rows, ())
        self.assertEqual(dataset.touchpoints, tuple(sorted(fixtures.SIMULATOR_COST_TYPES)))

    def test_performance_rows_are_annotated_and_keep_units_sold(self) -> None:
        dataset = self.load()
        self.assertEqual(len(dataset.ads_rows), 6)
        for row in dataset.ads_rows:
            self.assertIn(row["touchpoint"], fixtures.SIMULATOR_COST_TYPES)
            self.assertEqual(
                row["cost_type"], fixtures.SIMULATOR_COST_TYPES[row["touchpoint"]]
            )
            self.assertEqual(
                row["five_segment_touchpoint"],
                self.config.to_five_segment(row["touchpoint"]),
            )
            self.assertEqual(row["unitsSold"], "6")


class GroundTruthIsolationTest(DataloaderTestCase):
    def test_dataset_has_no_ground_truth_field(self) -> None:
        names = {field.name for field in dataclasses.fields(MtaSimDataset)}
        self.assertEqual(names & GROUND_TRUTH_ONLY_FIELDS, set())
        self.assertNotIn("ground_truth", names)

    def test_dataset_loader_accepts_no_ground_truth_argument(self) -> None:
        parameters = set(inspect.signature(load_mta_sim_dataset).parameters)
        self.assertEqual(parameters, {"path_report", "ads_performance", "config"})

    def test_no_loaded_row_carries_a_ground_truth_column(self) -> None:
        dataset = self.load()
        for row in (*dataset.path_rows, *dataset.ads_rows):
            self.assertEqual(set(row) & GROUND_TRUTH_ONLY_FIELDS, set())

    def test_ground_truth_column_in_path_report_is_rejected(self) -> None:
        rows = self.read_csv(self.paths["path_report"])
        for row in rows:
            row["credit_share"] = "0.5"
        self.rewrite_csv(
            self.paths["path_report"],
            rows,
            fixtures.PATH_REPORT_FIELDS + ("credit_share",),
        )
        with self.assertRaisesRegex(ValueError, "simulation_ground_truth column"):
            load_amc_path_report(self.paths["path_report"], config=self.config)

    def test_ground_truth_column_in_performance_table_is_rejected(self) -> None:
        rows = self.read_csv(self.paths["ads_performance"])
        for row in rows:
            row["causal_increment"] = "0.1"
        self.rewrite_csv(
            self.paths["ads_performance"],
            rows,
            MTA_SIM_ADS_FIELDS + ("causal_increment",),
        )
        with self.assertRaisesRegex(ValueError, "simulation_ground_truth column"):
            load_amazon_ads_daily_touchpoint_performance(
                self.paths["ads_performance"], config=self.config
            )


class ContractViolationTest(DataloaderTestCase):
    def test_unmapped_touchpoint_is_rejected(self) -> None:
        partial = SimulatorConfig.from_mapping({fixtures.SEARCH: "CPC"})
        with self.assertRaisesRegex(ValueError, "missing simulator cost_type"):
            load_amc_path_report(self.paths["path_report"], config=partial)

    def test_multiple_report_scopes_are_rejected(self) -> None:
        rows = self.read_csv(self.paths["path_report"])
        rows[0]["marketplace"] = "UK"
        self.rewrite_csv(self.paths["path_report"], rows, fixtures.PATH_REPORT_FIELDS)
        with self.assertRaisesRegex(ValueError, "exactly one report window"):
            load_amc_path_report(self.paths["path_report"], config=self.config)

    def test_inverted_report_window_is_rejected(self) -> None:
        rows = self.read_csv(self.paths["path_report"])
        for row in rows:
            row["report_start_date"] = "2026-02-01"
        self.rewrite_csv(self.paths["path_report"], rows, fixtures.PATH_REPORT_FIELDS)
        with self.assertRaisesRegex(ValueError, "report window is inverted"):
            load_amc_path_report(self.paths["path_report"], config=self.config)

    def test_unexpected_path_report_header_is_rejected(self) -> None:
        rows = self.read_csv(self.paths["path_report"])
        self.rewrite_csv(
            self.paths["path_report"],
            [{**row, "extra": "1"} for row in rows],
            fixtures.PATH_REPORT_FIELDS + ("extra",),
        )
        with self.assertRaises(ValueError):
            load_amc_path_report(self.paths["path_report"], config=self.config)

    def test_unexpected_performance_header_is_rejected(self) -> None:
        rows = []
        for row in self.read_csv(self.paths["ads_performance"]):
            row["unitsSoldTypo"] = row.pop("unitsSold")
            rows.append(row)
        self.rewrite_csv(
            self.paths["ads_performance"],
            rows,
            MTA_SIM_ADS_FIELDS[:-1] + ("unitsSoldTypo",),
        )
        with self.assertRaisesRegex(ValueError, "header must exactly match"):
            load_amazon_ads_daily_touchpoint_performance(
                self.paths["ads_performance"], config=self.config
            )

    def test_normalized_touchpoint_mismatch_is_rejected(self) -> None:
        rows = self.read_csv(self.paths["ads_performance"])
        rows[0]["normalizedTouchpoint"] = fixtures.BRAND
        self.rewrite_csv(self.paths["ads_performance"], rows, MTA_SIM_ADS_FIELDS)
        with self.assertRaisesRegex(ValueError, "normalizedTouchpoint mismatch"):
            load_amazon_ads_daily_touchpoint_performance(
                self.paths["ads_performance"], config=self.config
            )

    def test_performance_scope_mismatch_is_rejected(self) -> None:
        rows = self.read_csv(self.paths["ads_performance"])
        for row in rows:
            row["accountId"] = "OTHER"
        self.rewrite_csv(self.paths["ads_performance"], rows, MTA_SIM_ADS_FIELDS)
        with self.assertRaisesRegex(ValueError, "scope mismatch"):
            self.load()

    def test_path_contract_violation_is_rejected(self) -> None:
        rows = self.read_csv(self.paths["path_report"])
        rows[0]["converted_users"] = str(int(rows[0]["users"]) + 1)
        self.rewrite_csv(self.paths["path_report"], rows, fixtures.PATH_REPORT_FIELDS)
        with self.assertRaisesRegex(ValueError, "converted_users must be <= users"):
            load_amc_path_report(self.paths["path_report"], config=self.config)

    def test_empty_path_report_is_rejected(self) -> None:
        self.rewrite_csv(self.paths["path_report"], [], fixtures.PATH_REPORT_FIELDS)
        with self.assertRaisesRegex(ValueError, "at least one data row"):
            load_amc_path_report(self.paths["path_report"], config=self.config)


if __name__ == "__main__":
    unittest.main()
