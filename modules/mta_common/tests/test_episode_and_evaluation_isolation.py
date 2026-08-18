"""Tests for CampaignEpisode composition and evaluation-only isolation.

Covers: decision-time vs observed-after-treatment field classification,
campaign_id and currency consistency across an episode's parts, and the
structural (not just documentary) isolation of simulator ground truth —
CampaignEpisode has no field that can carry it, EvaluationEpisode composes
rather than extends CampaignEpisode, and assert_no_ground_truth_fields gives
that guarantee an automated check.
"""

from __future__ import annotations

import dataclasses
import unittest

from modules.mta_common.src.budget import BudgetConstraints, BudgetObservation
from modules.mta_common.src.campaign import Campaign
from modules.mta_common.src.enums import BudgetUsagePolicy, Provider
from modules.mta_common.src.episode import CampaignEpisode
from modules.mta_common.src.evaluation_only import (
    FORBIDDEN_MODEL_FACING_FIELDS,
    EvaluationEpisode,
    EvaluationGroundTruth,
    assert_no_ground_truth_fields,
)
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


def _campaign(**overrides: object) -> Campaign:
    fields = {
        "campaign_id": "CAMP-1",
        "campaign_name": "Campaign One",
        "provider": Provider.AMAZON_ADS,
        "ad_product": "SPONSORED_PRODUCTS",
        "status": "enabled",
        "reporting_scope": _scope(),
    }
    fields.update(overrides)
    return Campaign(**fields)


class CampaignEpisodeConsistencyTests(unittest.TestCase):
    def test_mismatched_budget_constraints_campaign_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CampaignEpisode(
                campaign=_campaign(campaign_id="CAMP-1"),
                budget_constraints=BudgetConstraints(
                    campaign_id="CAMP-OTHER",
                    budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
                ),
            )

    def test_mismatched_budget_observation_campaign_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CampaignEpisode(
                campaign=_campaign(campaign_id="CAMP-1"),
                budget_constraints=BudgetConstraints(
                    campaign_id="CAMP-1",
                    budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
                ),
                budget_observation=BudgetObservation(
                    campaign_id="CAMP-OTHER", reporting_scope=_scope()
                ),
            )

    def test_mismatched_currency_across_parts_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CampaignEpisode(
                campaign=_campaign(reporting_scope=_scope(currency="USD")),
                budget_constraints=BudgetConstraints(
                    campaign_id="CAMP-1",
                    budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
                ),
                budget_observation=BudgetObservation(
                    campaign_id="CAMP-1", reporting_scope=_scope(currency="EUR")
                ),
            )

    def test_consistent_episode_is_valid(self) -> None:
        episode = CampaignEpisode(
            campaign=_campaign(),
            budget_constraints=BudgetConstraints(
                campaign_id="CAMP-1",
                budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
            ),
            budget_observation=BudgetObservation(
                campaign_id="CAMP-1", reporting_scope=_scope(), configured_budget=100.0
            ),
        )
        self.assertEqual(episode.campaign.campaign_id, "CAMP-1")


class DecisionTimeVsObservedFieldClassificationTests(unittest.TestCase):
    def test_decision_time_fields_are_required(self) -> None:
        field_names = {
            f.name
            for f in dataclasses.fields(CampaignEpisode)
            if f.default is dataclasses.MISSING
            and f.default_factory is dataclasses.MISSING
        }
        self.assertEqual(field_names, {"campaign", "budget_constraints"})

    def test_observed_after_treatment_fields_default_to_unobserved(self) -> None:
        episode = CampaignEpisode(
            campaign=_campaign(),
            budget_constraints=BudgetConstraints(
                campaign_id="CAMP-1",
                budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
            ),
        )
        self.assertIsNone(episode.budget_observation)
        self.assertEqual(episode.delivery_observations, ())
        self.assertEqual(episode.outcome_observations, ())
        self.assertEqual(episode.attribution_evidence, ())


class EvaluationOnlyIsolationTests(unittest.TestCase):
    def test_campaign_episode_carries_no_ground_truth_field(self) -> None:
        assert_no_ground_truth_fields(CampaignEpisode)  # must not raise

    def test_evaluation_episode_composes_rather_than_extends(self) -> None:
        self.assertFalse(issubclass(EvaluationEpisode, CampaignEpisode))
        field_names = {f.name for f in dataclasses.fields(EvaluationEpisode)}
        self.assertEqual(field_names, {"episode", "ground_truth"})

    def test_evaluation_episode_is_not_a_campaign_episode(self) -> None:
        episode = CampaignEpisode(
            campaign=_campaign(),
            budget_constraints=BudgetConstraints(
                campaign_id="CAMP-1",
                budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
            ),
        )
        evaluation = EvaluationEpisode(
            episode=episode,
            ground_truth=EvaluationGroundTruth(
                true_incremental_units=3.0,
                true_incremental_revenue=75.0,
                true_causal_effect="SIMULATOR_HOLDOUT",
                simulator_ground_truth_id="GT-1",
            ),
        )
        self.assertNotIsInstance(evaluation, CampaignEpisode)
        self.assertIs(evaluation.episode, episode)

    def test_assert_no_ground_truth_fields_catches_a_leaking_type(self) -> None:
        @dataclasses.dataclass(frozen=True)
        class LeakyModelFacingType:
            campaign_id: str
            true_incremental_units: float

        with self.assertRaises(ValueError):
            assert_no_ground_truth_fields(LeakyModelFacingType)

    def test_forbidden_fields_cover_every_ground_truth_field(self) -> None:
        ground_truth_fields = {
            f.name for f in dataclasses.fields(EvaluationGroundTruth)
        }
        self.assertEqual(ground_truth_fields, FORBIDDEN_MODEL_FACING_FIELDS)


if __name__ == "__main__":
    unittest.main()
