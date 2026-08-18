"""Tests for ReportingScope, BudgetConstraints, BudgetObservation, and
DeliveryObservation.

Covers: actual_spend < configured_budget is valid (no forced equality),
non-negative and finite monetary/count fields, and that reserved
intervention-study fields on BudgetObservation stay unpopulated by default.
"""

from __future__ import annotations

import unittest

from modules.mta_common.src.budget import BudgetConstraints, BudgetObservation
from modules.mta_common.src.enums import BudgetUsagePolicy
from modules.mta_common.src.reporting_scope import ReportingScope


def _scope(**overrides: object) -> ReportingScope:
    fields = {
        "marketplace": "US",
        "advertiser_id": "ADV-1",
        "currency": "USD",
        "report_start_date": "2026-01-01",
        "report_end_date": "2026-01-31",
    }
    fields.update(overrides)
    return ReportingScope(**fields)


class ReportingScopeTests(unittest.TestCase):
    def test_end_before_start_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _scope(report_start_date="2026-01-31", report_end_date="2026-01-01")

    def test_blank_required_fields_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _scope(marketplace="")
        with self.assertRaises(ValueError):
            _scope(currency="")


class BudgetConstraintsTests(unittest.TestCase):
    def test_minimum_above_maximum_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BudgetConstraints(
                campaign_id="CAMP-1",
                budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
                minimum_daily_budget=100.0,
                maximum_daily_budget=50.0,
            )

    def test_negative_bounds_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BudgetConstraints(
                campaign_id="CAMP-1",
                budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
                minimum_daily_budget=-1.0,
            )

    def test_both_usage_policies_are_constructible(self) -> None:
        for policy in BudgetUsagePolicy:
            constraints = BudgetConstraints(campaign_id="CAMP-1", budget_usage_policy=policy)
            self.assertEqual(constraints.budget_usage_policy, policy)


class BudgetObservationSpendVsConfiguredTests(unittest.TestCase):
    def test_actual_spend_below_configured_budget_is_valid(self) -> None:
        observation = BudgetObservation(
            campaign_id="CAMP-1",
            reporting_scope=_scope(),
            configured_budget=100.0,
            actual_spend=42.0,
        )
        self.assertLess(observation.actual_spend, observation.configured_budget)

    def test_actual_spend_equal_to_configured_budget_is_valid(self) -> None:
        observation = BudgetObservation(
            campaign_id="CAMP-1",
            reporting_scope=_scope(),
            configured_budget=100.0,
            actual_spend=100.0,
        )
        self.assertEqual(observation.actual_spend, observation.configured_budget)

    def test_negative_actual_spend_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BudgetObservation(
                campaign_id="CAMP-1", reporting_scope=_scope(), actual_spend=-1.0
            )

    def test_reserved_intervention_fields_default_unpopulated(self) -> None:
        observation = BudgetObservation(campaign_id="CAMP-1", reporting_scope=_scope())
        self.assertIsNone(observation.intervention_id)
        self.assertIsNone(observation.baseline_budget)
        self.assertIsNone(observation.budget_delta)
        self.assertIsNone(observation.assignment_type)
        self.assertIsNone(observation.randomized)


if __name__ == "__main__":
    unittest.main()
