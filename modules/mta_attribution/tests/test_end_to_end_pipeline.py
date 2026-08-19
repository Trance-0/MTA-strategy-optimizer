"""End-to-end tests for the full attribution pipeline.

Asserts that the shipped sample dataset regenerates byte-identically, that all
six artifacts publish atomically, that a validation failure rolls the whole set
back, and that attributed outcomes conserve against the path report totals.
"""

from __future__ import annotations

import csv
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


from modules.mta_attribution.config import (
    AMAZON_ADS_REPORT_FILE,
    AMC_REPORT_FILE,
    AMC_TOUCHPOINT_ENTITY_AGGREGATE_FILE,
    AMC_TOUCHPOINT_EVENTS_FILE,
    MARKOV_OUTPUT_FILE,
    MODEL_COMPARISON_SUMMARY_FILE,
    MODEL_COMPARISON_TOUCHPOINTS_FILE,
    RECOMMENDED_ATTRIBUTION_FILE,
    REPORT_END_DATE,
    REPORT_START_DATE,
    SIMULATED_MAX_USER_EVENT_ROWS,
    SIMULATED_PRIVACY_MIN_USERS,
    SHAPLEY_OUTPUT_FILE,
    SYNTHETIC_USER_EVENTS_FILE,
)
from modules.mta_attribution.src.attribution_contract import (
    PATH_FIELD_DESCRIPTIONS,
    read_csv,
    write_csv  # noqa: E402,
)
from modules.mta_attribution.src.attribution_model_comparison import (
    RECOMMENDED_FIELDS,
    SUMMARY_FIELDS,
    TOUCHPOINT_COMPARISON_FIELDS,
)
from modules.mta_attribution.src.path_report_builder import (
    PATH_REPORT_FIELDS,
    build_aggregated_path_rows,
)
from modules.mta_attribution.src.simulated_touchpoints import (
    TOUCHPOINT_CATALOG,
    TOUCHPOINT_KEYS,
    validate_touchpoint_catalog,
)
from modules.mta_attribution.src import synthetic_event_pipeline as synthetic_pipeline
from modules.mta_attribution.src.synthetic_event_pipeline import (
    AMC_EVENT_FIELDS,
    ENTITY_AGGREGATE_FIELDS,
    SYNTHETIC_EVENT_FIELDS,
    derive_amazon_ads_rows,
    derive_amc_touchpoint_events,
    derive_touchpoint_entity_aggregate,
    generate_synthetic_user_events,
    validate_derivations,
    validate_synthetic_user_events,
)
from modules.mta_attribution.src.touchpoint_key import canonicalize_amc_touchpoint_key
from script.build_path_report import build_path_report
from script.compare_attribution_models import compare_model_files
from script.generate_simulated_amazon_ads_report import FIELDS, generate_file, generate_rows
from script.generate_simulated_amc_touchpoint_events import (
    generate_rows as generate_event_rows,
)
from script.regenerate_simulated_dataset import regenerate
from script.run_attribution_models import run_attribution_models
from script.run_pipeline import match_outputs_by_name, publish_with_rollback
from script.validate_data_alignment import validate_data_alignment_rows


ROOT = Path(__file__).resolve().parents[1]


RELIABILITY_FIELDS = {
    "calculation_valid",
    "data_support_sufficient",
    "models_consistent",
    "reliability_status",
    "reliability_reason",
}


