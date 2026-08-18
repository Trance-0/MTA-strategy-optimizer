"""Tests for the legacy-to-canonical compatibility bridge.

Covers: the five-segment key round-trips through Touchpoint adaptation and
back where every component is present, a Touchpoint with no interaction_type
cannot be projected back to a five-segment key, a bare four-segment key never
guesses interaction_type, AttributionResult fans out into exactly three
AttributionEvidence records, StandardAttributionRow adaptation cross-checks
(rather than fabricates) marketplace/window, TouchpointSpend adaptation
leaves the non-matching delivery metric None instead of 0, TouchpointSpend
adaptation into OutcomeObservation populates only total_units/total_revenue
and leaves every organic/incremental field None, and the
strategy_request.json/initial_budget_recommendation.json adapters produce the
documented fields while leaving unavailable ones (actual_spend,
maximum_daily_budget) None.
"""

from __future__ import annotations

import unittest

from modules.mta_attribution.src.attribution_contract import (
    AttributionResult,
    TouchpointSpend,
)
from modules.mta_common.src.enums import BudgetUsagePolicy, FieldAvailability, Provider
from modules.mta_common.src.legacy_adapters import (
    ad_group_from_recommended_slot,
    attribution_evidence_from_attribution_result,
    attribution_evidence_from_standard_row,
    budget_constraints_from_campaign_output,
    budget_observation_from_campaign_output,
    campaign_from_strategy_request_row,
    delivery_observation_from_touchpoint_spend,
    outcome_observation_from_touchpoint_spend,
    reporting_scope_from_campaign_group,
    touchpoint_from_five_segment_key,
    touchpoint_from_four_segment_key,
    touchpoint_to_five_segment_key,
)
from modules.mta_common.src.reporting_scope import ReportingScope
from modules.mta_standard.src.output_contract import StandardAttributionRow


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


class FiveSegmentKeyRoundTripTests(unittest.TestCase):
    def test_fully_populated_key_round_trips(self) -> None:
        key = "SPONSORED_PRODUCTS:SP:TOP_OF_SEARCH:VIDEO:CLICK"
        touchpoint = touchpoint_from_five_segment_key(key)
        self.assertEqual(touchpoint.placement, "TOP_OF_SEARCH")
        self.assertEqual(touchpoint.creative, "VIDEO")
        self.assertEqual(touchpoint.interaction_type, "CLICK")
        self.assertEqual(
            touchpoint.field_availability.placement, FieldAvailability.AVAILABLE
        )
        self.assertEqual(touchpoint_to_five_segment_key(touchpoint), key)

    def test_unspecified_placement_and_creative_round_trip(self) -> None:
        key = "SPONSORED_PRODUCTS:SP:UNSPECIFIED:UNSPECIFIED:CLICK"
        touchpoint = touchpoint_from_five_segment_key(key)
        self.assertIsNone(touchpoint.placement)
        self.assertIsNone(touchpoint.creative)
        self.assertEqual(
            touchpoint.field_availability.placement, FieldAvailability.NOT_PROVIDED
        )
        self.assertEqual(touchpoint_to_five_segment_key(touchpoint), key)

    def test_projection_without_interaction_type_is_rejected(self) -> None:
        touchpoint = touchpoint_from_four_segment_key(
            "SPONSORED_PRODUCTS:SP:TOP_OF_SEARCH:VIDEO"
        )
        with self.assertRaises(ValueError):
            touchpoint_to_five_segment_key(touchpoint)


class FourSegmentKeyNeverGuessesInteractionTypeTests(unittest.TestCase):
    def test_bare_four_segment_key_leaves_interaction_type_not_provided(self) -> None:
        touchpoint = touchpoint_from_four_segment_key(
            "SPONSORED_PRODUCTS:SP:TOP_OF_SEARCH:VIDEO"
        )
        self.assertIsNone(touchpoint.interaction_type)
        self.assertEqual(
            touchpoint.field_availability.interaction_type, FieldAvailability.NOT_PROVIDED
        )


class AttributionResultFanOutTests(unittest.TestCase):
    def test_one_result_produces_exactly_three_evidence_records(self) -> None:
        result = AttributionResult(
            touchpoint="SPONSORED_PRODUCTS:SP:TOP_OF_SEARCH:VIDEO:CLICK",
            converted_user_share=0.5,
            purchase_count_share=0.4,
            revenue_share=0.3,
            attributed_converted_users=2.0,
            attributed_purchase_count=3.0,
            attributed_revenue=100.0,
        )
        evidence = attribution_evidence_from_attribution_result(
            result,
            model_id="MODEL",
            model_version="1.0",
            reporting_scope=_scope(),
        )
        self.assertEqual(len(evidence), 3)
        outcomes = {record.outcome for record in evidence}
        self.assertEqual(outcomes, {"converted_users", "purchase_count", "revenue"})
        by_outcome = {record.outcome: record for record in evidence}
        self.assertEqual(by_outcome["revenue"].attribution_share, 0.3)
        self.assertEqual(by_outcome["revenue"].attributed_value, 100.0)


class StandardRowCrossValidationTests(unittest.TestCase):
    def _row(self, **overrides: object) -> StandardAttributionRow:
        fields = {
            "model_id": "MODEL",
            "model_version": "1.0",
            "report_start_date": "2026-01-01",
            "report_end_date": "2026-01-31",
            "marketplace": "US",
            "touchpoint": "SPONSORED_PRODUCTS:SP:TOP_OF_SEARCH:VIDEO",
            "outcome": "revenue",
            "attribution_share": 0.4,
            "attributed_value": 50.0,
        }
        fields.update(overrides)
        return StandardAttributionRow(**fields)

    def test_matching_row_adapts_without_error(self) -> None:
        evidence = attribution_evidence_from_standard_row(
            self._row(), reporting_scope=_scope()
        )
        self.assertEqual(evidence.reporting_scope.currency, "USD")
        self.assertIsNone(evidence.touchpoint.interaction_type)

    def test_marketplace_mismatch_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            attribution_evidence_from_standard_row(
                self._row(marketplace="UK"), reporting_scope=_scope()
            )

    def test_report_window_mismatch_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            attribution_evidence_from_standard_row(
                self._row(report_end_date="2026-02-28"), reporting_scope=_scope()
            )


