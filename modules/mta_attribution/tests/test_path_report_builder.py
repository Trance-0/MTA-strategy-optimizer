"""Tests for aggregated path reconstruction.

Covers the windowing rules that decide path membership: report-window boundaries,
the maximum gap between adjacent touchpoints and before the purchase, and the way
a prior purchase splits a journey into non-reusable segments.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from path_report_builder import build_aggregated_path_rows  # noqa: E402
from touchpoint_key import canonical_amc_touchpoint_key  # noqa: E402


def key(name: str, interaction_type: str = "IMPRESSION") -> str:
    return canonical_amc_touchpoint_key(
        f"PRODUCT_{name}",
        "FORMAT",
        "PLACEMENT",
        "CREATIVE",
        interaction_type,
    )


def touch(
    journey: str,
    name: str,
    when: str,
    *,
    placement: str = "PLACEMENT",
    creative: str = "CREATIVE",
    interaction_type: str = "IMPRESSION",
) -> dict:
    return {
        "journey_id": journey,
        "event_type": "TOUCHPOINT",
        "event_time": when,
        "ad_product": f"PRODUCT_{name}",
        "format": "FORMAT",
        "placement": placement,
        "creative": creative,
        "interaction_type": interaction_type,
    }


def conversion(journey: str, when: str, **overrides: object) -> dict:
    row = {
        "journey_id": journey,
        "event_type": "CONVERSION",
        "event_time": when,
        "touchpoint": "",
        "marketplace": "US",
        "advertiser_id": "adv_test",
        "users": "10",
        "converted_users": "2",
        "purchase_count": "3",
        "revenue": "200",
        "new_to_brand_purchases": "1",
    }
    row.update(overrides)
    return row


class BuildAggregatedPathRowsTests(unittest.TestCase):
    def build(self, rows: list[dict]) -> list[dict]:
        return build_aggregated_path_rows(rows, "2026-05-01", "2026-06-30", 14)

    def test_excludes_touchpoint_at_first_gap_over_14_days(self) -> None:
        rows = [
            touch("j1", "D", "2026-05-08T00:00:00Z"),
            touch("j1", "A", "2026-04-01T00:00:00Z"),
            conversion("j1", "2026-05-10T00:00:00Z"),
            touch("j1", "C", "2026-04-29T00:00:00Z"),
            touch("j1", "B", "2026-04-20T00:00:00Z"),
        ]

        result = build_aggregated_path_rows(rows, "2026-04-15", "2026-06-30", 14)

        self.assertEqual(
            [row["path"] for row in result],
            [f"{key('B')} > {key('C')} > {key('D')}"],
        )

    def test_includes_exact_14_day_gap(self) -> None:
        rows = [
            touch("j1", "A", "2026-05-01T12:00:00Z"),
            touch("j1", "B", "2026-05-15T12:00:00Z"),
            conversion("j1", "2026-05-20T00:00:00Z"),
        ]

        self.assertEqual(self.build(rows)[0]["path"], f"{key('A')} > {key('B')}")

    def test_sorts_touchpoints_by_timestamp_not_input_order(self) -> None:
        rows = [
            touch("j1", "C", "2026-05-09T00:00:00Z"),
            touch("j1", "A", "2026-05-01T00:00:01Z"),
            conversion("j1", "2026-05-10T00:00:00Z"),
            touch("j1", "B", "2026-05-05T00:00:00Z"),
        ]

        self.assertEqual(
            self.build(rows)[0]["path"], f"{key('A')} > {key('B')} > {key('C')}"
        )

    def test_rejects_path_whose_earliest_touchpoint_is_not_after_start(self) -> None:
        rows = [
            touch("j1", "A", "2026-04-28T00:00:00Z"),
            touch("j1", "B", "2026-05-05T00:00:00Z"),
            conversion("j1", "2026-05-06T00:00:00Z"),
        ]

        self.assertEqual(self.build(rows), [])

    def test_rejects_touchpoint_exactly_at_report_start(self) -> None:
        rows = [
            touch("j1", "A", "2026-05-01T00:00:00Z"),
            conversion("j1", "2026-05-02T00:00:00Z"),
        ]

        self.assertEqual(self.build(rows), [])

    def test_rejects_conversions_outside_report_window(self) -> None:
        rows = [
            touch("early", "A", "2026-04-20T00:00:00Z"),
            conversion("early", "2026-04-30T23:59:59Z"),
            touch("inside", "B", "2026-06-29T23:59:59Z"),
            conversion("inside", "2026-06-30T23:59:59Z"),
            touch("late", "C", "2026-07-01T00:00:00Z"),
            conversion("late", "2026-07-01T00:00:01Z"),
        ]

        with self.assertRaisesRegex(ValueError, "CONVERSION.*inside.*Ads report window"):
            self.build(rows)

    def test_skips_conversion_without_prior_touchpoint(self) -> None:
        self.assertEqual(self.build([conversion("j1", "2026-05-10T00:00:00Z")]), [])

    def test_aggregates_identical_anonymous_paths(self) -> None:
        rows = [
            touch("j1", "A", "2026-05-01T00:00:01Z"),
            conversion("j1", "2026-05-03T00:00:00Z"),
            touch("j2", "A", "2026-06-01T00:00:00Z"),
            conversion(
                "j2",
                "2026-06-05T00:00:00Z",
                users="5",
                converted_users="1",
                purchase_count="2",
                revenue="90",
            ),
        ]

        result = self.build(rows)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["users"], 15)
        self.assertEqual(result[0]["converted_users"], 3)
        self.assertEqual(result[0]["purchase_count"], 5)
        self.assertEqual(result[0]["revenue"], 290.0)

    def test_missing_placement_and_creative_use_unspecified(self) -> None:
        rows = [
            touch("j1", "A", "2026-05-02T00:00:00Z", placement="", creative=""),
            conversion("j1", "2026-05-03T00:00:00Z"),
        ]

        self.assertEqual(
            self.build(rows)[0]["path"],
            "PRODUCT_A:FORMAT:UNSPECIFIED:UNSPECIFIED:IMPRESSION",
        )

    def test_different_placements_remain_distinct_paths(self) -> None:
        rows = [
            touch("j1", "A", "2026-05-02T00:00:00Z", placement="TOP"),
            conversion("j1", "2026-05-03T00:00:00Z"),
            touch("j2", "A", "2026-05-02T00:00:00Z", placement="DETAIL"),
            conversion("j2", "2026-05-03T00:00:00Z"),
        ]

        self.assertEqual(
            [row["path"] for row in self.build(rows)],
            [
                "PRODUCT_A:FORMAT:DETAIL:CREATIVE:IMPRESSION",
                "PRODUCT_A:FORMAT:TOP:CREATIVE:IMPRESSION",
            ],
        )

    def test_different_creatives_remain_distinct_paths(self) -> None:
        rows = [
            touch("j1", "A", "2026-05-02T00:00:00Z", creative="IMAGE"),
            conversion("j1", "2026-05-03T00:00:00Z"),
            touch("j2", "A", "2026-05-02T00:00:00Z", creative="VIDEO"),
            conversion("j2", "2026-05-03T00:00:00Z"),
        ]

        self.assertEqual(
            [row["path"] for row in self.build(rows)],
            [
                "PRODUCT_A:FORMAT:PLACEMENT:IMAGE:IMPRESSION",
                "PRODUCT_A:FORMAT:PLACEMENT:VIDEO:IMPRESSION",
            ],
        )

    def test_impression_then_click_remain_distinct_ordered_touchpoints(self) -> None:
        rows = [
            touch(
                "j1",
                "A",
                "2026-05-02T00:00:00Z",
                interaction_type="IMPRESSION",
            ),
            touch(
                "j1",
                "A",
                "2026-05-02T00:01:00Z",
                interaction_type="CLICK",
            ),
            conversion("j1", "2026-05-03T00:00:00Z"),
        ]

        self.assertEqual(
            self.build(rows)[0]["path"],
            f"{key('A', 'IMPRESSION')} > {key('A', 'CLICK')}",
        )

    def test_interaction_type_is_required_and_strict(self) -> None:
        for interaction_type, message in (("", "interaction_type"), ("VIEW", "must be one of")):
            with self.subTest(interaction_type=interaction_type):
                with self.assertRaisesRegex(ValueError, message):
                    self.build(
                        [
                            touch(
                                "j1",
                                "A",
                                "2026-05-02T00:00:00Z",
                                interaction_type=interaction_type,
                            ),
                            conversion("j1", "2026-05-03T00:00:00Z"),
                        ]
                    )

    def test_rejects_invalid_event_timestamp(self) -> None:
        with self.assertRaisesRegex(ValueError, "event_time must be an ISO datetime"):
            self.build([touch("j1", "A", "not-a-time")])

    def test_rejects_missing_event_timestamp(self) -> None:
        with self.assertRaisesRegex(ValueError, "required field.*event_time"):
            self.build(
                [
                    {
                        "journey_id": "j1",
                        "event_type": "TOUCHPOINT",
                        "ad_product": "PRODUCT_A",
                        "format": "FORMAT",
                    }
                ]
            )

    def test_rejects_inverted_report_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "report_start_date must be on or before"):
            build_aggregated_path_rows([], "2026-07-01", "2026-06-30", 14)

    def test_rejects_missing_conversion_business_fields(self) -> None:
        for field in (
            "marketplace",
            "advertiser_id",
            "users",
            "converted_users",
            "purchase_count",
            "revenue",
        ):
            with self.subTest(field=field):
                row = conversion("j1", "2026-05-03T00:00:00Z")
                row[field] = ""
                with self.assertRaisesRegex(ValueError, "CONVERSION required field"):
                    self.build([touch("j1", "A", "2026-05-02T00:00:00Z"), row])

    def test_rejects_invalid_conversion_metric_relationships(self) -> None:
        cases = [
            (
                {"users": "1", "converted_users": "2", "purchase_count": "2"},
                "converted_users must be <= users",
            ),
            (
                {"converted_users": "1", "purchase_count": "1", "new_to_brand_purchases": "2"},
                "new_to_brand_purchases must be <= purchase_count",
            ),
            (
                {
                    "converted_users": "0",
                    "purchase_count": "0",
                    "revenue": "1",
                    "new_to_brand_purchases": "0",
                },
                "outcomes require converted_users > 0",
            ),
            (
                {"converted_users": "2", "purchase_count": "1"},
                "purchase_count must be >= converted_users",
            ),
            ({"users": "1.5"}, "users must be an integer"),
            ({"revenue": "nan"}, "revenue must be a finite non-negative"),
        ]
        for overrides, message in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, message):
                    self.build(
                        [
                            touch("j1", "A", "2026-05-02T00:00:00Z"),
                            conversion("j1", "2026-05-03T00:00:00Z", **overrides),
                        ]
                    )

    def test_rejects_ambiguous_same_type_timestamps(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate TOUCHPOINT event_time"):
            self.build(
                [
                    touch("j1", "A", "2026-05-02T00:00:00Z"),
                    touch("j1", "B", "2026-05-02T00:00:00Z"),
                    conversion("j1", "2026-05-03T00:00:00Z"),
                ]
            )
        with self.assertRaisesRegex(ValueError, "duplicate CONVERSION event_time"):
            self.build(
                [
                    touch("j1", "A", "2026-05-02T00:00:00Z"),
                    conversion("j1", "2026-05-03T00:00:00Z"),
                    conversion("j1", "2026-05-03T00:00:00Z"),
                ]
            )

    def test_rejects_touchpoint_component_with_delimiter(self) -> None:
        with self.assertRaisesRegex(ValueError, "uppercase letters, numbers, and underscores"):
            self.build(
                [
                    touch("j1", "A,B", "2026-05-02T00:00:00Z"),
                    conversion("j1", "2026-05-03T00:00:00Z"),
                ]
            )

    def test_rejects_purchase_more_than_14_days_after_last_touchpoint(self) -> None:
        rows = [
            touch("j1", "A", "2026-05-02T00:00:00Z"),
            conversion("j1", "2026-05-16T00:00:01Z"),
        ]

        self.assertEqual(self.build(rows), [])

    def test_includes_exact_14_days_from_last_touchpoint_to_purchase(self) -> None:
        rows = [
            touch("j1", "A", "2026-05-02T00:00:00Z"),
            conversion("j1", "2026-05-16T00:00:00Z"),
        ]

        self.assertEqual(self.build(rows)[0]["path"], key("A"))

    def test_has_no_total_path_duration_limit(self) -> None:
        rows = [
            touch("j1", "A", "2026-05-02T00:00:00Z"),
            touch("j1", "B", "2026-05-16T00:00:00Z"),
            touch("j1", "C", "2026-05-30T00:00:00Z"),
            conversion("j1", "2026-06-13T00:00:00Z"),
        ]

        self.assertEqual(
            self.build(rows)[0]["path"], f"{key('A')} > {key('B')} > {key('C')}"
        )

    def test_multiple_purchases_do_not_reuse_earlier_touchpoints(self) -> None:
        rows = [
            touch("j1", "A", "2026-05-02T00:00:00Z"),
            conversion(
                "j1",
                "2026-05-03T00:00:00Z",
                converted_users="1",
                purchase_count="1",
            ),
            touch("j1", "B", "2026-05-04T00:00:00Z"),
            conversion(
                "j1",
                "2026-05-05T00:00:00Z",
                converted_users="1",
                purchase_count="1",
            ),
        ]

        self.assertEqual([row["path"] for row in self.build(rows)], [key("A"), key("B")])


if __name__ == "__main__":
    unittest.main()