class EndToEndSampleTests(unittest.TestCase):
    def test_ads_short_window_is_deterministic_and_has_complete_grid(self) -> None:
        start = date(2026, 1, 1)
        end = date(2026, 1, 7)
        first = generate_rows(start, end)
        second = generate_rows(start, end)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 7 * 17)
        self.assertEqual(
            len({(row["reportDate"], row["normalizedTouchpoint"]) for row in first}),
            7 * 17,
        )

    def test_anonymous_event_sample_is_derived_and_reproducible(self) -> None:
        rows = generate_event_rows()
        stored = read_csv(AMC_TOUCHPOINT_EVENTS_FILE)
        self.assertEqual([{key: str(row.get(key, "")) for key in stored[0]} for row in rows], stored)
        source = read_csv(SYNTHETIC_USER_EVENTS_FILE)
        expected = derive_amc_touchpoint_events(source)
        self.assertEqual(
            [{field: str(row.get(field, "")) for field in AMC_EVENT_FIELDS} for row in expected],
            stored,
        )
        journey_ids = {row["journey_id"] for row in rows}
        self.assertGreater(len(rows), len(journey_ids))
        conversions = [row for row in rows if row["event_type"] == "CONVERSION"]
        self.assertEqual(len(conversions), len(journey_ids))
        self.assertEqual(
            {row["event_time"][:7] for row in conversions},
            {"2026-01", "2026-02", "2026-03"},
        )
        self.assertTrue(all("synthetic_user_id" not in row for row in stored))

    def test_user_event_source_reconciles_entities_ads_and_privacy_boundary(self) -> None:
        generated = generate_synthetic_user_events(REPORT_START_DATE, REPORT_END_DATE)
        stored_source = read_csv(SYNTHETIC_USER_EVENTS_FILE)
        self.assertEqual(
            [
                {field: str(row.get(field, "")) for field in SYNTHETIC_EVENT_FIELDS}
                for row in generated
            ],
            stored_source,
        )
        self.assertLessEqual(len(stored_source), SIMULATED_MAX_USER_EVENT_ROWS)
        user_count = len({row["synthetic_user_id"] for row in stored_source})
        journey_count = len({row["journey_instance_id"] for row in stored_source})
        self.assertLess(user_count, journey_count)
        outcomes = [row for row in stored_source if row["event_type"] == "OUTCOME"]
        self.assertTrue(any(row["converted"] == "1" for row in outcomes))
        self.assertTrue(any(row["converted"] == "0" for row in outcomes))

        touch_rows = [row for row in stored_source if row["event_type"] == "TOUCHPOINT"]
        search_products = {"SPONSORED_PRODUCTS", "SPONSORED_BRANDS"}
        self.assertTrue(
            all(
                bool(row["keyword_id"]) == (row["ad_product"] in search_products)
                and bool(row["match_type"]) == (row["ad_product"] in search_products)
                for row in touch_rows
            )
        )
        invalid_source = list(stored_source)
        invalid_index = next(
            index
            for index, row in enumerate(invalid_source)
            if row["event_type"] == "TOUCHPOINT" and row["ad_product"] == "AMAZON_DSP"
        )
        invalid_source[invalid_index] = {
            **invalid_source[invalid_index],
            "keyword_id": "K_ILLEGAL",
            "match_type": "EXACT",
        }
        with self.assertRaisesRegex(ValueError, "cannot carry keyword fields"):
            validate_synthetic_user_events(
                invalid_source, REPORT_START_DATE, REPORT_END_DATE
            )

        mismatched_user = list(stored_source)
        journey_id = stored_source[0]["journey_instance_id"]
        journey_indexes = [
            index
            for index, row in enumerate(mismatched_user)
            if row["journey_instance_id"] == journey_id
        ]
        mismatched_user[journey_indexes[0]] = {
            **mismatched_user[journey_indexes[0]],
            "synthetic_user_id": "SYN_U99999",
        }
        with self.assertRaisesRegex(ValueError, "rows must belong to one user"):
            validate_synthetic_user_events(
                mismatched_user, REPORT_START_DATE, REPORT_END_DATE
            )

        amc_rows = read_csv(AMC_TOUCHPOINT_EVENTS_FILE)
        ads_rows = read_csv(AMAZON_ADS_REPORT_FILE)
        entity_rows = read_csv(AMC_TOUCHPOINT_ENTITY_AGGREGATE_FILE)
        expected_entities = derive_touchpoint_entity_aggregate(
            stored_source,
            REPORT_START_DATE,
            REPORT_END_DATE,
            SIMULATED_PRIVACY_MIN_USERS,
        )
        self.assertEqual(
            [
                {field: str(row.get(field, "")) for field in ENTITY_AGGREGATE_FIELDS}
                for row in expected_entities
            ],
            entity_rows,
        )
        self.assertTrue(
            all(int(row["unique_users"]) >= SIMULATED_PRIVACY_MIN_USERS for row in entity_rows)
        )
        self.assertTrue(
            all(
                int(row["assisted_converted_users"]) <= int(row["unique_users"])
                for row in entity_rows
            )
        )
        source_cost = sum(
            (Decimal(row["cost"]) for row in stored_source), Decimal("0")
        )
        self.assertEqual(
            source_cost,
            sum((Decimal(row["cost"]) for row in ads_rows), Decimal("0")),
        )
        self.assertEqual(
            source_cost,
            sum((Decimal(row["cost"]) for row in entity_rows), Decimal("0")),
        )

        # Independently reconstruct the platform-reported outcome rule from the
        # master events: the last eligible click receives purchases and sales.
        journeys: dict[str, list[dict[str, str]]] = {}
        for row in stored_source:
            journeys.setdefault(row["journey_instance_id"], []).append(row)

        def parse_time(value: str) -> datetime:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

        expected_reported_purchases = 0
        expected_reported_sales = Decimal("0")
        for journey_rows in journeys.values():
            outcome = next(row for row in journey_rows if row["event_type"] == "OUTCOME")
            if outcome["converted"] != "1":
                continue
            outcome_time = parse_time(outcome["event_time"])
            eligible_clicks = [
                row
                for row in journey_rows
                if row["event_type"] == "TOUCHPOINT"
                and row["interaction_type"] == "CLICK"
                and timedelta(0)
                <= outcome_time - parse_time(row["event_time"])
                <= timedelta(days=14)
            ]
            if eligible_clicks:
                expected_reported_purchases += int(outcome["purchase_count"])
                expected_reported_sales += Decimal(outcome["revenue"])
        self.assertEqual(
            expected_reported_purchases,
            sum(int(row["purchases"]) for row in ads_rows),
        )
        self.assertEqual(
            expected_reported_sales,
            sum((Decimal(row["sales"]) for row in ads_rows), Decimal("0")),
        )
        validate_derivations(
            stored_source,
            amc_rows,
            ads_rows,
            entity_rows,
            REPORT_START_DATE,
            REPORT_END_DATE,
            SIMULATED_PRIVACY_MIN_USERS,
            SIMULATED_MAX_USER_EVENT_ROWS,
        )
        leaked_amc = [dict(row) for row in amc_rows]
        leaked_amc[0]["synthetic_user_id"] = "customer-SYN_U00001"
        with self.assertRaisesRegex(ValueError, "schema does not match"):
            validate_derivations(
                stored_source,
                leaked_amc,
                ads_rows,
                entity_rows,
                REPORT_START_DATE,
                REPORT_END_DATE,
                SIMULATED_PRIVACY_MIN_USERS,
                SIMULATED_MAX_USER_EVENT_ROWS,
            )
        downstream = (amc_rows, ads_rows, entity_rows, read_csv(AMC_REPORT_FILE))
        self.assertTrue(
            all(
                "synthetic_user_id" not in row
                and all(not value.startswith("SYN_U") for value in row.values())
                for rows in downstream
                for row in rows
            )
        )

        one_journey_id = stored_source[0]["journey_instance_id"]
        one_journey = [
            row for row in stored_source if row["journey_instance_id"] == one_journey_id
        ]
        self.assertEqual(
            derive_touchpoint_entity_aggregate(
                one_journey, REPORT_START_DATE, REPORT_END_DATE, privacy_min_users=2
            ),
            [],
        )

    def test_all_anonymous_cohorts_form_one_valid_path(self) -> None:
        rows = generate_event_rows()
        journey_ids = {row["journey_id"] for row in rows}
        self.assertTrue(any(value.startswith("cohort_") for value in journey_ids))
        self.assertTrue(any(value.startswith("coverage_") for value in journey_ids))
        for journey_id in journey_ids:
            journey_rows = [row for row in rows if row["journey_id"] == journey_id]
            built = build_aggregated_path_rows(
                journey_rows, REPORT_START_DATE, REPORT_END_DATE, 14
            )
            self.assertEqual(len(built), 1, journey_id)

    def test_removed_sales_quantity_is_absent_from_public_csv_schemas(self) -> None:
        paths = [
            SYNTHETIC_USER_EVENTS_FILE,
            AMC_TOUCHPOINT_EVENTS_FILE,
            AMC_TOUCHPOINT_ENTITY_AGGREGATE_FILE,
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
        self.assertGreaterEqual(len(stored), 17)
        self.assertEqual(len({row["path"] for row in stored}), len(stored))
        self.assertEqual(
            len({row["path"].split(" > ")[0] for row in stored}),
            17,
        )
        source_outcomes = [
            row
            for row in read_csv(SYNTHETIC_USER_EVENTS_FILE)
            if row["event_type"] == "OUTCOME"
        ]
        self.assertEqual(
            sum(int(row["users"]) for row in stored),
            len(source_outcomes),
        )
        self.assertEqual(
            sum(int(row["converted_users"]) for row in stored),
            sum(int(row["converted"]) for row in source_outcomes),
        )
        self.assertEqual(
            sum(int(row["purchase_count"]) for row in stored),
            sum(int(row["purchase_count"]) for row in source_outcomes),
        )
        self.assertAlmostEqual(
            sum(float(row["revenue"]) for row in stored),
            sum(float(row["revenue"]) for row in source_outcomes),
            places=2,
        )
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
            build_path_report(AMC_TOUCHPOINT_EVENTS_FILE, output)

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

    def test_reader_normalizes_edges_and_preserves_internal_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "normalized.csv"
            path.write_text(
                "  name  ,  value  \n  one  ,  one value  \n",
                encoding="utf-8",
            )
            self.assertEqual(
                read_csv(path),
                [{"name": "one", "value": "one value"}],
            )

    def test_reader_rejects_empty_or_duplicate_normalized_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid-header.csv"
            cases = (
                ("", "header is missing"),
                ("\n", "empty.*after stripping"),
                ("name,   \none,value\n", "empty.*after stripping"),
                ("name, name \none,value\n", "duplicate.*after stripping"),
            )
            for contents, message in cases:
                with self.subTest(contents=contents):
                    path.write_text(contents, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        read_csv(path)

    def test_reader_rejects_extra_or_missing_data_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid-width.csv"
            cases = (
                ("one,two\n1,2,3\n", "extra column"),
                ("one,two\n1\n", "missing column"),
            )
            for contents, message in cases:
                with self.subTest(contents=contents):
                    path.write_text(contents, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        read_csv(path)

    def test_ads_sample_is_reproducible_complete_and_source_derived(self) -> None:
        source = read_csv(SYNTHETIC_USER_EVENTS_FILE)
        generated = derive_amazon_ads_rows(
            source, date.fromisoformat(REPORT_START_DATE), date.fromisoformat(REPORT_END_DATE)
        )
        stored = read_csv(AMAZON_ADS_REPORT_FILE)
        normalized_generated = [
            {field: str(row[field]) for field in FIELDS} for row in generated
        ]

        self.assertEqual(normalized_generated, stored)
        start = date.fromisoformat(REPORT_START_DATE)
        end = date.fromisoformat(REPORT_END_DATE)
        day_count = (end - start).days + 1
        self.assertEqual(len(stored), day_count * 17)
        expected_keys = set(TOUCHPOINT_KEYS)
        self.assertEqual(len(expected_keys), 17)
        self.assertEqual({row["reportDate"] for row in stored}, {
            (start + timedelta(days=offset)).isoformat()
            for offset in range(day_count)
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
        self.assertGreater(sum(int(row["impressions"]) for row in stored), 0)
        self.assertGreater(sum(int(row["clicks"]) for row in stored), 0)
        self.assertGreater(sum(float(row["cost"]) for row in stored), 0)
        validate_data_alignment_rows(read_csv(AMC_REPORT_FILE), stored)

    def test_ads_billing_semantics_and_invalid_range_preserves_file(self) -> None:
        rows = generate_rows(date(2026, 1, 1), date(2026, 1, 1))
        for row in rows:
            if row["interaction_type"] == "CLICK":
                self.assertEqual(row["cost_type"], "CPC")
                self.assertGreaterEqual(row["purchases"], 0)
            else:
                self.assertEqual(row["cost_type"], "CPM")
                self.assertEqual(row["clicks"], 0)
                self.assertEqual(row["purchases"], 0)
                self.assertEqual(row["sales"], 0)
            spec = next(spec for spec in TOUCHPOINT_CATALOG if spec.key == row["normalizedTouchpoint"])
            if spec.interaction_type != spec.billed_interaction:
                self.assertEqual(float(row["cost"]), 0)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ads.csv"
            output.write_bytes(b"old artifact\n")
            with self.assertRaisesRegex(ValueError, "on or before"):
                generate_file(output, date(2026, 2, 1), date(2026, 1, 1))
            self.assertEqual(output.read_bytes(), b"old artifact\n")

    def test_catalog_drift_fails_before_ads_generation(self) -> None:
        with patch.object(
            synthetic_pipeline, "TOUCHPOINT_CATALOG", TOUCHPOINT_CATALOG[:-1]
        ):
            with self.assertRaisesRegex(ValueError, "exactly 17"):
                generate_synthetic_user_events(REPORT_START_DATE, REPORT_END_DATE)

        drifted = (
            replace(
                TOUCHPOINT_CATALOG[0],
                key="AMAZON_DSP:AUDIO:UNSPECIFIED:UNSPECIFIED:CLICK",
            ),
            *TOUCHPOINT_CATALOG[1:],
        )
        with self.assertRaisesRegex(ValueError, "approved 17-key"):
            validate_touchpoint_catalog(drifted)

        with self.assertRaisesRegex(ValueError, "must not be empty"):
            derive_amc_touchpoint_events([])

    def test_attribution_outputs_are_exactly_reproducible_and_conserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            generated_paths = run_attribution_models(
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
            path_rows = read_csv(AMC_REPORT_FILE)
            expected_totals = {
                "converted_users": sum(float(row["converted_users"]) for row in path_rows),
                "purchase_count": sum(float(row["purchase_count"]) for row in path_rows),
                "revenue": sum(float(row["revenue"]) for row in path_rows),
            }
            for generated_path in generated_paths:
                with generated_path.open(newline="") as file:
                    for row_number, physical_row in enumerate(csv.reader(file), start=1):
                        with self.subTest(
                            output=generated_path.name,
                            row_number=row_number,
                        ):
                            self.assertTrue(
                                all(value == value.strip() for value in physical_row)
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
                        expected_totals["converted_users"],
                        places=4,
                    )
                    self.assertAlmostEqual(
                        sum(float(row["attributed_purchase_count"]) for row in generated),
                        expected_totals["purchase_count"],
                        places=4,
                    )
                    self.assertAlmostEqual(
                        sum(float(row["attributed_revenue"]) for row in generated),
                        expected_totals["revenue"],
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
            for row in comparison_rows + summary_rows + recommended_rows:
                self.assertTrue(forbidden_reason_codes.isdisjoint(row))
                self.assertNotIn("reason_code", row)
            self.assertTrue(all("difference_level" not in row for row in comparison_rows + summary_rows + recommended_rows))
            self.assertEqual(
                len({(row["touchpoint"], row["outcome"]) for row in comparison_rows}),
                51,
            )

            five_part = {row["outcome"]: row for row in summary_rows}
            self.assertEqual(set(five_part), {"converted_users", "purchase_count", "revenue"})
            expected_summary = {
                "converted_users": (0.019451, 0.889025305, 0.6),
                "purchase_count": (0.01975, 0.911097657, 0.6),
                "revenue": (0.020585, 0.931372549, 0.8),
            }
            for outcome, row in five_part.items():
                with self.subTest(outcome=outcome):
                    self.assertGreaterEqual(float(row["tvd"]), 0.0)
                    self.assertLessEqual(float(row["tvd"]), 1.0)
                    self.assertGreaterEqual(float(row["spearman_rho"]), -1.0)
                    self.assertLessEqual(float(row["spearman_rho"]), 1.0)
                    self.assertGreaterEqual(float(row["top_k_overlap_rate"]), 0.0)
                    self.assertLessEqual(float(row["top_k_overlap_rate"]), 1.0)
                    expected_tvd, expected_rho, expected_top_k = expected_summary[outcome]
                    self.assertAlmostEqual(float(row["tvd"]), expected_tvd, places=6)
                    self.assertAlmostEqual(
                        float(row["spearman_rho"]), expected_rho, places=9
                    )
                    self.assertAlmostEqual(
                        float(row["top_k_overlap_rate"]), expected_top_k, places=6
                    )

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

            with patch(
                "script.run_pipeline.os.replace", side_effect=fail_on_second_replace
            ):
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

    def test_complete_dataset_is_byte_reproducible_and_rolls_back_all_ten(self) -> None:
        names = [
            Path(SYNTHETIC_USER_EVENTS_FILE).name,
            Path(AMC_TOUCHPOINT_EVENTS_FILE).name,
            Path(AMAZON_ADS_REPORT_FILE).name,
            Path(AMC_TOUCHPOINT_ENTITY_AGGREGATE_FILE).name,
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
            destinations[5:] = [root / "outputs" / name for name in names[5:]]
            destinations[:5] = [root / name for name in names[:5]]
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

            with patch(
                "script.run_pipeline.os.replace", side_effect=fail_on_fifth_replace
            ):
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
