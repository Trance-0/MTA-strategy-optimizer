"""Tests for the shared attribution data contract.

Covers the pieces every model depends on: result and spend dataclasses, spend
aggregation from Ads rows, conservation-preserving rounding in `result_rows`, and
the Markov and Shapley row adapters that read the aggregated path contract.
"""

from __future__ import annotations

import unittest

from modules.mta_attribution.src.attribution_contract import (
    AttributionResult,
    TouchpointSpend,
    result_rows,
)
from modules.mta_attribution.src.markov_attribution_model import (
    WeightedMarkovAttribution,
    amc_path_to_markov_path,
    amc_rows_to_markov_rows,
    run_markov_attribution,
)
from modules.mta_attribution.src.shapley_attribution_model import (
    AggregatedShapleyAttribution,
    amc_rows_to_shapley_rows,
    run_shapley_attribution,
)


BASE_A = "PRODUCT_A:FORMAT:PLACEMENT:CREATIVE"
BASE_B = "PRODUCT_B:FORMAT:PLACEMENT:CREATIVE"
A = f"{BASE_A}:IMPRESSION"
A_CLICK = f"{BASE_A}:CLICK"
B = f"{BASE_B}:IMPRESSION"


def amc_row(path: str = f"{A} > {B}", **overrides: object) -> dict:
    row = {
        "path": path,
        "users": "10",
        "converted_users": "2",
        "purchase_count": "3",
        "revenue": "100",
    }
    row.update(overrides)
    return row


class MarkovTerminalWeightTests(unittest.TestCase):
    def test_conversion_uses_converted_users_and_remainder_uses_null(self) -> None:
        model = WeightedMarkovAttribution(amc_rows_to_markov_rows([amc_row()]))
        matrix = model.transition_matrix()

        self.assertAlmostEqual(matrix[B]["Conversion"], 0.2)
        self.assertAlmostEqual(matrix[B]["Null"], 0.8)
        self.assertAlmostEqual(matrix["Start"][A], 1.0)

    def test_markov_conserves_each_outcome_separately(self) -> None:
        results = run_markov_attribution([amc_row()])

        self.assertAlmostEqual(sum(r.attributed_converted_users for r in results), 2.0)
        self.assertAlmostEqual(sum(r.attributed_purchase_count for r in results), 3.0)
        self.assertAlmostEqual(sum(r.attributed_revenue for r in results), 100.0)
        self.assertAlmostEqual(sum(r.converted_user_share for r in results), 1.0)
        self.assertAlmostEqual(sum(r.purchase_count_share for r in results), 1.0)
        self.assertAlmostEqual(sum(r.revenue_share for r in results), 1.0)

    def test_markov_revenue_credit_responds_to_path_revenue(self) -> None:
        rows = [
            amc_row(A, users="2", converted_users="1", purchase_count="1", revenue="900"),
            amc_row(B, users="2", converted_users="1", purchase_count="1", revenue="100"),
        ]
        results = {r.touchpoint: r for r in run_markov_attribution(rows)}

        self.assertGreater(results[A].revenue_share, results[B].revenue_share)
        self.assertAlmostEqual(results[A].converted_user_share, results[B].converted_user_share)

    def test_impression_and_click_are_separate_model_states(self) -> None:
        results = run_markov_attribution([amc_row(f"{A} > {A_CLICK}")])

        self.assertEqual({result.touchpoint for result in results}, {A, A_CLICK})
        self.assertTrue(all(result.attributed_revenue > 0 for result in results))

    def test_zero_outcomes_produce_zero_shares(self) -> None:
        results = run_markov_attribution(
            [amc_row(A, converted_users="0", purchase_count="0", revenue="0")]
        )

        self.assertEqual(results[0].converted_user_share, 0.0)
        self.assertEqual(results[0].purchase_count_share, 0.0)
        self.assertEqual(results[0].revenue_share, 0.0)

    def test_allows_explicit_null_path_without_outcomes(self) -> None:
        rows = amc_rows_to_markov_rows(
            [amc_row(f"{A} > Null", users="3", converted_users="0", purchase_count="0", revenue="0")]
        )

        self.assertEqual(rows[0]["path"], f"Start > {A} > Null")
        self.assertEqual(rows[0]["weight"], 3.0)