class DeliveryObservationFromSpendTests(unittest.TestCase):
    def test_click_touchpoint_leaves_impressions_none(self) -> None:
        spend = TouchpointSpend(
            touchpoint="SPONSORED_PRODUCTS:SP:TOP_OF_SEARCH:VIDEO:CLICK",
            impressions=0,
            clicks=120,
            cost=45.5,
            reported_purchases=3,
            reported_sales=90.0,
        )
        observation = delivery_observation_from_touchpoint_spend(
            spend, reporting_scope=_scope()
        )
        self.assertIsNone(observation.impressions)
        self.assertEqual(observation.clicks, 120)

    def test_impression_touchpoint_leaves_clicks_none(self) -> None:
        spend = TouchpointSpend(
            touchpoint="AMAZON_DSP:DISPLAY:TOP_OF_SEARCH:VIDEO:IMPRESSION",
            impressions=5000,
            clicks=0,
            cost=20.0,
            reported_purchases=0,
            reported_sales=0.0,
        )
        observation = delivery_observation_from_touchpoint_spend(
            spend, reporting_scope=_scope()
        )
        self.assertEqual(observation.impressions, 5000)
        self.assertIsNone(observation.clicks)


class OutcomeObservationFromSpendTests(unittest.TestCase):
    def test_total_units_and_revenue_come_from_reported_purchases_and_sales(self) -> None:
        spend = TouchpointSpend(
            touchpoint="SPONSORED_PRODUCTS:SP:TOP_OF_SEARCH:VIDEO:CLICK",
            impressions=0,
            clicks=120,
            cost=45.5,
            reported_purchases=3,
            reported_sales=90.0,
        )
        observation = outcome_observation_from_touchpoint_spend(
            spend, reporting_scope=_scope()
        )
        self.assertEqual(observation.total_units, 3)
        self.assertEqual(observation.total_revenue, 90.0)

    def test_organic_and_incremental_fields_are_left_none(self) -> None:
        spend = TouchpointSpend(
            touchpoint="SPONSORED_PRODUCTS:SP:TOP_OF_SEARCH:VIDEO:CLICK",
            impressions=0,
            clicks=120,
            cost=45.5,
            reported_purchases=3,
            reported_sales=90.0,
        )
        observation = outcome_observation_from_touchpoint_spend(
            spend, reporting_scope=_scope()
        )
        self.assertIsNone(observation.expected_organic_units)
        self.assertIsNone(observation.expected_organic_revenue)
        self.assertIsNone(observation.incremental_units)
        self.assertIsNone(observation.incremental_revenue)
        self.assertIsNone(observation.incrementality_evidence_source)


class StrategyRequestAdapterTests(unittest.TestCase):
    def test_campaign_and_scope_and_ad_group_adapt(self) -> None:
        campaign_group = {
            "campaign_group_id": "CG-1",
            "group_name": "Group One",
            "platform": "AMAZON_ADS",
            "marketplace": "US",
            "advertiser_id": "ADV-1",
            "currency": "USD",
        }
        mta_source = {
            "report_start_date": "2026-01-01",
            "report_end_date": "2026-01-31",
        }
        scope = reporting_scope_from_campaign_group(
            campaign_group, mta_source=mta_source
        )
        self.assertEqual(scope.campaign_group_id, "CG-1")

        campaign_row = {
            "campaign_id": "CAMP-1",
            "campaign_name": "Campaign One",
            "ad_product": "SPONSORED_PRODUCTS",
            "status": "enabled",
        }
        campaign = campaign_from_strategy_request_row(
            campaign_row, reporting_scope=scope
        )
        self.assertEqual(campaign.provider, Provider.AMAZON_ADS)
        self.assertEqual(campaign.ad_product, "SPONSORED_PRODUCTS")

        slot = {
            "ad_group_slot_id": "SLOT-1",
            "allocation_basis": "EQUAL_SPLIT",
            "budget_seed_share": 0.5,
        }
        ad_group = ad_group_from_recommended_slot(slot, campaign_id=campaign.campaign_id)
        self.assertEqual(ad_group.campaign_id, "CAMP-1")
        self.assertIsNone(ad_group.initial_daily_budget)


class BudgetOutputAdapterTests(unittest.TestCase):
    def test_actual_spend_is_always_none(self) -> None:
        campaign_output = {
            "campaign_id": "CAMP-1",
            "campaign_budget_seed": 75.0,
            "minimum_required_daily_budget": 10.0,
        }
        observation = budget_observation_from_campaign_output(
            campaign_output, reporting_scope=_scope()
        )
        self.assertEqual(observation.configured_budget, 75.0)
        self.assertIsNone(observation.actual_spend)

    def test_maximum_daily_budget_is_always_none(self) -> None:
        constraints = budget_constraints_from_campaign_output(
            {"campaign_id": "CAMP-1", "minimum_required_daily_budget": 10.0},
            budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
        )
        self.assertEqual(constraints.minimum_daily_budget, 10.0)
        self.assertIsNone(constraints.maximum_daily_budget)


if __name__ == "__main__":
    unittest.main()
