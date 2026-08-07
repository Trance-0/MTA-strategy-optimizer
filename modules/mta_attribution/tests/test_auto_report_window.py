"""Tests that the report window is inferred from the Ads report.

The published window must come from the delivery data rather than from
configuration, so these tests assert the pipeline never reads the fixed dates in
`config` when an Ads report is supplied, and that custom paths are honoured.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
SRC = ROOT / "src"
SCRIPTS = PROJECT_ROOT / "script"
sys.path[:0] = [str(ROOT), str(SRC), str(SCRIPTS)]

from attribution_contract import read_csv, write_csv  # noqa: E402
from config import (  # noqa: E402
    MARKOV_OUTPUT_FILE,
    MODEL_COMPARISON_SUMMARY_FILE,
    MODEL_COMPARISON_TOUCHPOINTS_FILE,
    RECOMMENDED_ATTRIBUTION_FILE,
    SHAPLEY_OUTPUT_FILE,
)
from generate_simulated_amazon_ads_report import FIELDS as ADS_FIELDS  # noqa: E402
from generate_simulated_amc_touchpoint_events import FIELDS as EVENT_FIELDS  # noqa: E402
from build_path_report import build_path_report  # noqa: E402
from run_pipeline import parse_args, run_pipeline  # noqa: E402
from validate_data_alignment import infer_ads_report_window  # noqa: E402


TOUCHPOINT = "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED:CLICK"


def ads_row(day: str, *, account: str = "adv_test") -> dict:
    return {
        "reportDate": day,
        "marketplace": "US",
        "accountId": account,
        "adProduct": "SPONSORED_PRODUCTS",
        "adType": "PRODUCT_AD",
        "creativeType": "",
        "inventoryType": "",
        "placement": "TOP_OF_SEARCH",
        "interaction_type": "CLICK",
        "cost_type": "CPC",
        "normalizedTouchpoint": TOUCHPOINT,
        "impressions": "0",
        "clicks": "10",
        "cost": "5",
        "purchases": "2",
        "sales": "100",
        "currencyCode": "USD",
    }


def touch(journey: str, when: str) -> dict:
    return {
        "journey_id": journey,
        "event_type": "TOUCHPOINT",
        "event_time": when,
        "ad_product": "SPONSORED_PRODUCTS",
        "format": "PRODUCT_AD",
        "placement": "TOP_OF_SEARCH",
        "creative": "",
        "interaction_type": "CLICK",
        "marketplace": "",
        "advertiser_id": "",
        "users": "",
        "converted_users": "",
        "purchase_count": "",
        "revenue": "",
        "new_to_brand_purchases": "",
    }


def conversion(journey: str, when: str) -> dict:
    return {
        "journey_id": journey,
        "event_type": "CONVERSION",
        "event_time": when,
        "ad_product": "",
        "format": "",
        "placement": "",
        "creative": "",
        "interaction_type": "",
        "marketplace": "US",
        "advertiser_id": "adv_test",
        "users": "10",
        "converted_users": "2",
        "purchase_count": "3",
        "revenue": "120",
        "new_to_brand_purchases": "1",
    }


class AutoReportWindowTests(unittest.TestCase):
    def test_infers_single_day_cross_year_and_leap_windows(self) -> None:
        self.assertEqual(
            infer_ads_report_window([ads_row("2028-02-29")]),
            (date(2028, 2, 29), date(2028, 2, 29)),
        )
        rows = [ads_row(day) for day in ("2027-12-31", "2028-01-01")]
        self.assertEqual(
            infer_ads_report_window(rows),
            (date(2027, 12, 31), date(2028, 1, 1)),
        )

    def test_rejects_empty_bad_gapped_duplicate_and_multi_scope_ads(self) -> None:
        cases = [
            ([], "at least one row"),
            ([ads_row("not-a-date")], "YYYY-MM-DD"),
            ([ads_row("20280228")], "YYYY-MM-DD"),
            ([ads_row("2028-02-30")], "ISO date"),
            ([ads_row("2028-02-28"), ads_row("2028-03-01")], "continuous"),
            ([ads_row("2028-02-28"), ads_row("2028-02-28")], "duplicate"),
            (
                [ads_row("2028-02-28"), ads_row("2028-02-29", account="other")],
                "one marketplace/account/currency",
            ),
        ]
        for rows, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                infer_ads_report_window(rows)

    def test_rejects_a_daily_touchpoint_set_change(self) -> None:
        extra = ads_row("2028-02-29")
        extra.update(
            {
                "placement": "PRODUCT_PAGE",
                "normalizedTouchpoint": (
                    "SPONSORED_PRODUCTS:PRODUCT_AD:PRODUCT_PAGE:UNSPECIFIED:CLICK"
                ),
            }
        )
        with self.assertRaisesRegex(ValueError, "same touchpoint set every day"):
            infer_ads_report_window(
                [ads_row("2028-02-28"), ads_row("2028-02-29"), extra]
            )

    def test_custom_pipeline_uses_ads_window_and_never_reads_fixed_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.csv"
            ads = root / "ads.csv"
            path_report = root / "derived" / "paths.csv"
            output_dir = root / "derived" / "outputs"
            write_csv(
                events,
                [
                    touch("j1", "2028-02-28T01:00:00Z"),
                    conversion("j1", "2028-02-29T02:00:00Z"),
                ],
                EVENT_FIELDS,
            )
            write_csv(
                ads,
                [ads_row("2028-02-28"), ads_row("2028-02-29")],
                ADS_FIELDS,
            )
            expected_events = events.read_bytes()
            expected_ads = ads.read_bytes()

            with patch("config.REPORT_START_DATE", "1900-01-01"), patch(
                "config.REPORT_END_DATE", "1900-01-02"
            ):
                outputs = run_pipeline(events, ads, path_report, output_dir)

            self.assertEqual(len(outputs), 6)
            self.assertTrue(all(path.exists() for path in outputs))
            paths = read_csv(path_report)
            self.assertEqual(
                {(row["report_start_date"], row["report_end_date"]) for row in paths},
                {("2028-02-28", "2028-02-29")},
            )
            self.assertEqual(events.read_bytes(), expected_events)
            self.assertEqual(ads.read_bytes(), expected_ads)

    def test_invalid_or_zero_path_input_preserves_all_six_artifacts(self) -> None:
        filenames = [
            "paths.csv",
            MARKOV_OUTPUT_FILE,
            SHAPLEY_OUTPUT_FILE,
            MODEL_COMPARISON_TOUCHPOINTS_FILE,
            MODEL_COMPARISON_SUMMARY_FILE,
            RECOMMENDED_ATTRIBUTION_FILE,
        ]
        invalid_events = (
            [],
            [touch("j1", "2028-02-28T01:00:00Z")],
            [conversion("j1", "2028-02-29T02:00:00Z")],
            [
                touch("j1", "2028-02-28T01:00:00Z"),
                conversion("j1", "2028-03-01T02:00:00Z"),
            ],
        )
        for index, rows in enumerate(invalid_events):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                events = root / "events.csv"
                ads = root / "ads.csv"
                path_report = root / "derived" / filenames[0]
                output_dir = root / "derived" / "outputs"
                write_csv(events, rows, EVENT_FIELDS)
                write_csv(
                    ads,
                    [ads_row("2028-02-28"), ads_row("2028-02-29")],
                    ADS_FIELDS,
                )
                destinations = [path_report, *[output_dir / name for name in filenames[1:]]]
                old = {}
                for artifact_index, path in enumerate(destinations):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    content = f"old-{artifact_index}\n".encode()
                    path.write_bytes(content)
                    old[path] = content

                with self.assertRaises(ValueError):
                    run_pipeline(events, ads, path_report, output_dir)
                self.assertEqual(old, {path: path.read_bytes() for path in destinations})

    def test_invalid_ads_preserves_all_six_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.csv"
            ads = root / "ads.csv"
            path_report = root / "derived" / "paths.csv"
            output_dir = root / "derived" / "outputs"
            write_csv(
                events,
                [
                    touch("j1", "2028-02-28T01:00:00Z"),
                    conversion("j1", "2028-03-01T02:00:00Z"),
                ],
                EVENT_FIELDS,
            )
            write_csv(
                ads,
                [ads_row("2028-02-28"), ads_row("2028-03-01")],
                ADS_FIELDS,
            )
            destinations = [
                path_report,
                output_dir / MARKOV_OUTPUT_FILE,
                output_dir / SHAPLEY_OUTPUT_FILE,
                output_dir / MODEL_COMPARISON_TOUCHPOINTS_FILE,
                output_dir / MODEL_COMPARISON_SUMMARY_FILE,
                output_dir / RECOMMENDED_ATTRIBUTION_FILE,
            ]
            old = {}
            for index, path in enumerate(destinations):
                path.parent.mkdir(parents=True, exist_ok=True)
                old[path] = f"old-{index}\n".encode()
                path.write_bytes(old[path])

            with self.assertRaisesRegex(ValueError, "continuous"):
                run_pipeline(events, ads, path_report, output_dir)
            self.assertEqual(old, {path: path.read_bytes() for path in destinations})

    def test_standalone_builder_and_cli_use_custom_ads_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.csv"
            ads = root / "ads.csv"
            output = root / "path.csv"
            write_csv(
                events,
                [
                    touch("j1", "2028-02-28T01:00:00Z"),
                    conversion("j1", "2028-02-29T02:00:00Z"),
                ],
                EVENT_FIELDS,
            )
            write_csv(
                ads,
                [ads_row("2028-02-28"), ads_row("2028-02-29")],
                ADS_FIELDS,
            )
            build_path_report(events, output, amazon_ads_report=ads)
            self.assertEqual(read_csv(output)[0]["report_end_date"], "2028-02-29")

            output.write_bytes(b"previous valid path report\n")
            write_csv(
                events,
                [conversion("j1", "2028-02-29T02:00:00Z")],
                EVENT_FIELDS,
            )
            with self.assertRaisesRegex(ValueError, "zero valid attribution paths"):
                build_path_report(events, output, amazon_ads_report=ads)
            self.assertEqual(output.read_bytes(), b"previous valid path report\n")

            argv = [
                "run_pipeline.py",
                "--events-file",
                str(events),
                "--amazon-ads-report",
                str(ads),
                "--path-report",
                str(output),
                "--output-dir",
                str(root / "out"),
            ]
            with patch.object(sys, "argv", argv):
                args = parse_args()
            self.assertEqual(args.events_file, events)
            self.assertEqual(args.amazon_ads_report, ads)
            self.assertEqual(args.path_report, output)

    def test_rejects_output_paths_that_would_overwrite_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = root / "events.csv"
            ads = root / "ads.csv"
            events.touch()
            ads.touch()
            with self.assertRaisesRegex(ValueError, "must not overwrite an input"):
                run_pipeline(events, ads, events, root / "outputs")
            with self.assertRaisesRegex(ValueError, "must not overwrite an input"):
                build_path_report(events, events, amazon_ads_report=ads)

            alias = root / "events-alias.csv"
            os.link(events, alias)
            with self.assertRaisesRegex(ValueError, "must not overwrite an input"):
                run_pipeline(events, ads, alias, root / "other-outputs")

            with self.assertRaisesRegex(ValueError, "must not contain one another"):
                run_pipeline(
                    events,
                    ads,
                    root / "derived",
                    root / "derived" / "outputs",
                )


if __name__ == "__main__":
    unittest.main()