class AggregatedInputValidationTests(unittest.TestCase):
    def assert_invalid(self, row: dict, message: str) -> None:
        with self.assertRaisesRegex(ValueError, message):
            amc_rows_to_markov_rows([row])

    def test_requires_new_core_fields_and_rejects_legacy_purchases_only(self) -> None:
        base = amc_row()
        for field in base:
            with self.subTest(field=field):
                row = dict(base)
                row[field] = ""
                self.assert_invalid(row, "required field")
        self.assert_invalid(
            {"path": A, "users": "2", "purchases": "1", "revenue": "10"},
            "converted_users, purchase_count",
        )

    def test_rejects_reserved_or_malformed_path_states(self) -> None:
        for path in (
            f"Start > {A}",
            f"{A} > Conversion",
            f"{A} > Null > {B}",
            "Null",
            f"{A} >",
            "A:B:C:D",
        ):
            with self.subTest(path=path):
                self.assert_invalid(amc_row(path), "AMC row")

    def test_rejects_invalid_metrics_and_relationships(self) -> None:
        cases = [
            ({"users": "nan"}, "finite non-negative"),
            ({"users": "1.5"}, "must be an integer"),
            ({"users": "1", "converted_users": "2"}, "converted_users must be <= users"),
            ({"converted_users": "2", "purchase_count": "1"}, "purchase_count must be >= converted_users"),
            ({"converted_users": "0", "purchase_count": "0", "revenue": "1"}, "positive outcomes require converted_users"),
        ]
        for overrides, message in cases:
            with self.subTest(overrides=overrides):
                self.assert_invalid(amc_row(**overrides), message)

    def test_markov_path_helper_enforces_canonical_touchpoints(self) -> None:
        self.assertEqual(amc_path_to_markov_path(A, 1), f"Start > {A} > Conversion")
        for path in ("PRODUCT_A:FORMAT", "PRODUCT_A:FORMAT::", f"{A} > > {B}"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    amc_path_to_markov_path(path, 1)


class ShapleyCoalitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.amc_rows = [
            amc_row(A, users="5", converted_users="4", purchase_count="5", revenue="40"),
            amc_row(f"{A} > {B}", users="8", converted_users="6", purchase_count="8", revenue="60"),
        ]

    def test_coalition_value_requires_all_unique_path_members(self) -> None:
        model = AggregatedShapleyAttribution(amc_rows_to_shapley_rows(self.amc_rows))
        self.assertEqual(model.coalition_value([], "revenue"), 0.0)
        self.assertEqual(model.coalition_value([A], "revenue"), 40.0)
        self.assertEqual(model.coalition_value([A, B], "revenue"), 100.0)

    def test_duplicate_touchpoints_receive_credit_once_per_path(self) -> None:
        duplicate_rows = [
            amc_row(f"{A} > {A}", users="5", converted_users="4", purchase_count="5", revenue="40"),
            self.amc_rows[1],
        ]
        results = {r.touchpoint: r for r in run_shapley_attribution(duplicate_rows)}

        self.assertAlmostEqual(results[A].attributed_revenue, 70.0)
        self.assertAlmostEqual(results[B].attributed_revenue, 30.0)
        self.assertAlmostEqual(results[A].attributed_purchase_count, 9.0)
        self.assertAlmostEqual(results[B].attributed_purchase_count, 4.0)

    def test_shapley_conserves_all_outcomes(self) -> None:
        results = run_shapley_attribution(self.amc_rows)

        self.assertAlmostEqual(sum(r.attributed_converted_users for r in results), 10.0)
        self.assertAlmostEqual(sum(r.attributed_purchase_count for r in results), 13.0)
        self.assertAlmostEqual(sum(r.attributed_revenue for r in results), 100.0)
        self.assertAlmostEqual(sum(r.converted_user_share for r in results), 1.0)
        self.assertAlmostEqual(sum(r.purchase_count_share for r in results), 1.0)
        self.assertAlmostEqual(sum(r.revenue_share for r in results), 1.0)


class ResultRowTests(unittest.TestCase):
    def test_cost_rows_reject_four_part_touchpoint(self) -> None:
        with self.assertRaisesRegex(ValueError, "canonical five-part"):
            result_rows(
                "test",
                [AttributionResult(BASE_A, 1, 1, 1, 1, 1, 10)],
                {},
            )

    def test_impression_and_click_remain_separate_cost_rows(self) -> None:
        interaction_results = [
            AttributionResult(A, 0.4, 0.3, 0.2, 4, 3, 20),
            AttributionResult(A_CLICK, 0.6, 0.7, 0.8, 6, 7, 80),
        ]
        rows = result_rows(
            "test",
            interaction_results,
            {
                A: TouchpointSpend(A, 100, 0, 12, 0, 0),
                A_CLICK: TouchpointSpend(A_CLICK, 0, 10, 0, 1, 20),
            },
        )
        self.assertEqual([row["interaction_type"] for row in rows], ["IMPRESSION", "CLICK"])
        self.assertEqual([row["cost"] for row in rows], [12.0, 0.0])
        self.assertEqual(rows[1]["roas"], "")
        self.assertEqual(rows[1]["cpa"], "")
        self.assertEqual(rows[1]["cost_per_converted_user"], "")

    def test_rounding_preserves_totals_and_uses_explicit_cpa_denominators(self) -> None:
        interaction_results = [
            AttributionResult(A, 1 / 3, 1 / 3, 1 / 3, 1 / 3, 2 / 3, 10 / 3),
            AttributionResult(B, 2 / 3, 2 / 3, 2 / 3, 2 / 3, 4 / 3, 20 / 3),
        ]
        spend = {
            key: TouchpointSpend(key, 100, 10, 12.0, 1, 20.0)
            for key in (A, B)
        }
        rows = result_rows(
            "test",
            interaction_results,
            spend,
        )

        self.assertEqual(sum(r["converted_user_share"] for r in rows), 1.0)
        self.assertEqual(sum(r["attributed_purchase_count"] for r in rows), 2.0)
        self.assertEqual(sum(r["attributed_revenue"] for r in rows), 10.0)
        self.assertNotEqual(rows[0]["cpa"], rows[0]["cost_per_converted_user"])

    def test_missing_ads_touchpoint_is_an_error(self) -> None:
        result = AttributionResult(A, 1, 1, 1, 1, 1, 10)
        with self.assertRaisesRegex(ValueError, "missing Amazon Ads spend"):
            result_rows("test", [result], {})

    def test_rounding_never_creates_negative_small_values(self) -> None:
        results = [
            AttributionResult(key, 1 / 3, 1 / 3, 1 / 3, 1 / 3, 1 / 3, 0.005)
            for key in (
                A,
                B,
                "PRODUCT_C:FORMAT:PLACEMENT:CREATIVE:CLICK",
            )
        ]
        spend = {
            result.touchpoint: TouchpointSpend(
                result.touchpoint, 1, 1, 1.0, 0, 0.0
            )
            for result in results
        }

        rows = result_rows("test", results, spend)

        self.assertTrue(all(row["attributed_revenue"] >= 0 for row in rows))
        self.assertEqual(sum(row["attributed_revenue"] for row in rows), 0.01)


if __name__ == "__main__":
    unittest.main()
